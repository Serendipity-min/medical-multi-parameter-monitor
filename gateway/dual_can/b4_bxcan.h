#ifndef B4_BXCAN_H
#define B4_BXCAN_H
#include "b4_gateway.h"
typedef struct { uint32_t received, overflow, malformed, high_water, busoff, tx_busy, tx_acked, tx_failed; } B4HwDiag;
extern volatile B4HwDiag b4_hw_diag[2];
int b4_hw_init(void);
void b4_hw_poll(B4Gateway *g);
#endif
