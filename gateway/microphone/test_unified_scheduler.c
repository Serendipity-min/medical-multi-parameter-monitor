/* 真实出口推进器与Router；替身复现完成一次AT查询后又启动下一次的空档竞争。 */
#include "../b5/egress.h"
#include <stdio.h>
#include <stdlib.h>
static unsigned busy,progress_calls,checks;
volatile uint32_t g_uptime_ms;
#define CHECK(x) do {if(!(x)){fprintf(stderr,"FAIL line=%d\n",__LINE__);exit(3);}checks++;}while(0)
int b5_network_stopped(void){return 0;}
uint64_t gateway_epoch_milliseconds(void){return 1800000000000ULL;}
int gateway_mqtt_progress(void){progress_calls++;busy=!busy;return GW_COMPLETE;}
int gateway_mqtt_admit(void){return busy?GW_DEFERRED:GW_COMPLETE;}
int gateway_mqtt_begin(const MpFrame *f){(void)f;CHECK(0);return GW_FAILED;}
int main(void){
    MpRouter r;mp_router_init(&r);B5Publisher p={0};unsigned opportunities=0;
    for(unsigned i=0;i<100;i++){CHECK(b5_egress_step(&r,&p,true));opportunities+=!busy;}
#ifdef MP_FINAL_UNIFIED
    CHECK(opportunities==50 && progress_calls==100);
    printf("UNIFIED_AT_IDLE_SLOT_PASS opportunities=%u progress_calls=%u hardware=NOT_RUN\n",opportunities,progress_calls);
#else
    CHECK(opportunities==0);
    printf("LEGACY_DOUBLE_POLL_STARVATION_REPRODUCED opportunities=%u progress_calls=%u hardware=NOT_RUN\n",opportunities,progress_calls);
#endif
    return 0;
}
