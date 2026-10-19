/* 真实bench/栈/队列，寄存器与传感器帧仅为Host夹具，不冒充实板证据。 */
#include "bench.h"
#include "link_policy.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>
volatile uint32_t g_uptime_ms;
static PhysicalTx tx;
static bool txok,hardware_ok=true;
static char output[32768];
static unsigned output_used;
void console(const char *s) {
    size_t n=strlen(s);assert(output_used+n<sizeof(output));memcpy(output+output_used,s,n+1);output_used+=(unsigned)n;
}
int mp_bxcan_init(void) {
    physical_invalidate();memset(&tx,0,sizeof(tx));
    if(!hardware_ok) return 0;
    mp_bus_set_online(true);physical_link_ready=true;
    bench_observe_registers(16000000,0x001c0001,0,0,0,0);return 1;
}
void mp_bus_hardware_poll(void) { /* Host无外设，接收只由下方input显式注入。 */ }
int mp_bus_transmit(MpCanFrame *f) {
    unsigned step=physical_tx_step(&tx,g_uptime_ms,true,txok,txok,false,false);
    if(step==LINK_START) bench_observe_tx(f,false);
    if(step==LINK_ACK) {bench_observe_tx(f,true);return 1;}
    if(step==LINK_FAULT) physical_invalidate();
    return 0;
}
static void advance(unsigned n) {while(n--) {g_uptime_ms++;bench_step();}}
static void input(uint16_t id,uint8_t dlc,uint32_t low,uint32_t high) {
    MpCanFrame f={0};f.ident=id;f.dlc=dlc;memcpy(f.data,&low,4);memcpy(f.data+4,&high,4);
    bench_observe_rx(&f);physical_receive(&f);
}
int main(int argc,char **argv) {
    (void)argc;
    bench_init();assert(!bench_stats.armed && !bench_stats.fault);
    advance(20);assert(bench_stats.tx_started==0 && !bench_stats.node_a_online && !bench_stats.node_b_online);
    assert(strstr(output,"OFFLINE_NO_CONFIG") && strstr(output,"TIME_BLOCKED"));
    bench_command('W');bench_command('M');assert(!bench_stats.armed); /* 没有联网命令入口。 */
    bench_command('S');advance(1);assert(bench_stats.nmt_started==1 && bench_stats.nmt_txok==0);
    advance(1);assert(bench_stats.nmt_txok==0);txok=true;advance(1);assert(bench_stats.nmt_txok==1);
    input(0x701,1,0,0);input(0x701,1,5,0);advance(2);
    assert(bench_stats.bootups==1 && bench_stats.node_a_online && !bench_stats.node_b_online);
    input(0x681,8,0,1);input(0x481,8,0,g_uptime_ms);input(0x381,8,0,0);advance(2);
    assert(bench_stats.rx[3].count==1 && bench_stats.quality==0 && bench_stats.model_frames==0);
    assert(bench_stats.scalar[0]==0 && !bench_stats.test_time); /* 无传感器/授时不填示例值。 */
#ifdef CAN_BENCH_IRQ
    MpCanFrame delayed={0};delayed.ident=0x381;delayed.dlc=8;
    /* 队列内已老化的PDO保留真实入队时刻，不因主循环取出而延长1500ms有效窗。 */
    physical_receive_at(&delayed,g_uptime_ms-1490u);
    assert(physical_fresh(1,2,g_uptime_ms));advance(11);
    assert(!physical_fresh(1,2,g_uptime_ms));
#endif
    bench_command('T');advance(2);assert(bench_stats.test_time && bench_stats.model_frames>0);
    assert(strstr(output,"BENCH_TEST_TIME_UNTRUSTED"));
    uint32_t starts_before_pause=bench_stats.tx_started;
    bench_command('P');assert(bench_stats.paused && !bench_stats.test_time && !bench_stats.last_valid);
    advance(1100);assert(bench_stats.tx_started==starts_before_pause && !bench_stats.fault);
    uint32_t boots_before=bench_stats.bootups;input(0x701,1,0,0);
    assert(bench_stats.bootups==boots_before+1 && !bench_stats.node_a_online);
    bench_command('G');advance(2);assert(!bench_stats.test_time && !bench_stats.fault);
    assert(!bench_stats.paused && bench_stats.tx_started>starts_before_pause);
    input(0x701,1,5,0);advance(1600);assert(!bench_stats.node_a_online && !bench_stats.node_b_online);
    assert(strstr(output,"NODE_B_OFFLINE") && strstr(output,"NMT_TXOK="));
    /* 各故障场景独立进程运行，故障后S/G不能自动解除锁止。 */
    if(argv[1] && strcmp(argv[1],"unexpected-b")==0) input(0x702,1,5,0);
    else {txok=false;bench_command('G');advance(110);}
    bench_step();assert(bench_stats.fault && !physical_link_ready);
    uint32_t starts=bench_stats.nmt_started;bench_command('S');bench_command('G');advance(1);
    assert(bench_stats.nmt_started==starts);
    puts("PASS CAN_ONLY_BENCH Host: disarmed/no-network/no-sensors/B-OFFLINE/NMT simulated-TXOK/time opt-in/HB timeout/fault latch; HARDWARE_NOT_RUN");
    return 0;
}
