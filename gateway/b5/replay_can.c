/* 只读B4原始CAN回执，经真实CANopen/双总线模型/JSON序列化；绝不连硬件。 */
#include "../dual_can/b4_gateway.h"
#include "b5_policy.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
static B4Gateway gateway;
static unsigned requests[2];
int b5_network_stopped(void) { return 0; }
int b4_bus_transmit(unsigned bus, const MpCanFrame *f) {
    (void)f; requests[bus]++; return 1; /* Host边界交付，不能称为真实CAN ACK。 */
}
static void drain(uint32_t tick) {
    MpFrame f; char payload[2048],topic[120];
    while (mp_router_take(&gateway.router,&f,tick)) {
        if (!mp_json(&f,payload,sizeof(payload)) || !mp_topic(&f,topic,sizeof(topic))) exit(4);
        printf("{\"arrival_tick\":%lu,\"topic\":\"%s\",\"qos\":%u,\"payload\":%s}\n",
               (unsigned long)tick,topic,f.rate&&!f.replay?0:1,payload);
        mp_router_ack(&gateway.router,&f,true);
    }
}
int main(int argc,char **argv) {
    if (argc!=2) return 2;
    FILE *input=fopen(argv[1],"r");if(!input)return 2;
    if(b4_gateway_init(&gateway))return 3;
    b4_gateway_link(&gateway,0,false);mp_router_online(&gateway.router,true);
    unsigned long tick,id;unsigned dlc;char hex[17];unsigned first=1;
    while(fscanf(input,"%lu %lx %u %16s",&tick,&id,&dlc,hex)==4) {
        MpCanFrame frame={0};if(dlc>8 || strlen(hex)!=dlc*2)return 2;
        frame.ident=(uint32_t)id;frame.dlc=dlc;
        for(unsigned i=0;i<dlc;i++) {char pair[3]={hex[i*2],hex[i*2+1],0};frame.data[i]=(uint8_t)strtoul(pair,NULL,16);}
        if(first) {gateway.now=(uint32_t)tick;first=0;}
        b4_gateway_tick(&gateway,(uint32_t)tick);
        if(frame.ident==0x482 && dlc==8) {
            uint32_t epoch;memcpy(&epoch,frame.data,4);
            /* 保留台架真实源UTC；仅在隔离Backend的受控时钟下验证，不伪装成今天的采集。 */
            b4_gateway_sync(&gateway,epoch,(uint32_t)tick);
            if(!gateway.session)gateway.session=epoch;
        }
        b4_gateway_receive(&gateway,1,&frame,(uint32_t)tick);drain((uint32_t)tick);
    }
    fclose(input);b4_gateway_close(&gateway);
    return 0;
}
