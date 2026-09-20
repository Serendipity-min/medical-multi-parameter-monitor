#ifndef MP_ROUTER_H
#define MP_ROUTER_H
#include "../data_model/model.h"
#define MP_LIVE_CAPACITY 16
#define MP_CACHE_CAPACITY 32
typedef struct {MpFrame live[MP_LIVE_CAPACITY],cache[MP_CACHE_CAPACITY];unsigned lh,ln,ch,cn;uint32_t dropped,stored,replayed,last_replay;bool online,ready_for_replay;uint8_t live_credit;} MpRouter;
void mp_router_init(MpRouter *r);
void mp_router_online(MpRouter *r,bool online);
void mp_router_put(MpRouter *r,const MpFrame *f);
bool mp_router_take(MpRouter *r,MpFrame *out,uint32_t now);
void mp_router_ack(MpRouter *r,const MpFrame *f,bool success);
#endif
