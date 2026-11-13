#include "transport_bench_control.h"
#include "transport_bench_source.h"
#include <assert.h>
#include <stdio.h>

static int command(BenchControl *control,const char *line,uint32_t tick){
    int accepted=0;
    while(*line)accepted+=bench_byte(control,*line++,tick);
    return accepted;
}

int main(void){
    const char *valid[]={"BENCH N115\r\n","BENCH N230\n","BENCH P115\r\n","BENCH P230\n"};
    for(unsigned i=0;i<4;i++){
        BenchControl c={0};
        assert(!command(&c,"START\r\nKEY\nBENCH P500\nBENCH N115xxxxxxxxxxxxx\n",1));
        assert(command(&c,valid[i],44999)==1 && c.state==BENCH_OPENING);
        assert(c.pass==(i>=2) && c.fast==(int)(i%2));
        assert(!command(&c,valid[i],1));
        c.state=BENCH_DIRTY;
        assert(!command(&c,valid[i],1));
        c.state=BENCH_RESTORED;
        assert(!command(&c,valid[i],1));
    }
    BenchControl c={0};
    assert(!command(&c,valid[0],45000) && c.state==BENCH_DISARMED);
    unsigned total=0;
    for(unsigned tick=200;tick<=BENCH_SOURCE_MS;tick+=200){
        for(unsigned i=0;i<BENCH_STREAM_COUNT;i++){
            const BenchStream *s=&bench_streams[i];unsigned seq=bench_sequence(s,tick);
            if(!seq)continue;
            MpFrame f;bench_frame(&f,s,seq,1800000000000ULL+tick,1800000000u,5000u);
            char topic[120],body[2048];
            assert(f.synthetic && f.valid && mp_topic(&f,topic,sizeof topic) && mp_json(&f,body,sizeof body));
            printf("%s\t%s\n",topic,body);total++;
        }
    }
    assert(total==1261);
}
