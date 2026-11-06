/* 真实出口推进器与Router；替身复现完成一次AT查询后又启动下一次的空档竞争。 */
#include "../b5/egress.h"
#include <stdio.h>
#include <stdlib.h>
static unsigned busy,progress_calls,checks,q0_allowed,q0_sent;
#ifdef MP_FINAL_UNIFIED
static unsigned audio_due,audio_started,audio_pending,slots_full;
bool unified_audio_send_due(void){return audio_due!=0;}
void unified_audio_wait(unsigned mask){(void)mask;}
bool unified_audio_step(bool allowed){if(allowed){audio_started++;audio_pending=1;audio_due=0;return true;}return false;}
int gateway_mqtt_pending(void){return 0;}
int gateway_mqtt_slots_full(void){return (int)slots_full;}
uint16_t gateway_mqtt_ticket(void){return 2;}
int gateway_mqtt_ticket_result(uint16_t id){return id==1?GW_COMPLETE:id>=2 && id<=4?GW_PENDING:GW_FAILED;}
int gateway_audio_pending(void){return audio_pending!=0;}
#endif
volatile uint32_t g_uptime_ms;
#define CHECK(x) do {if(!(x)){fprintf(stderr,"FAIL line=%d\n",__LINE__);exit(3);}checks++;}while(0)
int b5_network_stopped(void){return 0;}
uint64_t gateway_epoch_milliseconds(void){return 1800000000000ULL;}
int gateway_mqtt_progress(void){progress_calls++;busy=!busy;return GW_COMPLETE;}
int gateway_mqtt_admit(void){return busy?GW_DEFERRED:GW_COMPLETE;}
int gateway_mqtt_begin(const MpFrame *f){CHECK(q0_allowed && f->rate);q0_sent++;return GW_COMPLETE;}
int main(void){
    MpRouter r;mp_router_init(&r);B5Publisher p={0};unsigned opportunities=0;
    for(unsigned i=0;i<100;i++){CHECK(b5_egress_step(&r,&p,true));opportunities+=!busy;}
#ifdef MP_FINAL_UNIFIED
    CHECK(opportunities==50 && progress_calls==100);
    /* 使用真实Router保留一个标量；回调必须位于已在途PUBACK释放后、下次取帧前。 */
    MpFrame f={0};f.node=2;f.stream=MP_HR;f.epoch=1800000000u;f.boot=1;f.seq=1;
    f.timestamp=1800000000000ULL;f.count=1;f.values[0]=6000;f.valid=f.synthetic=true;
    mp_router_online(&r,true);mp_router_put(&r,&f);CHECK(r.ln==1);
    p.pending=true;p.inflight[0]=f;p.tickets[0]=1;audio_due=1;
    CHECK(b5_egress_step(&r,&p,true));CHECK(!p.pending && audio_started==1 && p.audio_yield && r.ln==1);
    printf("UNIFIED_REAL_ROUTER_POST_ACK_AUDIO_SLOT_PASS queued=%u audio=%u hardware=NOT_RUN\n",r.ln,audio_started);
    /* 实板反例：仍有11个空槽，但半容量门槛让音频一直等不到机会。 */
    mp_router_init(&r);mp_router_online(&r,true);p=(B5Publisher){0};
    for(unsigned i=0;i<13;i++){f.seq++;mp_router_put(&r,&f);}
    CHECK(r.ln==13);audio_due=1;audio_pending=0;busy=0;
    CHECK(b5_egress_step(&r,&p,true));CHECK(audio_started==2 && r.ln==13);
    p=(B5Publisher){0};audio_pending=0;audio_due=1;busy=0;
    r.live[r.lh].timestamp-=2501;
    CHECK(b5_egress_step(&r,&p,true));CHECK(audio_started==2);
    r.live[r.lh].timestamp=f.timestamp;
    p.tickets[0]=2;p.inflight[0]=f;p.inflight[0].timestamp-=2501;busy=0;
    CHECK(b5_egress_step(&r,&p,true));CHECK(audio_started==2);p=(B5Publisher){0};
    while(r.ln<MP_LIVE_CAPACITY-2){f.seq++;mp_router_put(&r,&f);}
    busy=0;CHECK(b5_egress_step(&r,&p,true));CHECK(audio_started==2);
    printf("UNIFIED_HALF_FULL_BURST_ADMISSION_PASS stale_and_capacity_backpressure_preserved=1\n");
    mp_router_init(&r);mp_router_online(&r,true);p=(B5Publisher){0};
    f.node=1;f.stream=MP_PPG;f.rate=50;f.seq++;mp_router_put(&r,&f);
    f.seq++;mp_router_put(&r,&f);
    CHECK(r.ln==2 && !r.live_replaced && !r.cn);
    audio_due=1;audio_pending=0;busy=0;
    CHECK(b5_egress_step(&r,&p,true));CHECK(audio_started==3 && r.ln==2);
    MpFrame wave;
    CHECK(mp_router_take_egress(&r,&wave,g_uptime_ms,f.timestamp,false) && wave.seq==f.seq-1);
    CHECK(mp_router_take_egress(&r,&wave,g_uptime_ms,f.timestamp,false) && wave.seq==f.seq);
    puts("UNIFIED_PPG_FIFO_AND_AUDIO_FAIR_TURN_PASS");
    /* 波形发送也应归还音频额度，不能一直等下一条QoS1标量。 */
    mp_router_init(&r);mp_router_online(&r,true);p=(B5Publisher){0};p.audio_yield=true;
    f.node=2;f.stream=MP_ECG;f.rate=250;f.count=1;f.seq++;mp_router_put(&r,&f);
    q0_allowed=1;busy=1;audio_due=1;audio_pending=0;
    CHECK(b5_egress_step(&r,&p,true));CHECK(q0_sent==1 && !p.audio_yield);
    busy=1;CHECK(b5_egress_step(&r,&p,true));CHECK(audio_started==4);
    printf("UNIFIED_QOS0_RETURNS_AUDIO_TURN_PASS hardware=NOT_RUN\n");
    /* 三医疗槽等待ACK、无可运行医疗帧时，空闲音频槽不能被deferred标量封住。 */
    mp_router_init(&r);mp_router_online(&r,true);p=(B5Publisher){0};
    p.deferred=p.audio_yield=true;p.publishing=f;p.publishing.stream=MP_HR;p.publishing.rate=0;
    for(unsigned i=0;i<3;i++){p.tickets[i]=(uint16_t)(i+2);p.inflight[i]=f;}
    slots_full=1;audio_due=1;audio_pending=0;busy=0;
    CHECK(b5_egress_step(&r,&p,true));CHECK(audio_started==5 && p.deferred);
    p.audio_yield=false;p.publishing.timestamp-=2501;audio_due=1;audio_pending=0;busy=0;
    CHECK(b5_egress_step(&r,&p,true));CHECK(audio_started==5);
    p.publishing.timestamp=f.timestamp;p.publishing.rate=250;busy=0;
    CHECK(b5_egress_step(&r,&p,true));CHECK(audio_started==5);slots_full=0;
    printf("UNIFIED_FULL_MEDICAL_ACK_WINDOW_AUDIO_PROGRESS_PASS stale_held_and_qos0_backpressure_preserved=1\n");
    mp_router_init(&r);mp_router_online(&r,true);
    f.node=2;f.stream=MP_TEMP;f.rate=0;f.timestamp=1800000000000ULL-3000u;f.seq++;mp_router_put(&r,&f);
    f.stream=MP_NODE_STATUS;f.timestamp=1800000000000ULL;f.seq++;mp_router_put(&r,&f);
    CHECK(mp_router_take_egress(&r,&wave,g_uptime_ms,f.timestamp,false) && wave.stream==MP_TEMP);
    CHECK(mp_router_take_egress(&r,&wave,g_uptime_ms,f.timestamp,false) && wave.stream==MP_NODE_STATUS);
    puts("UNIFIED_AGED_MEASUREMENT_PRECEDES_FRESH_STATUS_PASS");
    printf("UNIFIED_AT_IDLE_SLOT_PASS opportunities=%u progress_calls=%u hardware=NOT_RUN\n",opportunities,progress_calls);
#else
    CHECK(opportunities==0);
    printf("LEGACY_DOUBLE_POLL_STARVATION_REPRODUCED opportunities=%u progress_calls=%u hardware=NOT_RUN\n",opportunities,progress_calls);
#endif
    return 0;
}
