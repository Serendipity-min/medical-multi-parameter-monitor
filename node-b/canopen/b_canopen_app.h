#ifndef B_CANOPEN_APP_H
#define B_CANOPEN_APP_H
#include <stdint.h>
#define B_CAN_NODE_ID 2u
#define B_CAN_BITRATE 500u
/* 主循环投递已处理帧，不从ADC ISR发送CAN，不改变BIO引擎状态。 */
void CanOpen_Init(void);
void CanOpen_Task(uint32_t now_ms);
void BCan_Sample(uint32_t tick, uint32_t sequence, uint8_t flags);
void BCan_Interrupt(void);
typedef struct {
    uint32_t offered, enqueued, sent_ecg, sent_resp, overflow, expired, comm_reset, app_reset_rejected;
    uint32_t high_water, error, discontinuities;
} BCanDiag;
extern BCanDiag g_b_can;
#endif
