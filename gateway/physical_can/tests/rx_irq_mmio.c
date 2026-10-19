/* Host三深度FIFO/W1C替身；同一个IRQ/静态队列实现参与测试，不冒充真实总线。 */
#include "rx_irq.h"
#include <assert.h>
#include <limits.h>
#include <stdio.h>
#include <string.h>

volatile uint32_t g_uptime_ms;
typedef struct {MpCanFrame f;uint32_t flags;} Raw;
static Raw fifo[3];
static unsigned used;
static uint32_t sticky,cycles,clear_writes,release_writes;
static bool inject_after_release;
uint32_t bench_clock_cycles(void) {return ++cycles;}
uint32_t bench_hw_rx_status(void) {return used|sticky;}
void bench_hw_rx_clear(uint32_t flags) {
    assert(!(flags&~(BENCH_FIFO_FULL|BENCH_FIFO_OVERRUN)));
    clear_writes|=flags;sticky&=~flags; /* W1C不释放帧，pending位不得被读改写污染。 */
}
void bench_hw_rx_read(MpCanFrame *f,uint32_t *flags) {assert(used);*f=fifo[0].f;*flags=fifo[0].flags;}
static void arrive(uint16_t id,uint8_t dlc,uint32_t flags,uint32_t serial,bool irq) {
    if(used==3) sticky|=BENCH_FIFO_OVERRUN;
    else {
        Raw *r=&fifo[used++];memset(r,0,sizeof(*r));r->f.ident=id;r->f.dlc=dlc;r->flags=flags;
        memcpy(r->f.data,&serial,4);if(used==3) sticky|=BENCH_FIFO_FULL;
    }
    if(irq) bench_rx_irq();
}
void bench_hw_rx_release(void) {
    assert(used);release_writes++;used--;
    memmove(fifo,fifo+1,used*sizeof(fifo[0]));
    if(inject_after_release) {inject_after_release=false;arrive(0x181,8,0,4,false);}
}
static void clean(void) {
    /* 只有独立Host场景重置夹具；生产重初始化不得清累计诊断。 */
    memset(&bench_rx_path,0,sizeof(bench_rx_path));used=0;sticky=cycles=clear_writes=release_writes=0;
    g_uptime_ms=0;inject_after_release=false;
}
static void burst_and_foreground_stall(void) {
    clean();
    /* 对照：旧轮询在前台停止期间接收4帧，第四帧已不可恢复。 */
    for(unsigned i=0;i<4;i++) arrive(0x181,8,0,i,false);
    assert(used==3 && (sticky&BENCH_FIFO_OVERRUN));
    clean();
    const uint16_t ids[]={0x701,0x381,0x481,0x681,0x181};
    for(unsigned i=0;i<5;i++) {g_uptime_ms=i;arrive(ids[i],i?8:1,0,i,true);}
    /* 主循环格式化/诊断暂停期间继续到达，IRQ仅入队，无任何协议函数链接在这里。 */
    for(unsigned i=5;i<100;i++) {g_uptime_ms=i;arrive(0x181,8,0,i,true);}
    assert(!used && !bench_rx_path.hw_overrun && !bench_rx_path.sw_overrun);
    assert(bench_rx_depth()==100 && bench_rx_path.high_water==100);
    BenchRxItem item;
    for(unsigned i=0;i<100;i++) {
        assert(bench_rx_take(&item));uint32_t serial;memcpy(&serial,item.frame.data,4);
        assert(serial==i && item.at_ms==i);
        if(i<5) assert(item.frame.ident==ids[i]);
    }
    assert(!bench_rx_take(&item));puts("PASS IRQ: 4+ burst/1Hz clustered PDO/foreground stall/arrival timestamp/order");
}
static void arrives_during_irq(void) {
    clean();for(unsigned i=1;i<=3;i++) arrive(0x181,8,0,i,false);
    inject_after_release=true;bench_rx_irq();
    /* 释放后立即补入第4帧，FIFO会再次达到3深度，因此FULL重新置位两次是正确语义。 */
    assert(bench_rx_depth()==4 && !bench_rx_path.hw_overrun && bench_rx_path.hw_full==2);
    assert(clear_writes==BENCH_FIFO_FULL && release_writes==4);
    puts("PASS IRQ: full3 plus fourth during release; exact W1C, all frames drained");
}
static void overflow_and_reinit(void) {
    clean();for(unsigned i=0;i<4;i++) arrive(0x181,8,0,i,true);
    BenchRxItem old;assert(bench_rx_take(&old));bench_rx_discard_pending();
    assert(bench_rx_path.reinit_discard==3 && bench_rx_path.high_water==4);
    arrive(0x181,8,0,99,true);assert(bench_rx_take(&old));
    uint32_t next;memcpy(&next,old.frame.data,4);assert(next==99 && !bench_rx_take(&old));
    clean();for(unsigned i=0;i<BENCH_RX_CAPACITY+1;i++) arrive(0x181,8,0,i,true);
    assert(!bench_rx_path.hw_overrun && bench_rx_path.sw_overrun==1);
    assert(bench_rx_path.fault_bits==BENCH_RX_SW_LOSS && bench_rx_depth()==BENCH_RX_CAPACITY);
    bench_rx_discard_pending();assert(bench_rx_depth()==0);
    assert(bench_rx_path.sw_overrun==1 && bench_rx_path.reinit_discard==BENCH_RX_CAPACITY);
    assert(bench_rx_path.high_water==BENCH_RX_CAPACITY && bench_rx_path.fault_bits);
    arrive(0x181,8,0,99,true);assert(!bench_rx_depth() && bench_rx_path.fault_discard==1);
    clean();for(unsigned i=0;i<4;i++) arrive(0x181,8,0,i,false);
    bench_rx_irq();assert(bench_rx_path.hw_overrun==1 && !bench_rx_path.sw_overrun);
    assert(clear_writes==(BENCH_FIFO_FULL|BENCH_FIFO_OVERRUN));
    bench_rx_discard_pending();bench_rx_irq();assert(bench_rx_path.hw_overrun==1);
    puts("PASS IRQ: distinct HW/SW loss; lockout and reinit preserve fault/high-water/counters");
}
static void bad_types_and_wrap(void) {
    for(unsigned bad=0;bad<3;bad++) {
        clean();arrive(0x181,bad==2?9:8,bad==0?4u:bad==1?2u:0u,0,true);
        assert(bench_rx_path.bad==1 && !bench_rx_depth() && bench_rx_path.fault_bits==BENCH_RX_BAD_FRAME);
    }
    clean();atomic_store(&bench_rx_path.head,UINT32_MAX-2u);atomic_store(&bench_rx_path.tail,UINT32_MAX-2u);
    for(unsigned i=0;i<12;i++) {g_uptime_ms=UINT32_MAX-5u+i;arrive(0x181,8,0,i,true);}
    for(unsigned i=0;i<12;i++) {
        BenchRxItem item;assert(bench_rx_take(&item));uint32_t serial;memcpy(&serial,item.frame.data,4);
        assert(serial==i && item.at_ms==UINT32_MAX-5u+i);
    }
    assert(!bench_rx_depth());puts("PASS IRQ: IDE/RTR/DLC filtering, ring index and timestamp wrap");
}
int main(void) {
    burst_and_foreground_stall();arrives_during_irq();overflow_and_reinit();bad_types_and_wrap();
    puts("PASS H2R MMIO/SPSC; no hardware accessed, no real sensor/physical acceptance claimed");return 0;
}
