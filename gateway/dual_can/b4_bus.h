#ifndef B4_BUS_H
#define B4_BUS_H
#include "mp_od.h"
/* bus是物理接口身份，node是全网业务身份，两者绝不能互相替代。 */
typedef struct { unsigned node, bus; bool enabled; CO_CANmodule_t *module; } B4Port;
typedef struct { uint32_t queued, sent, overflow, offline_drop, high_water; } B4BusDiag;
extern B4BusDiag b4_bus_diag[2];
void b4_bus_reset(void);
void b4_bus_poll(void);
void b4_bus_online(unsigned bus, bool online);
void b4_bus_receive(unsigned bus, MpCanFrame *frame);
int b4_bus_transmit(unsigned bus, const MpCanFrame *frame);
#endif
