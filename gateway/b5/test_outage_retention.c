#include "../dual_can/b4_gateway.h"
#include "../data_model/roles.h"
#include "../../node-b/canopen/node_policy.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>

#define UTC0 1800000000000ULL
volatile uint32_t g_uptime_ms;
uint64_t gateway_epoch_milliseconds(void){return UTC0+g_uptime_ms;}

static B4Gateway gateway;
static MpRouter router;
static MpRetention history;
static NodeClock clocks[2];
static unsigned time_frames[2];
static uint64_t time_sent[2];

int b4_bus_transmit(unsigned bus,const MpCanFrame *f){
    if(f->ident==0x100){
        uint32_t ms;uint16_t days;
        assert(f->dlc==6);
        memcpy(&ms,f->data,4);memcpy(&days,f->data+4,2);
        uint64_t stamp=441763200000ULL+(uint64_t)days*86400000u+ms;
        assert(!time_frames[bus] || stamp>time_sent[bus]);
        time_sent[bus]=stamp;time_frames[bus]++;
        node_clock_set(&clocks[bus],ms,days,g_uptime_ms);
    }
    return 1;
}

static void receive_b(unsigned pdo,const void *data,unsigned len){
    MpCanFrame f={.ident=pdo,.dlc=len};
    memcpy(f.data,data,len);
    b4_gateway_receive(&gateway,1,&f,g_uptime_ms);
}

static void clock_holdover(void){
    const uint32_t start=UINT32_MAX-10000;
    assert(b4_gateway_init(&gateway)==0);
    g_uptime_ms=start;
    b4_gateway_sync_ms(&gateway,UTC0,start);
    const uint8_t operational=5;
    const uint32_t quality[2]={0x8000000fu,1u};
    const uint16_t vitals[4]={6000,1800,0,0};
    for(unsigned second=0;second<=600;second++){
        g_uptime_ms=start+second*1000u;
        b4_gateway_tick(&gateway,g_uptime_ms);
        uint32_t identity[2];
        node_clock_read(&clocks[1],g_uptime_ms,&identity[0],&identity[1]);
        assert(identity[0]==1800000000u+second && identity[1]==g_uptime_ms);
        receive_b(0x702,&operational,1);receive_b(0x682,quality,8);
        receive_b(0x482,identity,8);receive_b(0x382,vitals,8);
    }
    assert(time_frames[0]==61 && time_frames[1]==61);
    assert(gateway.router.enqueued[MP_HR]==601 && gateway.unstamped==0);
    uint64_t before=b4_gateway_utc(&gateway,g_uptime_ms);
    assert(before==UTC0+600000);
    b4_gateway_sync_ms(&gateway,before-500,g_uptime_ms);
    assert(b4_gateway_utc(&gateway,g_uptime_ms)==before);
    uint64_t previous=before;
    for(unsigned ms=1;ms<=50000;ms++){
        uint64_t stamp=b4_gateway_utc(&gateway,g_uptime_ms+ms);
        assert(stamp>=previous && stamp<=previous+1);previous=stamp;
    }
    assert(previous==before+49500);
    const uint32_t corrected_at=g_uptime_ms;
    b4_gateway_sync_ms(&gateway,previous+750,corrected_at+50000);
    assert(b4_gateway_utc(&gateway,corrected_at+50000)==previous);
    assert(b4_gateway_utc(&gateway,corrected_at+125000)==previous+75750);
    g_uptime_ms=corrected_at+50000+B4_UTC_HOLD_MS+1u;
    assert(!b4_gateway_utc(&gateway,g_uptime_ms));
    b4_gateway_tick(&gateway,g_uptime_ms);
    assert(time_frames[0]==61 && time_frames[1]==61);
    uint32_t identity[2]={1800001260u,g_uptime_ms};
    receive_b(0x702,&operational,1);receive_b(0x682,quality,8);
    receive_b(0x482,identity,8);receive_b(0x382,vitals,8);
    assert(gateway.unstamped>0 && gateway.router.enqueued[MP_HR]==601);
    b4_gateway_close(&gateway);
}

static MpFrame scalar(unsigned second,unsigned i){
    static const MpStream streams[]={MP_SPO2,MP_PR,MP_HR,MP_RR,MP_TEMP,MP_NIBP};
    MpFrame f={.timestamp=UTC0+second*1000u+i,.seq=second+1,.epoch=7,.boot=3,
        .count=i==5?2:1,.node=mp_role_node(streams[i]),.stream=streams[i],.valid=true,.synthetic=true,
        .values={(int32_t)(second*6+i),800}};
    return f;
}

static void put_second(unsigned second){
    /* 模拟倒序迁入的在途数据，并用波形压力反复覆盖旧波形。 */
    for(unsigned i=6;i>0;i--){
        MpFrame f=scalar(second,i-1);mp_router_put(&router,&f);
    }
    MpFrame wave={.timestamp=UTC0+second*1000u,.stream=MP_ECG,.node=2,.seq=second+1,.count=100,.rate=250};
    for(unsigned i=0;i<3;i++)mp_router_put(&router,&wave);
    if(second%5==0){
        const uint8_t nodes[]={1,2,3,4,5};
        for(unsigned i=0;i<5;i++){
            MpFrame f={.timestamp=UTC0+second*1000u+i,.stream=nodes[i]==3?MP_GATEWAY_STATUS:MP_NODE_STATUS,
                .node=nodes[i],.seq=second/5+1,.epoch=9,.boot=2,.count=1,.valid=(second%10)==0};
            mp_router_put(&router,&f);
        }
    }
}

static void begin_recovery(uint32_t now){
    MpFrame live=scalar(now/1000u,0),out;
    mp_router_online(&router,true);
    assert(!mp_router_take_egress(&router,&out,now,live.timestamp,false));
    mp_router_put(&router,&live);
    assert(!mp_router_take_egress(&router,&out,now,live.timestamp,true));
    assert(mp_router_take_egress(&router,&out,now,live.timestamp,false) && !out.replay && out.seq==live.seq);
    mp_router_ack(&router,&out,true);
}

static void retain_180(void){
    mp_router_init(&router);mp_router_attach_retention(&router,&history);
    for(unsigned second=0;second<180;second++)put_second(second);
    assert(router.scalar_history.count==1080 && router.status_history.count==180);
    assert(!router.scalar_history.pressure && !router.status_history.pressure && router.dropped>0);
    begin_recovery(180000);
    MpFrame f;assert(!mp_router_take_egress(&router,&f,180000,UTC0+180000,true));
    assert(mp_router_take_egress(&router,&f,180000,UTC0+180000,false));
    assert(f.seq==1 && f.stream==MP_SPO2);
    assert(!mp_router_take_egress(&router,&f,180000,UTC0+180000,false));
    mp_router_ack(&router,&f,false);
    assert(router.scalar_history.count==1080 && !router.scalar_pending && !router.online);
    begin_recovery(181000);
    for(unsigned second=0;second<180;second++){
        for(unsigned i=0;i<6;i++){
            MpFrame expected=scalar(second,i);
            assert(mp_router_take_egress(&router,&f,181000,UTC0+181000,false));
            assert(f.replay && f.timestamp==expected.timestamp && f.stream==expected.stream &&
                f.seq==expected.seq && f.epoch==expected.epoch && f.boot==expected.boot && f.node==expected.node &&
                f.valid && f.synthetic && f.count==expected.count && f.values[0]==expected.values[0] && f.values[1]==800);
            mp_router_ack(&router,&f,true);
        }
    }
    for(unsigned i=0;i<180;i++){
        const MpRetainedEntry *entry=&history.status[i];
        assert(entry->node==i%5+1 && entry->seq==i/5+1 && entry->epoch==9 && entry->boot==2);
        assert(entry->seconds==1800000000u+(i/5)*5 && entry->millis==i%5);
        assert(!!(entry->tag&16u)==(i/5%2==0));
    }
    assert(!router.scalar_history.count && router.scalar_replayed==1080);
    assert(mp_router_take_egress(&router,&f,181000,UTC0+181000,false) && f.replay && f.rate==250);
}

static void retain_boundary(void){
    mp_router_init(&router);mp_router_attach_retention(&router,&history);
    for(unsigned second=0;second<=240;second++)put_second(second);
    assert(router.scalar_history.count==1446 && router.status_history.count==245);
    assert(!router.scalar_history.expired && !router.scalar_history.pressure && history.scalars[0].seq==1);
    MpFrame burst=scalar(240,0);
    for(unsigned i=0;i<MP_RETAIN_SCALARS-1446+1u;i++){
        burst.seq++;mp_router_put(&router,&burst);
    }
    assert(router.scalar_history.count==MP_RETAIN_SCALARS && router.scalar_history.pressure==1 &&
        !router.scalar_history.expired && history.scalars[0].seq==1);
    burst=scalar(241,0);mp_router_put(&router,&burst);
    assert(router.scalar_history.expired==1 && router.scalar_history.pressure==1);
}

int main(void){
    clock_holdover();retain_180();retain_boundary();
    printf("R24_HOST_HOLDOVER_RETAIN_PASS frame=%u retention=%u\n",(unsigned)sizeof(MpFrame),(unsigned)sizeof(MpRetention));
    return 0;
}
