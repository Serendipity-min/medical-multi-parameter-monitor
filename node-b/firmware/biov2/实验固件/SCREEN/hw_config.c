/*!
*  \file hw_config.c
*  \brief 硬件配置（STM32F407 标准外设库版）
*  \copyright 广州大彩光电科技有限公司（原文件）/ F407 移植版
*
*  与 F1 官方版的差异：
*  1) 删除 Set_System()——F1 的 HSI 倍频时钟配置在 F407 上无效，
*     F407 由启动文件自动调用 SystemInit() 配到 168MHz。
*  2) NVIC_InitTypeDef 在 F4 标准库里多一个 NVIC_IRQChannelCmd 字段。
*  3) 串口引脚初始化放在 hmi_user_uart.c 的 UartInit() 里，
*     本文件只负责 NVIC 优先级。
*/
#include "stm32f4xx_it.h"
#include "hw_config.h"

/*!
*  \brief  中断向量配置（main 最先调用）
*/
void Interrupts_Config(void)
{
    NVIC_InitTypeDef NVIC_InitStructure;

    NVIC_PriorityGroupConfig(NVIC_PriorityGroup_2);   // 2 位抢占 + 2 位子优先级

    // 串口屏 USART1 接收中断（UartInit 里还会再开一次 RXNE）
    NVIC_InitStructure.NVIC_IRQChannel                   = USART1_IRQn;
    NVIC_InitStructure.NVIC_IRQChannelPreemptionPriority = 1;
    NVIC_InitStructure.NVIC_IRQChannelSubPriority        = 0;
    NVIC_InitStructure.NVIC_IRQChannelCmd                = ENABLE;
    NVIC_Init(&NVIC_InitStructure);
}
