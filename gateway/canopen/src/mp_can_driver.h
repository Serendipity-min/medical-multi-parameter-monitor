#ifndef MP_CAN_DRIVER_H
#define MP_CAN_DRIVER_H
#include "301/CO_driver.h"

typedef struct
{
    unsigned id;
    bool enabled;
    CO_CANmodule_t *module;
} MpCanPort;

void mp_bus_poll(void);
void mp_bus_receive(MpCanFrame *frame);
int mp_bus_transmit(MpCanFrame *frame);
void mp_bus_reset(void);
void mp_bus_set_online(bool online);
uint32_t mp_bus_frames(void);
uint32_t mp_bus_dropped(void);
#ifdef MP_CAN_RX_IRQ
/* 独立联网目标的明确丢弃回执，不能把无ACK帧当成已发送；P4回环不启用。 */
#define MP_CAN_TX_DISCARD (-1)
uint32_t mp_bus_discard_pending(void);
#endif
#endif
