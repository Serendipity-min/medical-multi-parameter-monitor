/**
 * @file ads1292.c
 * @brief ADS1292R：PG15控制START，DRDY中断采集原始帧，主循环消费128帧队列。
 * PA0=PWDN，PA2=CS，PA3=DRDY，PA5/6/7=SPI1；旧PA1释放为输入。
 * 默认芯片时钟512kHz，4tCLK约7.81us；命令与数据末端保留10us间隔。
 * 初始化失败不启动；采集阶段SPI仅由ISR使用，统计不伪造物理丢帧数量。
 */
#include "ads1292.h"
#include "spi.h"
#include "ecg_frame_queue.h"
#include "timer.h"
#include "systick.h"    // Delay_us：命令字节之间的 10us 间隔，删不得

// DRDY 下降沿后有 4·tCLK（≈7.8us @fCLK=512kHz）禁读区，这里留够余量
#define ADS_DRDY_KEEPOUT_US   10

/* DRDY ISR 为唯一生产者；主循环只消费队列，不与ISR同时访问SPI。 */
static volatile uint8_t s_ready;
static volatile ADS1292Stats s_stats;
static uint32_t s_previous_irq_cycles, s_last_frame_ms, s_last_sequence;
static uint8_t s_last_frame_flags;
// ---- 统计量 ----
static volatile uint32_t s_drdy_cnt    = 0;   // DRDY 次数（中断里自增，永不丢）
static uint32_t          s_frame_cnt   = 0;   // 实际读走的帧数
static uint32_t          s_miss_cnt    = 0;   // 主循环来不及处理而丢掉的帧数

//寄存器配置结构体
typedef struct {
    uint8_t     addr; //寄存器地址
    uint8_t     val; //值
    const char *name;
} ads_reg_cfg_t;

static const ads_reg_cfg_t k_regs[] = {
    /* CONFIG1 (01h) = 0x01
       bit7 SINGLE_SHOT=0      连续转换
       bit6:3 必须为 0
       bit2:0 DR[2:0]=001      fMOD/512 → 250 SPS
       ⚠ 改这里必须同步改 pan_tompkins.h / resp_rate.h 的采样率宏！ */
    { ADS_REG_CONFIG1,   0x01, "CONFIG1 " },

    /* LOFF (03h) = 0xF0
       bit7:5 COMP_TH=111      断线比较器阈值（正端 70% / 负端 30%）
       bit4   必须为 1
       bit3:2 ILEAD_OFF=00     激励电流 6nA
       bit1   必须为 0
       bit0   FLEAD_OFF=0      DC 断线检测 */
    { ADS_REG_LOFF,      0xF0, "LOFF    " },

    /* CH1SET (04h) = 0x40   —— 通道1 = 呼吸阻抗
       bit7   PD1=0            通道工作
       bit6:4 GAIN1=100        增益 4
       bit3:0 MUX1=0000        正常电极输入
       满量程 = ±2.42V/4 = ±605mV
       ⚠ 2026-09-24 由 0x60（增益12）降到这里：手册 9.4 推荐 32kHz 呼吸
         调制用增益 3~4。增益12 满量程只有 ±202mV，而解调输出含 ∝基础阻抗
         的直流分量（约 30mV，×12=360mV）会削顶成方波；增益4 时只占 20%。
         备选 0x30（增益3）。编码 000=6 001=1 010=2 011=3 100=4 101=8 110=12 */
    { ADS_REG_CH1SET,    0x40, "CH1SET  " },

    // CH2SET (05h) = 0x40 —— 通道2 = 心电，增益4（满量程 ±605mV）；本轮不调增益。
    // A/B 实测（10-10）：0x40 增益4（±605mV）/ 0x20 增益2（±1210mV）对照，
    // 看 0.1-0.5Hz 慢漂移占比是否随量程放宽而下降（电极直流顶轨假设）
    { ADS_REG_CH2SET,    0x40, "CH2SET  " },

    // RLD_SENS (06h) = 0xEC —— 开 RLD 缓冲，只从 CH2 感测共模（TI 官方配置）
    // （10-09 由 0xCB 改：关缓冲时人体共模没人压，环境干扰经电极失配转差模钻进心电）
    { ADS_REG_RLD_SENS,  0xEC, "RLD_SENS" },

    /* LOFF_SENS (07h) = 0x00  —— 关断线检测电流
       （电极经模块 56K 接入，6uA 电流压降 336mV 会把通道顶轨；
         电流关掉后 STATUS 脱落位仅作参考，不再作为脱落判据） */
    { ADS_REG_LOFF_SENS, 0x00, "LOFF_SENS" },

    /* RESP1 (09h) = 0xEA   —— 仅 ADS1292R，呼吸调制/解调
       bit7   RESP_DEMOD_EN1=1  解调使能
       bit6   RESP_MOD_EN=1     调制使能
       bit5:2 RESP_PH=1010      相位 112.5°（32kHz 下）
       bit1   必须为 1
       bit0   RESP_CTRL=0       内部时钟
       注：手册 9.4 推荐"32kHz → 相位 112.5° 或 135°"，0xEA 符合；
           而手册 8.3 的示例代码写 0xD5 并注释成 112.5°，其实 0101 在
           32kHz 表里是 56.25°，手册那段示例自身前后矛盾，不要照抄。 */
    { ADS_REG_RESP1,     0xEA, "RESP1   " },

    /* RESP2 (0Ah) = 0x03
       bit7   CALIB_ON=0
       bit6:3 必须为 0
       bit2   RESP_FREQ=0       调制频率 32kHz
       bit1   RLDREF_INT=1      RLD 参考用内部 (AVDD-AVSS)/2
       bit0   必须为 1 */
    { ADS_REG_RESP2,     0x03, "RESP2   " },

    /* GPIO (0Bh) = 0x0C = 复位默认值
       bit7:4 必须为 0
       bit3:2 GPIOC[2:1]=11     两个 GPIO 都设为输入（1=输入，是复位默认）
       bit1:0 GPIOD[2:1]=00     引脚为输入时这两位读回的是引脚电平，
                                所以回读值不一定是 00（见步骤⑦的说明），
                                这里写 0x0C 只是把配置位对齐复位值。
       注：本工程用呼吸阻抗（CH1SET=0x40），手册 9.7 说明呼吸外部时钟
           模式下 GPIO1/GPIO2 会被自动配置为输入，与这里一致。 */
    { ADS_REG_GPIO,      0x0C, "GPIO    " },
};
#define ADS_REG_NUM   (sizeof(k_regs) / sizeof(k_regs[0]))



// 命令时序的两个间隔（us）：字节与字节之间、最后一个字节 → CS 抬高 之间。
// 数据手册要 4 tCLK（≈2.0us）与 3 tCLK（≈1.46us）
#define ADS_CMD_GAP_IB_US   10
#define ADS_CMD_GAP_CS_US   10

//防止0进入Delay_us
static void gap_us(uint16_t us)
{
    if (us != 0)
        Delay_us(us);
}

// 配置控制脚和 DRDY 外部中断。
static void ads_gpio_init(void)
{
    GPIO_InitTypeDef GPIO_InitStructure;
	EXTI_InitTypeDef EXTI_InitStructure;
	NVIC_InitTypeDef NVIC_InitStructure;

    RCC_AHB1PeriphClockCmd(RCC_AHB1Periph_GPIOA|RCC_AHB1Periph_GPIOG,ENABLE);
    RCC_APB2PeriphClockCmd(RCC_APB2Periph_SYSCFG,ENABLE);

    // PA0=PWDN/RESET, PG15=START；PA1只输入, PA2=CS
    GPIO_InitStructure.GPIO_Pin=GPIO_Pin_0|GPIO_Pin_2;
	GPIO_InitStructure.GPIO_Mode=GPIO_Mode_OUT;
	GPIO_InitStructure.GPIO_Speed=GPIO_Speed_50MHz;
	GPIO_InitStructure.GPIO_OType=GPIO_OType_PP;
	GPIO_InitStructure.GPIO_PuPd=GPIO_PuPd_UP;
	GPIO_Init(GPIOA,&GPIO_InitStructure);

    /* PA1 为板载PHY共用网络，不再作为START输出；新START独占PG15。 */
    GPIO_InitStructure.GPIO_Pin=GPIO_Pin_15;
    GPIO_ResetBits(GPIOG,GPIO_Pin_15);
    GPIO_Init(GPIOG,&GPIO_InitStructure);
    GPIO_InitStructure.GPIO_Pin=GPIO_Pin_1;
    GPIO_InitStructure.GPIO_Mode=GPIO_Mode_IN;
    GPIO_InitStructure.GPIO_PuPd=GPIO_PuPd_NOPULL;
    GPIO_Init(GPIOA,&GPIO_InitStructure);
    // PA3 = DRDY，输入；ADS1292 推挽输出，上拉只是防悬空
    GPIO_InitStructure.GPIO_Pin=GPIO_Pin_3;
	GPIO_InitStructure.GPIO_Mode=GPIO_Mode_IN;
	GPIO_InitStructure.GPIO_PuPd=GPIO_PuPd_UP;
	GPIO_Init(GPIOA,&GPIO_InitStructure);

    // DRDY 低电平表示有新数据 → 下降沿触发
    SYSCFG_EXTILineConfig(EXTI_PortSourceGPIOA,EXTI_PinSource3);
    EXTI_InitStructure.EXTI_Line=EXTI_Line3;
	EXTI_InitStructure.EXTI_Mode=EXTI_Mode_Interrupt;
	EXTI_InitStructure.EXTI_Trigger=EXTI_Trigger_Falling;
	EXTI_InitStructure.EXTI_LineCmd=ENABLE;
	EXTI_Init(&EXTI_InitStructure);

    // 抢占优先级 2，高于 TIM2 的时基中断（3）
    NVIC_InitStructure.NVIC_IRQChannel=EXTI3_IRQn;
	NVIC_InitStructure.NVIC_IRQChannelPreemptionPriority=2;
	NVIC_InitStructure.NVIC_IRQChannelSubPriority=0;
	NVIC_InitStructure.NVIC_IRQChannelCmd=ENABLE;
	NVIC_Init(&NVIC_InitStructure);

    ADS_CS_HIGH();
	ADS_START_LOW();
	ADS_PWDN_HIGH();
}

//DRDY 下降沿中断,表示数据就绪
void EXTI3_IRQHandler(void)
{
    EcgQueuedFrame frame;
    uint32_t at, delta, begin, queued;
    uint8_t i, ok=1;
    if (EXTI_GetITStatus(EXTI_Line3)==RESET) { return; }
    at=DWT->CYCCNT; EXTI_ClearITPendingBit(EXTI_Line3);
    if (!s_ready) { return; } /* 初始化配置SPI尚未归ISR所有，不允许争用。 */
    s_stats.irq_count++; frame.irq_sequence=s_stats.irq_count;
    frame.irq_cycles=at; frame.irq_ms=TimeBase_GetMs(); frame.flags=0;
    if (s_stats.irq_count>1) {
        delta=(uint32_t)(at-s_previous_irq_cycles);
        if (delta<s_stats.min_irq_gap_cycles) { s_stats.min_irq_gap_cycles=delta; }
        if (delta>s_stats.max_irq_gap_cycles) { s_stats.max_irq_gap_cycles=delta; }
        if (delta>(SystemCoreClock/1000u)*6u) { frame.flags=1; s_stats.long_gap_count++; }
    }
    s_previous_irq_cycles=at;
    begin=DWT->CYCCNT; Delay_us(10); ADS_CS_LOW();
    for (i=0;i<9;i++) {
        if (!SPI1_TxRxChecked(0xFF,&frame.bytes[i])) { ok=0; frame.bytes[i]=0xFF; }
    }
    { uint32_t wait=DWT->CYCCNT;
      while (SPI1->SR & SPI_I2S_FLAG_BSY) {
        if ((uint32_t)(DWT->CYCCNT-wait)>SystemCoreClock/20000u) { ok=0; break; }
      }
    }
    Delay_us(10); ADS_CS_HIGH();
    delta=(uint32_t)(DWT->CYCCNT-begin);
    if (delta>s_stats.max_read_cycles) { s_stats.max_read_cycles=delta; }
    if (!ok) { s_stats.spi_errors++; s_miss_cnt++; return; }
    if ((frame.bytes[0]&0xF0)!=0xC0 || (frame.bytes[1]&0x1F)!=0 || frame.bytes[2]!=0) {
        s_stats.bad_status++; s_miss_cnt++; return;
    }
    s_stats.captured++;
    /* 缓冲满只丢新帧并计数，保持旧帧顺序；消费者用序号断段，不隐藏溢出。 */
    if (!EcgQueue_Push(&frame)) { s_stats.queue_overflow++; s_miss_cnt++; }
    queued=EcgQueue_Count();
    if (queued>s_stats.queue_peak) { s_stats.queue_peak=queued; }
}

//发送命令(抬 CS 之前必须留 ADS_CMD_GAP_CS_US（tSCCS ≥ 3 tCLK），否则命令会被丢弃。
void ADS1292_Cmd(uint8_t cmd)
{
    ADS_CS_LOW();
    SPI1_TxRx(cmd);
    gap_us(ADS_CMD_GAP_CS_US);      // ★ tSCCS：第 8 个 SCLK 下降到 CS 高要 ≥3 tCLK，10us
    ADS_CS_HIGH();
    Delay_us(10);         // 命令之间 4 tCLK
}

// WREG 格式：命令、数量减一、寄存器值。
// ⚠ 三个字节之间以及抬 CS 之前都要留间隔，否则写入静默失败。
void ADS1292_WriteReg(uint8_t a, uint8_t v)
{
    ADS_CS_LOW();
    SPI1_TxRx(ADS_WREG | (a & 0x1F));  // 命令 + 地址
    gap_us(ADS_CMD_GAP_IB_US);                      // ★ 4 tCLK：芯片要在第 8 个沿解码
    SPI1_TxRx(0);                     // 写 1 个寄存器（数量-1 = 0）
    gap_us(ADS_CMD_GAP_IB_US);                      // ★ 同上，给解码器留时间
    SPI1_TxRx(v);                      // 寄存器值
    gap_us(ADS_CMD_GAP_CS_US);                      // ★ tSCCS：抬 CS 前必须保持
    ADS_CS_HIGH();
    Delay_us(10);
}

// RREG 格式：命令、数量减一、发送空字节取得返回值。
uint8_t ADS1292_ReadReg(uint8_t a)
{
    uint8_t v;
    ADS_CS_LOW();
    SPI1_TxRx(ADS_RREG | (a & 0x1F));  // 命令 + 地址
    gap_us(ADS_CMD_GAP_IB_US);                      // ★
    SPI1_TxRx(0);                     // 读 1 个寄存器（数量-1 = 0）
    gap_us(ADS_CMD_GAP_IB_US);                      // ★
    v = SPI1_TxRx(0x00);              // 发空字节产生 SCLK，读回寄存器值
    gap_us(ADS_CMD_GAP_CS_US);                      // ★ tSCCS
    ADS_CS_HIGH();
    Delay_us(10); /* 保证下一条命令前的CS高间隔。 */
    return v;
}


//初始化
void ADS1292_Init(void)
{
    uint8_t i, actual, mask;
    s_ready=0; EcgQueue_Reset();
    s_stats.irq_count=s_stats.captured=s_stats.delivered=0;
    s_stats.bad_status=s_stats.spi_errors=s_stats.queue_overflow=0;
    s_stats.queue_peak=s_stats.init_errors=s_stats.long_gap_count=0;
    s_stats.min_irq_gap_cycles=0xFFFFFFFFu; s_stats.max_irq_gap_cycles=s_stats.max_read_cycles=0;
    s_drdy_cnt=s_frame_cnt=s_miss_cnt=0;
    s_last_frame_ms=s_last_sequence=0; s_last_frame_flags=0;
    ads_gpio_init();
    ADS_PWDN_LOW(); Delay_ms(10); ADS_PWDN_HIGH(); Delay_ms(1000);
    ADS1292_Cmd(ADS_RESET); Delay_ms(10);
    ADS1292_Cmd(ADS_SDATAC); Delay_us(10);
    /* 本工程固定ADS1292R；失败不启动并不向算法提交假帧。 */
    if (ADS1292_ReadReg(ADS_REG_ID)!=0x73) { s_stats.init_errors++; return; }
    ADS1292_WriteReg(ADS_REG_CONFIG2,0xE0); Delay_ms(20);
    if (ADS1292_ReadReg(ADS_REG_CONFIG2)!=0xE0) { s_stats.init_errors++; return; }
    for (i=0;i<(uint8_t)ADS_REG_NUM;i++) {
        mask=(k_regs[i].addr==ADS_REG_GPIO)?0xFC:0xFF;
        ADS1292_WriteReg(k_regs[i].addr,k_regs[i].val);
        actual=ADS1292_ReadReg(k_regs[i].addr);
        if ((actual&mask)!=(k_regs[i].val&mask)) {
            ADS1292_WriteReg(k_regs[i].addr,k_regs[i].val);
            actual=ADS1292_ReadReg(k_regs[i].addr);
            if ((actual&mask)!=(k_regs[i].val&mask)) { s_stats.init_errors++; return; }
        }
    }
    ADS1292_Cmd(ADS_RDATAC);
    EXTI_ClearITPendingBit(EXTI_Line3);
    s_ready=1; ADS_START_HIGH();
}


// ============================ 数据读取与解析 ============================

/**
 * @brief  读一帧（STATUS 3 字节 + CH1 3 字节 + CH2 3 字节）。
 * @retval 1 = 这一轮读到了一帧；0 = 还没有新数据。
 */
uint8_t ADS1292_ReadFrame(uint8_t f[9])
{
    EcgQueuedFrame frame;
    uint8_t i;
    if (f==0 || !EcgQueue_Pop(&frame)) { return 0; }
    for (i=0;i<9;i++) { f[i]=frame.bytes[i]; }
    s_last_frame_ms=frame.irq_ms; s_last_sequence=frame.irq_sequence; s_last_frame_flags=frame.flags;
    s_frame_cnt++; s_stats.delivered++;
    return 1;
}

// ADS1292 输出 24 位二进制补码，这里进行符号扩展到 32 位。
int32_t ADS1292_S24ToS32(const uint8_t *p)
{
    int32_t v = ((int32_t)p[0] << 16) |
                ((int32_t)p[1] << 8)  |
                 (int32_t)p[2];

    if (v & 0x00800000)      // 判断符号位（第 23 位）
        v |= 0xFF000000;     // 负数则高 8 位补 1

    return v;
}


// ============================ 对外查询接口 ============================

uint32_t ADS1292_GetFrameCount(void)     { return s_frame_cnt; }
uint32_t ADS1292_GetMissCount(void)      { return s_miss_cnt; }

/* 末帧元数据仅由主循环更新，ISR不会把消费时戳悄悄改为另一帧。 */
uint32_t ADS1292_GetLastFrameMs(void) { return s_last_frame_ms; }
uint32_t ADS1292_GetLastFrameSequence(void) { return s_last_sequence; }
uint8_t ADS1292_GetLastFrameFlags(void) { return s_last_frame_flags; }
uint8_t ADS1292_IsReady(void) { return s_ready; }
void ADS1292_GetStats(ADS1292Stats *out)
{
    uint32_t irq;
    if (out==0) { return; }
    irq=__get_PRIMASK(); __disable_irq(); *out=s_stats; __set_PRIMASK(irq);
}
