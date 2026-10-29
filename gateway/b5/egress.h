#ifndef B5_EGRESS_H
#define B5_EGRESS_H
#include "b5_policy.h"
#include "gateway_transport.h"
#include "../storage/router.h"
typedef struct { MpFrame inflight,publishing;bool pending,deferred;uint32_t q0,q1,failed; } B5Publisher;
/* 固件入口和TLS Host夹具调用同一个推进器；在途帧只在对应PUBACK后交Router成功。 */
static inline int b5_egress_step(MpRouter *r,B5Publisher *s,bool allow_new) {
    if(s->pending) {
        int result=gateway_mqtt_progress();
        if(b5_network_stopped())return 1;
        if(result==GW_FAILED){mp_router_ack(r,&s->inflight,false);s->pending=false;s->failed++;return 0;}
        if(result==GW_COMPLETE){mp_router_ack(r,&s->inflight,true);s->pending=false;s->q1++;}
    }else if(gateway_mqtt_progress()==GW_FAILED){s->failed++;return 0;}
    if(!allow_new)return 1;
    int admission=gateway_mqtt_admit();
    if(admission==GW_FAILED){s->failed++;return 0;}
    if(admission==GW_DEFERRED)return 1;
    uint64_t utc=gateway_epoch_milliseconds();
    if(s->deferred || mp_router_take_egress(r,&s->publishing,g_uptime_ms,utc,s->pending)) {
        if(!s->deferred && !b5_prepare_publish(&s->publishing,utc))return 1;
        int result=gateway_mqtt_begin(&s->publishing);
        s->deferred=result==GW_DEFERRED;
        if(s->deferred)return 1;
        if(b5_network_stopped())return 1;
        if(result==GW_PENDING){s->inflight=s->publishing;s->pending=true;}
        else {mp_router_ack(r,&s->publishing,result==GW_COMPLETE);
            if(result==GW_FAILED){s->failed++;return 0;}s->q0++;}
    } else if(!s->pending && gateway_mqtt_progress()==GW_FAILED){s->failed++;return 0;}
    return 1;
}
#endif
