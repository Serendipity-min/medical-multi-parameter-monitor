#include "mic_format.h"

int32_t mic_sample24(uint16_t high, uint16_t low) {
    uint32_t v = ((uint32_t)high << 8) | (low >> 8);
    return (v & 0x800000u) ? (int32_t)v - 16777216 : (int32_t)v;
}

int16_t mic_pcm16(uint16_t high, uint16_t low) {
    int32_t v = mic_sample24(high, low);
    /* 保留高16位，不增益、不归一化；负数显式向负无穷取整。 */
    return (int16_t)(v >= 0 ? v / 256 : -((-v + 255) / 256));
}

uint32_t mic_crc32_update(uint32_t crc, const void *data, unsigned bytes) {
    const uint8_t *p = data;
    for (unsigned i = 0; i < bytes; ++i) {
        crc ^= p[i];
        for (unsigned b = 0; b < 8; ++b)
            crc = (crc >> 1) ^ ((crc & 1u) ? 0xedb88320u : 0u);
    }
    return crc;
}
uint32_t mic_crc32(const void *data, unsigned bytes) {
    return mic_crc32_update(0xffffffffu, data, bytes) ^ 0xffffffffu;
}
