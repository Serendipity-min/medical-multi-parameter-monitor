#include "../storage/router.h"
#include <assert.h>
#include <stdio.h>

volatile uint32_t g_uptime_ms=5000;
uint64_t gateway_epoch_milliseconds(void){return 1800000000000ULL+g_uptime_ms;}
static void put(MpRouter *r,unsigned node,unsigned stream,uint64_t stamp,unsigned rate){
    MpFrame f={0};f.node=node;f.stream=stream;f.timestamp=stamp;f.rate=rate;f.count=1;f.valid=true;f.synthetic=true;
    mp_router_put(r,&f);
}
int main(void){
    const uint64_t base=1800000000000ULL;MpRouter r;MpFrame f;
    mp_router_init(&r);mp_router_online(&r,true);
    put(&r,1,MP_SPO2,base+2000,0);
    put(&r,2,MP_HR,base+1000,0);put(&r,2,MP_RR,base+1000,0);put(&r,2,MP_TEMP,base+1000,0);
    put(&r,2,MP_ECG,base+4800,250);
    put(&r,1,MP_SPO2,base+4500,0);
    assert(r.live_replaced==1);
    assert(mp_router_take_egress(&r,&f,5000,base+5000,false));
    printf("first scalar stream=%u node=%u source_age=%lu\n",f.stream,f.node,(unsigned long)(base+5000-f.timestamp));fflush(stdout);
    assert(f.node==2 && f.stream==MP_HR && f.timestamp==base+1000);
    assert(mp_router_take_egress(&r,&f,5000,base+5000,false));assert(f.stream==MP_ECG && f.timestamp==base+4800);
    assert(mp_router_take_egress(&r,&f,5000,base+5000,false));assert(f.stream==MP_RR);
    assert(mp_router_take_egress(&r,&f,5000,base+5000,false));assert(f.stream==MP_TEMP);
    assert(mp_router_take_egress(&r,&f,5000,base+5000,false));assert(f.stream==MP_SPO2 && f.timestamp==base+4500);
    mp_router_init(&r);mp_router_online(&r,true);
    put(&r,2,MP_TEMP,base+1000,0);put(&r,2,MP_ECG,base+4500,250);
    assert(mp_router_take_egress(&r,&f,5000,base+5000,true));assert(f.stream==MP_ECG);
    assert(!mp_router_take_egress(&r,&f,5000,base+5000,true));assert(r.ln==1);
    puts("ABC_SCALAR_SOURCE_ORDER_FAIR_WAVE_AND_PENDING_ACK_PASS");return 0;
}
