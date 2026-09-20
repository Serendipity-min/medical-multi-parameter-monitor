#ifndef MP_CAN_DRIVER_H
#define MP_CAN_DRIVER_H
#include "301/CO_driver.h"
typedef struct { unsigned id; bool enabled; CO_CANmodule_t *module; } MpCanPort;
void mp_bus_poll(void);
void mp_bus_receive(MpCanFrame *frame);
int mp_bus_transmit(MpCanFrame *frame);
void mp_bus_reset(void);
void mp_bus_set_online(bool online);
uint32_t mp_bus_frames(void);
uint32_t mp_bus_dropped(void);
#endif
