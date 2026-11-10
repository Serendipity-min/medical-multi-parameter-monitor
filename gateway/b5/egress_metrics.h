#ifndef B5_EGRESS_METRICS_H
#define B5_EGRESS_METRICS_H
#include <stdint.h>
/* 桶内只声明上界；不能把周期采样的最后耗时当p99。 */
typedef struct { uint32_t count, max, bins[12]; } B5Latency;
static inline void b5_latency_add(B5Latency *s,uint32_t ms) {
    static const uint16_t bounds[]={1,5,10,25,50,100,250,500,1000,1500,2516};
    unsigned i=0;while(i<11 && ms>bounds[i])i++;
    s->count++;s->bins[i]++;if(ms>s->max)s->max=ms;
}
static inline uint32_t b5_latency_percentile(const B5Latency *s,unsigned percent) {
    static const uint16_t bounds[]={1,5,10,25,50,100,250,500,1000,1500,2516};
    uint32_t total=0,target=
#ifdef MP_PRODUCTION_DIAG
        s->count/100*percent+(s->count%100*percent+99)/100;
#else
        (s->count*percent+99)/100;
#endif
    if(!target)return 0;
    for(unsigned i=0;i<12;i++){total+=s->bins[i];if(total>=target)return i==11?s->max:bounds[i];}
    return s->max;
}
#endif
