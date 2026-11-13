#ifndef MPM_TTS_QUEUE_H
#define MPM_TTS_QUEUE_H
#include "tts_frame.h"
#include <stdbool.h>

typedef enum { TTS_DISABLED, TTS_IDLE, TTS_SENDING, TTS_ACCEPTED, TTS_PLAYING,
               TTS_DONE, TTS_ERROR, TTS_TIMEOUT } TtsState;
typedef struct {
    void *context;
    /* 单次尝试最多写一个字节；busy返回0，故障返回-1，严禁内部等待TXE。 */
    int (*write_byte)(void *, uint8_t);
    bool (*tx_idle)(void *);
    void (*abort_tx)(void *);
} TtsIo;
typedef struct {
    TtsIo io;
    TtsState state;
    uint8_t frame[TTS_FRAME_MAX];
    size_t length, position;
    uint32_t at, last_submit, last_id, tx_done_count, ack_count, done_count, errors;
    bool enabled, power_good, protocol_confirmed, submitted, tx_done, admin_command;
    bool stopping, stop_sent, stop_ack, stop_idle, stop_failed;
    bool stop_query_started, stop_query_sent;
} TtsQueue;

/* 全部队列方法只由主循环调用；ISR只操作独立UART接收队列。 */
void tts_init(TtsQueue *, TtsIo);
bool tts_enable(TtsQueue *, bool power_good, bool protocol_confirmed);
bool tts_ready(const TtsQueue *, uint32_t now);
bool tts_submit(TtsQueue *, const uint8_t *, size_t, uint32_t id, uint32_t now);
bool tts_bench_volume(TtsQueue *, unsigned volume, uint32_t now);
void tts_poll(TtsQueue *, uint32_t now);
void tts_receive(TtsQueue *, uint8_t status, uint32_t now);
void tts_cancel(TtsQueue *, uint32_t now);
void tts_power_lost(TtsQueue *, uint32_t now);
#endif
