/* 固定16槽实时队列：短突发不制造历史，真实过载/断链仍保留REPLAY语义。 */
#include "../storage/router.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>
static MpFrame wave(unsigned seq,unsigned stream){
    MpFrame f={0};f.node=2;f.stream=(uint8_t)stream;f.rate=stream==MP_ECG?250:50;
    f.count=stream==MP_ECG?100:50;f.synthetic=true;f.valid=true;f.seq=seq;f.timestamp=1700000000000ULL+seq*400;
    return f;
}
int main(void){
    MpRouter r;MpFrame f,out;mp_router_init(&r);mp_router_online(&r,true);
    for(unsigned seq=1;seq<=3;seq++){f=wave(seq,MP_ECG);mp_router_put(&r,&f);}
    for(unsigned seq=1;seq<=2;seq++){f=wave(seq,MP_RESP);mp_router_put(&r,&f);}
    assert(r.ln==5 && !r.cn && !r.stored && !r.dropped);
    for(unsigned seq=1;seq<=3;seq++){assert(mp_router_take(&r,&out,100));assert(out.seq==seq && out.stream==MP_ECG && !out.replay);mp_router_ack(&r,&out,true);}
    for(unsigned seq=1;seq<=2;seq++){assert(mp_router_take(&r,&out,100));assert(out.seq==seq && out.stream==MP_RESP && !out.replay);mp_router_ack(&r,&out,true);}
    assert(!r.ln && !r.cn && !r.replayed);
    const unsigned scalars[]={MP_HR,MP_RR,MP_TEMP};
    for(unsigned i=0;i<3;i++){
        unsigned stream=scalars[i];
        mp_router_init(&r);mp_router_online(&r,true);
        f=wave(1,stream);f.rate=0;f.count=1;f.valid=stream==MP_HR;
        mp_router_put(&r,&f);f.seq=2;mp_router_put(&r,&f);
        assert(r.ln==2 && !r.cn);
        for(unsigned seq=1;seq<=2;seq++){
            assert(mp_router_take(&r,&out,100));assert(out.seq==seq && !out.replay);
            assert(out.valid==(stream==MP_HR));mp_router_ack(&r,&out,true);
        }
    }
    f=wave(1,MP_HR);f.node=1;f.rate=0;f.count=1;mp_router_put(&r,&f);f.seq=2;mp_router_put(&r,&f);
    assert(r.ln==1 && r.cn==1);assert(mp_router_take(&r,&out,100));assert(out.seq==2);
    mp_router_init(&r);mp_router_online(&r,true);
    f=wave(1,MP_NODE_STATUS);f.rate=0;f.count=1;mp_router_put(&r,&f);f.seq=2;mp_router_put(&r,&f);
    assert(r.ln==1 && !r.cn);assert(mp_router_take(&r,&out,100));assert(out.seq==2);
    mp_router_init(&r);mp_router_online(&r,true);
    for(unsigned seq=1;seq<=MP_LIVE_CAPACITY+1;seq++){f=wave(seq,MP_ECG);mp_router_put(&r,&f);}
    assert(r.ln==MP_LIVE_CAPACITY && r.cn==1 && r.stored==1 && !r.dropped);
    mp_router_online(&r,false);assert(!r.ln && r.cn==MP_LIVE_CAPACITY+1);
    mp_router_online(&r,true);assert(!mp_router_take(&r,&out,3000));
    f=wave(100,MP_ECG);mp_router_put(&r,&f);assert(mp_router_take(&r,&out,3000) && !out.replay);mp_router_ack(&r,&out,true);
    assert(mp_router_take(&r,&out,3000) && out.replay && out.seq==1 && out.timestamp==1700000000400ULL);
    mp_router_init(&r);mp_router_online(&r,true);
    for(unsigned seq=1;seq<=MP_LIVE_CAPACITY+MP_CACHE_CAPACITY+1;seq++){f=wave(seq,MP_ECG);mp_router_put(&r,&f);}
    assert(r.ln==MP_LIVE_CAPACITY && r.cn==MP_CACHE_CAPACITY && r.dropped==1);
    puts("B5_TELEMETRY_FIFO_PASS wave_and_scalar_order validity_preserved legacy_and_status_coalescing overload_history reconnect_capacity_preserved");
    return 0;
}
