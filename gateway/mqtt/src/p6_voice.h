#ifndef P6_VOICE_H
#define P6_VOICE_H
#include "p6_config.h"
#include <stddef.h>
#include <stdint.h>
/* writer 必须非阻塞，最多消费本次给定预算；本轮只注入 Host 回调，不选择实际 UART。 */
typedef int (*P6Writer)(void *context, const uint8_t *data, size_t size);
typedef enum { TW_OFF, TW_BOOT, TW_IDLE, TW_SEND, TW_ACCEPT, TW_PLAY, TW_FAULT } TwState;
typedef struct {
    uint8_t frame[P6_TEXT_MAX + 5U];
    size_t size, offset;
    uint32_t since, accepted, completed, errors;
    uint8_t last_status;
    TwState state;
    P6Writer writer;
    void *context;
} TwTts;
int p6_utf8_valid(const uint8_t *data, size_t size);
void tw_tts_init(TwTts *tts, P6Writer writer, void *context, uint32_t now);
int tw_tts_queue(TwTts *tts, const uint8_t *text, size_t size, uint32_t now);
void tw_tts_poll(TwTts *tts, uint32_t now);
void tw_tts_feedback(TwTts *tts, uint8_t status, uint32_t now);
void p6_voice_bind(P6Writer writer, void *context, uint32_t now);
int p6_voice_bound(void);
int p6_voice_receive(const char *topic, size_t topic_size, const uint8_t *payload,
                     size_t payload_size, int qos, int retain, uint64_t now_ms, uint32_t tick);
void p6_voice_poll(uint32_t now);
void p6_voice_feedback(uint8_t status, uint32_t now);
const TwTts *p6_voice_driver(void);
uint32_t p6_voice_rejected(void);
#endif
