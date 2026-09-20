#ifndef MP_ADAPTER_H
#define MP_ADAPTER_H
#include "mp_stack.h"
#include "../../storage/router.h"
typedef struct {uint32_t tick[2][2],anchor[2],boot[2],seq[3][MP_STREAMS],quality[2],fault[2],status_tick;bool online[2];MpFrame waves[3];} MpAdapter;
void mp_adapter_init(MpAdapter *a);
void mp_adapter_poll(MpAdapter *a,MpStack *s,MpRouter *r);
#endif
