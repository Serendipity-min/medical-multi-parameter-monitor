/* 排队CAN帧保留IRQ到达时刻，跨重新校时边界不能变成约49天后的到达。 */
#include "../dual_can/b4_gateway.c"
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#undef assert
#define assert(x) do { if(!(x)){fprintf(stderr,"FAIL line=%d\n",__LINE__);exit(3);} } while(0)

int main(void) {
    B4Gateway g={0};B4Segment *s=&g.segments[1];
    assert(mp_od_init(&s->od,3,&s->config)==0);
    g.now=2001;g.utc_at=2000;g.epoch=1800000001u;g.utc_valid=true;
    s->seen[3]=true;s->seen_at[3]=1990;
    mp_od_write(&s->od,0x3200,1,1800000000u);
    mp_od_write(&s->od,0x3200,2,1000);
    assert(sample_utc(&g,s,0x3200,1999,1999)==UINT64_C(1800000000999));
    assert(sample_utc(&g,s,0x3200,2001,2001)==UINT64_C(1800000001001));
    g.now=1;g.utc_at=0;s->seen_at[3]=UINT32_MAX-9;
    mp_od_write(&s->od,0x3200,2,UINT32_MAX-999);
    assert(sample_utc(&g,s,0x3200,UINT32_MAX,UINT32_MAX)==UINT64_C(1800000000999));
    /* 新鲜度和源端时间界限不放宽。 */
    s->seen_at[3]=g.now-1501;
    assert(sample_utc(&g,s,0x3200,UINT32_MAX,UINT32_MAX)==0);
    s->seen_at[3]=0;
    assert(sample_utc(&g,s,0x3200,4000,0)==0);
    puts("HOST_QUEUED_IRQ_RESYNC_AND_WRAP_PASS freshness_unchanged=1");
    return 0;
}
