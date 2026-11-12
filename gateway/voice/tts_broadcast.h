#ifndef MPM_TTS_BROADCAST_H
#define MPM_TTS_BROADCAST_H

#include "tts_queue.h"

#define TTS_BROADCAST_TOPIC "mpm/v1/GW-C-001/voice/broadcast"

void tts_broadcast_init(TtsIo io);
bool tts_broadcast_offer(const uint8_t *frame, size_t length, uint64_t utc_ms);
void tts_broadcast_poll(uint32_t now);
void tts_broadcast_stop(uint32_t now);

#endif
