/* 复用既有 POSIX TCP 外设桩与真实 coreMQTT；不改 ESP8266/TLS 生产实现。 */
#define main original_broker_fixture_main
#include "../../mqtt/tests/broker_gateway.c"
#undef main
#include "physical.h"
#include "mp_adapter.h"
#include <assert.h>
static MpStack stack;
static MpAdapter adapter;
static MpRouter output_router;
static unsigned messages,acked;
static void step_wire(void) {
    mp_stack_tick(&stack);mp_adapter_poll(&adapter,&stack,&output_router);MpFrame f;
    while(mp_router_take(&output_router,&f,g_uptime_ms)) {
        received_id=0;assert(gateway_mqtt_publish(&f));
        if(published_id) {assert(published_id==received_id);acked++;}
        mp_router_ack(&output_router,&f,true);messages++;
    }
}
int main(int argc,char **argv) {
    if(argc!=3 || (port=atoi(argv[1]))<=1024 || port>65535) return 64;
    FILE *input=fopen(argv[2],"r");if(!input) return 65;
    platform_poll();MpFrame will={0};will.node=3;will.stream=MP_GATEWAY_STATUS;will.epoch=1800000000;will.timestamp=1800000000000ULL;will.boot=65536;
    assert(gateway_config_valid() && gateway_network_open() && gateway_mqtt_open(&will));
    assert(!mp_stack_init(&stack,1800000000));physical_link_ready=true;
    mp_adapter_init(&adapter);mp_router_init(&output_router);mp_router_online(&output_router,true);
    unsigned time,id,dlc;char bytes[17];
    while(fscanf(input,"%u %u %u %16s",&time,&id,&dlc,bytes)==4) {
        assert(dlc<=8);while(stack.milliseconds<time) step_wire();
        MpCanFrame f={0};f.ident=(uint16_t)id;f.dlc=(uint8_t)dlc;
        for(unsigned i=0;i<dlc;i++) {unsigned v;assert(sscanf(bytes+i*2,"%2x",&v)==1);f.data[i]=(uint8_t)v;}
        physical_receive(&f);
    }
    step_wire();fclose(input);mp_stack_close(&stack);gateway_network_close();
    printf("{\"messages\":%u,\"matching_pubacks\":%u}\n",messages,acked);return 0;
}
