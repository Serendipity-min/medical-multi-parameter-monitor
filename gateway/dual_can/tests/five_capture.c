/* 四个源经真实协议栈/网关/台架消费；仅替换物理CAN与UART。 */
#include "b4_bench.h"
#include "b4_capture.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>
static B4Bench b;
static unsigned controls, points[6][MP_STREAMS], valid[6][MP_STREAMS];
static unsigned bus_controls[2];
int b4_bus_transmit(unsigned bus,const MpCanFrame *f) {
    assert(bus<2);
    if(!f->ident) {
        const unsigned nodes[2][2]={{1,5},{2,4}};
        assert(controls<4 && f->dlc==2 && f->data[0]==CO_NMT_ENTER_OPERATIONAL);
        assert(bus_controls[bus]<2 && f->data[1]==nodes[bus][bus_controls[bus]++]);controls++;
    }
    if(f->ident==0x100) assert(bus_controls[bus]==2);
    return 1;
}
int b4_capture_emit(unsigned kind,unsigned bus,unsigned id,unsigned dlc,const uint8_t *data,uint32_t tick,uint32_t flags) {
    (void)dlc;(void)data;(void)tick;
    if(kind==B4_CAP_MODEL) {
        unsigned node=flags&255;
        assert((node==1 || node==2 || node==4 || node==5) && id<MP_STREAMS);
        assert(bus==((node==1 || node==5)?0u:1u));
        points[node][id]+=flags>>16;if(flags&256)valid[node][id]++;
    }
    return 1;
}
static void send(unsigned node,unsigned pdo,const void *data,unsigned n,uint32_t now) {
    MpCanFrame f={0};f.ident=pdo==5?0x700+node:mp_pdo_id(node,pdo);f.dlc=n;memcpy(f.data,data,n);
    b4_gateway_receive(&b.gateway,(node==1 || node==5)?0:1,&f,now);
}
static void pair(unsigned node,unsigned pdo,uint32_t a,uint32_t c,uint32_t now) {uint32_t data[2]={a,c};send(node,pdo,data,8,now);}
int main(void) {
    assert(B4_BENCH_LIMIT_MS==60000u && !b4_bench_init(&b,0));
    assert(b.gateway.segments[0].link_up && b.gateway.segments[1].link_up);
    assert(b4_hw_protocol_link_up(0,1) && b4_hw_protocol_link_up(1,1));
    for(uint32_t now=0;now<60000;now++) {
        b4_bench_step(&b,now);
        if(now%500==0) {uint8_t v=5;send(1,5,&v,1,now);send(2,5,&v,1,now);send(4,5,&v,1,now);send(5,5,&v,1,now);}
        if(now%1000==0) {
            const unsigned nodes[4]={1,2,4,5}, flags[4]={7,15,16,520};
            for(unsigned i=0;i<4;i++) {pair(nodes[i],4,flags[i],1,now);pair(nodes[i],3,B4_BENCH_EPOCH+now/1000,now,now);}
            uint16_t temp[4]={0,0,2500,10};send(4,2,temp,8,now);
        }
        if(now>=20 && now%4==0)pair(2,0,now,now,now);
        if(now>=20 && now%20==0) {pair(2,1,now,now,now);pair(1,0,now,now,now);}
        if(now==2000) {uint16_t bp[4]={0,0,1150,800};pair(5,1,now,1150u|(800u<<16),now);send(5,2,bp,8,now);}
    }
    assert(points[1][MP_PPG]+b.gateway.segments[0].wave[0].count==2999);
    assert(points[2][MP_ECG]+b.gateway.segments[1].wave[0].count==14995);
    assert(points[2][MP_RESP]+b.gateway.segments[1].wave[1].count==2999);
    assert(valid[1][MP_PPG]==59 && valid[2][MP_ECG]==149 && valid[2][MP_RESP]==59 && valid[4][MP_TEMP]>=59 && valid[5][MP_NIBP]==1);
    b4_bench_step(&b,60000);assert(b.diag.stopped && !b.gateway.utc_valid);
    assert(!b.gateway.segments[0].link_up && !b.gateway.segments[1].link_up);
    b4_bench_step(&b,61000);assert(controls==4 && b.diag.elapsed_ms==60000);
    b4_gateway_close(&b.gateway);puts("FIVE_CAPTURE_FULL_STREAMS_AND_60S_STOP_PASS");return 0;
}
