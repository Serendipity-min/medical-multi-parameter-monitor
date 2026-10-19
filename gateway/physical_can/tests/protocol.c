/* 外部帧注入仅在 Host：编译的是 Gateway-only 栈，不在候选固件内放 A/B 生产者。 */
#include "physical.h"
#include "mp_adapter.h"
#include "link_policy.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>
static MpStack stack;
static MpAdapter adapter;
static MpRouter router;
static unsigned ppg_frames,scalars,b_offline,b_measurements;
/* 隔离联网目标显式标记非个人测试源；常规物理目标仍按原质量位判断。 */
#ifdef MP_H3_TEST_SOURCE
#define EXPECT_SYNTHETIC true
#else
#define EXPECT_SYNTHETIC false
#endif
static void input(uint16_t id,uint8_t dlc,uint32_t a,uint32_t b) {
    MpCanFrame f={0};f.ident=id;f.dlc=dlc;memcpy(f.data,&a,4);memcpy(f.data+4,&b,4);physical_receive(&f);
}
static void drain(void) {
    MpFrame f;
    while(mp_router_take(&router,&f,stack.milliseconds)) {
        if(f.node==2) {if(f.stream==MP_NODE_STATUS && !f.valid) b_offline++;else if(f.stream!=MP_FAULT) b_measurements++;}
        if(f.stream==MP_PPG) {assert(f.synthetic==EXPECT_SYNTHETIC && f.count==50 && f.rate==50);assert(f.timestamp<((uint64_t)stack.epoch*1000+stack.milliseconds+1000));ppg_frames++;}
        if(f.stream==MP_SPO2) {assert(f.values[0]==9800 && f.synthetic==EXPECT_SYNTHETIC);scalars++;}
        mp_router_ack(&router,&f,true);
    }
}
static void tick(void) {mp_stack_tick(&stack);mp_adapter_poll(&adapter,&stack,&router);drain();}
int main(void) {
    uint32_t btr;
    assert(physical_btr(16000000,&btr) && btr==((1u<<20)|(12u<<16)|1u));
    assert(physical_btr(42000000,&btr) && btr==((1u<<20)|(10u<<16)|5u));
    assert(!physical_btr(1234567,&btr));
    PhysicalTx tx={0};assert(physical_tx_step(&tx,0,true,false,false,false,false)==LINK_START);
    assert(physical_tx_step(&tx,10,false,false,false,false,false)==LINK_WAIT);
    assert(physical_tx_step(&tx,20,true,true,true,false,false)==LINK_ACK && tx.acked==1);
    assert(physical_tx_step(&tx,30,true,false,false,false,false)==LINK_START);
    assert(physical_tx_step(&tx,130,false,false,false,false,false)==LINK_FAULT && tx.failed==1);
    assert(physical_tx_step(&tx,131,true,true,true,false,false)==LINK_FAULT); /* 锁止不假恢复 */
    memset(&tx,0,sizeof(tx));assert(physical_tx_step(&tx,0,true,false,false,false,true)==LINK_FAULT);
    memset(&tx,0,sizeof(tx));physical_tx_step(&tx,0xFFFFFFF0u,true,false,false,false,false);
    assert(physical_tx_step(&tx,85,false,false,false,false,false)==LINK_FAULT); /* 回绕超时 */
    puts("PCLK1 / normal BTR / TX ACK gating / timeout / bus-off / explicit recovery policy PASS");
    assert(!mp_stack_init(&stack,0));physical_link_ready=true;
    assert(!stack.nodes[0].co && !stack.nodes[1].co && stack.nodes[2].co);
    mp_adapter_init(&adapter);mp_router_init(&router);mp_router_online(&router,true);
    for(unsigned i=0;i<100;i++) tick();assert(!mp_stack_online(&stack,1) && !mp_stack_online(&stack,2));
    assert(!ppg_frames && !scalars); /* 无可信时间、无外部数据不造读数。 */
    stack.epoch=1800000000u;
    input(0x701,1,0,0);tick();input(0x701,1,5,0);tick();
    for(unsigned i=0;i<3200;i++) {
        unsigned next=stack.milliseconds+1;
        if(next%500==0) input(0x701,1,5,0);
        if(next%1000==0) {
            input(0x681,8,0x10Fu,1); /* 真实来源位、显式重采样标识 */
            input(0x481,8,stack.epoch+next/1000,next-next%1000);
            input(0x381,8,9800u|(7200u<<16),1180u|(760u<<16));
        }
        if(next%20==0) input(0x181,8,next*100,next);
        tick();
    }
    assert(mp_stack_online(&stack,1) && !mp_stack_online(&stack,2));
    assert(ppg_frames>=2 && scalars>=1 && b_offline && !b_measurements);
    input(0x181,7,0,0);assert(physical_malformed==1);
    uint32_t old_generation=physical_nodes[0].session_generation;
    /* Heartbeat 持续也不能让静止 PDO 永久有效；部分批次丢弃。 */
    unsigned old_ppg=ppg_frames,old_scalar=scalars;
    for(unsigned i=0;i<1700;i++) {if(i%500==0) input(0x701,1,5,0);tick();}
    assert(ppg_frames==old_ppg && scalars==old_scalar && !physical_fresh(1,4,stack.milliseconds));
    for(unsigned i=0;i<1600;i++) tick();assert(!mp_stack_online(&stack,1));
    input(0x701,1,0,0);input(0x681,8,0x10Fu,1);tick();
    assert(physical_nodes[0].session_generation>old_generation && !physical_fresh(1,3,stack.milliseconds));
    physical_invalidate();assert(!mp_stack_online(&stack,1) && !mp_stack_online(&stack,2));
    assert(mp_stack_restart(&stack,1)==-1);assert(!mp_stack_restart(&stack,3));physical_link_ready=true;mp_bus_set_online(true);
    assert(!physical_nodes[0].seen[3] && !physical_nodes[1].seen[4]);
    /* 绝对 UTC 跨本地32位计数回绕仍严格递增，不能回到开机日期。 */
    stack.milliseconds=0xFFFFFFFEu;tick();uint64_t before_wrap=physical_now(&stack);
    tick();assert(physical_now(&stack)==before_wrap+1u);tick();assert(physical_now(&stack)==before_wrap+2u);
    mp_stack_close(&stack);puts("Gateway-only / external RPDO / A valid / B OFFLINE / stale / restart PASS");
    return 0;
}
