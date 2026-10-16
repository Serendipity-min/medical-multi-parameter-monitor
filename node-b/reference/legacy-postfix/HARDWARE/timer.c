/**
 * @file    timer.c
 * @brief   自由运行的 1ms 时基（TIM2 更新中断），只做"开机以来过了多少毫秒"。
 */
#include "timer.h"

// 毫秒计数。只有 TIM2 中断里改写，主循环只读，volatile 防止被优化掉。
static volatile uint32_t s_ms_tick = 0;


/**
 * @brief  启动 TIM2，让 s_ms_tick 每 1ms 自增一次。
 * @note   必须在任何用到 TimeBase_GetMs() 的模块 Init 之前调用
 *         （main 里的顺序：SysTick_Init → TimeBase_Init → ...）。
 */
void TimeBase_Init(void)
{
    TIM_TimeBaseInitTypeDef TIM_TimeBaseStructure;
    NVIC_InitTypeDef        NVIC_InitStructure;

    // TIM2 挂在 APB1（42MHz），但定时器时钟是 APB1 的 2 倍 = 84MHz
    // （APB1 分频系数不为 1 时硬件自动倍频）。
    RCC_APB1PeriphClockCmd(RCC_APB1Periph_TIM2, ENABLE);

    TIM_TimeBaseStructure.TIM_Prescaler         = 8400 - 1;   // 84MHz / 8400 = 10kHz
    TIM_TimeBaseStructure.TIM_CounterMode       = TIM_CounterMode_Up;
    TIM_TimeBaseStructure.TIM_Period            = 10 - 1;     // 10kHz / 10   = 1kHz，即 1ms
    TIM_TimeBaseStructure.TIM_ClockDivision     = TIM_CKD_DIV1;
    TIM_TimeBaseStructure.TIM_RepetitionCounter = 0;
    TIM_TimeBaseInit(TIM2, &TIM_TimeBaseStructure);

    TIM_ClearITPendingBit(TIM2, TIM_IT_Update);
    TIM_ITConfig(TIM2, TIM_IT_Update, ENABLE);

    // 抢占优先级 3，低于 DRDY 的 2：
    // 采样数据的读取时序比"记时间"重要，两者冲突时让位给 DRDY。
    NVIC_InitStructure.NVIC_IRQChannel                   = TIM2_IRQn;
    NVIC_InitStructure.NVIC_IRQChannelPreemptionPriority = 3;
    NVIC_InitStructure.NVIC_IRQChannelSubPriority        = 0;
    NVIC_InitStructure.NVIC_IRQChannelCmd                = ENABLE;
    NVIC_Init(&NVIC_InitStructure);

    TIM_Cmd(TIM2, ENABLE);
}


// TIM2 更新中断：只做一次自增，别的什么都不干。
void TIM2_IRQHandler(void)
{
    if (TIM_GetITStatus(TIM2, TIM_IT_Update) != RESET) {
        s_ms_tick++;
        TIM_ClearITPendingBit(TIM2, TIM_IT_Update);
    }
}


/**
 * @brief  取当前毫秒时间戳。
 * @note   返回的是"开机以来的毫秒数"，不是日期时间。49.7 天回绕。
 *         判断间隔请写成 (TimeBase_GetMs() - t_start) >= N，不要写成
 *         TimeBase_GetMs() >= t_start + N（后者在回绕时会出错）。
 */
uint32_t TimeBase_GetMs(void)
{
    return s_ms_tick;
}
