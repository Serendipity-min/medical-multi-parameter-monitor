/* 裸机 assert 的终止策略：固定诊断、有界 UART、关中断停机；保留全部上游 assert。 */
#include <stdint.h>

#define ASSERT_TX_SPIN_LIMIT 8192U
volatile uint32_t gateway_assert_latched;

#ifdef GATEWAY_ASSERT_HOST_TEST
/* 普通功能测试仅替换寄存器动作和最终停机，不能带入生产配置或 OS signal。 */
extern int gateway_assert_tx_ready(void);
extern void gateway_assert_tx_write(unsigned char value);
extern void gateway_assert_disable_interrupts(void);
extern void gateway_assert_halt(void) __attribute__((noreturn));
#else
#include "stm32f4xx.h"
static int gateway_assert_tx_ready(void)
{
    return (USART1->SR & USART_SR_TXE) != 0;
}
static void gateway_assert_tx_write(unsigned char value)
{
    USART1->DR = value;
}
static void gateway_assert_disable_interrupts(void)
{
    __disable_irq();
}
static void gateway_assert_halt(void) __attribute__((noreturn));
static void gateway_assert_halt(void)
{
    /* 停止主循环采样/网络活动；不擅自复位、写 Flash 或尝试从断言返回。 */
    for (;;)
        __WFI();
}
#endif

void __assert_func(const char *file, int line, const char *function, const char *expression)
    __attribute__((noreturn));
void __assert_func(const char *file, int line, const char *function, const char *expression)
{
    (void)file;
    (void)line;
    (void)function;
    (void)expression;
    gateway_assert_latched = 1;
    gateway_assert_disable_interrupts();
    /* 不使用 printf/_write/console，避免分配、信号桩、重入 CAN 或无限 UART 等待。
       SysTick 已停，只用固定次数约束；串口不可用时跳过诊断并进入同一停机终点。 */
    const unsigned char *message = (const unsigned char *)"GW ASSERT_FATAL\r\n";
    while (*message)
    {
        uint32_t spins = ASSERT_TX_SPIN_LIMIT;
        while (!gateway_assert_tx_ready() && --spins)
            ;
        if (!spins)
            break;
        gateway_assert_tx_write(*message++);
    }
    gateway_assert_halt();
}
