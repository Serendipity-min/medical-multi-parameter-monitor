#ifndef MPM_TTS_UART_PORT_H
#define MPM_TTS_UART_PORT_H
#include "tts_queue.h"

/* 普通H3不启用USART2；离线或独立云语音候选必须显式选择。 */
#if defined(MP_TTS_BENCH) || defined(MP_CLOUD_VOICE)
void tts_uart_init(void);
TtsIo tts_uart_io(void);
int tts_uart_receive(void);
uint32_t tts_uart_errors(void);
uint32_t tts_uart_overflow(void);
#endif
#endif
