#include "stm32f4xx.h"

/*
 * 此最小控制台固定运行在复位后即可用的 16 MHz HSI 上。
 * 原厂模板默认按 25 MHz 外部晶振配置 PLL，而本开发板实物为 8 MHz；
 * 使用 HSI 可避免外部时钟参数不匹配导致首个可烧录固件无法启动。
 */
uint32_t SystemCoreClock = HSI_VALUE;

void SystemInit(void)
{
#if (__FPU_PRESENT == 1) && (__FPU_USED == 1)
  /* 仅在硬浮点 ABI 生效时开放协处理器访问，避免以后加入浮点代码触发 UsageFault。 */
  SCB->CPACR |= (3UL << (10U * 2U)) | (3UL << (11U * 2U));
  __DSB();
  __ISB();
#endif

  /* 复位态默认就是 HSI；显式记录频率，供 SysTick 与 USART 分频计算使用。 */
  SystemCoreClock = HSI_VALUE;
}

void SystemCoreClockUpdate(void)
{
  /* 本固件不在运行期切换时钟，保持该函数与 CMSIS 调用约定兼容。 */
  SystemCoreClock = HSI_VALUE;
}
