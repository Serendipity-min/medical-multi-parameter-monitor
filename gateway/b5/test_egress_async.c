#include "../mqtt/tests/mocks/mock_esp.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>
extern unsigned mock_send_stall_ms;
extern unsigned mock_send_base_ms,mock_emulate_uart;
extern unsigned mock_model_poll_divisor;
extern void (*mock_poll_callback)(void);
static MpRouter router;
static uint32_t produced,origin,seq[MP_STREAMS];
static unsigned delivered[MP_STREAMS];
static uint32_t max_age[MP_STREAMS];
static void put(unsigned stream,unsigned rate,unsigned count,uint32_t tick){
    MpFrame f=mock_frame((MpStream)stream,(uint16_t)rate,false);f.seq=++seq[stream];f.count=(uint16_t)count;
    f.timestamp=1800000000000ULL+tick;f.values[0]=stream==MP_TEMP?2686:stream==MP_HR?6000:0;
    mp_router_put(&router,&f);
}
static void produce(void){
    while(produced<g_uptime_ms-origin){
        produced++;
        if(produced%400==0)put(MP_ECG,250,100,produced);
        if(produced%1000==0){put(MP_RESP,50,50,produced);put(MP_HR,0,1,produced);put(MP_RR,0,1,produced);put(MP_TEMP,0,1,produced);}
        if(produced%5000==0){put(MP_NODE_STATUS,0,1,produced);put(MP_GATEWAY_STATUS,0,1,produced);}
    }
}
static void verify(const MpFrame *f){
    uint32_t age=(uint32_t)(1800000000000ULL+g_uptime_ms-origin-f->timestamp);
    if(age>max_age[f->stream])max_age[f->stream]=age;
#ifdef MP_B5_EGRESS_FINAL
    assert(!f->replay && age<=5000);
#endif
    delivered[f->stream]++;
}
int main(int argc,char **argv){
    (void)argv;
#ifdef MP_B5_EGRESS_FINAL
    MpFrame scalar=mock_frame(MP_HR,0,false),wave=mock_frame(MP_ECG,250,false);
    mock_connect();mock_delay_ms=1500;
    uint32_t start=g_uptime_ms;assert(gateway_mqtt_begin(&scalar)==GW_PENDING);
    uint16_t id=mock_last_id;assert(gateway_mqtt_pending());
    unsigned waves=0;
    while(gateway_mqtt_progress()==GW_PENDING){assert(gateway_mqtt_begin(&wave)==GW_COMPLETE);assert(mock_last_id==id);waves++;}
    assert(waves>10 && g_uptime_ms-start>=1500 && !gateway_mqtt_pending());
    puts("ASYNC_REAL_COREMQTT_Q0_ADVANCES_DURING_Q1_ACK_WAIT");
    const unsigned bad[]={ACK_WRONG,ACK_NONE,ACK_HALF,ACK_DUPLICATE,ACK_OLD};
    for(unsigned i=0;i<5;i++){
        mock_connect();mock_ack_mode=(int)bad[i];mock_old_id=65000;
        assert(gateway_mqtt_begin(&scalar)==GW_PENDING);start=g_uptime_ms;int state;
        do{state=gateway_mqtt_progress();}while(state==GW_PENDING);
        if(bad[i]==ACK_DUPLICATE){assert(state==GW_COMPLETE);assert(gateway_mqtt_begin(&scalar)==GW_PENDING);state=gateway_mqtt_progress();}
        assert(state==GW_FAILED);assert(g_uptime_ms-start<5100);
    }
    mock_connect();mock_read_limit=1;assert(gateway_mqtt_begin(&scalar)==GW_PENDING);
    while(gateway_mqtt_progress()==GW_PENDING){}assert(!gateway_mqtt_pending());
    puts("STRICT_WRONG_MISSING_PARTIAL_DUPLICATE_OLD_ACK_CASES_PASS");
#endif
    mock_connect();mock_send_base_ms=15;mock_emulate_uart=1;mock_delay_ms=40;mock_model_poll_divisor=10;
    origin=g_uptime_ms;produced=0;memset(seq,0,sizeof(seq));mp_router_init(&router);mp_router_online(&router,true);
    mock_poll_callback=produce;MpFrame f,inflight;int pending=0;unsigned injected=0;
    while(g_uptime_ms-origin<305000){
        platform_poll();uint32_t elapsed=g_uptime_ms-origin;
        static const uint32_t stall_at[]={100000,101500,131593};
        if(injected<3 && elapsed>=stall_at[injected]){mock_send_stall_ms=injected==2?2516:1500;injected++;}
#ifdef MP_B5_EGRESS_FINAL
        if(pending){int result=gateway_mqtt_progress();assert(result!=GW_FAILED);if(result==GW_COMPLETE){verify(&inflight);mp_router_ack(&router,&inflight,true);pending=0;}}
        bool taken=mp_router_take_egress(&router,&f,g_uptime_ms,1800000000000ULL+elapsed,pending);
#else
        (void)inflight;(void)pending;bool taken=mp_router_take(&router,&f,g_uptime_ms);
#endif
        if(taken){
            if(f.timestamp>=1800000300000ULL)continue;
#ifdef MP_B5_EGRESS_FINAL
            int result=gateway_mqtt_begin(&f);assert(result!=GW_FAILED);
            if(result==GW_PENDING){inflight=f;pending=1;}else{verify(&f);mp_router_ack(&router,&f,true);}
#else
            bool sent=gateway_mqtt_publish(&f);assert(sent);verify(&f);mp_router_ack(&router,&f,sent);
#endif
        }
    }
#ifdef MP_B5_EGRESS_FINAL
    assert(!router.live_overflow && !router.live_replaced && !router.cn && !router.dropped && !router.expired);
    assert(delivered[MP_ECG]>=749 && delivered[MP_RESP]>=299 && delivered[MP_HR]>=299 && delivered[MP_TEMP]>=299);
    assert(max_age[MP_NODE_STATUS]<5000 && max_age[MP_GATEWAY_STATUS]<5000);
    printf("THREE_STALL_300S_PASS high=%lu ECG=%u RESP=%u HR=%u TEMP=%u status_age=%lu/%lu sizeof_router=%u\n",(unsigned long)router.high_water,
        delivered[MP_ECG],delivered[MP_RESP],delivered[MP_HR],delivered[MP_TEMP],(unsigned long)max_age[MP_NODE_STATUS],(unsigned long)max_age[MP_GATEWAY_STATUS],(unsigned)sizeof(router));
    mock_poll_callback=NULL;mp_router_init(&router);mp_router_online(&router,true);
    for(unsigned i=0;i<MP_LIVE_CAPACITY+MP_CACHE_CAPACITY+1;i++)put(MP_ECG,250,100,i);
    assert(router.live_overflow && router.dropped==1 && router.ln==MP_LIVE_CAPACITY && router.cn==MP_CACHE_CAPACITY);
    puts("OVERLOAD_NEGATIVE_REMAINS_EXPLICIT_HISTORY_AND_DROP_NOT_MOCK_PASS");
#else
#if MP_LIVE_CAPACITY == 16
    assert(router.stored>0 || max_age[MP_HR]>5000);
#endif
    printf("LEGACY_CAPACITY_CONTROL live=%u stored=%lu replayed=%lu dropped=%lu max_HR_age=%lu status_age=%lu/%lu\n",MP_LIVE_CAPACITY,
        (unsigned long)router.stored,(unsigned long)router.replayed,(unsigned long)router.dropped,(unsigned long)max_age[MP_HR],
        (unsigned long)max_age[MP_NODE_STATUS],(unsigned long)max_age[MP_GATEWAY_STATUS]);
#endif
    return argc>5;
}
