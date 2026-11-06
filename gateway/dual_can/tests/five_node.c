/* 仅模拟端口报文输入，CANopenNode、OD、有效性、队列与序列化均为生产实现。 */
#include "b4_gateway.h"
#include "../../../node-a/STM32F407_HOSPITAL/HARDWARE/CANopen/node_policy.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>

static B4Gateway g;
static uint32_t now=1000;
static unsigned valid[6][MP_STREAMS];
static MpFrame latest[6][MP_STREAMS];
static MpFrame ppg[8];
static unsigned ppg_count;
int b4_bus_transmit(unsigned bus,const MpCanFrame *f){(void)bus;(void)f;return 1;}
static void drain(void){
    MpFrame f;char topic[128],json[2048];
    while(mp_router_take(&g.router,&f,now)){
        assert(f.node==1 || f.node==2 || f.node==4 || f.node==5);
        assert(mp_topic(&f,topic,sizeof(topic))>0 && mp_json(&f,json,sizeof(json))>0);
        if (f.stream==MP_PPG) { assert(ppg_count<8); ppg[ppg_count++]=f; }
        if(!f.replay){latest[f.node][f.stream]=f;if(f.valid)valid[f.node][f.stream]++;}
        mp_router_ack(&g.router,&f,true);
    }
}
static void send(unsigned bus,unsigned id,const void *data,unsigned length){
    MpCanFrame f={0};f.ident=id;f.dlc=length;memcpy(f.data,data,length);
    b4_gateway_tick(&g,++now);b4_gateway_receive(&g,bus,&f,now);
    b4_gateway_tick(&g,++now);drain();
}
static void pair(unsigned bus,unsigned id,uint32_t a,uint32_t b){uint32_t v[2]={a,b};send(bus,id,v,8);}
static void hb(unsigned bus,unsigned node,unsigned value){uint8_t v=value;send(bus,0x700+node,&v,1);}
static void setup(unsigned bus,unsigned node,uint32_t flags,unsigned generation){
    hb(bus,node,0);hb(bus,node,5);pair(bus,mp_pdo_id(node,4),flags|0x80000000u,generation);
    pair(bus,mp_pdo_id(node,3),1800000000u,now);
}
static void vitals(unsigned bus,unsigned node,uint16_t a,uint16_t b,uint16_t c,uint16_t d){uint16_t v[4]={a,b,c,d};send(bus,mp_pdo_id(node,2),v,8);}
static void partial_ppg(void){
    assert(b4_gateway_init(&g)==0);mp_router_online(&g.router,true);b4_gateway_sync(&g,1800000000u,now);
    setup(0,1,7,1);setup(0,5,520,1);setup(1,2,15,1);setup(1,4,16,1);
    uint32_t anchor=now;
    pair(1,0x182,101,anchor+4);pair(1,0x182,102,anchor+8);
    pair(0,0x181,11,anchor+20);pair(0,0x181,22,anchor+40);pair(0,0x181,33,anchor+60);
    assert(!ppg_count);
    pair(0,0x181,44,anchor+100);pair(0,0x181,55,anchor+120);
    assert(ppg_count==1 && ppg[0].count==3 && ppg[0].valid);
    assert(ppg[0].values[0]==11 && ppg[0].values[1]==22 && ppg[0].values[2]==33);
    pair(0,0x681,0x80000006u,1);pair(0,0x181,66,anchor+140);
    assert(ppg_count==2 && ppg[1].count==2 && ppg[1].valid);
    assert(ppg[1].values[0]==44 && ppg[1].values[1]==55);
    uint64_t tail_time=g.segments[0].wave[0].timestamp;
    now+=150;b4_gateway_tick(&g,now);drain();
    assert(ppg_count==3 && ppg[2].count==1 && !ppg[2].valid && ppg[2].values[0]==66);
    assert(ppg[2].timestamp==tail_time && ppg[0].seq+1==ppg[1].seq && ppg[1].seq+1==ppg[2].seq);
    assert(g.partial_discarded==0 && g.ppg_partial_batches==3 && g.ppg_partial_samples==6);
    assert(g.wave_gaps==1 && g.quality_resets==1 && g.segments[1].wave[0].count==2);
    assert(g.segments[0].remote[0].wave_gaps[0]==1 && g.segments[1].remote[0].wave_gaps[0]==0);
    for(unsigned i=3;i<=100;i++)pair(1,0x182,100+i,anchor+4*i);
    assert(latest[2][MP_ECG].count==100 && latest[2][MP_ECG].values[0]==101 && latest[2][MP_ECG].values[99]==200);
    assert(g.segments[1].remote[0].pdo_count[0]==100);
    b4_gateway_close(&g);memset(valid,0,sizeof(valid));now=1000;
}
int main(void){
    assert(node_age_within(1000,1001,250) && node_age_within(1000,750,250));
    assert(!node_age_within(1000,749,250) && node_age_within(5,0xfffffff0u,250));
    partial_ppg();
    assert(b4_gateway_init(&g)==0);mp_router_online(&g.router,true);b4_gateway_sync(&g,1800000000u,now);
    setup(0,1,7,1);setup(0,5,(1u<<9)|8,1);setup(1,2,15,1);setup(1,4,16,1);
    assert(b4_gateway_online(&g,1) && b4_gateway_online(&g,2) && b4_gateway_online(&g,4) && b4_gateway_online(&g,5));
    assert(mp_od_read(&g.segments[0].od,0x1406,1)==0x285);
    assert(mp_od_read(&g.segments[1].od,0x1407,1)==0x384);
    vitals(0,1,9800,6000,0,0);vitals(1,2,6000,1800,0,0);vitals(1,4,0,0,3020,10);
    assert(valid[1][MP_SPO2] && valid[2][MP_HR] && valid[4][MP_TEMP]);
    assert(latest[4][MP_TEMP].values[0]==3020);
    unsigned dvalid=valid[4][MP_TEMP];vitals(1,4,0,0,3020,2501);
    assert(valid[4][MP_TEMP]==dvalid && !latest[4][MP_TEMP].valid);
    vitals(1,4,0,0,3020,10);assert(valid[4][MP_TEMP]==dvalid+1);
    unsigned rejected=g.wrong_bus;pair(0,0x384,1,2);pair(1,0x385,1,2);
    pair(0,0x681,0x8000020fu,1);pair(1,0x682,0x8000001fu,1);
    assert(g.wrong_bus==rejected+4);
    uint32_t completion=now;pair(0,0x285,completion,1200u|(800u<<16));vitals(0,5,0,0,1200,800);pair(0,0x485,1800000000u,now);
    assert(valid[5][MP_NIBP]==1 && latest[5][MP_NIBP].values[0]==1200);
    uint64_t timestamp=latest[5][MP_NIBP].timestamp;
    pair(0,0x285,completion,1200u|(800u<<16));vitals(0,5,0,0,1200,800);
    assert(valid[5][MP_NIBP]==1 && latest[5][MP_NIBP].timestamp==timestamp);
    completion=now;pair(0,0x285,completion,1200u|(800u<<16));vitals(0,5,0,0,1200,800);pair(0,0x485,1800000000u,now);
    assert(valid[5][MP_NIBP]==2);
    unsigned bboot=g.segments[1].remote[0].observed_boot;
    hb(1,4,4);assert(!b4_gateway_online(&g,4) && b4_gateway_online(&g,2));
    assert(g.segments[1].remote[1].nmt_state==4);
    assert(g.segments[1].remote[0].observed_boot==bboot);
    dvalid=valid[4][MP_TEMP];hb(1,4,5);vitals(1,4,0,0,3020,10);assert(valid[4][MP_TEMP]==dvalid);
    pair(1,0x684,0x80000010u,2);pair(1,0x484,1800000000u,now);vitals(1,4,0,0,3020,10);
    assert(latest[4][MP_TEMP].valid);
    unsigned malformed=g.malformed;pair(1,0x684,0x80000010u,1);
    assert(g.malformed==malformed+1 && g.segments[1].remote[1].generation==2);
    hb(0,5,4);assert(!b4_gateway_online(&g,5) && b4_gateway_online(&g,1));
    hb(0,5,5);pair(0,0x685,0x80000208u,1);pair(0,0x485,1800000000u,now);
    pair(0,0x285,completion,1200u|(800u<<16));vitals(0,5,0,0,1200,800);
    assert(valid[5][MP_NIBP]==2);
    assert(g.segments[0].remote[0].heartbeat_count>=2 && g.segments[0].remote[0].nmt_state==5);
    assert(g.segments[1].remote[1].nmt_state==5);
    MpFrame wrong={0};wrong.node=1;wrong.stream=MP_NIBP;char topic[128];assert(!mp_topic(&wrong,topic,sizeof(topic)));
    wrong.node=5;assert(mp_topic(&wrong,topic,sizeof(topic))>0 && strstr(topic,"NODE-E/telemetry/nibp"));
    /* 旧血压完成 tick 超过90秒时不得重新产生有效结果。 */
    now+=91000;b4_gateway_tick(&g,now);b4_gateway_sync(&g,1800000091u,now);
    hb(0,5,5);pair(0,0x685,0x80000208u,1);pair(0,0x485,1800000091u,now);
    pair(0,0x285,completion,1200u|(800u<<16));vitals(0,5,0,0,1200,800);
    assert(valid[5][MP_NIBP]==2);
    assert(g.segments[0].remote[1].pdo_count[1]>0 && g.segments[1].remote[0].pdo_count[2]>0);
    assert(g.segments[1].remote[1].nmt_state==5);
    uint8_t error[8]={0x10,0x81,0x10,0x14,0,0,0,0};
    send(0,0x85,error,8);memset(error,0,sizeof(error));send(0,0x85,error,8);
    assert(g.segments[0].remote[1].emcy_errors==1 && g.segments[0].remote[1].last_emcy_error==0x8110);
    b4_gateway_close(&g);puts("FIVE_NODE_GATEWAY_HOST_PASS");return 0;
}
