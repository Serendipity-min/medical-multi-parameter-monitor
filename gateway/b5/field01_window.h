#ifndef FIVE_FIELD01_WINDOW_H
#define FIVE_FIELD01_WINDOW_H
#include <stdint.h>
#define FIELD01_READY_MS 45000u
#define FIELD01_WINDOW_MS 150000u
#define FIELD01_HARD_MS 210000u
#define FIELD01_AUDIO_AT_MS 35000u
#define FIELD01_AUDIO_END_MS 40000u
#define FIELD01_AUDIO_CHUNKS 64u
#define FIELD01_MIN_SAMPLES ((FIELD01_AUDIO_CHUNKS-1u)*256u+1u)
#define FIELD01_PCM_SAMPLES (FIELD01_MIN_SAMPLES+31u)

static inline uint32_t field01_remaining(uint32_t now,uint32_t t0) {
    uint32_t end=t0?t0+FIELD01_WINDOW_MS:FIELD01_READY_MS;
    if(end>FIELD01_HARD_MS)end=FIELD01_HARD_MS;
    return now<end?end-now:0;
}
#endif
