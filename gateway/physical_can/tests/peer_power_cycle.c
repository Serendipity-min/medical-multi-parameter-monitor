/* 编译真实联网IRQ驱动/协议/队列；只替换MMIO，不连接开发板。 */
#include "physical.h"
#include "mp_adapter.h"
#include "peer_tx.h"
#include "link_policy.h"
#include "rx_metrics.h"
#include "stm32f4xx.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>
HostCan host_can;
HostDebug host_debug;
HostDwt host_dwt;
volatile uint32_t g_uptime_ms;
static MpStack stack;
static MpAdapter adapter;
static MpRouter router;
static bool present=true,stuck;
static unsigned forced_error,starts,nmt_starts,time_starts,invalid_values,valid_measurements;
extern void CAN1_RX0_IRQHandler(void);

static void arrive(unsigned id,unsigned dlc,uint32_t a,uint32_t b) {
    host_can.RF0R=1;host_can.sFIFOMailBox[0].RIR=id<<21;host_can.sFIFOMailBox[0].RDTR=dlc;
    host_can.sFIFOMailBox[0].RDLR=a;host_can.sFIFOMailBox[0].RDHR=b;CAN1_RX0_IRQHandler();
}
static void advance(unsigned ms) {
    while(ms--) {
        g_uptime_ms++;host_dwt.CYCCNT+=8000;
        if(host_can.sTxMailBox[0].TIR&1u) {
            if(!stuck) {
                unsigned id=host_can.sTxMailBox[0].TIR>>21;
                starts++;nmt_starts+=id==0;time_starts+=id==0x100;
                host_can.sTxMailBox[0].TIR=0;
                host_can.TSR=CAN_TSR_TME0|CAN_TSR_RQCP0;
                if(present && !forced_error) {host_can.TSR|=CAN_TSR_TXOK0;host_can.ESR=0;}
                else {host_can.TSR|=CAN_TSR_TERR0;host_can.ESR=(forced_error?forced_error:3u)<<4;}
            }
        } else host_can.TSR=CAN_TSR_TME0;
        mp_stack_tick(&stack);mp_adapter_poll(&adapter,&stack,&router);
        MpFrame f;
        while(mp_router_take(&router,&f,g_uptime_ms)) {
            assert(!(f.node==2 && f.valid && f.stream==MP_NODE_STATUS));
            if(f.node==1 && (f.stream==MP_SPO2 || f.stream==MP_PR))invalid_values+=!f.valid;
            if(f.node==1 && f.valid && (f.stream==MP_SPO2 || f.stream==MP_PR || f.stream==MP_PPG))valid_measurements++;
            mp_router_ack(&router,&f,true);
        }
    }
}
static void queue_time(void) {
    CO_CANtx_t frame={0};frame.ident=0x100;frame.DLC=6;
    assert(CO_CANsend(stack.nodes[2].co->CANmodule,&frame)==CO_ERROR_NO);
}
static void policy_checks(void) {
    /* 用未修改的bench策略复现旧失败，再证明新策略保留100ms和硬故障锁止。 */
    PhysicalTx old={0};physical_tx_step(&old,0,true,false,false,false,false);
    assert(physical_tx_step(&old,1,true,true,false,true,false)==LINK_FAULT);
    puts("BASELINE: no ACK becomes permanent LINK_FAULT");
    PeerTx p={0};assert(peer_tx_step(&p,0xFFFFFFF0u,7,true,false,false,false,false,7,false)==PEER_TX_START);
    assert(peer_tx_step(&p,0xFFFFFFF1u,7,true,true,false,true,false,3,false)==PEER_TX_NO_ACK);
    assert(!peer_tx_resume(&p,7));assert(peer_tx_resume(&p,8));
    assert(peer_tx_step(&p,0,8,true,false,false,false,false,7,false)==PEER_TX_START);
    assert(peer_tx_step(&p,99,8,true,true,false,false,true,7,false)==PEER_TX_WAIT);
    assert(peer_tx_step(&p,100,8,true,false,false,false,false,7,false)==PEER_TX_FAULT);
    assert(!peer_tx_resume(&p,9));
    memset(&p,0,sizeof(p));assert(peer_tx_step(&p,0,0,true,false,false,false,false,7,true)==PEER_TX_FAULT);
    assert(!peer_tx_resume(&p,1));
    puts("PASS: ACK-only recovery / new heartbeat required / arbitration budget / BOFF latch");
}
int main(int argc,char **argv) {
    policy_checks();assert(!mp_stack_init(&stack,1800000000u));physical_link_ready=true;
    mp_adapter_init(&adapter);mp_router_init(&router);mp_router_online(&router,true);
    arrive(0x701,1,0,0);advance(1);arrive(0x701,1,5,0);advance(3);
    assert(mp_stack_online(&stack,1) && !mp_stack_online(&stack,2));
    if(argc>1) {
        /* 先消费注入的BOFF，不能让下一步模拟硬件TXOK把该寄存器覆盖。 */
        if(!strcmp(argv[1],"busoff")) {host_can.ESR=CAN_ESR_BOFF;mp_bus_poll();}
        else {queue_time();advance(1);if(!strcmp(argv[1],"stuck"))stuck=true;else forced_error=1;}
        advance(105);assert(!physical_link_ready && physical_rx_metrics.fault==8);
        uint32_t esr=physical_rx_metrics.fault_esr,tsr=physical_rx_metrics.fault_tsr;
        present=true;forced_error=0;stuck=false;host_can.ESR=0;
        arrive(0x701,1,5,0);advance(10);
        assert(!physical_link_ready && physical_rx_metrics.fault_esr==esr && physical_rx_metrics.fault_tsr==tsr);
        puts("PASS: real driver hard fault snapshot preserved; heartbeat cannot unlock");return 0;
    }
    arrive(0x681,8,0x10f,1);advance(1);
    uint32_t generation=physical_nodes[0].session_generation,acked=physical_rx_metrics.tx_acked;
    present=false;queue_time();advance(3);
    assert(physical_peer_waiting() && physical_link_ready && !physical_rx_metrics.fault);
    assert(physical_rx_metrics.tx_no_ack==1 && physical_rx_metrics.tx_acked==acked);
    assert(!mp_stack_online(&stack,1) && !physical_fresh(1,4,g_uptime_ms));
    unsigned sent=starts;advance(20000);
    assert(physical_link_ready && !physical_rx_metrics.fault && starts==sent);
    assert(mp_bus_dropped()>0 && physical_rx_metrics.tx_peer_discard>0);
    assert(physical_rx_metrics.bootup_a==1);
    /* 模拟等待期遗留TIME；真实驱动必须先清旧队列，再为新心跳排新的定向START。 */
    queue_time();unsigned old_time_starts=time_starts;
    present=true;arrive(0x701,1,0,0);advance(5);arrive(0x701,1,5,0);advance(5);
    assert(!physical_peer_waiting() && physical_rx_metrics.peer_returns==1 && physical_rx_metrics.bootup_a==2);
    assert(physical_nodes[0].session_generation>generation && !physical_fresh(1,4,g_uptime_ms));
    assert(time_starts==old_time_starts && nmt_starts>=1);
    assert(mp_stack_online(&stack,1) && !mp_stack_online(&stack,2));
    assert(physical_rx_metrics.tx_no_ack==1 && physical_rx_metrics.tx_acked>acked);
    assert(physical_rx_metrics.tx_failed==1 && !physical_rx_metrics.fault);
    unsigned valid_before=valid_measurements;
    uint32_t restarted=g_uptime_ms;
    /* 新会话只接受新质量/采集锚/波形；合成数据仅存在Host夹具，不进入设备镜像。 */
    for(unsigned i=0;i<2200;i++) {
        uint32_t next=g_uptime_ms+1,tick=next-restarted;
        if(next%500==0)arrive(0x701,1,5,0);
        if(next%1000==0) {
            arrive(0x681,8,0x10fu,1);
            arrive(0x481,8,1800000000u+next/1000,tick);
            arrive(0x381,8,9800u|(7200u<<16),0);
        }
        if(tick%20==0)arrive(0x181,8,tick,tick);
        advance(1);
    }
    assert(valid_measurements>valid_before && !mp_stack_online(&stack,2));
    mp_stack_close(&stack);
    puts("PASS: actual driver / 20s A off / RX alive / fresh Boot-up / old TIME discarded / NMT TXOK / B OFFLINE");
    return 0;
}
