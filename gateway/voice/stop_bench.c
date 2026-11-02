#include "tts_uart_port.h"
#include "stm32f4xx.h"
#include "stm32f4xx_gpio.h"
#include "stm32f4xx_rcc.h"
#include "stm32f4xx_usart.h"
#include <stdio.h>

extern int physical_clock_ready(void);
static volatile uint32_t ticks;
static TtsQueue speaker;
static TtsIo uart;
static unsigned tx_pending;
static uint8_t tx_byte;
static uint32_t request_id;

void SysTick_Handler(void) { ++ticks; }
static void text(const char *s) {
    while (*s) {
        while (!(USART1->SR & USART_SR_TXE)) {}
        USART1->DR = (uint8_t)*s++;
    }
}
static void event(const char *kind, unsigned byte) {
    char line[96];
    snprintf(line, sizeof line, "TTS_EVT %s ms=%lu byte=%02x\r\n", kind, (unsigned long)ticks, byte);
    text(line);
}
static int write_byte(void *ctx, uint8_t byte) {
    (void)ctx;
    int result = uart.write_byte(uart.context, byte);
    if (result > 0) { tx_byte = byte; tx_pending = 1; }
    return result;
}
static bool tx_idle(void *ctx) { (void)ctx; return uart.tx_idle(uart.context); }
static void abort_tx(void *ctx) { (void)ctx; uart.abort_tx(uart.context); }
static void report(void) {
    char line[288];
    snprintf(line, sizeof line,
        "TTS_STATE ms=%lu state=%u enabled=%u stopping=%u stop_sent=%u stop_ack=%u query_sent=%u stop_idle=%u stop_failed=%u ack=%lu done=%lu uart_errors=%lu uart_overflow=%lu\r\n",
        (unsigned long)ticks, speaker.state, speaker.enabled, speaker.stopping,
        speaker.stop_sent, speaker.stop_ack, speaker.stop_query_sent, speaker.stop_idle, speaker.stop_failed,
        (unsigned long)speaker.ack_count, (unsigned long)speaker.done_count,
        (unsigned long)tts_uart_errors(), (unsigned long)tts_uart_overflow());
    text(line);
}
static unsigned state_key(void) {
    return (unsigned)speaker.state | ((unsigned)speaker.stopping << 4) |
        ((unsigned)speaker.stop_sent << 5) | ((unsigned)speaker.stop_ack << 6) |
        ((unsigned)speaker.stop_query_sent << 7) | ((unsigned)speaker.stop_idle << 8) |
        ((unsigned)speaker.stop_failed << 9);
}
int main(void) {
    RCC_AHB1PeriphClockCmd(RCC_AHB1Periph_GPIOA, ENABLE);
    RCC_APB2PeriphClockCmd(RCC_APB2Periph_USART1, ENABLE);
    GPIO_InitTypeDef gpio; GPIO_StructInit(&gpio);
    gpio.GPIO_Pin = GPIO_Pin_9 | GPIO_Pin_10; gpio.GPIO_Mode = GPIO_Mode_AF;
    gpio.GPIO_Speed = GPIO_Speed_25MHz; gpio.GPIO_PuPd = GPIO_PuPd_UP;
    GPIO_PinAFConfig(GPIOA, GPIO_PinSource9, GPIO_AF_USART1);
    GPIO_PinAFConfig(GPIOA, GPIO_PinSource10, GPIO_AF_USART1); GPIO_Init(GPIOA, &gpio);
    USART_InitTypeDef console; USART_StructInit(&console); console.USART_BaudRate = 115200;
    USART_Init(USART1, &console); USART_Cmd(USART1, ENABLE);
    if (!physical_clock_ready() || SysTick_Config(SystemCoreClock / 1000u)) {
        text("TTS_STOP_CLOCK_FAIL\r\n"); for (;;) {}
    }
    tts_uart_init(); uart = tts_uart_io();
    tts_init(&speaker, (TtsIo){NULL, write_byte, tx_idle, abort_tx});
    text("TTS_STOP_BENCH_READY C_ONLY MIC_CAN_ESP_DISABLED; I=identity V=volume1 P=phrase S=stop Q=status\r\n");
    unsigned previous = ~0u;
    for (;;) {
        tts_poll(&speaker, ticks);
        if (tx_pending) { tx_pending = 0; event("TX", tx_byte); }
        /* 日志串口可能跨过TTS的TX完成；消费ACK前补记TC，且不多发下一字节。 */
        if (speaker.position == speaker.length) tts_poll(&speaker, ticks);
        for (unsigned i = 0; i < 4; ++i) {
            int byte = tts_uart_receive(); if (byte < 0) break;
            event("RX", (unsigned)byte); tts_receive(&speaker, (uint8_t)byte, ticks);
        }
        if ((tts_uart_errors() || tts_uart_overflow()) && speaker.enabled)
            tts_power_lost(&speaker, ticks);
        unsigned current = state_key();
        if (current != previous) { previous = current; report(); }
        if (!(USART1->SR & USART_SR_RXNE)) continue;
        unsigned c = (uint8_t)USART1->DR;
        if (c == 'I') text("TTS_STOP_BENCH_ID V1 QUERY_AFTER_STOP_ACK NO_MIC_CAN_ESP\r\n");
        else if (c == 'Q') report();
        else if (c == 'V') {
            if (!tts_enable(&speaker, true, true) || !tts_bench_volume(&speaker, 1, ticks)) text("TTS_REJECT_VOLUME\r\n");
        } else if (c == 'P') {
            const uint8_t phrase[] = "停止测试。这是一段用于验证语音停止与空闲状态的非人体测试语音。";
            if (!tts_submit(&speaker, phrase, sizeof phrase - 1, request_id + 1u, ticks)) text("TTS_REJECT_PHRASE\r\n");
            else ++request_id;
        } else if (c == 'S') tts_cancel(&speaker, ticks);
    }
}
