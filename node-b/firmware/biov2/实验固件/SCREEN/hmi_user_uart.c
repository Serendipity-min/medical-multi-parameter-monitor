/*!
*  \file  hmi_user_uart.c
*  \brief 用户 MCU 串口驱动函数库 —— STM32F407 + ST 标准外设库版
*  \note  直接替换官方工程里的 hmi_user_uart.c
*
*  与原版的差异（重要）：
*  1) 原版 UartInit() 里配置的是 USART2(PA2/PA3)，而 SendChar() 和中断
*     却用的 USART1──官方源码本身前后不一致。本文件统一用 USART1(PA9/PA10)。
*  2) F4 的 GPIO 复用必须额外做两件事：开 AHB1 时钟、调 GPIO_PinAFConfig()
*     设置复用功能号，且 GPIO_Mode 用 GPIO_Mode_AF（不是 F1 的 AF_PP）。
*  3) NVIC 结构体在 F4 标准库里多一个 NVIC_IRQChannelCmd 字段。
*
*  接线（与屏背面 8P 座对应，DN050：1/2=VCC 4=DOUT 5/6=DIN 7/8=GND）：
*        MCU PA9(TX)  -> 屏 5/6(DIN)    屏 4(DOUT) -> MCU PA10(RX)
*        共地；屏 DC 5V 独立供电、与 MCU 共地
*  ⚠ 屏出厂是 RS232 电平，短接屏背面 J5 才是 TTL，否则会打坏 PA9/PA10！
*
*  \copyright 广州大彩光电科技有限公司（原文件）/ F407 移植版
*/
#include "hmi_user_uart.h"

/*!
*   \brief   串口初始化
*   \param   BaudRate 波特率设置（必须与屏幕设定一致）
*/
void UartInit(uint32 BaudRate)
{
    GPIO_InitTypeDef  GPIO_InitStructure;
    USART_InitTypeDef USART_InitStructure;
    NVIC_InitTypeDef  NVIC_InitStructure;

    // 1. 开时钟：GPIOA 在 AHB1，USART1 在 APB2（F4 与 F1 总线不同）
    RCC_AHB1PeriphClockCmd(RCC_AHB1Periph_GPIOA, ENABLE);
    RCC_APB2PeriphClockCmd(RCC_APB2Periph_USART1, ENABLE);

    // 2. 把 PA9 / PA10 的复用功能号切成 USART1（F1 不需要这一步）
    GPIO_PinAFConfig(GPIOA, GPIO_PinSource9,  GPIO_AF_USART1);
    GPIO_PinAFConfig(GPIOA, GPIO_PinSource10, GPIO_AF_USART1);

    // 3. PA9 = USART1_TX，复用推挽输出
    GPIO_InitStructure.GPIO_Pin   = GPIO_Pin_9;
    GPIO_InitStructure.GPIO_Mode  = GPIO_Mode_AF;
    GPIO_InitStructure.GPIO_Speed = GPIO_Speed_50MHz;
    GPIO_InitStructure.GPIO_OType = GPIO_OType_PP;
    GPIO_InitStructure.GPIO_PuPd  = GPIO_PuPd_UP;
    GPIO_Init(GPIOA, &GPIO_InitStructure);

    // 4. PA10 = USART1_RX
    GPIO_InitStructure.GPIO_Pin  = GPIO_Pin_10;
    GPIO_InitStructure.GPIO_Mode = GPIO_Mode_AF;
    GPIO_InitStructure.GPIO_OType = GPIO_OType_PP;
    GPIO_InitStructure.GPIO_PuPd  = GPIO_PuPd_UP;
    GPIO_Init(GPIOA, &GPIO_InitStructure);

    // 5. 参数：8 位数据、1 位停止、无校验、无流控 —— 必须与屏幕设定一致
    USART_DeInit(USART1);
    USART_InitStructure.USART_BaudRate            = BaudRate;
    USART_InitStructure.USART_WordLength          = USART_WordLength_8b;
    USART_InitStructure.USART_StopBits            = USART_StopBits_1;
    USART_InitStructure.USART_Parity              = USART_Parity_No;
    USART_InitStructure.USART_HardwareFlowControl = USART_HardwareFlowControl_None;
    USART_InitStructure.USART_Mode                = USART_Mode_Tx | USART_Mode_Rx;
    USART_Init(USART1, &USART_InitStructure);

    // 6. 接收中断使能 + 开串口（RXNE 中断里调用 queue_push 入队）
    USART_ITConfig(USART1, USART_IT_RXNE, ENABLE);
    USART_Cmd(USART1, ENABLE);

    // 7. NVIC（F4 结构体多一个 NVIC_IRQChannelCmd）
    NVIC_InitStructure.NVIC_IRQChannel                   = USART1_IRQn;
    NVIC_InitStructure.NVIC_IRQChannelPreemptionPriority = 1;
    NVIC_InitStructure.NVIC_IRQChannelSubPriority        = 0;
    NVIC_InitStructure.NVIC_IRQChannelCmd                = ENABLE;
    NVIC_Init(&NVIC_InitStructure);
}

/*!
*   \brief  发送 1 个字节（阻塞式）
*   \param  t 发送的字节
*   \note   原版先写数据再等 TXE，这里改为先等 TXE 再写，语义更标准
*/
void SendChar(uchar t)
{
    while (USART_GetFlagStatus(USART1, USART_FLAG_TXE) == RESET);   // 等发送数据寄存器空
    USART_SendData(USART1, (uint8_t)t);
    while (USART_GetFlagStatus(USART1, USART_FLAG_TC) == RESET);   // 等发送完毕，避免帧最后一个字节被截断
}
