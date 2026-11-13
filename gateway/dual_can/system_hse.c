#include "stm32f4xx.h"
#include "hse_clock.h"

/* 仅替代独立H3 IRQ目标的HSI模板；P4和旧轮询目标仍链接原文件。 */
uint32_t SystemCoreClock=HSI_VALUE;
static int clock_ready;
int physical_clock_ready(void) {return clock_ready;}

void SystemInit(void) {
#if (__FPU_PRESENT == 1) && (__FPU_USED == 1)
    SCB->CPACR|=(3UL<<20)|(3UL<<22);__DSB();__ISB();
#endif
    /* ROM GO也由启动文件进入此初始化；切换发生在UART、SysTick、CAN初始化之前。 */
    clock_ready=physical_hse_start(&RCC->CR,&RCC->CFGR,0,1000000u);
    SystemCoreClock=clock_ready?8000000u:HSI_VALUE;
}

void SystemCoreClockUpdate(void) {
    /* 此目标不启用PLL及总线分频；硬件SWS必须真实指向已核验的外部晶体。 */
    SystemCoreClock=(RCC->CFGR&12u)==4u?8000000u:HSI_VALUE;
}
