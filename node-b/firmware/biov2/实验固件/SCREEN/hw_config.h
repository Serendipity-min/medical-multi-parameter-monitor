/*!
*  \file hw_config.h
*  \brief 系统中断配置（STM32F407 移植版）
*  \version 1.1
*  \date 2012-2018 / 移植 2026
*  \copyright 广州大彩光电科技有限公司（原文件）/ F407 移植版
*/
#ifndef _HW_CONFIG_H
#define _HW_CONFIG_H

/*
 * F1 版的 Set_System() 在这里被删掉了：
 * 那段代码是 F1 专属的 RCC_PLLConfig(RCC_PLLSource_HSI_Div2, RCC_PLLMul_12)，
 * 在 F407 上编译不过。F407 的 168MHz 时钟由 startup_stm32f40_41xxx.s
 * 自动调用 system_stm32f4xx.c 里的 SystemInit() 完成，不需要用户代码。
 */
void Interrupts_Config(void);

#endif
