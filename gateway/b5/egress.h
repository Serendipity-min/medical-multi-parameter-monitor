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
    MpFrame inflight[GATEWAY_TELEMETRY_SLOTS];uint16_t tickets[GATEWAY_TELEMETRY_SLOTS];
#else
    MpFrame inflight;
#endif
    MpFrame publishing;bool pending,deferred;
#ifdef MP_FINAL_UNIFIED
#ifndef MP_AUDIO_DISABLED
    bool audio_yield;
#endif
#endif
    uint32_t q0,q1,failed; } B5Publisher;
/* 固件入口和TLS Host夹具调用同一个推进器；在途帧只在对应PUBACK后交Router成功。 */
#ifdef MP_FINAL_UNIFIED
#ifndef MP_AUDIO_DISABLED
static inline bool b5_audio_room(const MpRouter *r,uint64_t utc) {
    if(r->ln>=MP_LIVE_CAPACITY-2)return false;
    /* 留出医疗发送余量；不再把尚有空间的半满队列当作永久音频禁令。 */
    for(unsigned i=0;i<r->ln;i++) {
        const MpFrame *f=&r->live[(r->lh+i)%MP_LIVE_CAPACITY];
        if(mp_realtime_yield_due(utc,f->timestamp,false))return false;
    }
    return true;
}
#endif
#endif
#ifdef MP_FIVE_FIELD01
static void field01_published(const MpFrame *frame);
static void field01_admission(void);
#endif
static inline int b5_egress_step(MpRouter *r,B5Publisher *s,bool allow_new) {
#ifdef MP_FINAL_UNIFIED
    int progress=gateway_mqtt_progress();
    if(b5_network_stopped())return 1;
    if(progress==GW_FAILED){
        for(unsigned i=0;i<GATEWAY_TELEMETRY_SLOTS;i++)if(s->tickets[i]){mp_router_ack(r,&s->inflight[i],false);s->tickets[i]=0;}
        s->pending=false;s->failed++;return 0;
    }
    for(unsigned i=0;i<GATEWAY_TELEMETRY_SLOTS;i++)if(s->tickets[i] && gateway_mqtt_ticket_result(s->tickets[i])==GW_COMPLETE){
        mp_router_ack(r,&s->inflight[i],true);s->tickets[i]=0;s->q1++;
#ifdef MP_FIVE_FIELD01
        field01_published(&s->inflight[i]);
#endif
    }
#if GATEWAY_TELEMETRY_SLOTS == 3
    s->pending=s->tickets[0] || s->tickets[1] || s->tickets[2];
#else
    s->pending=false;
    for(unsigned i=0;i<GATEWAY_TELEMETRY_SLOTS;i++)s->pending|=s->tickets[i]!=0;
#endif
    if(!allow_new)return 1;
    uint64_t utc=gateway_epoch_milliseconds();
    bool medical_due=false;
    for(unsigned i=0;i<GATEWAY_TELEMETRY_SLOTS;i++)if(s->tickets[i] && !s->inflight[i].replay &&
        mp_realtime_yield_due(utc,s->inflight[i].timestamp,true))medical_due=true;
#ifndef MP_AUDIO_DISABLED
    if(!s->deferred && !s->audio_yield && !medical_due && b5_audio_room(r,utc) && unified_audio_send_due()){
        unified_audio_step(true);if(gateway_audio_pending()){s->audio_yield=true;return 1;}
    }
#endif
    int admission=gateway_mqtt_admit();
    if(admission==GW_FAILED){s->failed++;return 0;}
    if(admission==GW_DEFERRED){
#ifdef MP_FIVE_FIELD01
        field01_admission();
#endif
        return 1;
    }
    /* 老实时事务优先收确认；此时仅允许不占QoS1槽的实时波形。 */
    if(s->deferred || mp_router_take_egress(r,&s->publishing,g_uptime_ms,utc,gateway_mqtt_slots_full() || medical_due)){
        if(!s->deferred && !b5_prepare_publish(&s->publishing,utc))return 1;
        int result=gateway_mqtt_begin(&s->publishing);s->deferred=result==GW_DEFERRED;
        if(s->deferred || b5_network_stopped())return 1;
        if(result==GW_PENDING){unsigned i=0;while(i<GATEWAY_TELEMETRY_SLOTS && s->tickets[i])i++;if(i==GATEWAY_TELEMETRY_SLOTS){s->failed++;return 0;}s->tickets[i]=gateway_mqtt_ticket();s->inflight[i]=s->publishing;s->pending=true;
#ifndef MP_AUDIO_DISABLED
            s->audio_yield=false;
#endif
        }
        else{
            mp_router_ack(r,&s->publishing,result==GW_COMPLETE);
            if(result==GW_FAILED){s->failed++;return 0;}
            s->q0++;
#ifdef MP_FIVE_FIELD01
            if(result==GW_COMPLETE)field01_published(&s->publishing);
#endif
        }
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
