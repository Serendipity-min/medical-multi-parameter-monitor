/**
 * @file    systick.h
 * @brief   DWT 微秒/毫秒阻塞延时
 * @note    SysTick 已被串口屏层占用（10ms 节拍，见 SCREEN/ulitity.c），
 *          ADS1292 的命令时序延时改用 DWT CYCCNT 实现，API 与原版一致。
 */
#ifndef __SYSTICK_H
#define __SYSTICK_H

#include "stm32f4xx.h"

void SysTick_Init(void);
void Delay_us(uint32_t us);
void Delay_ms(uint32_t ms);

#endif
