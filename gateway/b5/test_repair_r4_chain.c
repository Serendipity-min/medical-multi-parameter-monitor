/* 真实egress/coreMQTT/adapter/platform；只替换STM32寄存器及ESP/服务器对端。 */
#include "gateway_platform.h"
#include "esp_io_metrics.h"
#include "../mqtt/tests/mocks/platform_mmio.h"
#ifndef REPAIR_TRANSPORT_SOURCE
#define REPAIR_TRANSPORT_SOURCE "../mqtt/src/gateway_transport.c"
#endif
#ifndef REPAIR_PLATFORM_SOURCE
#define REPAIR_PLATFORM_SOURCE "../mqtt/src/platform.c"
#endif
#include REPAIR_TRANSPORT_SOURCE
#include REPAIR_PLATFORM_SOURCE
#include "egress.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>
const GatewayConfig gateway_test_config={GATEWAY_CONFIG_MAGIC,1700000000u,
    "synthetic-wifi","synthetic-pass","mqtt.example.invalid","b5-gateway","synthetic-pass","b5-c-isolated"};
volatile uint32_t g_uptime_ms;
TestUsart platform_usart[2]={{USART_SR_TXE,0},{USART_SR_TXE,0}};
void USART3_IRQHandler(void);
static uint64_t us;
static uint32_t base,stop_after=420000,ack_delay=30,at_delay=2,send_delay=5;
static unsigned stop_phase,wire,commands,sends,pings,published[MP_STREAMS],stall_i;
static unsigned bad_ack,no_ack,terminal_mode,fragment=1;
static unsigned freeze_after;
static unsigned close_mode;
#ifdef MP_H3_FRESH_SNTP
static unsigned ntp_packets,ntp_fixture;
#endif
static uint32_t clock_valid_at;
static unsigned char response[16384],server[512],packet[2048];
static unsigned rn,ri,sn,expected,packet_n,cmd_n;
static uint32_t response_at,server_at;
static char command[128];
static MpRouter router;
static uint32_t origin,produced,sequences[MP_STREAMS];
static int pressure;
static void trace_event(MQTTContext_t *c,MQTTPacketInfo_t *p,MQTTDeserializedInfo_t *d){
    if(base)printf("callback type=%u id=%u pending=%u status=%u tick=%lu\n",p->type,d->packetIdentifier,pending_id,d->deserializationResult,(unsigned long)g_uptime_ms);
    mqtt_event(c,p,d);
}
int b5_network_stopped(void){return (uint32_t)(g_uptime_ms-base)>=stop_after;}
uint32_t b5_business_remaining(void){uint32_t n=g_uptime_ms-base;return n>=stop_after?0:stop_after-n;}
static void queue_bytes(const void *p,unsigned n,uint32_t delay){
    assert(ri==rn);assert(n<=sizeof(response));memcpy(response,p,n);rn=n;ri=0;response_at=g_uptime_ms+delay;
}
static void terminal(const char *p,uint32_t delay){queue_bytes(p,(unsigned)strlen(p),delay);}
static unsigned varint(unsigned *pos){unsigned n=0,shift=0,b;do{b=packet[(*pos)++];n|=(b&127u)<<shift;shift+=7;}while(b&128);return n;}
static void mqtt_packet(void){
    unsigned type=packet[0]>>4;
#ifdef MP_H3_FRESH_SNTP
    if(ntp_fixture && packet_n==48 && packet[0]==0x23){
        ntp_packets++;
        if(ntp_packets>1){memset(server,0,48);server[0]=0x24;server[1]=1;memcpy(server+24,packet+40,8);
            sntp_put32(server+32,1800000000u+2208988800u);sntp_put32(server+40,1800000000u+2208988800u);sn=48;server_at=g_uptime_ms;}
        return;
    }
#endif
    if(type==1){const unsigned char c[]={0x20,2,0,0};memcpy(server,c,4);sn=4;server_at=g_uptime_ms;}
    if(type==12){if(!sn)server_at=g_uptime_ms;server[sn++]=0xd0;server[sn++]=0;pings++;}
    if(type==3){
        unsigned pos=1;(void)varint(&pos);unsigned topic_n=packet[pos]*256u+packet[pos+1];pos+=2;
        assert(pos+topic_n<=packet_n);
        const char *names[]={"ECG","RESP","HR","RR","TEMP","NODE_STATUS","GATEWAY_STATUS"};
        for(unsigned i=0;i<7;i++){
            unsigned z=(unsigned)strlen(names[i]);
            if(topic_n>=z && !memcmp(packet+pos+topic_n-z,names[i],z))published[i]++;
        }
        pos+=topic_n;
        if(packet[0]&2u){
            assert(!sn);server[0]=0x40;server[1]=2;server[2]=packet[pos];server[3]=(unsigned char)(packet[pos+1]+bad_ack);
            sn=no_ack?0:4;server_at=g_uptime_ms+ack_delay;
        }
    }
}
void platform_test_tx(unsigned char b){
    wire++;us+=87;g_uptime_ms=base+(uint32_t)(us/1000u);
    if(expected){
        assert(packet_n<sizeof(packet));packet[packet_n++]=b;
        if(freeze_after && packet_n==freeze_after)USART3->SR&=~USART_SR_TXE;
        if(packet_n==expected){expected=0;mqtt_packet();
            if(terminal_mode==1)terminal("",0);
            else if(terminal_mode==2)terminal("\r\nSEND FAIL\r\n",send_delay);
            else if(terminal_mode==3)terminal("\r\nCLOSED\r\n",send_delay);
            else if(terminal_mode==4)terminal("\r\nready\r\n",send_delay);
            else if(terminal_mode==5)terminal("busy s...\r\n",send_delay);
            else terminal("\r\nSEND OK\r\n",send_delay);
        }
        return;
    }
    assert(cmd_n<sizeof(command)-1);command[cmd_n++]=(char)b;
    if(cmd_n<2 || command[cmd_n-2]!='\r' || b!='\n')return;
    command[cmd_n]=0;commands++;cmd_n=0;
    if(sscanf(command,"AT+CIPSEND=%u",&expected)==1){packet_n=0;sends++;terminal(">",at_delay);}
    else if(strstr(command,"CIPRECVLEN")){
        char line[80];unsigned n=(int32_t)(g_uptime_ms-server_at)>=0?sn:0;
        int z=snprintf(line,sizeof(line),"\r\n+CIPRECVLEN:%u,0,0,0,0\r\n\r\nOK\r\n",n);queue_bytes(line,(unsigned)z,at_delay);
    }else if(strstr(command,"CIPRECVDATA")){
        unsigned char line[600];int z=snprintf((char *)line,sizeof(line),"\r\n+CIPRECVDATA:%u,",sn);
        memcpy(line+z,server,sn);memcpy(line+z+sn,"\r\nOK\r\n",6);queue_bytes(line,(unsigned)z+sn+6,at_delay);sn=0;
    }else if(strstr(command,"AT+GMR"))terminal("\r\nAT version:2.3.0.0\r\n\r\nOK\r\n",at_delay);
    else if(strstr(command,"AT+SLEEP?"))terminal("\r\n+SLEEP:0\r\n\r\nOK\r\n",at_delay);
    else if(strstr(command,"AT+CIPCLOSE") && close_mode)terminal(close_mode==2?"\r\nCLOSED\r\n":"\r\nCLOSED\r\n\r\nOK\r\n",at_delay);
    else if(strstr(command,"AT+CIPSNTPCFG?"))terminal("\r\n+CIPSNTPCFG:1,0,\"ntp-0.example.invalid\",\"ntp-1.example.invalid\",\"ntp-2.example.invalid\"\r\n\r\nOK\r\n",at_delay);
    else if(strstr(command,"AT+SYSTIMESTAMP?"))terminal((int32_t)(g_uptime_ms-clock_valid_at)>=0?"\r\n+SYSTIMESTAMP:1800000000\r\n\r\nOK\r\n":"\r\n+SYSTIMESTAMP:0\r\n\r\nOK\r\n",at_delay);
    else terminal("\r\nOK\r\n",at_delay);
}
static void put(unsigned stream,unsigned rate,unsigned count,uint32_t at){
    MpFrame f={0};f.node=stream==MP_GATEWAY_STATUS?3:2;f.stream=(uint8_t)stream;f.rate=(uint16_t)rate;f.count=(uint16_t)count;
    f.synthetic=true;f.valid=true;f.timestamp=1800000000000ULL+at;f.epoch=1;f.boot=1;f.seq=++sequences[stream];
    f.values[0]=stream==MP_HR?6000:stream==MP_TEMP?2300:0;
    mp_router_put(&router,&f);
}
static void tick(void){
    us+=100;g_uptime_ms=base+(uint32_t)(us/1000u);
    if(pressure){
        while(produced<(uint32_t)(g_uptime_ms-origin)){
            produced++;
            if(produced%400==0)put(MP_ECG,250,100,produced);
            if(produced%1000==0){put(MP_RESP,50,50,produced);put(MP_HR,0,1,produced);put(MP_RR,0,1,produced);put(MP_TEMP,0,1,produced);}
            if(produced%5000==0){put(MP_NODE_STATUS,0,1,produced);put(MP_GATEWAY_STATUS,0,1,produced);}
        }
    }
    if(ri<rn && (int32_t)(g_uptime_ms-response_at)>=0){
        for(unsigned k=0;k<fragment && ri<rn;k++){
            USART3->DR=response[ri++];USART3->SR|=USART_SR_RXNE;USART3_IRQHandler();USART3->SR&=~USART_SR_RXNE;
        }
    }
    if(stop_phase){EspIoMetrics io;platform_io_snapshot(&io);if(io.at_phase==stop_phase && (stop_phase!=ESP_AT_DATA || io.written>=3))stop_after=g_uptime_ms-base;}
}
static void open_session(void){
    platform_set_poll(tick);mqtt_adapter_reset(&network);esp_mqtt_reset();epoch=1800000000;epoch_tick=g_uptime_ms;
    MpFrame will={0};will.node=3;will.stream=MP_GATEWAY_STATUS;will.synthetic=true;will.timestamp=gateway_epoch_milliseconds();
    assert(gateway_mqtt_open(&will));
    client.appCallback=trace_event;
    mp_router_init(&router);mp_router_online(&router,true);
}
int main(int argc,char **argv){
    const char *mode=argc>1?argv[1]:"normal";
    if(strstr(mode,"wrap")){base=0xfffff000u;g_uptime_ms=base;}
    open_session();
    if(!strcmp(mode,"expected-close") || !strcmp(mode,"close-no-ok")){
        close_mode=!strcmp(mode,"close-no-ok")?2:1;
        int ok=at_command("AT+CIPCLOSE",2000);
#ifdef EXPECT_CLOSE_DEFECT
        assert(!ok && platform_at_unsynced());puts("DEPLOYED_R4_EXPECTED_CLOSED_MISCLASSIFIED_REPRODUCED");
#else
        if(close_mode==1)assert(ok && platform_at_synchronized() && io_metrics.at_phase==ESP_AT_CLOSED);
        else assert(!ok && platform_at_unsynced());
        puts("EXPECTED_CLOSED_REQUIRES_OWN_COMMAND_AND_TRAILING_OK_PASS");
#endif
        return 0;
    }
#ifdef MP_H3_FRESH_SNTP
    if(!strcmp(mode,"clock19") || !strcmp(mode,"clock19-wrap") || !strcmp(mode,"clock-never")){
        ntp_fixture=1;ntp_packets=1;close_mode=1;
        clock_valid_at=g_uptime_ms+(strcmp(mode,"clock-never")?19000u:60000u);
        uint32_t start=g_uptime_ms;int ok=gateway_network_open();
#ifdef EXPECT_TIME_DEFECT
        assert(!ok && g_uptime_ms-start<19000);puts("DEPLOYED_15_FAST_QUERIES_END_BEFORE_SYNTHETIC_19S_READY_REPRODUCED");
#else
        if(strcmp(mode,"clock-never"))assert(ok && g_uptime_ms-start>=19000 && g_uptime_ms-start<35000);
        else assert(!ok && g_uptime_ms-start>=28000 && g_uptime_ms-start<31000);
        printf("BOUNDED_TIME_PREP_%s_PASS elapsed=%lu\n",mode,(unsigned long)(g_uptime_ms-start));
#endif
        return 0;
    }
    if(!strcmp(mode,"fresh-rotate")){
        close_mode=1;ntp_fixture=1;opening_ntp_retry=0;
        assert(!fresh_sntp() && gateway_network_retryable() && platform_at_synchronized());
        opening_ntp_retry=0;assert(fresh_sntp() && ntp_packets==2 && !gateway_network_retryable());
        puts("ACTUAL_SNTP_UART_NO_REPLY_CLOSE_CLOSED_OK_ROTATES_NEW_NONCE_AND_VALIDATES_FRESH_SAMPLE_PASS");return 0;
    }
#endif
    if(!strcmp(mode,"no-prompt") || !strcmp(mode,"slow-prompt") || !strcmp(mode,"partial-data")){
        unsigned char bytes[854]={0};
        if(!strcmp(mode,"partial-data"))freeze_after=400;else at_delay=!strcmp(mode,"no-prompt")?6000:200;
        int result=esp_mqtt_send(bytes,854,5000);
        if(!strcmp(mode,"slow-prompt"))assert(result==854 && platform_at_synchronized());
        else assert(result<0 && io_metrics.unsynced && (!freeze_after || io_metrics.written==400));
        printf("PROMPT_OR_PARTIAL_UART_TIMING_%s_PASS written=%lu\n",mode,(unsigned long)io_metrics.written);return 0;
    }
    if(!strncmp(mode,"raw",3)){
        unsigned n=(unsigned)atoi(mode+3);unsigned char bytes[2048]={0};assert(n<=sizeof(bytes));
        assert(esp_mqtt_send(bytes,(int)n,5000)==(int)n);
        assert(io_metrics.required==n && io_metrics.written==n && platform_at_synchronized());
        printf("EXACT_UART_BYTES_%u_SEND_OK_NOT_SERVER_ACCEPTANCE_PASS\n",n);return 0;
    }
    if(!strcmp(mode,"pressure")){
        B5Publisher publisher={0};origin=g_uptime_ms;epoch_tick=origin;pressure=1;
        while((uint32_t)(g_uptime_ms-origin)<305000){
            platform_poll();
            static const uint32_t stalls[]={100000,101500,131593};
            if(stall_i<3 && g_uptime_ms-origin>=stalls[stall_i]){send_delay=stall_i==2?2516:1500;stall_i++;}else send_delay=5;
            int good=b5_egress_step(&router,&publisher,true);
            if(!good){EspIoMetrics io;platform_io_snapshot(&io);printf("pressure failed tick=%lu phase=%lu reason=%lu pending=%u age=%lu high=%lu state=%u ri=%u rn=%u sn=%u\n",(unsigned long)g_uptime_ms,(unsigned long)io.at_phase,(unsigned long)io.wait_reason,pending_id,(unsigned long)(g_uptime_ms-pending_started),(unsigned long)router.high_water,rx_state,ri,rn,sn);fflush(stdout);}
            assert(good);
        }
        printf("pressure counters dropped=%lu expired=%lu overflow=%lu replaced=%lu cache=%u high=%lu q0=%lu q1=%lu age=%lu\n",(unsigned long)router.dropped,(unsigned long)router.expired,(unsigned long)router.live_overflow,(unsigned long)router.live_replaced,router.cn,(unsigned long)router.high_water,(unsigned long)publisher.q0,(unsigned long)publisher.q1,(unsigned long)router.source_age.max);fflush(stdout);
        assert(!router.dropped && !router.expired && !router.live_overflow && !router.live_replaced && !router.cn);
        assert(publisher.q0>=1048 && publisher.q1>=1000);
        printf("COMBINED_UART_300S_STALLS_PASS high=%lu q0=%lu q1=%lu source_age=%lu\n",(unsigned long)router.high_water,(unsigned long)publisher.q0,(unsigned long)publisher.q1,(unsigned long)router.source_age.max);
        return 0;
    }
    if(!strcmp(mode,"poll")){
        at_delay=200;unsigned before=commands;unsigned char out[4];
        for(unsigned i=0;i<100;i++){uint32_t at=g_uptime_ms;assert(esp_mqtt_recv(out,4,5)==0);assert((uint32_t)(g_uptime_ms-at)<=5);}
        assert(commands-before<=3);puts("PERSISTENT_AT_5MS_SLICES_NO_REISSUE_PASS");return 0;
    }
    if(!strcmp(mode,"keepalive")){
        while((uint32_t)(g_uptime_ms-epoch_tick)<16000){platform_poll();assert(gateway_mqtt_progress()!=GW_FAILED);}
        assert(pings>=1);puts("KEEPALIVE_ACTUAL_PLATFORM_NOT_5MS_TX_BUDGET_PASS");return 0;
    }
    if(!strcmp(mode,"close-active")){
        unsigned char byte;assert(esp_mqtt_recv(&byte,1,1)==0 && rx_state);
        gateway_network_close();assert(platform_at_synchronized() && io_metrics.at_phase==ESP_AT_CLOSED);
        puts("CLOSE_DRAINS_KNOWN_RX_OWNER_WITHIN_ORIGINAL_2S_PASS");return 0;
    }
    MpFrame scalar={0};scalar.node=2;scalar.stream=MP_HR;scalar.synthetic=true;scalar.valid=true;
    scalar.timestamp=gateway_epoch_milliseconds();scalar.count=1;scalar.values[0]=6000;
    if(!strcmp(mode,"wrong"))bad_ack=1;
    if(!strcmp(mode,"missing") || !strcmp(mode,"deferqueue") || !strcmp(mode,"stopack"))no_ack=1;
    if(!strcmp(mode,"late"))ack_delay=5100;
    ack_delay=(!strcmp(mode,"normal") || !strcmp(mode,"wrap"))?200:ack_delay;
    assert(gateway_mqtt_begin(&scalar)==GW_PENDING);
    if(!strcmp(mode,"slowrx"))at_delay=200;
    if(!strcmp(mode,"rxlate"))at_delay=1200;
    if(!strcmp(mode,"stopack")){
        stop_after=(g_uptime_ms-base)+100;
        int state;do{state=gateway_mqtt_progress();}while(state==GW_PENDING);
        assert(state==GW_FAILED && b5_network_stopped() && sends==2);
        puts("STOP_DURING_PUBACK_NO_NEW_BUSINESS_PASS");return 0;
    }
    if(!strcmp(mode,"deferqueue")){
        us+=(4500u-(g_uptime_ms-pending_started))*1000ULL;g_uptime_ms=base+(uint32_t)(us/1000u);
        put(MP_ECG,250,100,g_uptime_ms);unsigned before=sends;uint16_t id=pending_id;
        B5Publisher publisher={0};publisher.pending=true;publisher.inflight=scalar;
        assert(b5_egress_step(&router,&publisher,true));
        assert(router.ln==1 && !router.cn && !router.taken[MP_ECG] && sends==before && pending_id==id);
        puts("INSUFFICIENT_PENDING_BUDGET_LEAVES_FIFO_ITEM_UNTAKEN_PASS");return 0;
    }
    if(!strcmp(mode,"during")){
        uint16_t saved=pending_id;send_delay=300;
        MpFrame wave=scalar;wave.stream=MP_ECG;wave.rate=250;wave.count=100;
        assert(gateway_mqtt_begin(&wave)==GW_COMPLETE && pending_id==saved);
        int state;do{state=gateway_mqtt_progress();}while(state==GW_PENDING);
        assert(state==GW_COMPLETE && !pending_id);puts("ACK_READY_DURING_Q0_SEND_PROCESSED_BY_UNIQUE_OWNER_PASS");return 0;
    }
    if(!strncmp(mode,"age",3)){
        unsigned age=(unsigned)strtoul(mode+3,0,10);us+=(age-(g_uptime_ms-pending_started))*1000ULL;g_uptime_ms=base+(uint32_t)(us/1000u);
        uint16_t id=pending_id;unsigned before=sends;MpFrame wave=scalar;wave.stream=MP_ECG;wave.rate=250;wave.count=100;
        int state=gateway_mqtt_begin(&wave);
        assert(pending_id==id && (age<2500?state==GW_COMPLETE:(state==GW_DEFERRED || (age==4999 && state==GW_FAILED))));
        if(state!=GW_COMPLETE)assert(sends==before);
        printf("PENDING_AGE_%u_ADMISSION_%d_NO_OVERWRITE_PASS\n",age,state);return 0;
    }
    if(!strncmp(mode,"terminal",8))terminal_mode=(unsigned)atoi(mode+8);
    if(!strncmp(mode,"stop",4))stop_phase=(unsigned)atoi(mode+4);
    if(terminal_mode || stop_phase){
        MpFrame wave=scalar;wave.stream=MP_ECG;wave.rate=250;wave.count=100;
        assert(gateway_mqtt_begin(&wave)==GW_FAILED);EspIoMetrics io;platform_io_snapshot(&io);
        assert(io.unsynced || terminal_mode==2);unsigned before=wire;
        if(io.unsynced)assert(!at_command("AT+CIPCLOSE",2000) && wire==before);
        printf("COMBINED_FAILURE_STOP_NO_BLIND_CLOSE_PASS reason=%lu\n",(unsigned long)io.wait_reason);return 0;
    }
    int state;do{state=gateway_mqtt_progress();}while(state==GW_PENDING);
    if(state!=GW_COMPLETE && !bad_ack && !no_ack && ack_delay<=5000 && strcmp(mode,"rxlate")){EspIoMetrics io;platform_io_snapshot(&io);
        printf("unexpected state=%d tick=%lu base=%lu age=%lu io_phase=%lu reason=%lu flags=%lu queries=%lu empty=%lu reads=%lu sn=%u ri=%u rn=%u\n",state,(unsigned long)g_uptime_ms,(unsigned long)base,(unsigned long)(g_uptime_ms-pending_started),(unsigned long)io.at_phase,(unsigned long)io.wait_reason,(unsigned long)io.reply_flags,(unsigned long)io.rx_queries,(unsigned long)io.rx_empty,(unsigned long)io.rx_reads,sn,ri,rn);fflush(stdout);}
    if(bad_ack || no_ack || ack_delay>5000 || !strcmp(mode,"rxlate"))assert(state==GW_FAILED);else assert(state==GW_COMPLETE && !gateway_mqtt_pending());
    if(!strcmp(mode,"duplicate")){
        uint16_t old=(uint16_t)(client.nextPacketId-1);assert(gateway_mqtt_begin(&scalar)==GW_PENDING);
        server[0]=0x40;server[1]=2;server[2]=(unsigned char)(old>>8);server[3]=(unsigned char)old;sn=4;server_at=g_uptime_ms;
        do{state=gateway_mqtt_progress();}while(state==GW_PENDING);assert(state==GW_FAILED);
        puts("DUPLICATE_OLD_ACK_CANNOT_COMPLETE_NEW_INFLIGHT_PASS");
    }
    puts("REAL_CORE_ADAPTER_PLATFORM_UART_ACK_RESULT_PASS");return 0;
}
