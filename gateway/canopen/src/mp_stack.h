#ifndef MP_STACK_H
#define MP_STACK_H
#include "mp_od.h"
#include "mp_can_driver.h"
typedef struct { MpOD od; CO_config_t config; CO_t *co; MpCanPort port; uint32_t boot, tick; } MpNode;
typedef struct { MpNode nodes[3]; uint32_t milliseconds, epoch, allocated, emcy[2], resets[3]; } MpStack;
int mp_stack_init(MpStack *s, uint32_t epoch);
void mp_stack_close(MpStack *s);
void mp_stack_tick(MpStack *s);
void mp_stack_enable(MpStack *s,unsigned node,bool enabled);
int mp_stack_restart(MpStack *s,unsigned node);
int mp_stack_online(MpStack *s,unsigned node);
void mp_stack_nmt(MpStack *s,unsigned node,CO_NMT_command_t command);
#endif
