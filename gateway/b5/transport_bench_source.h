#ifndef MP_TRANSPORT_BENCH_SOURCE_H
#define MP_TRANSPORT_BENCH_SOURCE_H

#include "../data_model/model.h"

typedef struct {
    uint8_t node,stream,count;
    uint16_t period,rate;
    int32_t value;
} BenchStream;

static const BenchStream bench_streams[]={
    {2,MP_ECG,100,400,250,1103},
    {2,MP_RESP,50,1000,50,10000}, {1,MP_PPG,50,1000,50,1230000},
    {1,MP_SPO2,1,1000,0,9750}, {1,MP_PR,1,1000,0,7200},
    {2,MP_HR,1,1000,0,6000}, {2,MP_RR,1,1000,0,1800}, {4,MP_TEMP,1,1000,0,2450},
    {3,MP_GATEWAY_STATUS,1,5000,0,1}, {1,MP_NODE_STATUS,1,5000,0,1},
    {2,MP_NODE_STATUS,1,5000,0,1}, {4,MP_NODE_STATUS,1,5000,0,1}, {5,MP_NODE_STATUS,1,5000,0,1},
    {5,MP_NIBP,2,0,0,1180}
};
enum { BENCH_STREAM_COUNT=sizeof bench_streams/sizeof bench_streams[0] };

static inline unsigned bench_sequence(const BenchStream *source,uint32_t tick){
    if(!source->period)return tick==2000u?1u:0u;
    return tick%source->period==0?tick/source->period:0u;
}

static inline void bench_frame(MpFrame *frame,const BenchStream *source,unsigned seq,
                               uint64_t utc,uint32_t epoch,uint32_t boot){
    *frame=(MpFrame){.node=source->node,.stream=source->stream,.count=source->count,
        .rate=source->rate,.timestamp=utc,.seq=seq,.epoch=epoch,.boot=boot,.valid=true,.synthetic=true};
    for(unsigned i=0;i<source->count;i++){
        int32_t value=source->value+(source->rate?(int32_t)(i+seq%10u):0);
        frame->values[i]=source->rate && source->stream!=MP_PPG && (i&1u)?-value:value;
    }
    if(source->stream==MP_NIBP)frame->values[1]=760;
}
#endif
