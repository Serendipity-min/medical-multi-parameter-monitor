/* 独立C台架入口：不链接ESP/MQTT、配置读取、Flash写入或麦克风驱动。 */
#include "b4_bench.h"
#include "b4_bxcan.h"
#include "stm32f4xx.h"

B4Bench g_b4_bench;
volatile uint32_t b4_bench_milliseconds, b4_bench_init_error;
uint32_t b4_hw_time(void) { return b4_bench_milliseconds; }
void SysTick_Handler(void) { b4_bench_milliseconds++; }
int main(void) {
    SystemCoreClockUpdate();
    if (SysTick_Config(SystemCoreClock / 1000u)) b4_bench_init_error = 1;
    if (!b4_bench_init_error && b4_bench_init(&g_b4_bench, b4_bench_milliseconds)) b4_bench_init_error = 2;
    if (!b4_bench_init_error && b4_hw_init()) b4_bench_init_error = 3;
    /* 初始化失败即停留诊断，不切换网络/时钟/复位路径补救；成功也只运行180秒窗口。 */
    while (1) {
        if (b4_bench_init_error || g_b4_bench.diag.stopped) continue;
        /* RX和协议均使用同一上电tick域，窗口时长另行累计。
         * 主循环先推进协议时钟，再接收ISR队列，避免未来毫秒样本被误丢。 */
        b4_bench_step(&g_b4_bench, b4_bench_milliseconds);
        if (!g_b4_bench.diag.stopped) b4_hw_poll(&g_b4_bench.gateway);
    }
}
