/* 新B5编码与未启用快速路径的原编码逐字节对照；没有设备或网络边界。 */
#include "../data_model/model.h"
#include <assert.h>
#include <limits.h>
#include <stdio.h>
#include <string.h>
#include <time.h>
int reference_json(const MpFrame *,char *,size_t);
static uint32_t random_state=0x81926745u;
static int32_t next_value(void){random_state=random_state*1664525u+1013904223u;return (int32_t)random_state;}
int main(void){
    char original[2048],actual[2048];MpFrame f={0};unsigned checked=0;
    static const int32_t edges[]={INT32_MIN,INT32_MAX,-1000001,-1000000,-1001,-1000,-101,-100,-11,-10,-1,0,1,9,10,99,100,999,1000,999999,1000000};
    f.node=2;f.synthetic=true;f.timestamp=1793169000123ULL;f.epoch=2167682321u;f.boot=1;
    for(unsigned stream=0;stream<MP_STREAMS;stream++)for(unsigned round=0;round<500;round++){
        f.stream=(uint8_t)stream;f.valid=(round&1)!=0;f.replay=(round&2)!=0;f.seq=round;
        f.rate=stream==MP_ECG?250:stream==MP_RESP?50:0;f.count=f.rate?(stream==MP_ECG?100:50):2;
        for(unsigned i=0;i<f.count;i++)f.values[i]=round<sizeof(edges)/sizeof(edges[0])?edges[(round+i)%(sizeof(edges)/sizeof(edges[0]))]:next_value();
        int n=reference_json(&f,original,sizeof(original)),m=mp_json(&f,actual,sizeof(actual));
        assert(n==m && n>0 && !memcmp(original,actual,(size_t)n+1));checked++;
        size_t sizes[]={0,1,17,64,(size_t)n-1,(size_t)n,(size_t)n+1};
        for(unsigned j=0;j<sizeof(sizes)/sizeof(sizes[0]);j++){
            n=reference_json(&f,original,sizes[j]);m=mp_json(&f,actual,sizes[j]);
            assert(n==m);if(n)assert(!memcmp(original,actual,(size_t)n+1));checked++;
        }
    }
    f.stream=MP_ECG;f.rate=250;f.count=100;f.valid=true;f.replay=false;
    for(unsigned i=0;i<100;i++)f.values[i]=(int32_t)i*17-1000;
    unsigned total=0;clock_t start=clock();for(unsigned i=0;i<30000;i++)total+=(unsigned)reference_json(&f,original,sizeof(original));
    double old_s=(double)(clock()-start)/CLOCKS_PER_SEC;start=clock();for(unsigned i=0;i<30000;i++)total+=(unsigned)mp_json(&f,actual,sizeof(actual));
    double new_s=(double)(clock()-start)/CLOCKS_PER_SEC;
    printf("JSON_EQUIVALENCE_PASS checks=%u max_buffer=2048 reference_host_s=%.3f B5_host_s=%.3f checksum=%u ARM_throughput_NOT_PROVEN\n",checked,old_s,new_s,total);
    return 0;
}
