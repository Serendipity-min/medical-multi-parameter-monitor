#ifndef MPM_CLOUD_VOICE_H
#define MPM_CLOUD_VOICE_H
#include "p6v1.h"
#include "tts_queue.h"
typedef struct {
    uint32_t received, accepted, rejected[VOICE_BUSY+1], suback, subfail;
    uint32_t uart_rx, uart_errors, uart_overflow, stage, armed_tick;
    uint32_t poll_calls, max_poll_gap_ms, last_poll_tick;
    uint32_t accepted_tick, last_status, ack_tick, done_tick;
    uint8_t turn[16], digest[16];
} CloudVoiceMetrics;
extern CloudVoiceMetrics cloud_voice_metrics;
extern TtsQueue cloud_voice_queue;
void cloud_voice_init(void);
void cloud_voice_poll(void);
void cloud_voice_session(bool ready);
void cloud_voice_receive(const char *,size_t,unsigned,bool,const uint8_t *,size_t);
#endif
