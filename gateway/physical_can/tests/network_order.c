/* Host网络前台停顿→IRQ排队→真实RPDO/Adapter：合成帧，不读取或生成板端真人采样。 */
#include "physical.h"
#include "mp_adapter.h"
#include "rx_irq.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>
volatile uint32_t g_uptime_ms;
static MpStack stack;
static MpAdapter adapter;
static MpRouter router;
static MpCanFrame hardware;
static bool pending,coalesced_reference;
static unsigned batches,points;
uint32_t bench_clock_cycles(void) {return g_uptime_ms*16000u;}
uint32_t bench_hw_rx_status(void) {return pending?1:0;}
void bench_hw_rx_clear(uint32_t flags) {(void)flags;}
void bench_hw_rx_release(void) {pending=false;}
void bench_hw_rx_read(MpCanFrame *f,uint32_t *flags) {*f=hardware;*flags=0;}
void mp_bus_hardware_poll(void) {
    BenchRxItem item;
    /* 仅Host负对照重现旧批量交付；生产目标不编译这个夹具。 */
    if(coalesced_reference) {
        while(bench_rx_take(&item)) physical_receive_at(&item.frame,item.at_ms);
        return;
    }
    /* 同ARM准入顺序：每个协议tick交付一帧，避免单份RPDO镜像吞掉中间点。 */
    if(bench_rx_peek(&item) && physical_receive_due(item.at_ms)) {
        assert(bench_rx_take(&item));physical_receive_at(&item.frame,item.at_ms);
    }
}
static void arrive(unsigned id,unsigned dlc,uint32_t a,uint32_t b) {
    assert(!pending);memset(&hardware,0,sizeof(hardware));hardware.ident=id;hardware.dlc=dlc;
    memcpy(hardware.data,&a,4);memcpy(hardware.data+4,&b,4);pending=true;bench_rx_irq();
}
static void consume(void) {
    MpFrame f;
    while(mp_router_take(&router,&f,stack.milliseconds)) {
        if(f.stream==MP_PPG) {
            assert(f.count==50 && f.rate==50);
            for(unsigned i=1;i<f.count;i++) assert(f.values[i]-f.values[i-1]==2000);
            batches++;points+=f.count;
        }
        assert(!(f.node==2 && f.stream!=MP_NODE_STATUS && f.stream!=MP_FAULT));
        mp_router_ack(&router,&f,true);
    }
}
int main(int argc,char **argv) {
    (void)argv;coalesced_reference=argc>1;
    assert(!mp_stack_init(&stack,1800000000u));physical_link_ready=true;
    mp_adapter_init(&adapter);mp_router_init(&router);mp_router_online(&router,true);
    for(g_uptime_ms=1;g_uptime_ms<=3400;g_uptime_ms++) {
        unsigned t=g_uptime_ms;
        if(t==1) arrive(0x701,1,0,0);
        if(t==2 || t%500==0) arrive(0x701,1,5,0);
        if(t==3 || t%1000==0) {
            arrive(0x681,8,0x10fu,1);
            arrive(0x481,8,1800000000u+t/1000,t-t%1000);
            arrive(0x381,8,9800u|(7200u<<16),1180u|(760u<<16));
        }
        if(t%20==0) arrive(0x181,8,t*100,t);
        /* 模拟AT/TLS工作占用前台100ms，IRQ仍把到达帧保留在固定队列。 */
        if(t>=1000 && t<1100) continue;
        while(stack.milliseconds<g_uptime_ms) {
            mp_stack_tick(&stack);mp_adapter_poll(&adapter,&stack,&router);consume();
        }
    }
    assert(batches>=3 && points>=150 && !bench_rx_path.hw_overrun && !bench_rx_path.sw_overrun);
    assert(!mp_stack_online(&stack,2));
    mp_stack_close(&stack);puts("IRQ queue / 100ms foreground stall / every PPG point / B OFFLINE PASS");
    return 0;
}
