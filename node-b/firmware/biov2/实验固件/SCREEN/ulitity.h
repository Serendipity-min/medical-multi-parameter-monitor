/*!
*  \file ulitity.h
*  \brief 定时器节拍与毫秒延时（STM32F407 移植版）
*  \version 1.1
*  \date 2012-2018 / 移植 2026
*  \copyright 广州大彩光电科技有限公司（原文件）/ F407 移植版
*/
#ifndef _ULITITY_H
#define _ULITITY_H

#include "hmi_user_uart.h"

// 10ms 一个节拍，由 SysTick_Handler 累加，定义在 ulitity.c
extern volatile uint32 timer_tick_count;

void systicket_init(void);

void delay_ms(uint32 delay);

#endif
