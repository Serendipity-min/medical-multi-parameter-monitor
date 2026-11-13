#ifndef MP_TRANSPORT_BENCH_CONTROL_H
#define MP_TRANSPORT_BENCH_CONTROL_H
#include <stdint.h>
#include <string.h>

enum { BENCH_ARM_MS=45000, BENCH_OPEN_MS=60000, BENCH_SOURCE_MS=120000,
       BENCH_DRAIN_MS=9000, BENCH_CLEAN_MS=8000, BENCH_HARD_MS=210000 };
typedef enum { BENCH_DISARMED,BENCH_OPENING,BENCH_RUNNING,BENCH_DRAINING,
               BENCH_RESTORED,BENCH_DIRTY } BenchState;
typedef struct { BenchState state; char command[16]; unsigned used; int pass,fast; } BenchControl;
static inline int bench_byte(BenchControl *ctl,int c,uint32_t now){
    if(ctl->state!=BENCH_DISARMED || now>=BENCH_ARM_MS)return 0;
    if(c!='\n'){
        if(ctl->used<sizeof ctl->command)ctl->command[ctl->used++]=(char)c;
        return 0;
    }
    unsigned size=ctl->used;ctl->used=0;
    if(size==11u && ctl->command[10]=='\r')size--;
    if(size!=10u || memcmp(ctl->command,"BENCH ",6))return 0;
    char mode=ctl->command[6];
    const char *rate=ctl->command+7;
    if((mode!='N' && mode!='P') || (memcmp(rate,"115",3) && memcmp(rate,"230",3)))return 0;
    ctl->pass=mode=='P';ctl->fast=rate[0]=='2';ctl->state=BENCH_OPENING;
    return 1;
}
#endif
