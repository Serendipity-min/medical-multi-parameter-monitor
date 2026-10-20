#ifndef MP_HOST_RCC_H
#define MP_HOST_RCC_H
#include "stm32f4xx.h"
/* 固定8MHz模拟时钟只用于编译/运行生产驱动的Host边界测试。 */
typedef struct {uint32_t PCLK1_Frequency;} RCC_ClocksTypeDef;
#define RCC_AHB1Periph_GPIOA 1u
#define RCC_APB1Periph_CAN1 1u
#define ENABLE 1
static inline void RCC_GetClocksFreq(RCC_ClocksTypeDef *c) {c->PCLK1_Frequency=8000000;}
static inline void RCC_AHB1PeriphClockCmd(uint32_t p,int e) {(void)p;(void)e;}
static inline void RCC_APB1PeriphClockCmd(uint32_t p,int e) {(void)p;(void)e;}
#endif
