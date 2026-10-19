/* 使用真实 CANopen 队列及发送策略；寄存器完成/TXOK 由 Host 注入，不代表实板 ACK。 */
#include "physical.h"
#include "link_policy.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>
static MpStack stack;
static PhysicalTx tx;
static bool hardware_ok=true,ready=true,complete,txok,fill_queue;
static unsigned starts,acks;
static uint32_t now;

int mp_bxcan_init(void) {
    /* 与实驱动一样，初始化先丢弃待发队列，再建立链路。 */
    physical_invalidate();memset(&tx,0,sizeof(tx));complete=txok=false;
    if(!hardware_ok) return 0;
    if(ready) {mp_bus_set_online(true);physical_link_ready=true;}
    /* 容量负例在入口提交前占满真实128槽队列，验证错误返回而非无限重试。 */
    if(fill_queue) for(unsigned i=0;i<128;i++) mp_stack_nmt(&stack,0,CO_NMT_ENTER_OPERATIONAL);
    return 1;
}
int mp_bus_transmit(MpCanFrame *frame) {
    assert(frame->ident==0 && frame->dlc==2);
    assert(frame->data[0]==CO_NMT_ENTER_OPERATIONAL && frame->data[1]==0);
    unsigned step=physical_tx_step(&tx,now,true,complete,txok,false,false);
    if(step==LINK_START) starts++;
    if(step==LINK_ACK) {acks++;return 1;}
    if(step==LINK_FAULT) physical_invalidate();
    return 0;
}
#ifndef H0_BASELINE
static void acknowledge(void) {
    unsigned before=acks,submitted=starts;
    assert(mp_bus_frames()==0);
    mp_bus_poll();assert(starts==submitted+1 && acks==before && mp_bus_frames()==0);
    now++;mp_bus_poll();assert(starts==submitted+1 && mp_bus_frames()==0);
    /* 完成位不等于 TXOK；没有 TXOK 时队首必须继续保留。 */
    complete=true;now++;mp_bus_poll();assert(acks==before && mp_bus_frames()==0);
    txok=true;now++;mp_bus_poll();assert(acks==before+1 && mp_bus_frames()==1);
    for(unsigned i=0;i<10;i++) mp_bus_poll();
    assert(starts==submitted+1 && acks==before+1);
}
#endif
int main(int argc,char **argv) {
    if(argc>1 && strcmp(argv[1],"baseline")==0) {
        /* 用受审基线的真实 gateway_init 排队行为复现原 main 初始化顺序。 */
        assert(mp_stack_init(&stack,0)==0);assert(mp_bxcan_init());
        complete=txok=true;mp_bus_poll();
        unsigned boot_acks=acks;
        printf("BASELINE boot expected_NMT_TXOK=1 actual=%u dropped=%lu\n",boot_acks,(unsigned long)mp_bus_dropped());
        assert(mp_stack_restart(&stack,3)==0);assert(mp_bxcan_init());
        complete=txok=true;mp_bus_poll();
        unsigned restart_acks=acks-boot_acks;
        printf("BASELINE G expected_NMT_TXOK=1 actual=%u dropped=%lu\n",restart_acks,(unsigned long)mp_bus_dropped());
        mp_stack_close(&stack);return boot_acks==1 && restart_acks==1?0:1;
    }
#ifndef H0_BASELINE
    assert(mp_stack_init(&stack,0)==0);
    mp_stack_nmt(&stack,0,CO_NMT_ENTER_OPERATIONAL);
    assert(mp_bxcan_init());mp_bus_poll();
    assert(starts==0 && mp_bus_frames()==0 && mp_bus_dropped()==1);
    puts("PASS negative: preloaded START discarded by physical init");
    mp_stack_close(&stack);
    assert(physical_gateway_open(&stack,false)==0);acknowledge();
    puts("PASS boot: one START retained until simulated driver TXOK");
    assert(physical_gateway_open(&stack,true)==0 && stack.resets[2]==1);acknowledge();
    puts("PASS explicit G: one START retained until simulated driver TXOK");
    unsigned before=starts;
    hardware_ok=false;assert(physical_gateway_open(&stack,true)!=0);
    mp_bus_poll();assert(!physical_link_ready && starts==before);
    hardware_ok=true;ready=false;assert(physical_gateway_open(&stack,true)!=0);
    mp_bus_poll();assert(!physical_link_ready && starts==before);
    puts("PASS absent/unfinished physical link: failure, no START success");
    ready=true;assert(physical_gateway_open(&stack,true)==0);acknowledge();
    assert(!mp_stack_online(&stack,2));
    puts("PASS recovery after failed G; absent Node-B remains OFFLINE; HARDWARE_NOT_RUN");
    before=starts;fill_queue=true;
    assert(physical_gateway_open(&stack,true)!=0);mp_bus_poll();
    assert(!physical_link_ready && starts==before && mp_bus_frames()==0);
    puts("PASS bounded enqueue overflow: failure and pending queue invalidated");
    mp_stack_close(&stack);
#endif
    return 0;
}
