/* 完全离线的C单板候选：不链接CAN、ESP、MQTT、Flash配置或任何网络密钥。 */
#include "tts_uart_port.h"
#include "stm32f4xx.h"
#include "stm32f4xx_gpio.h"
#include "stm32f4xx_rcc.h"

static volatile uint32_t ticks;
/* 供运行中只读定位；这些状态均不等同人工可闻结果。 */
TtsQueue voice_bench;
volatile uint32_t voice_bench_stage, voice_bench_rx, voice_bench_last_status;
volatile uint32_t voice_bench_uart_errors, voice_bench_overflow, voice_bench_triggers;
void SysTick_Handler(void) { ticks++; }

int main(void)
{
    tts_uart_init(); tts_init(&voice_bench, tts_uart_io());
    GPIO_InitTypeDef gpio; GPIO_StructInit(&gpio);
    gpio.GPIO_Pin = GPIO_Pin_0; gpio.GPIO_Mode = GPIO_Mode_IN; gpio.GPIO_PuPd = GPIO_PuPd_DOWN;
    GPIO_Init(GPIOA, &gpio); SysTick_Config(SystemCoreClock / 1000);
    uint32_t changed = 0, settled = 0;
    bool raw_previous = true, stable = true, released = false;
    const uint8_t phrase[] = "语音模块测试完成";
    for (;;) {
        uint32_t now = ticks;
        tts_poll(&voice_bench, now);
        /* 每轮最多消费4个状态字节，接收洪泛也不能形成无界主循环。 */
        for (unsigned i = 0; i < 4; i++) {
            int c = tts_uart_receive(); if (c < 0) break;
            voice_bench_rx++; voice_bench_last_status = (uint32_t)c;
            tts_receive(&voice_bench, (uint8_t)c, now);
        }
        voice_bench_uart_errors = tts_uart_errors(); voice_bench_overflow = tts_uart_overflow();
        if ((voice_bench_uart_errors || voice_bench_overflow) && voice_bench_stage < 90) {
            tts_power_lost(&voice_bench, now); voice_bench_stage = 90;
        }
        bool raw = GPIO_ReadInputDataBit(GPIOA, GPIO_Pin_0) != 0;
        if (raw != raw_previous) { raw_previous = raw; changed = now; }
        if (raw != stable && (uint32_t)(now - changed) >= 30) {
            stable = raw;
            if (!stable) released = true;
            else if (released && now >= 2000) {
                released = false;
                if (voice_bench_stage == 0 && tts_enable(&voice_bench, true, true) &&
                    tts_bench_volume(&voice_bench, 1, now)) {
                    voice_bench_triggers++; voice_bench_stage = 1;
                } else if (voice_bench_stage < 90) {
                    tts_cancel(&voice_bench, now); voice_bench_stage = 90;
                }
            }
        }
        if (voice_bench_stage == 1 && voice_bench.state == TTS_DONE) { settled = now; voice_bench_stage = 2; }
        if (voice_bench_stage == 2 && (uint32_t)(now - settled) >= 100) {
            if (tts_submit(&voice_bench, phrase, sizeof(phrase) - 1, 1, now)) voice_bench_stage = 3;
            else voice_bench_stage = 90;
        }
        if (voice_bench_stage == 3 && voice_bench.state == TTS_DONE) {
            /* 单次短句后关闭，不开机自动播放、不自动重试，下一轮需正常重启。 */
            voice_bench.enabled = false; voice_bench_stage = 4;
        }
        if (voice_bench.state == TTS_ERROR || voice_bench.state == TTS_TIMEOUT) voice_bench_stage = 90;
    }
}
