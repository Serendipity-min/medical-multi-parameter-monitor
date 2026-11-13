/* 真实coreMQTT/语音回调/adapter回放；ESP返回为合成字节，不连接设备。 */
#include "core_mqtt.h"
static MQTTStatus_t observed_publish(MQTTContext_t *,const MQTTPublishInfo_t *,uint16_t);
#define MQTT_Publish observed_publish
#include "network_transport.c"
#undef MQTT_Publish
#include <assert.h>

volatile uint32_t g_uptime_ms;
static uint8_t answer[128],request[2048];
static unsigned cursor,answer_length,fragment,request_length,replies;
void platform_poll(void){++g_uptime_ms;}
void mp_model_poll(void){platform_poll();}
int at_command(const char *s,uint32_t ms){(void)s;(void)ms;assert(0);return 0;}
const char *at_response(void){assert(0);return "";}
void esp_mqtt_reset(void){assert(0);}
void delay_ms(uint32_t ms){(void)ms;assert(0);}
uint32_t platform_uart_errors_total(void){return 0;}
void console(const char *s){(void)s;}
void mic_network_reply(const uint8_t *p,size_t n){assert(n==19 && !memcmp(p,"MR01",4));++replies;}
int esp_mqtt_send(const unsigned char *p,int n,uint32_t timeout){
    assert(timeout && n>0 && n<(int)sizeof request);memcpy(request,p,(size_t)n);request_length=(unsigned)n;
    if((p[0]&0xf0)==0x30) {
        unsigned i=1;while(p[i++]&0x80){};unsigned topic=((unsigned)p[i]<<8)|p[i+1];i+=2+topic;
        memcpy(answer,(uint8_t[]){0x40,2,p[i],p[i+1]},4);cursor=0;answer_length=4;fragment=1;
    }
    return n;
}
int esp_mqtt_recv(unsigned char *p,int n,uint32_t timeout){
    assert(timeout);unsigned remaining=answer_length-cursor;
    unsigned count=(unsigned)n;if(count>remaining)count=remaining;if(count>fragment)count=fragment;
    memcpy(p,answer+cursor,count);cursor+=count;return (int)count;
}
static MQTTStatus_t observed_publish(MQTTContext_t *c,const MQTTPublishInfo_t *p,uint16_t id){
    MQTTStatus_t status=MQTT_Publish(c,p,id);printf("ACTUAL_CORE_PUBLISH status=%d payload=%u\n",(int)status,(unsigned)p->payloadLength);fflush(stdout);return status;
}

static void replay(uint8_t grant,unsigned chunk,int wrong_id){
    memset(&client,0,sizeof client);mqtt_adapter_reset(&network);
    TransportInterface_t io=mqtt_adapter_interface(&network);MQTTFixedBuffer_t b={rx_buffer,sizeof rx_buffer};
    assert(MQTT_Init(&client,&io,mqtt_adapter_time,mic_event,&b)==MQTTSuccess);
    client.connectStatus=MQTTConnected;client.nextPacketId=1;
    mqtt_online=1;session_error=0;partial_waiting=0;subscription_ack=0;
    subscription_id=MQTT_GetPacketId(&client);cursor=0;answer_length=5;fragment=chunk;
    uint16_t response_id=(uint16_t)(subscription_id+wrong_id);
    memcpy(answer,(uint8_t[]){0x90,3,(uint8_t)(response_id>>8),(uint8_t)response_id,grant},5);
    MQTTSubscribeInfo_t s={MQTTQoS1,MIC_OUTPUT,sizeof(MIC_OUTPUT)-1};mqtt_adapter_begin(&network,5000);
    request_length=0;
    assert(MQTT_Subscribe(&client,&s,1,subscription_id)==MQTTBadParameter && request_length==0);
    client.nextPacketId=subscription_id;
    assert(subscribe_reply()==(grant==1 && !wrong_id));
    assert(request[0]==0x82 && request_length==sizeof(MIC_OUTPUT)+6);
    assert(subscription_ack==(grant==1 && !wrong_id));
}
int main(void){
    replay(1,5,0);replay(1,1,0);replay(1,2,0);
    replay(0,5,0);replay(0x80,5,0);replay(1,5,1);
    replay(1,5,0);cursor=0;fragment=1;answer_length=39;
    memcpy(answer,(uint8_t[]){0x32,37,0,14},4);memcpy(answer+4,MIC_OUTPUT,14);
    answer[18]=0;answer[19]=55;memset(answer+20,0,19);memcpy(answer+20,"MR01",4);
    for(unsigned i=0;i<1000 && !replies && network.connected;i++)gateway_mqtt_yield();
    assert(replies==1 && network.connected && request_length==4 && request[0]==0x40 && request[3]==55);
    uint8_t data[512]={0},packet[544];mic_chunk_packet(packet,7,0,8,data);
    assert(mic_network_send(packet,sizeof packet));
    assert(request_length>544 && (request[0]&0xf0)==0x30);
    puts("HOST_SUBACK_REAL_CORE_REPLAY_PASS: complete/fragments, QoS0/refusal/wrong ID, incoming QoS1/PUBACK; no devices");return 0;
}
