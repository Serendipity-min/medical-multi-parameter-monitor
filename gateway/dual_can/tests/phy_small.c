/* 合成帧经过实际五节点网关，检查NMT先于TIME以及硬截止。 */
#include "b4_bench.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>
static B4Bench bench;
static unsigned controls,temps;
int b4_bus_transmit(unsigned bus,const MpCanFrame *f) {
    assert(bus==1);
    if(f->ident==0) {
        assert(controls<2 && f->dlc==2);
        assert(f->data[0]==(controls?CO_NMT_ENTER_OPERATIONAL:CO_NMT_ENTER_PRE_OPERATIONAL));
        assert(f->data[1]==(controls?4:2));controls++;
    }
    if(f->ident==0x100)assert(controls==2);
    return 1;
}
static void inject(unsigned id,const void *data,unsigned n,uint32_t tick) {
    MpCanFrame f={0};f.ident=id;f.dlc=n;memcpy(f.data,data,n);
    b4_gateway_receive(&bench.gateway,1,&f,tick);
}
int main(void) {
    assert((B4_BENCH_LIMIT_MS==15000u || B4_BENCH_LIMIT_MS==300000u) && !b4_bench_init(&bench,0));
    for(uint32_t now=0;now<B4_BENCH_LIMIT_MS;now++) {
        b4_bench_step(&bench,now);
        if(now%500==0) {
            uint8_t b=127,d=5;inject(0x702,&b,1,now);inject(0x704,&d,1,now);
        }
        if(now%1000==0) {
            uint32_t q[2]={16,1},anchor[2]={B4_BENCH_EPOCH+now/1000,now};
            uint16_t value[4]={0,0,2370,10};
            inject(0x684,q,8,now);inject(0x484,anchor,8,now);inject(0x384,value,8,now);
        }
        for(unsigned i=0;i<B4_BENCH_RING;i++) {
            MpFrame *f=&bench.records[i];
            if(f->stream==MP_TEMP && f->node==4 && f->valid) {
                assert(f->values[0]==2370);temps++;
            }
            assert(!(f->node==2 && f->stream==MP_ECG && f->valid));
        }
    }
    assert(controls==2 && temps && !bench.diag.stopped);
    b4_bench_step(&bench,B4_BENCH_LIMIT_MS);assert(bench.diag.stopped && !bench.gateway.utc_valid);
    b4_bench_step(&bench,B4_BENCH_LIMIT_MS+1000u);assert(controls==2 && bench.diag.elapsed_ms==B4_BENCH_LIMIT_MS);
    b4_gateway_close(&bench.gateway);printf("PHY_SMALL_NMT_BEFORE_TIME_TEMP_AND_%uMS_STOP_PASS\n",B4_BENCH_LIMIT_MS);return 0;
}
