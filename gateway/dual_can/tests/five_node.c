/* 仅模拟端口报文输入，CANopenNode、OD、有效性、队列与序列化均为生产实现。 */
#include "b4_gateway.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>

static B4Gateway g;
static uint32_t now=1000;
static unsigned valid[6][MP_STREAMS];
static MpFrame latest[6][MP_STREAMS];
int b4_bus_transmit(unsigned bus,const MpCanFrame *f){(void)bus;(void)f;return 1;}
static void drain(void){
    MpFrame f;char topic[128],json[2048];
    while(mp_router_take(&g.router,&f,now)){
        assert(f.node==1 || f.node==2 || f.node==4 || f.node==5);
        assert(mp_topic(&f,topic,sizeof(topic))>0 && mp_json(&f,json,sizeof(json))>0);
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
int main(void){
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
    MpFrame wrong={0};wrong.node=1;wrong.stream=MP_NIBP;char topic[128];assert(!mp_topic(&wrong,topic,sizeof(topic)));
    wrong.node=5;assert(mp_topic(&wrong,topic,sizeof(topic))>0 && strstr(topic,"NODE-E/telemetry/nibp"));
    /* 旧血压完成 tick 超过90秒时不得重新产生有效结果。 */
    now+=91000;b4_gateway_tick(&g,now);b4_gateway_sync(&g,1800000091u,now);
    hb(0,5,5);pair(0,0x685,0x80000208u,1);pair(0,0x485,1800000091u,now);
    pair(0,0x285,completion,1200u|(800u<<16));vitals(0,5,0,0,1200,800);
    assert(valid[5][MP_NIBP]==2);
    b4_gateway_close(&g);puts("FIVE_NODE_GATEWAY_HOST_PASS");return 0;
}
