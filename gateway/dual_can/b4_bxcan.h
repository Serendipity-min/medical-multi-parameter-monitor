#ifndef B4_BXCAN_H
#define B4_BXCAN_H
#include "b4_gateway.h"
typedef struct { uint32_t received, overflow, malformed, high_water, busoff, tx_busy, tx_acked, tx_failed; } B4HwDiag;
extern volatile B4HwDiag b4_hw_diag[2];
int b4_hw_init(void);
/* 等待台架START时只丢弃旧RX，不启动协议或重置控制器。 */
void b4_hw_idle(void);
void b4_hw_poll(B4Gateway *g);
#endif
