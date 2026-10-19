/* 两个独立真实协议实现以离线 CAN 帧相连；输入来自 Node-A Host 实际 CO_CANsend。 */
#include "physical.h"
#include "mp_adapter.h"
#include <assert.h>
#include <stdio.h>
static MpStack stack;
static MpAdapter adapter;
static MpRouter router;
static unsigned waves,scalars,b_offline;
static void step(void) {
    mp_stack_tick(&stack);mp_adapter_poll(&adapter,&stack,&router);MpFrame f;
    while(mp_router_take(&router,&f,stack.milliseconds)) {
        if(f.node==2) {assert(f.stream==MP_NODE_STATUS && !f.valid);b_offline++;}
        if(f.stream==MP_PPG) {assert(f.rate==50 && f.count==50);waves++;}
        if(f.stream==MP_SPO2) {assert(f.values[0]==9800);scalars++;}
        char topic[128],body[2300];assert(mp_topic(&f,topic,sizeof(topic)) && mp_json(&f,body,sizeof(body)));
        printf("%s\t%s\n",topic,body);mp_router_ack(&router,&f,true);
    }
}
int main(void) {
    assert(!mp_stack_init(&stack,1800000000));physical_link_ready=true;
    mp_adapter_init(&adapter);mp_router_init(&router);mp_router_online(&router,true);
    unsigned time,id,dlc;char bytes[17];
    while(scanf("%u %u %u %16s",&time,&id,&dlc,bytes)==4) {
        assert(dlc<=8);while(stack.milliseconds<time) step();
        MpCanFrame f={0};f.ident=(uint16_t)id;f.dlc=(uint8_t)dlc;
        for(unsigned i=0;i<dlc;i++) {unsigned v;assert(sscanf(bytes+i*2,"%2x",&v)==1);f.data[i]=(uint8_t)v;}
        physical_receive(&f);
    }
    step();assert(waves>=4 && scalars>=2 && b_offline);assert(!mp_stack_online(&stack,2));
    mp_stack_close(&stack);return 0;
}
