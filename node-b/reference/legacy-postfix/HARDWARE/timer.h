#ifndef __TIMER_H
#define __TIMER_H

#include "stm32f4xx.h"

void     TimeBase_Init(void);
uint32_t TimeBase_GetMs(void);

#endif
