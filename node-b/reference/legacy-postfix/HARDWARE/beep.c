/**
 * @file    beep.c
 * @brief   蜂鸣器驱动（PF8 = TIM13_CH1 PWM，约 1kHz，报警急促连响）
 */
#include "beep.h"
#include "stm32f4xx.h"

static uint16_t s_arr = 999;          // 重装值固定(1MHz 计数 -> 约 1kHz)

void BEEP_Init(void)
{
    GPIO_InitTypeDef  GPIO_InitStructure;
    TIM_TimeBaseInitTypeDef TIM_TimeBaseInitStruct;
    TIM_OCInitTypeDef TIM_OCInitStruct;

    RCC_AHB1PeriphClockCmd(RCC_AHB1Periph_GPIOF, ENABLE);
    RCC_APB1PeriphClockCmd(RCC_APB1Periph_TIM13, ENABLE);

    GPIO_InitStructure.GPIO_Pin = GPIO_Pin_8;
    GPIO_InitStructure.GPIO_Mode = GPIO_Mode_AF;
    GPIO_InitStructure.GPIO_Speed = GPIO_Speed_100MHz;
    GPIO_InitStructure.GPIO_PuPd = GPIO_PuPd_DOWN;
    GPIO_Init(GPIOF, &GPIO_InitStructure);

    GPIO_PinAFConfig(GPIOF, GPIO_PinSource8, GPIO_AF_TIM13);

    // 1MHz 计数: 84MHz / 84，周期固定约 1kHz
    TIM_TimeBaseInitStruct.TIM_Prescaler = 84 - 1;   // 预分频 84：84MHz → 1MHz 计数频率
    TIM_TimeBaseInitStruct.TIM_Period = s_arr;       // 计数到 999 溢出 → 1MHz/1000 = 1kHz PWM
    TIM_TimeBaseInitStruct.TIM_CounterMode = TIM_CounterMode_Up;
    TIM_TimeBaseInitStruct.TIM_ClockDivision = 0;
    TIM_TimeBaseInitStruct.TIM_RepetitionCounter = 0;
    TIM_TimeBaseInit(TIM13, &TIM_TimeBaseInitStruct);

    TIM_OCStructInit(&TIM_OCInitStruct);
    TIM_OCInitStruct.TIM_OCMode = TIM_OCMode_PWM1;      // PWM1 模式：CNT<CCR 时输出有效电平
    TIM_OCInitStruct.TIM_OCPolarity = TIM_OCPolarity_High;
    TIM_OCInitStruct.TIM_OutputState = TIM_OutputState_Enable;
    TIM_OCInitStruct.TIM_Pulse = 0;       // 上电静音，报警时再开（CCR=0 占空比为 0）
    TIM_OC1Init(TIM13, &TIM_OCInitStruct);

    TIM_OC1PreloadConfig(TIM13, TIM_OCPreload_Enable);

    TIM_Cmd(TIM13, ENABLE);
}

void BEEP_On(void)
{
    // 比较值设为周期的一半 → 50% 占空比，蜂鸣器鸣响
    TIM_SetCompare1(TIM13, (uint16_t)((s_arr + 1) / 2));
}

void BEEP_Off(void)
{
    // 比较值清零 → 占空比 0，停止鸣响
    TIM_SetCompare1(TIM13, 0);
}
