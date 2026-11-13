#include "can.h"

static CanStats_t s_stats;
static CanFrame_t s_rx_buf[CAN_RX_BUF_SIZE];
static volatile uint16_t s_rx_head = 0;
static volatile uint16_t s_rx_tail = 0;

//PA11/CAN1_Rx  PA12/CAN1_Tx（CAN1 默认映射）
static void CAN1_GPIO_Config(void)
{
	GPIO_InitTypeDef  GPIO_InitStructure;
	
	RCC_AHB1PeriphClockCmd(RCC_AHB1Periph_GPIOA, ENABLE);

	GPIO_InitStructure.GPIO_Pin = GPIO_Pin_11|GPIO_Pin_12;
	GPIO_InitStructure.GPIO_Mode = GPIO_Mode_AF;//复用模式
	GPIO_InitStructure.GPIO_OType = GPIO_OType_PP;//推挽输出
	GPIO_InitStructure.GPIO_Speed = GPIO_Speed_100MHz;
	GPIO_InitStructure.GPIO_PuPd = GPIO_PuPd_UP;//上拉
	GPIO_Init(GPIOA, &GPIO_InitStructure);

	GPIO_PinAFConfig(GPIOA, GPIO_PinSource11,GPIO_AF_CAN1);//CAN1_Rx
	GPIO_PinAFConfig(GPIOA, GPIO_PinSource12,GPIO_AF_CAN1);//CAN1_Tx
}

static void CAN1_Mode_Config(uint8_t mode)
{
	CAN_InitTypeDef   CAN_InitStructure;

	RCC_APB1PeriphClockCmd(RCC_APB1Periph_CAN1, ENABLE);

	//初始化CAN1的寄存器为默认
	CAN_DeInit(CAN1);

	CAN_InitStructure.CAN_TTCM = DISABLE;//失能时间触发
	CAN_InitStructure.CAN_ABOM = ENABLE;//使能自动离线管理(bus-off 自动恢复)
	CAN_InitStructure.CAN_AWUM = DISABLE;//失能自动唤醒
	CAN_InitStructure.CAN_NART = DISABLE;//使用自动重传
	CAN_InitStructure.CAN_RFLM = DISABLE;//不锁定接收FIFO
	CAN_InitStructure.CAN_TXFP = DISABLE;//以报文ID的优先级发送
	CAN_InitStructure.CAN_Mode = mode;//CAN_Mode_Normal=正常 / CAN_Mode_LoopBack=回环自测
	CAN_InitStructure.CAN_SJW = CAN_SJW_2tq;//SJW

	//42M/6=7M,1tq=1/7M s,1bit：(1+4+2)=7tq → 1us，波特率1Mbps
	//(想提高采样点到85.7%：Prescaler=3 + BS1_11tq + BS2_2tq，波特率不变)
	CAN_InitStructure.CAN_BS1 = CAN_BS1_4tq;
	CAN_InitStructure.CAN_BS2 = CAN_BS2_2tq;
	CAN_InitStructure.CAN_Prescaler = 6;
	CAN_Init(CAN1, &CAN_InitStructure);
}

//激活过滤器0，接收全部报文到第0组FIFO，ID 过滤交给软件层，便于调试
//CAN没有CAN_Cmd,配置好后直接开始工作
static void CAN1_Filter_Config(void)
{
	CAN_FilterInitTypeDef  CAN_FilterInitStructure;

	CAN_FilterInitStructure.CAN_FilterNumber = 0;//过滤器编号
	CAN_FilterInitStructure.CAN_FilterMode = CAN_FilterMode_IdMask;//掩码模式
	CAN_FilterInitStructure.CAN_FilterScale = CAN_FilterScale_32bit;//位宽32位
	CAN_FilterInitStructure.CAN_FilterIdHigh = 0x0000;//筛选的ID高位
	CAN_FilterInitStructure.CAN_FilterIdLow = 0x0000;//筛选的ID低位
	CAN_FilterInitStructure.CAN_FilterMaskIdHigh = 0x0000;//掩码高位
	CAN_FilterInitStructure.CAN_FilterMaskIdLow = 0x0000; //掩码低位
	CAN_FilterInitStructure.CAN_FilterFIFOAssignment = CAN_Filter_FIFO0;//FIFO管理
	CAN_FilterInitStructure.CAN_FilterActivation = ENABLE;
	CAN_FilterInit(&CAN_FilterInitStructure);
}

void CAN1_Config(void)
{
	NVIC_InitTypeDef NVIC_InitStructure;

	CAN1_GPIO_Config();
	CAN1_Mode_Config(CAN_Mode_Normal);
	CAN1_Filter_Config();

	//接收走 RX0 中断，错误走 SCE；优先级低于串口屏(1)，别抢采样/刷屏
	CAN_ITConfig(CAN1, CAN_IT_FMP0 | CAN_IT_EWG | CAN_IT_EPV | CAN_IT_BOF, ENABLE);

	NVIC_InitStructure.NVIC_IRQChannel = CAN1_RX0_IRQn;
	NVIC_InitStructure.NVIC_IRQChannelPreemptionPriority = 2;
	NVIC_InitStructure.NVIC_IRQChannelSubPriority = 2;
	NVIC_InitStructure.NVIC_IRQChannelCmd = ENABLE;
	NVIC_Init(&NVIC_InitStructure);

	NVIC_InitStructure.NVIC_IRQChannel = CAN1_SCE_IRQn;
	NVIC_InitStructure.NVIC_IRQChannelPreemptionPriority = 3;
	NVIC_InitStructure.NVIC_IRQChannelSubPriority = 3;
	NVIC_InitStructure.NVIC_IRQChannelCmd = ENABLE;
	NVIC_Init(&NVIC_InitStructure);

	CAN1_ResetStats();
}

//发送数据(std_id：标准帧ID；成功：0，失败：1)
uint8_t CAN1_Send_Msg(uint32_t std_id, const uint8_t *data, uint8_t dlc)
{
	uint8_t i,Mailbox;

	CanTxMsg TxMessage;
	TxMessage.StdId = std_id & 0x7FF;//标准ID
	TxMessage.ExtId = 0;//扩展ID,由IDE决定是否有效
	TxMessage.RTR = CAN_RTR_Data;//数据帧
	TxMessage.IDE = CAN_Id_Standard;//标准格式
	TxMessage.DLC = (dlc > 8) ? 8 : dlc;//数据长度

	for(i = 0; i < TxMessage.DLC; i++)
	{
		TxMessage.Data[i]=data[i];
	}

	//发送结构体，返回值是邮箱编号；邮箱占满返回 NoMailBox
	Mailbox = CAN_Transmit(CAN1, &TxMessage);
	if(Mailbox == CAN_TxStatus_NoMailBox)
	{
		s_stats.tx_busy++;
		return 1;
	}
	s_stats.tx_ok++;
	return 0;
}

//接收数据(从环形缓冲取一帧; 返回 1 = 取到, 0 = 缓冲为空)
uint8_t CAN1_Recv_Msg(CanFrame_t *f)
{
	if(s_rx_head == s_rx_tail)
	{
		return 0;
	}
	*f = s_rx_buf[s_rx_tail];
	s_rx_tail = (uint16_t)((s_rx_tail + 1) % CAN_RX_BUF_SIZE);
	return 1;
}

//FIFO0 中断：只把帧搬进环形缓冲，业务解析放主循环
void CAN1_RX0_IRQHandler(void)
{
	CanRxMsg RxMessage;
	uint16_t next;
	uint8_t  i;

	while(CAN_MessagePending(CAN1,CAN_FIFO0) > 0)
	{
		CAN_Receive(CAN1, CAN_FIFO0, &RxMessage);

		next = (uint16_t)((s_rx_head + 1) % CAN_RX_BUF_SIZE);
		if(next == s_rx_tail)
		{
			s_stats.rx_drop++;
			continue;
		}
		s_rx_buf[s_rx_head].id  = (RxMessage.IDE == CAN_Id_Standard) ? RxMessage.StdId : RxMessage.ExtId;
		s_rx_buf[s_rx_head].dlc = RxMessage.DLC & 0x0F;
		for(i = 0; i < s_rx_buf[s_rx_head].dlc; i++)
		{
			s_rx_buf[s_rx_head].data[i] = RxMessage.Data[i];
		}
		s_rx_head = next;
		s_stats.rx_ok++;
	}
}

//错误中断：只计数，恢复交给 ABOM
void CAN1_SCE_IRQHandler(void)
{
	if(CAN_GetITStatus(CAN1, CAN_IT_EWG) != RESET) { s_stats.err_warning++; CAN_ClearITPendingBit(CAN1, CAN_IT_EWG); }
	if(CAN_GetITStatus(CAN1, CAN_IT_EPV) != RESET) { s_stats.err_passive++; CAN_ClearITPendingBit(CAN1, CAN_IT_EPV); }
	if(CAN_GetITStatus(CAN1, CAN_IT_BOF) != RESET) { s_stats.bus_off++;     CAN_ClearITPendingBit(CAN1, CAN_IT_BOF); }
	CAN_ClearITPendingBit(CAN1, CAN_IT_LEC);
	CAN_ClearITPendingBit(CAN1, CAN_IT_ERR);
}

void CAN1_GetStats(CanStats_t *s) { if (s != 0) { *s = s_stats; } }

void CAN1_ResetStats(void)
{
	s_stats.tx_ok = 0; s_stats.tx_busy = 0; s_stats.rx_ok = 0; s_stats.rx_drop = 0;
	s_stats.err_warning = 0; s_stats.err_passive = 0; s_stats.bus_off = 0;
}

//切回环/正常等模式(回环自测用)，位时序不变
//切换模式（回环自测用）：重初始化会清掉中断使能，滤波器和中断都必须重配
void CAN1_SetMode(uint8_t mode)
{
	CAN1_Mode_Config(mode);
	CAN1_Filter_Config();
	CAN_ITConfig(CAN1, CAN_IT_FMP0 | CAN_IT_EWG | CAN_IT_EPV | CAN_IT_BOF, ENABLE);
}
