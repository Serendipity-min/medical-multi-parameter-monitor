/*!
*  \file ulitity.c
*  \brief 定时器节拍与毫秒延时（STM32F407 移植版）
*  \copyright 广州大彩光电科技有限公司（原文件）/ F407 移植版
*/
#include "ulitity.h"

volatile uint32 timer_tick_count = 0;   // 定时器节拍：10ms +1，SysTick_Handler 累加

/*!
* 名    称： delay_ms
* 功    能： 延时n毫秒（基于节拍，与主频无关）
* 入口参数： n-延时时间
* 出口参数： 无
*/
void delay_ms(uint32 delay)
{
    uint32 tick = timer_tick_count;
    while(1)
    {
        // 无符号相减：节拍计数溢出回绕时差值仍正确；节拍10ms故换算为 delay/10
        if(timer_tick_count - tick > delay/10)
            break;
    }
}

/*!
* 名    称： systicket_init
* 功    能： SysTick 节拍定时器，10ms 一次中断
* 说明    ： F1 官方版写死 48000000/100（48MHz 主频）；
*            F4 版改用 SystemCoreClock 变量，168MHz 下自动正确。
*            注意用 HCLK 不分频（F1 例程里是 HCLK_Div8，别照搬）。
*/
void systicket_init(void)
{
    SysTick_CLKSourceConfig(SysTick_CLKSource_HCLK);
    SysTick_Config(SystemCoreClock / 100);     // 1 秒 100 次中断 => 10ms 节拍
}
