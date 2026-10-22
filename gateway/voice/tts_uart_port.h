#ifndef MPM_TTS_UART_PORT_H
#define MPM_TTS_UART_PORT_H
#include "tts_queue.h"

/* 普通H3构建不包含本文件；只有独立离线台架才显式启用USART2。 */
#ifdef MP_TTS_BENCH
void tts_uart_init(void);
TtsIo tts_uart_io(void);
int tts_uart_receive(void);
uint32_t tts_uart_errors(void);
uint32_t tts_uart_overflow(void);
#endif
#endif
