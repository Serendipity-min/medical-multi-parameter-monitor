/* 独立C台架入口：不链接ESP/MQTT、配置读取、Flash写入或麦克风驱动。 */
#include "b4_bench.h"
#include "b4_bxcan.h"
#include "stm32f4xx.h"
#if defined(B4_CAPTURE_SERIAL)
#include "b4_capture.h"
extern volatile uint32_t b4_bench_milliseconds;
static void diagnostic(unsigned id,uint32_t a,uint32_t b,uint32_t flags) {
    uint8_t data[8];
    for (unsigned i=0;i<4;i++) { data[i]=(uint8_t)(a>>(8*i)); data[i+4]=(uint8_t)(b>>(8*i)); }
    b4_capture_emit(B4_CAP_DIAG,1,id,8,data,b4_bench_milliseconds,flags);
}
#endif

B4Bench g_b4_bench;
volatile uint32_t b4_bench_milliseconds, b4_bench_init_error;
uint32_t b4_hw_time(void) { return b4_bench_milliseconds; }
void SysTick_Handler(void) { b4_bench_milliseconds++; }
int main(void) {
    SystemCoreClockUpdate();
#if defined(B4_CAPTURE_SERIAL)
    b4_capture_init(); b4_capture_uart_init();
#endif
    if (SysTick_Config(SystemCoreClock / 1000u)) b4_bench_init_error = 1;
#if !defined(B4_CAPTURE_SERIAL)
    if (!b4_bench_init_error && b4_bench_init(&g_b4_bench, b4_bench_milliseconds)) b4_bench_init_error = 2;
#endif
    if (!b4_bench_init_error && b4_hw_init()) b4_bench_init_error = 3;
#if defined(B4_CAPTURE_SERIAL)
    uint8_t identity[8]={'B','4','C','4',0,0,0,0};
    uint32_t reset_cause=RCC->CSR;
    for (unsigned i=0;i<4;i++) identity[i+4]=(uint8_t)(reset_cause>>(8*i));
    b4_capture_emit(B4_CAP_BOOT,1,4,8,identity,b4_bench_milliseconds,b4_bench_init_error);
    uint32_t diag_at=0; unsigned stop_recorded=0, armed=0;
#endif
    /* 初始化失败即停留诊断，不切换网络/时钟/复位路径补救；成功也只运行180秒窗口。 */
    while (1) {
#if defined(B4_CAPTURE_SERIAL)
        b4_capture_drain(64);
        if (!armed && !g_b4_bench.diag.stopped && !b4_bench_init_error) {
            b4_hw_idle();
            for (unsigned budget=0;budget<8;budget++) {
                int byte=b4_capture_uart_get(); if (byte<0) break;
                if (b4_capture_arm_byte((uint8_t)byte)) {
                    uint8_t data[8]; uint32_t start=b4_bench_milliseconds;
                    if (b4_bench_init(&g_b4_bench,start)) b4_bench_init_error=2;
                    for (unsigned i=0;i<4;i++) { data[i]=(uint8_t)(start>>(8*i));
                        data[i+4]=(uint8_t)(b4_hw_diag[1].received>>(8*i)); }
                    b4_capture_emit(B4_CAP_START,1,0,8,data,start,b4_bench_init_error);
                    armed=1; break;
                }
            }
            /* 安装后最多等待5分钟转接调试器；超时停窗，不自动复位或重新武装。 */
            if (!armed && b4_bench_milliseconds>=300000u) {
                g_b4_bench.diag.stopped=1; b4_bench_init_error=0x100u;
            }
        }
        if ((uint32_t)(b4_bench_milliseconds-diag_at)>=1000u && !g_b4_bench.diag.stopped) {
            diag_at=b4_bench_milliseconds;
            diagnostic(0,CAN1->ESR,b4_hw_diag[0].received,b4_hw_diag[0].overflow);
            diagnostic(1,CAN2->ESR,b4_hw_diag[1].received,b4_hw_diag[1].overflow);
            diagnostic(2,g_b4_capture.dropped,g_b4_capture.high_water,b4_bench_init_error);
            diagnostic(3,g_b4_bench.diag.records,g_b4_bench.gateway.wave_gaps,g_b4_bench.diag.overwritten);
            diagnostic(4,SCB->VTOR,SCB->CFSR,SCB->HFSR);
        }
        if (g_b4_bench.diag.stopped && !stop_recorded) {
            uint8_t done[8];
            for (unsigned i=0;i<4;i++) { done[i]=(uint8_t)(g_b4_bench.diag.elapsed_ms>>(8*i));
                done[i+4]=(uint8_t)(g_b4_capture.dropped>>(8*i)); }
            b4_capture_emit(B4_CAP_STOP,1,0,8,done,b4_bench_milliseconds,b4_bench_init_error);
            stop_recorded=1;
        }
#endif
        if (b4_bench_init_error || g_b4_bench.diag.stopped) continue;
#if defined(B4_CAPTURE_SERIAL)
        if (!armed) continue;
#endif
        /* RX和协议均使用同一上电tick域，窗口时长另行累计。
         * 主循环先推进协议时钟，再接收ISR队列，避免未来毫秒样本被误丢。 */
        b4_bench_step(&g_b4_bench, b4_bench_milliseconds);
        if (!g_b4_bench.diag.stopped) b4_hw_poll(&g_b4_bench.gateway);
    }
}
