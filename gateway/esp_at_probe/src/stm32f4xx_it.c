#include "main.h"
#ifdef MP_B5_EGRESS_FINAL
#include "b5_policy.h"
#endif

/* 系统节拍仅累加运行时间；不在中断中执行串口解析，避免命令输入阻塞实时性。 */
volatile uint32_t g_uptime_ms;

void SysTick_Handler(void)
{
    g_uptime_ms++;
#ifdef MP_B5_EGRESS_FINAL
    b5_hard_tick();
#endif
}
