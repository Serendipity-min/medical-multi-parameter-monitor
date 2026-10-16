/**
 * @file    stm32f4xx_it.c
 * @brief   中断服务函数
 *
 * USART1（串口屏）：逐字节丢进指令队列，整帧解析放主循环。
 * EXTI3（ADS1292 DRDY）在 ads1292.c 里，TIM2（算法时基）在 timer.c 里，
 * 都不在这里重复定义。SysTick：10ms 节拍，供 ulitity.c 的 timer_tick_count。
 */
#include "stm32f4xx_it.h"
#include "cmd_queue.h"
#include "ulitity.h"

// 以下为 Cortex-M4 内核异常入口：NMI/SVC/调试/PendSV 本工程未使用，空函数直接返回
void NMI_Handler(void)       {}
// 各类 fault 为致命错误，原地死循环停住，防止跑飞后继续执行
void HardFault_Handler(void) { while (1) {} }
void MemManage_Handler(void) { while (1) {} }
void BusFault_Handler(void)  { while (1) {} }
void UsageFault_Handler(void){ while (1) {} }
void SVC_Handler(void)       {}
void DebugMon_Handler(void)  {}
void PendSV_Handler(void)    {}

// USART1 接收中断（串口屏）：只收字节，不做解析/刷屏
void USART1_IRQHandler(void)
{
    // RXNE：收到一个字节，读出后逐字节压入指令队列（整帧解析在主循环）
    if (USART_GetITStatus(USART1, USART_IT_RXNE) != RESET)
    {
        uint8_t data = (uint8_t)USART_ReceiveData(USART1);
        queue_push(data);
    }
    // ORE 溢出标志不清除会反复进中断卡死：读一次 DR 即清除
    if (USART_GetFlagStatus(USART1, USART_FLAG_ORE) != RESET)
    {
        (void)USART_ReceiveData(USART1);
    }
}

// SysTick 中断：10ms 一次，节拍计数供主循环换算时间与界面分频
void SysTick_Handler(void)
{
    ++timer_tick_count;
}
