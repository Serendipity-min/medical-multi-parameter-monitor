#ifndef MP_MIC_FORMAT_H
#define MP_MIC_FORMAT_H
#include <stdint.h>
#define MIC_RATE 16000u
#define MIC_BLOCK_FRAMES 160u
#define MIC_BLOCK_WORDS (MIC_BLOCK_FRAMES * 4u)
#define MIC_SAMPLES (MIC_RATE * 2u)
int32_t mic_sample24(uint16_t high, uint16_t low);
int16_t mic_pcm16(uint16_t high, uint16_t low);
uint32_t mic_crc32(const void *data, unsigned bytes);
uint32_t mic_crc32_update(uint32_t crc, const void *data, unsigned bytes);
#endif
