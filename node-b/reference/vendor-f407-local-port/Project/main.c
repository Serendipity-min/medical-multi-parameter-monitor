//-----------------------------------------------------------------
// 程序描述:
//     ADS1292心电实验
// 作    者: 凌智电子
// 开始日期: 2020-09-25
// 完成日期: 2020-09-25
// 修改日期: 
// 当前版本: V1.0
// 历史版本:
//  - V1.0: (2020-09-25)	ADS1292心电实验
// 调试工具: 凌智STM32F429+CycloneIV电子系统设计开发板、LZE_ST_LINK2、ADS1292模块
// 说    明: 接口说明
//           ADS1292模块      开发板
// 					   ST(START)  ->   PA1
// 						 PW(PWDN) 	->   PA0
// 						 DR(DRDY)  	->   PA3
// 						 CS  	 			->   PA2
// 						 SCL(SCLK)	->   PA5
// 						 OUT(DOUT) 	->   PA6
// 						 IN(DIN) 		->   PA7
//             5V 				->   +5V
//						 GND				->	 GND
//
//					   三导联线						 心电模拟器
//						 红线（RL）		-> 				 RL
//						 黄线（LA）		-> 				 LA
//						 绿线（RA）		-> 				 RA
//
//					   三导联线						 		人体（导联线需要用电极片）
//						 红线（RL）		-> 				右脚
//						 黄线（LA）		-> 				左脚
//						 绿线（RA）		-> 				右手
//
//-----------------------------------------------------------------

//-----------------------------------------------------------------
// 头文件包含
//-----------------------------------------------------------------
#include "stm32f429_winner.h"
#include "arm_math.h"
#include "delay.h"
#include "lcd.h"
/* F407: no SDRAM */
#include "usart.h"
#include "ads1292.h"
#include "spi.h"
#include "exti.h"
//-----------------------------------------------------------------
#define Samples_Number  1    				// 采样点数
#define Block_Size      1     			// 调用一次arm_fir_f32处理的采样点个数
#define NumTaps        	129     		// 滤波器系数个数

uint32_t blockSize = Block_Size;											// 调用一次arm_fir_f32处理的采样点个数
uint32_t numBlocks = Samples_Number/Block_Size;       // 需要调用arm_fir_f32的次数

static float32_t Input_data1; 					// 输入缓冲区
static float32_t Output_data1;         // 输出缓冲区
static float32_t firState1[Block_Size + NumTaps - 1]; 	// 状态缓存，大小numTaps + blockSize - 1
static float32_t Input_data2; 					// 输入缓冲区
static float32_t Output_data2;         // 输出缓冲区
static float32_t firState2[Block_Size + NumTaps - 1]; 	// 状态缓存，大小numTaps + blockSize - 1

u32 ch1_data;	// 通道1的数据-呼吸测量数据
u32 ch2_data;	// 通道2的数据-心电图数据
u8 flog;			// 触发中断标志位
u16 point_cnt;									// 两个峰值之间的采集点数，用于计算心率

u8 dg_a[9], dg_b[9], dg_c[9];	// diag: 3 frames read by RDATA (no DRDY needed)
u8 dg_diff;						// diag: 1 = data changed -> chip is converting

// 心电带通滤波器系数：采样频率为250Hz，截止频率为5Hz~40Hz 通过filterDesigner获取
const float32_t BPF_5Hz_40Hz[NumTaps]  = {
  3.523997657e-05,0.0002562592272,0.0005757701583,0.0008397826459, 0.000908970891,
  0.0007304374012,0.0003793779761,4.222582356e-05,-6.521392788e-05,0.0001839015895,
  0.0007320778677, 0.001328663086, 0.001635892317, 0.001413777587,0.0006883906899,
  -0.0002056905651,-0.0007648666506,-0.0005919140531,0.0003351111372, 0.001569915912,
   0.002375603188, 0.002117323689,0.0006689901347,-0.001414557919,-0.003109993879,
  -0.003462586319, -0.00217742566,8.629632794e-05, 0.001947802957, 0.002011778764,
  -0.0002987752669,-0.004264956806, -0.00809297245,-0.009811084718,-0.008411717601,
  -0.004596390296,-0.0006214127061,0.0007985962438,-0.001978532877,-0.008395017125,
   -0.01568987407, -0.02018531598, -0.01929843985, -0.01321159769,-0.005181713495,
  -0.0001112028476,-0.001950757345, -0.01125541423,  -0.0243169684, -0.03460548073,
   -0.03605531529, -0.02662901953, -0.01020727865, 0.004513713531, 0.008002913557,
  -0.004921500571, -0.03125274926, -0.05950148031, -0.07363011688, -0.05986980721,
   -0.01351031102,  0.05752891302,   0.1343045086,   0.1933406889,   0.2154731899,
     0.1933406889,   0.1343045086,  0.05752891302, -0.01351031102, -0.05986980721,
   -0.07363011688, -0.05950148031, -0.03125274926,-0.004921500571, 0.008002913557,
   0.004513713531, -0.01020727865, -0.02662901953, -0.03605531529, -0.03460548073,
    -0.0243169684, -0.01125541423,-0.001950757345,-0.0001112028476,-0.005181713495,
   -0.01321159769, -0.01929843985, -0.02018531598, -0.01568987407,-0.008395017125,
  -0.001978532877,0.0007985962438,-0.0006214127061,-0.004596390296,-0.008411717601,
  -0.009811084718, -0.00809297245,-0.004264956806,-0.0002987752669, 0.002011778764,
   0.001947802957,8.629632794e-05, -0.00217742566,-0.003462586319,-0.003109993879,
  -0.001414557919,0.0006689901347, 0.002117323689, 0.002375603188, 0.001569915912,
  0.0003351111372,-0.0005919140531,-0.0007648666506,-0.0002056905651,0.0006883906899,
   0.001413777587, 0.001635892317, 0.001328663086,0.0007320778677,0.0001839015895,
  -6.521392788e-05,4.222582356e-05,0.0003793779761,0.0007304374012, 0.000908970891,
  0.0008397826459,0.0005757701583,0.0002562592272,3.523997657e-05
	};

// 呼吸波低通滤波器系数：采样频率为250Hz，截止频率为2Hz 通过filterDesigner获取
const float32_t LPF_2Hz[NumTaps]  = {
  -0.0004293085367,-0.0004170549801,-0.0004080719373,-0.0004015014856,-0.0003963182389,
  -0.000391335343,-0.0003852125083,-0.0003764661378,-0.0003634814057,-0.0003445262846,
  -0.0003177672043,-0.0002812864841,-0.0002331012802,-0.0001711835939,-9.348169988e-05,
  2.057720394e-06,0.0001174666468, 0.000254732382,0.0004157739459,0.0006024184986,
   0.000816378044, 0.001059226575, 0.001332378131,  0.00163706555,  0.00197432097,
   0.002344956854, 0.002749550389, 0.003188427072, 0.003661649302, 0.004169005435,
    0.00471000094, 0.005283853505, 0.005889489781, 0.006525543984, 0.007190360688,
   0.007882000878, 0.008598247543, 0.009336617775,  0.01009437256,  0.01086853724,
    0.01165591553,  0.01245311089,  0.01325654797,  0.01406249963,  0.01486710832,
    0.01566641964,  0.01645640284,  0.01723298989,  0.01799209975,  0.01872966997,
    0.01944169216,  0.02012423798,  0.02077349275,  0.02138578519,  0.02195761539,
     0.0224856846,  0.02296692133,  0.02339850739,  0.02377789468,  0.02410283685,
    0.02437139489,  0.02458196506,  0.02473328263,  0.02482444048,  0.02485488541,
    0.02482444048,  0.02473328263,  0.02458196506,  0.02437139489,  0.02410283685,
    0.02377789468,  0.02339850739,  0.02296692133,   0.0224856846,  0.02195761539,
    0.02138578519,  0.02077349275,  0.02012423798,  0.01944169216,  0.01872966997,
    0.01799209975,  0.01723298989,  0.01645640284,  0.01566641964,  0.01486710832,
    0.01406249963,  0.01325654797,  0.01245311089,  0.01165591553,  0.01086853724,
    0.01009437256, 0.009336617775, 0.008598247543, 0.007882000878, 0.007190360688,
   0.006525543984, 0.005889489781, 0.005283853505,  0.00471000094, 0.004169005435,
   0.003661649302, 0.003188427072, 0.002749550389, 0.002344956854,  0.00197432097,
    0.00163706555, 0.001332378131, 0.001059226575, 0.000816378044,0.0006024184986,
  0.0004157739459, 0.000254732382,0.0001174666468,2.057720394e-06,-9.348169988e-05,
  -0.0001711835939,-0.0002331012802,-0.0002812864841,-0.0003177672043,-0.0003445262846,
  -0.0003634814057,-0.0003764661378,-0.0003852125083,-0.000391335343,-0.0003963182389,
  -0.0004015014856,-0.0004080719373,-0.0004170549801,-0.0004293085367
	};

//-----------------------------------------------------------------
// 诊断: 采样DRDY(上下拉各20次)
//-----------------------------------------------------------------
static void DrdySample(u32 pull, u8 *mn, u8 *mx)
{
	GPIO_InitTypeDef g;
	u8 v, i;

	g.Pin   = GPIO_PIN_3;
	g.Mode  = GPIO_MODE_INPUT;
	g.Pull  = pull;
	g.Speed = GPIO_SPEED_HIGH;
	HAL_GPIO_Init(GPIOA, &g);

	*mn = 1; *mx = 0;
	for (i = 0; i < 20; i++)
	{
		v = (u8)HAL_GPIO_ReadPin(GPIOA, GPIO_PIN_3);
		if (v < *mn) { *mn = v; }
		if (v > *mx) { *mx = v; }
		delay_ms(5);
	}
}

// 0=芯片驱动低(在转换) 1=芯片驱动高(未转换) 2=悬空(线断/虚焊) 3=脉冲
static u8 DrdyVerdict(u8 umn, u8 umx, u8 dmn, u8 dmx)
{
	if (umn != umx) return 3;
	if (umn == 0)   return 0;
	if (dmn == 1)   return 1;
	return 2;
}

static void DrdyTest(const char *tag)
{
	u8 umn, umx, dmn, dmx, v;
	GPIO_InitTypeDef g;

	DrdySample(GPIO_PULLUP,   &umn, &umx);
	DrdySample(GPIO_PULLDOWN, &dmn, &dmx);
	v = DrdyVerdict(umn, umx, dmn, dmx);

	printf("%s up=%d%d dn=%d%d %s\r\n", tag, umn, umx, dmn, dmx,
	       (v == 0) ? "DRDY=LOW:converting" :
	       (v == 1) ? "DRDY=HIGH:chip idle" :
	       (v == 2) ? "FLOAT:DRDY wire open" : "PULSE:converting");

	g.Pin = GPIO_PIN_3;
	g.Mode = GPIO_MODE_IT_FALLING;
	g.Pull = GPIO_PULLUP;
	HAL_GPIO_Init(GPIOA, &g);
}

//-----------------------------------------------------------------
// 诊断: 轮询PA3数下降沿(不靠中断)
//-----------------------------------------------------------------
static u16 PollDrdy(u16 ms, u8 *lv)
{
	u8 prev, cur;
	u16 edges = 0;
	u32 t0 = HAL_GetTick();

	prev = (u8)HAL_GPIO_ReadPin(GPIOA, GPIO_PIN_3);
	while (HAL_GetTick() - t0 < ms)
	{
		cur = (u8)HAL_GPIO_ReadPin(GPIOA, GPIO_PIN_3);
		if (prev == 1 && cur == 0) { edges++; }
		prev = cur;
	}
	*lv = prev;
	return edges;
}

//-----------------------------------------------------------------
// 诊断: 用START命令启动转换(绕开ST引脚)
// 没人读数据时DRDY拉低后会一直保持低, 所以"读到低"就说明芯片真在转换
//-----------------------------------------------------------------
static void StartCmdTest(void)
{
	u8 lv, k;
	u16 e;

	ADS1292_CS = 0; delay_us(10); SPI5_Send_Byte(SDATAC); delay_us(10); ADS1292_CS = 1;
	delay_ms(2);
	ADS1292_CS = 0; delay_us(10); SPI5_Send_Byte(START);  delay_us(10); ADS1292_CS = 1;

	e = PollDrdy(300, &lv);
	printf("[5] START cmd: edges=%d now=%d %s\r\n", (int)e, (int)lv,
	       ((e > 0) || (lv == 0)) ? "CHIP CONVERTS" : "chip silent");

	if ((e > 0) || (lv == 0))	// 能转换: 收掉积压的数据
	{
		ADS1292_CS = 0; delay_us(10); SPI5_Send_Byte(RDATAC); delay_us(10);
		for (k = 0; k < 9; k++) { SPI5_ReadWrite_Byte(0xFF); }
		ADS1292_CS = 1;
	}
}

//-----------------------------------------------------------------
// diag: read data by RDATA command (does NOT depend on DRDY pin)
// same data every time = chip not converting
// changing data        = chip IS converting => DRDY line is the problem
//-----------------------------------------------------------------
static void DataMotionTest(void)
{
	u8 i, k;
	u8 *dst[3];

	dst[0] = dg_a; dst[1] = dg_b; dst[2] = dg_c;

	ADS1292_CS = 0; delay_us(10); SPI5_Send_Byte(SDATAC); delay_us(10); ADS1292_CS = 1;
	delay_ms(2);

	for (i = 0; i < 3; i++)
	{
		ADS1292_CS = 0; delay_us(10); SPI5_Send_Byte(RDATA); delay_us(10);
		for (k = 0; k < 9; k++) { dst[i][k] = SPI5_ReadWrite_Byte(0xFF); }
		ADS1292_CS = 1;
		delay_ms(15);
	}

	dg_diff = 0;
	for (k = 3; k < 9; k++)	// 只比数据字节: 状态字节跳变(c1<->c0)会误报
	{
		if (dg_a[k] != dg_b[k]) { dg_diff = 1; }
		if (dg_b[k] != dg_c[k]) { dg_diff = 1; }
	}

	for (i = 0; i < 3; i++)
	{
		printf("[6] RDATA%d:", i);
		for (k = 0; k < 9; k++) { printf(" %02x", dst[i][k]); }
		printf("\r\n");
	}
	printf("[6] %s\r\n", dg_diff ? "DATA CHANGES -> chip IS converting"
	                             : "DATA STATIC -> chip NOT converting");

	ADS1292_CS = 0; delay_us(10); SPI5_Send_Byte(RDATAC); delay_us(10); ADS1292_CS = 1;
}

//-----------------------------------------------------------------
// 诊断: 一次报全(寄存器/DRDY/START命令/原始数据)
//-----------------------------------------------------------------
static void DiagReport(void)
{
	u8 i, k;
	u8 f[9];

	HAL_NVIC_DisableIRQ(EXTI3_IRQn);	// 自检期间不让中断抢SPI

	printf("\r\n--- ADS1292 DIAG ---\r\n");

	ADS1292_CS = 0; delay_us(10); SPI5_Send_Byte(SDATAC); delay_us(10); ADS1292_CS = 1;

	printf("[1] regs ID=%02x C1=%02x C2=%02x CH1=%02x CH2=%02x\r\n",
	       ADS1292_Read_Reg(RREG|ID),     ADS1292_Read_Reg(RREG|CONFIG1),
	       ADS1292_Read_Reg(RREG|CONFIG2),ADS1292_Read_Reg(RREG|CH1SET),
	       ADS1292_Read_Reg(RREG|CH2SET));

	DrdyTest("[2] now ");

	StartCmdTest();

	DataMotionTest();

	ADS1292_CS = 0; delay_us(10); SPI5_Send_Byte(SDATAC); delay_us(10); ADS1292_CS = 1;
	ADS1292_CS = 0; delay_us(10);
	SPI5_Send_Byte(RDATAC); delay_us(10);
	for (i = 0; i < 3; i++)
	{
		for (k = 0; k < 9; k++) { f[k] = SPI5_ReadWrite_Byte(0xFF); }
		printf("[4] F%d:", i);
		for (k = 0; k < 9; k++) { printf(" %02x", f[k]); }
		printf("\r\n");
	}
	ADS1292_CS = 1;

	printf("--------------------\r\n\r\n");

	HAL_NVIC_EnableIRQ(EXTI3_IRQn);
}

//-----------------------------------------------------------------
// PA8 = MCO1, output HSE/4 = 2MHz clock -> ADS1292 CLK pin (LK)
// test: if R16/CLKSEL net broken, chip falls into external-clock
// mode and starts converting with this clock
//-----------------------------------------------------------------
static void Mco1_Init(void)
{
	GPIO_InitTypeDef g;

	__HAL_RCC_GPIOA_CLK_ENABLE();
	g.Pin        = GPIO_PIN_8;
	g.Mode       = GPIO_MODE_AF_PP;
	g.Pull       = GPIO_NOPULL;
	g.Speed      = GPIO_SPEED_HIGH;
	g.Alternate  = GPIO_AF0_MCO;
	HAL_GPIO_Init(GPIOA, &g);
	HAL_RCC_MCOConfig(RCC_MCO1, RCC_MCO1SOURCE_HSE, RCC_MCODIV_4);
}

//-----------------------------------------------------------------
// 主程序
//-----------------------------------------------------------------
int main(void)
{
	arm_fir_instance_f32 S1;
	arm_fir_instance_f32 S2;
	
	u32 p_num=0;	  	// 用于刷新最大值和最小值
	u32 min[2]={0xFFFFFFFF,0xFFFFFFFF};
	u32 max[2]={0,0};
	u32 Peak;					// 峰峰值
	u32 BPM_LH[3];		// 用于判断波峰
	float BPM;				// 心率
	u32 last_tick;		// 最近一次收到数据的时刻
	u32 loff_tick;		// 上次读导联脱落状态的时刻
	u8 loff_skip;		// LOFF读寄存器后要丢弃的帧数

	flog=0;
	loff_skip=0;
	
  HAL_Init();          							// 初始化HAL库
	SystemClock_Config(336,8,2,7); 	// 设置系统时钟,180Mhz
	uart_init(115200);
	printf("V0928-F407-FIR FW v13-LOFFSKIP\r\n");
	Mco1_Init();										// PA8 output 2MHz clock to ADS1292 CLK
	ADS1292_Init();										// ADS1292引脚初始化
  ADS1292_PowerOnInit();						// ADS1292上电初始化
	EXTI_Init();											// 外部中断初始化(放在初始化之后, 避免中断与SPI配置抢总线)
	
	// 滤波初始化
	arm_fir_init_f32(&S1, NumTaps, (float32_t *)LPF_2Hz, firState1, blockSize);
	arm_fir_init_f32(&S2, NumTaps, (float32_t *)BPF_5Hz_40Hz, firState2, blockSize);
	
	DiagReport();		// 开机自检报告
	
	// wakeup first, then give START pin a clean rising edge
	ADS1292_CS=0; delay_us(10); SPI5_ReadWrite_Byte(WAKEUP); delay_us(10); ADS1292_CS=1;
	ADS1292_START=0; delay_ms(2); ADS1292_START=1; delay_ms(2);

	ADS1292_CS=0;
	delay_us(10);
  SPI5_ReadWrite_Byte(RDATAC);		// 发送启动连续读取数据命令
  delay_us(10);
	ADS1292_CS=1;						
  ADS1292_START=1; 				// 启动转换
	ADS1292_CS=0;
	last_tick=HAL_GetTick();
	loff_tick=HAL_GetTick()-2000;	// 负偏移: 让第一行[LOFF]开机立刻打印
	while(1)
	{
		if(flog==1)
		{
			if(loff_skip)		// 刚读完LOFF寄存器, 这几帧是重对齐垃圾, 不进FIR不上屏
			{
				loff_skip--;
				flog=0;
				last_tick=HAL_GetTick();
				continue;
			}
			// 通道1呼吸波数据
			Input_data1=(float32_t)(ch1_data^0x800000);
			// 实现FIR滤波
			arm_fir_f32(&S1, &Input_data1, &Output_data1, blockSize);
			
			// 通道2心电波形数据			
			Input_data2=(float32_t)(ch2_data^0x800000);
			// 实现FIR滤波
			arm_fir_f32(&S2, &Input_data2, &Output_data2, blockSize);
			
			// 比较大小
			if(min[1]>Output_data2)
				min[1]=Output_data2;
			if(max[1]<Output_data2)
				max[1]=Output_data2;
			
			BPM_LH[0]=BPM_LH[1];
			BPM_LH[1]=BPM_LH[2];
			BPM_LH[2]=Output_data2;
			if((BPM_LH[0]<BPM_LH[1])&(BPM_LH[1]>max[0]-Peak/3)&(BPM_LH[2]<BPM_LH[1]))
			{
				BPM=(float)60000.0/(point_cnt*4);
				point_cnt=0;
			}
			
			// 每隔2000个点重新测量一次最大最小值
			p_num++;;
			if(p_num>2000)
			{
				min[0]=min[1];			
				max[0]=max[1];
				min[1]=0xFFFFFFFF;
				max[1]=0;
				Peak=max[0]-min[0];
				p_num=0;
			}
			// 数据：呼吸波、心电信号、心率
			printf("B: %8d",(int)Output_data1);
			printf("A: %8d",(int)(Output_data2));
			printf("C: %6.2f\r\n",(BPM));
			flog=0;
			last_tick=HAL_GetTick();
		}
		else if(HAL_GetTick()-last_tick>2000)	// 2s no data: re-check chip without DRDY
		{
			DataMotionTest();
			last_tick=HAL_GetTick();
		}
		
		// 每2秒读一次电极脱落状态: 读寄存器须暂停连续读, 期间关中断防抢SPI
		if(HAL_GetTick()-loff_tick>2000)
		{
			u8 s;
			HAL_NVIC_DisableIRQ(EXTI3_IRQn);
			s=ADS1292_GetLeadOff();
			HAL_NVIC_EnableIRQ(EXTI3_IRQn);
			loff_skip=20;		// SDATAC/RDATAC切换后前几帧错位, 丢弃(实测毛刺宽3~10帧)
			printf("[LOFF] %02X 1P=%d 1N=%d 2P=%d 2N=%d RLD=%d\r\n",
			       s, s&1, (s>>1)&1, (s>>2)&1, (s>>3)&1, (s>>4)&1);
			loff_tick=HAL_GetTick();
		}
	}
}

//-----------------------------------------------------------------
// End Of File
//----------------------------------------------------------------- 
