/**
 * @file    systick.c
 * @brief   DWT CYCCNT 阻塞延时（原工程用 SysTick 一次性倒计时，会打断
 *          串口屏层的 10ms 节拍，这里换成 DWT 计数，SysTick 完整让给屏层）
 */
#include "systick.h"

// 打开 DWT 计数器（CoreDebug->DEMCR 的 TRCENA 位 + CYCCNT 使能）
void SysTick_Init(void)
{
    CoreDebug->DEMCR |= CoreDebug_DEMCR_TRCENA_Msk;  // TRCENA：使能 DWT/ITM 跟踪单元
    DWT->CYCCNT = 0;                                 // 周期计数器清零
    DWT->CTRL |= DWT_CTRL_CYCCNTENA_Msk;             // CYCCNTENA：启动 CYCCNT，每过一个内核周期加 1
}

// 微秒阻塞延时（168MHz 主频下 1us = 168 周期，无符号回绕安全）
void Delay_us(uint32_t us)
{
    uint32_t start = DWT->CYCCNT;
    uint32_t ticks = us * (SystemCoreClock / 1000000);   // 换算成需要等待的内核周期数

    // 无符号差值比较：CYCCNT 回绕时结果依然正确
    while ((DWT->CYCCNT - start) < ticks) { }
}

void Delay_ms(uint32_t ms)
{
    while (ms--) { Delay_us(1000); }
}
