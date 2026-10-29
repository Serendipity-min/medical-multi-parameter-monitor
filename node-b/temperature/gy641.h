#ifndef B_GY641_H
#define B_GY641_H
#include <stdint.h>
#define GY641_FRAME_BYTES 12u
typedef struct {
    uint32_t frames, checksum_errors, header_errors, last_ms;
    uint16_t object_centi, ambient_centi, body_centi;
    uint8_t emissivity, used, present, frame[GY641_FRAME_BYTES], last_frame[GY641_FRAME_BYTES];
} Gy641;
void gy641_init(Gy641 *s);
int gy641_feed(Gy641 *s, uint8_t byte, uint32_t now);
int gy641_object(const Gy641 *s, uint32_t now, uint16_t *centi);
#endif
