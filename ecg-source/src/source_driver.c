#include "source_driver.h"
#include <stddef.h>
#ifdef SRC_HOST_TEST
#include "mmio_mock.h"
#else
#include "stm32f4xx.h"
#endif

/* 只由源板独占：TIM6 TRGO、DMA1 Stream5 Channel7、DAC1 PA4与静态DAC2 PA5。
   RCC/寄存器位按RM0090 DMA/DAC/TIM6章节；不初始化SPI、CAN、USB或B板引脚。 */
#define DMA_ENABLE (1u<<0)
#define DMA_ERRORS ((1u<<6)|(1u<<8)|(1u<<9))
#define DMA_ALL_FLAGS (DMA_ERRORS|(1u<<10)|(1u<<11))
#define DMA_COMPLETE (1u<<11)
#define DAC_ENABLES ((1u<<0)|(1u<<16))
#define DAC_TRIGGER_DMA ((1u<<2)|(1u<<12)|(1u<<13))
#define DAC_UNDERRUN ((1u<<13)|(1u<<29))
#define DMA_STOP_LIMIT 10000u
volatile SrcDiagnostic g_source_diag;
volatile uint32_t g_source_requested_mode=SRC_OFF;
uint32_t g_source_dma_buffer[SRC_MAX_TABLE];

static void write_reg(volatile uint32_t *address,uint32_t value)
{
#ifdef SRC_HOST_TEST
    SrcMock_Write(address,value);
#else
    *address=value;
#endif
}
static void write_tim(volatile uint16_t *address,uint32_t value)
{
    /* 现有ST设备头文件将TIM6低16位与保留高16位分开；按真实字段宽度访问，
       不把uint16_t地址强转uint32_t以绕过ARM检查。分频/周期均已验证在16位范围。 */
#ifdef SRC_HOST_TEST
    SrcMock_WriteTimer(address,(uint16_t)value);
#else
    *address=(uint16_t)value;
#endif
}
static uint8_t quiet(void)
{
    uint32_t count=0;
    /* 先停止TRGO并关闭DAC输出，再停DMA；在途请求结束前不发布“静态输出已成立”。 */
    write_tim(&TIM6->CR1,0);write_reg(&DAC->CR,0);
    write_reg(&DMA1_Stream5->CR,DMA1_Stream5->CR&~DMA_ENABLE);
    while((DMA1_Stream5->CR&DMA_ENABLE) && count<DMA_STOP_LIMIT)count++;
    if(DMA1_Stream5->CR&DMA_ENABLE) {
        g_source_diag.faults|=SRC_FAULT_DMA_STOP;g_source_diag.dma_reset_count++;
        /* 本固件不分配其它DMA1资源；有界停用失败时仅重置源板DMA1，不复位两块板。 */
        write_reg(&RCC->AHB1RSTR,RCC->AHB1RSTR|(1u<<21));
        __DSB();
        write_reg(&RCC->AHB1RSTR,RCC->AHB1RSTR&~(1u<<21));
        if(DMA1_Stream5->CR&DMA_ENABLE)return 0;
    }
    write_reg(&DMA1->HIFCR,DMA_ALL_FLAGS);
    write_reg(&DAC->SR,DAC_UNDERRUN);
    return 1;
}
static void static_output(void)
{
    /* 两路同一DAC码，仅声称数字静态状态；实际偏置/差分/负载均待G2测量。 */
    write_reg(&DAC->DHR12R1,SRC_BIAS_CODE);write_reg(&DAC->DHR12R2,SRC_BIAS_CODE);
    write_reg(&DAC->CR,DAC_ENABLES);
}
static void fault_locked(uint32_t reason)
{
    g_source_diag.faults|=reason;g_source_diag.mode=SRC_OFF;
    if(quiet()) {
        static_output();g_source_diag.state=SRC_STATE_FAULT_STATIC;
    } else {
        /* 硬件停用仍不能确认时保留高阻，不伪称DAC电压稳定；故障保持至显式复位。 */
        write_reg(&DAC->CR,0);g_source_diag.state=SRC_STATE_FAULT_HIGHZ;
    }
}
void Src_Fault(uint32_t reason)
{
    uint32_t irq=__get_PRIMASK();__disable_irq();
    fault_locked(reason);__set_PRIMASK(irq);
}
void Src_Init(void)
{
    uint32_t irq=__get_PRIMASK(),i;
    volatile uint32_t *p=(volatile uint32_t *)&g_source_diag;
    __disable_irq();
    for(i=0;i<sizeof(g_source_diag)/sizeof(uint32_t);i++)p[i]=0;
    g_source_diag.tag=0x31524353u;g_source_diag.version=1;g_source_diag.bias_code=SRC_BIAS_CODE;
    g_source_requested_mode=SRC_OFF;
    write_reg(&RCC->AHB1ENR,RCC->AHB1ENR|(1u<<0)|(1u<<21));
    write_reg(&RCC->APB1ENR,RCC->APB1ENR|(1u<<4)|(1u<<29));
    __DSB();
    write_reg(&GPIOA->MODER,(GPIOA->MODER&~((3u<<8)|(3u<<10)))|(3u<<8)|(3u<<10));
    write_reg(&GPIOA->PUPDR,GPIOA->PUPDR&~((3u<<8)|(3u<<10)));
    write_reg(&DBGMCU->APB1FZ,DBGMCU->APB1FZ|(1u<<4));
    SystemCoreClockUpdate();g_source_diag.core_hz=SystemCoreClock;
    /* 复用的8MHz HSE/PLL平台应为168MHz、APB1/4、TIM6倍频到84MHz。
       HSE失败退到HSI或时钟树漂移时不偷偷使用另一拍频。 */
    if(SystemCoreClock!=168000000u || (RCC->CFGR&0xcu)!=0x8u || ((RCC->CFGR>>10)&7u)!=5u) {
        fault_locked(SRC_FAULT_CLOCK);
    } else {
        g_source_diag.timer_hz=84000000u;
        if(!quiet())fault_locked(SRC_FAULT_DMA_STOP);
        /* 上电默认OFF：两DAC不使能，没有自动输出QRS/正弦。 */
    }
    NVIC_ClearPendingIRQ(DMA1_Stream5_IRQn);NVIC_ClearPendingIRQ(TIM6_DAC_IRQn);
    NVIC_SetPriority(DMA1_Stream5_IRQn,2);NVIC_SetPriority(TIM6_DAC_IRQn,1);
    NVIC_EnableIRQ(DMA1_Stream5_IRQn);NVIC_EnableIRQ(TIM6_DAC_IRQn);
    __set_PRIMASK(irq);
}
uint8_t Src_ApplyMode(uint32_t mode)
{
    uint32_t irq=__get_PRIMASK(),psc,arr,dma_error,dac_error;
    const SrcTable *table;
    __disable_irq();
    /* 模式切换不能抢在待处理错误IRQ前清掉原标志；先留证并锁存故障。
       两类错误同时存在时都记录，不让重新配置伪装成正常恢复。 */
    dma_error=DMA1->HISR&DMA_ERRORS;dac_error=DAC->SR&DAC_UNDERRUN;
    if(dma_error || dac_error) {
        if(dma_error)g_source_diag.last_dma_flags=DMA1->HISR&DMA_ALL_FLAGS;
        if(dac_error)g_source_diag.last_dac_flags=dac_error;
        fault_locked((dma_error ? SRC_FAULT_DMA : 0u)|(dac_error ? SRC_FAULT_UNDERRUN : 0u));
        __set_PRIMASK(irq);return 0;
    }
    /* 故障锁存后拒绝自动重启；OFF可再次撤销输出，但不清除故障历史。 */
    if(g_source_diag.faults) {
        if(mode==SRC_OFF) {
            /* 只有停用得到确认才报告OFF，否则继续保留高阻故障状态及历史。 */
            g_source_diag.state=quiet() ? SRC_STATE_OFF : SRC_STATE_FAULT_HIGHZ;
        }
        __set_PRIMASK(irq);return 0;
    }
    table=Src_GetTable(mode);
    if(!table) {fault_locked(SRC_FAULT_MODE);__set_PRIMASK(irq);return 0;}
    if(mode==g_source_diag.mode) {__set_PRIMASK(irq);return 1;}
    if(!quiet() || g_source_diag.faults) {
        fault_locked(SRC_FAULT_DMA_STOP);__set_PRIMASK(irq);return 0;
    }
    g_source_diag.mode_changes++;g_source_diag.table_length=0;
    if(mode==SRC_OFF)g_source_diag.state=SRC_STATE_OFF;
    else if(mode==SRC_BIAS) {static_output();g_source_diag.state=SRC_STATE_STATIC;}
    else {
        if(!Src_CopyRotated(table->codes,table->length,g_source_dma_buffer) ||
           !Src_TimerPlan(g_source_diag.timer_hz,&psc,&arr)) {
            fault_locked(SRC_FAULT_TABLE);__set_PRIMASK(irq);return 0;
        }
        /* 强制UG装载PSC/ARR时TRGO和DAC触发尚未开启，不能多打一次DMA请求。 */
        write_tim(&TIM6->CR2,0);write_tim(&TIM6->PSC,psc);
        /* 共用TIM结构的ARR/CNT为32位，CR/PSC/EGR/SR为16位，分别按设备声明访问。 */
        write_reg(&TIM6->ARR,arr);write_reg(&TIM6->CNT,0);
        write_tim(&TIM6->EGR,1);write_tim(&TIM6->SR,0);
        write_tim(&TIM6->CR2,2u<<4); /* MMS=010，更新事件为TRGO。 */
        write_reg(&DMA1_Stream5->PAR,(uint32_t)(uintptr_t)&DAC->DHR12R1);
        write_reg(&DMA1_Stream5->M0AR,(uint32_t)(uintptr_t)g_source_dma_buffer);
        write_reg(&DMA1_Stream5->NDTR,table->length);
        /* DAC寄存器按32位访问；DMA缓冲在普通SRAM，不放DMA不可访问的CCM。 */
        write_reg(&DMA1_Stream5->FCR,1u<<7); /* 直接模式，FIFO错误中断。 */
        write_reg(&DMA1_Stream5->CR,(7u<<25)|(2u<<16)|(2u<<13)|(2u<<11)|
                  (1u<<10)|(1u<<8)|(1u<<6)|(1u<<4)|(1u<<2)|(1u<<1));
        write_reg(&DAC->DHR12R1,table->codes[0]);write_reg(&DAC->DHR12R2,SRC_BIAS_CODE);
        __DMB(); /* DMA可见的整表先发布，再使能传输及DAC。 */
        write_reg(&DMA1_Stream5->CR,DMA1_Stream5->CR|DMA_ENABLE);
        write_reg(&DAC->CR,DAC_ENABLES|DAC_TRIGGER_DMA);
        g_source_diag.psc=psc;g_source_diag.arr=arr;g_source_diag.table_length=table->length;
        g_source_diag.first_code=table->codes[0];g_source_diag.state=SRC_STATE_STREAM;
        write_tim(&TIM6->CR1,1); /* 定时器最后启动，预装第0点后第1点依次接续。 */
    }
    g_source_diag.mode=mode;__set_PRIMASK(irq);return 1;
}
void DMA1_Stream5_IRQHandler(void)
{
    uint32_t flags=DMA1->HISR&DMA_ALL_FLAGS;
    if(!flags)return; /* 模式切换清标志后残留的IRQ不能抹掉已保存的错误原值。 */
    g_source_diag.last_dma_flags=flags;
    write_reg(&DMA1->HIFCR,flags);
    /* 同时有完成/错误时错误优先；错误传输不计完整表，也不再启动输出。 */
    if(flags&DMA_ERRORS)Src_Fault(SRC_FAULT_DMA);
    else if((flags&DMA_COMPLETE) && g_source_diag.state==SRC_STATE_STREAM) {
        g_source_diag.completed_tables++;
        g_source_diag.completed_dma_samples+=g_source_diag.table_length;
    }
}
void TIM6_DAC_IRQHandler(void)
{
    uint32_t flags=DAC->SR&DAC_UNDERRUN;
    if(!flags)return;
    g_source_diag.last_dac_flags=flags;
    if(flags)Src_Fault(SRC_FAULT_UNDERRUN);
}
