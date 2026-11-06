#ifndef B5_EGRESS_H
#define B5_EGRESS_H
#include "b5_policy.h"
#include "gateway_transport.h"
#include "../storage/router.h"
#ifdef MP_FINAL_UNIFIED
#include "../microphone/unified_audio.h"
#endif
typedef struct {
#ifdef MP_FINAL_UNIFIED
    MpFrame inflight[GATEWAY_PUBLISH_SLOTS];uint16_t tickets[GATEWAY_PUBLISH_SLOTS];
#else
    MpFrame inflight;
#endif
    MpFrame publishing;bool pending,deferred;
#ifdef MP_FINAL_UNIFIED
    bool audio_yield;
#endif
    uint32_t q0,q1,failed; } B5Publisher;
/* 固件入口和TLS Host夹具调用同一个推进器；在途帧只在对应PUBACK后交Router成功。 */
#ifdef MP_FINAL_UNIFIED
static inline bool b5_audio_room(const MpRouter *r,uint64_t utc) {
    if(r->ln>=MP_LIVE_CAPACITY-2)return false;
    /* 留出医疗发送余量；不再把尚有空间的半满队列当作永久音频禁令。 */
    for(unsigned i=0;i<r->ln;i++) {
        const MpFrame *f=&r->live[(r->lh+i)%MP_LIVE_CAPACITY];
        if(utc>f->timestamp && utc-f->timestamp>2500u)return false;
    }
    return true;
}
#endif
static inline int b5_egress_step(MpRouter *r,B5Publisher *s,bool allow_new) {
#ifdef MP_FINAL_UNIFIED
    int progress=gateway_mqtt_progress();
    if(b5_network_stopped())return 1;
    if(progress==GW_FAILED){
        for(unsigned i=0;i<GATEWAY_PUBLISH_SLOTS;i++)if(s->tickets[i]){mp_router_ack(r,&s->inflight[i],false);s->tickets[i]=0;}
        s->pending=false;s->failed++;return 0;
    }
    for(unsigned i=0;i<GATEWAY_PUBLISH_SLOTS;i++)if(s->tickets[i] && gateway_mqtt_ticket_result(s->tickets[i])==GW_COMPLETE){
        mp_router_ack(r,&s->inflight[i],true);s->tickets[i]=0;
        if(s->inflight[i].rate && !s->inflight[i].replay)s->q0++;else s->q1++;
    }
    s->pending=false;for(unsigned i=0;i<GATEWAY_PUBLISH_SLOTS;i++)if(s->tickets[i])s->pending=true;
    if(!allow_new)return 1;
    uint64_t utc=gateway_epoch_milliseconds();
    bool medical_due=false;
    for(unsigned i=0;i<GATEWAY_PUBLISH_SLOTS;i++)if(s->tickets[i] && utc>s->inflight[i].timestamp && utc-s->inflight[i].timestamp>2500u)medical_due=true;
    if(s->deferred && utc>s->publishing.timestamp && utc-s->publishing.timestamp>2500u)medical_due=true;
    bool q1_blocked=s->deferred && (!s->publishing.rate || s->publishing.replay) && gateway_mqtt_slots_full();
    bool deferred_ready=s->deferred && !q1_blocked;
    if(!r->ln && !deferred_ready)s->audio_yield=false;
    bool room=b5_audio_room(r,utc),audio_due=unified_audio_send_due();
    unified_audio_wait((deferred_ready || medical_due || !room?UA_BLOCK_MEDICAL:0u)|
        (s->audio_yield?UA_BLOCK_YIELD:0u)|(!audio_due?UA_BLOCK_GAP:0u));
    if(!deferred_ready && !s->audio_yield && !medical_due && room && audio_due){
        if(unified_audio_step(true)){s->audio_yield=true;return 1;}
    }
    int admission=gateway_mqtt_admit();
    if(admission==GW_FAILED){s->failed++;return 0;}if(admission==GW_DEFERRED)return 1;
    if(s->deferred || mp_router_take_egress(r,&s->publishing,g_uptime_ms,utc,gateway_mqtt_slots_full())){
        if(!s->deferred && !b5_prepare_publish(&s->publishing,utc))return 1;
        int result=gateway_mqtt_begin(&s->publishing);s->deferred=result==GW_DEFERRED;
        if(s->deferred || b5_network_stopped())return 1;
        if(result==GW_PENDING){unsigned i=0;while(i<GATEWAY_PUBLISH_SLOTS && s->tickets[i])i++;if(i==GATEWAY_PUBLISH_SLOTS){s->failed++;return 0;}s->tickets[i]=gateway_mqtt_ticket();s->inflight[i]=s->publishing;s->pending=true;s->audio_yield=false;}
        else{mp_router_ack(r,&s->publishing,result==GW_COMPLETE);if(result==GW_FAILED){s->failed++;return 0;}s->q0++;s->audio_yield=false;}
    }
    return 1;
#else
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
    }
#ifndef MP_FINAL_UNIFIED
    else if(!s->pending && gateway_mqtt_progress()==GW_FAILED){s->failed++;return 0;}
#endif
    /* 统一入口每轮已推进接收；空闲时保留AT空档交给低优先级音频。 */
    return 1;
#endif
}
#endif
