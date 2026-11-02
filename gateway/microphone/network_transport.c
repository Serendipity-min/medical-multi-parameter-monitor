/* 仅独立语音目标编译此适配，原Gateway传输源保持原字节。 */
#include "../mqtt/src/gateway_config.h"
#include "mic_format.h"
#include "mic_protocol.h"
#include "network_transport.h"
#include <string.h>
static GatewayConfig mic_config;
#undef GATEWAY_CONFIG
#define GATEWAY_CONFIG (&mic_config)
#include "../mqtt/src/gateway_transport.c"

#define MIC_INPUT "mpm/mic/v1/in"
#define MIC_OUTPUT "mpm/mic/v1/out"
static uint16_t subscription_id;
static int subscription_ack;
static MQTTPubAckInfo_t incoming[1];
static uint32_t reference_epoch, reference_tick;

static void report_open_failure(void) {
    const char *reply=at_response();
    const char *join=strstr(reply,"+CWJAP:");
    int code=-1;
    if(join && join[7]>='1' && join[7]<='4' && join[8]=='\r')code=join[7]-'0';
    /* 只输出错误枚举和累计计数，绝不打印含SSID/地址的原始AT回复。 */
    char line[160];
    snprintf(line,sizeof line,"MIC_OPEN_DIAG join_code=%d busy=%u ready=%u error=%u uart_errors=%lu\r\n",
             code,(unsigned)(strstr(reply,"busy ")!=NULL),(unsigned)(strstr(reply,"\r\nready\r\n")!=NULL),
             (unsigned)(strstr(reply,"\r\nERROR\r\n")!=NULL),(unsigned long)platform_uart_errors_total());
    console(line);
}

int mic_network_configure(const uint8_t *p,size_t n) {
    memset(&mic_config,0,sizeof mic_config);
    if(!mic_config_packet_valid(p,n))return 0;
    if(!h3_config_record_valid((const H3ConfigRecord *)H3_CONFIG_ADDRESS)) return 0;
    memcpy(&mic_config,(const void *)0x0800c018u,sizeof mic_config);
    memcpy(mic_config.username,p+4,33);memcpy(mic_config.password,p+37,65);memcpy(mic_config.client_id,p+102,41);
    memcpy(mic_config.ssid,p+143,33);memcpy(mic_config.wifi_password,p+176,65);
    reference_epoch=(uint32_t)p[241]|((uint32_t)p[242]<<8)|((uint32_t)p[243]<<16)|((uint32_t)p[244]<<24);
    reference_tick=g_uptime_ms;
    if(reference_epoch<mic_config.minimum_epoch)return 0;
    return gateway_config_valid();
}

static void mic_event(MQTTContext_t *context,MQTTPacketInfo_t *packet,MQTTDeserializedInfo_t *decoded) {
    if(context!=&client || decoded->deserializationResult!=MQTTSuccess) { mqtt_failed();return; }
    if(packet->type==MQTT_PACKET_TYPE_PUBACK && pending_id && decoded->packetIdentifier==pending_id) acknowledged=1;
    else if(packet->type==MQTT_PACKET_TYPE_SUBACK && decoded->packetIdentifier==subscription_id) {
        uint8_t *codes=NULL;size_t count=0;
        subscription_ack=MQTT_GetSubAckStatusCodes(packet,&codes,&count)==MQTTSuccess && count==1 && codes[0]==1;
    } else if((packet->type&0xf0u)==MQTT_PACKET_TYPE_PUBLISH) {
        MQTTPublishInfo_t *p=decoded->pPublishInfo;
        if(p && p->qos==MQTTQoS1 && !p->retain && p->topicNameLength==sizeof(MIC_OUTPUT)-1 &&
           !memcmp(p->pTopicName,MIC_OUTPUT,sizeof(MIC_OUTPUT)-1) && p->payloadLength<=80)
            mic_network_reply(p->pPayload,p->payloadLength);
    } else { mqtt_failed(); }
}

static int subscribe_reply(void) {
    /* 原发布者没有入站记录；QoS1订阅及回复必须显式配置同一条入站状态。 */
    memset(incoming,0,sizeof incoming);
    if(MQTT_InitStatefulQoS(&client,outgoing,1,incoming,1)!=MQTTSuccess)return 0;
    client.appCallback=mic_event;subscription_ack=0;subscription_id=MQTT_GetPacketId(&client);
    MQTTSubscribeInfo_t s={MQTTQoS1,MIC_OUTPUT,sizeof(MIC_OUTPUT)-1};
    mqtt_adapter_begin(&network,5000);
    if(MQTT_Subscribe(&client,&s,1,subscription_id)!=MQTTSuccess)return 0;
    uint32_t at=g_uptime_ms;
    while(!subscription_ack && g_uptime_ms-at<5000 && network.connected)
        if(!gateway_mqtt_yield())return 0;
    if(subscription_ack)console("MIC_SUBACK_QOS1_OK\r\n");
    return subscription_ack;
}

int mic_network_connect(void) {
    MpFrame will={0};will.node=3;will.stream=MP_GATEWAY_STATUS;will.synthetic=true;will.seq=UINT32_MAX;
    /* 此独立台架使用经SSH读取的同步UTC；不改原B5的新鲜UDP授时目标。 */
    esp_mqtt_reset();
    if(!at_command("AT",2000) || !at_command("ATE0",2000) || !at_command("AT+SYSSTORE=0",2000)) {
        report_open_failure();return 0;
    }
    uint32_t expected=reference_epoch+(g_uptime_ms-reference_tick)/1000u;
    char time_command[64];snprintf(time_command,sizeof time_command,"AT+SYSTIMESTAMP=%lu",(unsigned long)expected);
    if(!at_command(time_command,2000) || !at_command("AT+SYSTIMESTAMP?",2000)){report_open_failure();return 0;}
    const char *stamp=strstr(at_response(),"+SYSTIMESTAMP:");
    uint32_t observed=stamp?(uint32_t)strtoul(stamp+14,NULL,10):0;
    if(observed<expected || observed-expected>2u){console("MIC_UTC_READBACK_FAILED\r\n");return 0;}
    snprintf(time_command,sizeof time_command,"MIC_UTC source=SSH_SYNCED_SERVER epoch=%lu\r\n",(unsigned long)observed);console(time_command);
    if(!gateway_network_open()){report_open_failure();return 0;}
    will.timestamp=gateway_epoch_milliseconds();will.epoch=gateway_epoch();will.boot=1;
    if(!gateway_mqtt_open(&will)){report_open_failure();return 0;}
    return subscribe_reply();
}
int mic_network_send(const uint8_t *packet,size_t length) {
    if(!mqtt_online || !network.connected || length>544){console("MIC_SEND_NOT_READY\r\n");return 0;}
    MQTTPublishInfo_t m={0};m.qos=MQTTQoS1;m.pTopicName=MIC_INPUT;m.topicNameLength=sizeof(MIC_INPUT)-1;
    m.pPayload=packet;m.payloadLength=length;pending_id=MQTT_GetPacketId(&client);acknowledged=0;
    mqtt_adapter_begin(&network,5000);uint32_t at=g_uptime_ms;
    MQTTStatus_t published=MQTT_Publish(&client,&m,pending_id);
    int ok=published==MQTTSuccess;
    while(ok && !acknowledged && g_uptime_ms-at<5000)ok=process_once();
    ok=ok && acknowledged && network.connected && g_uptime_ms-at<5000;
    if(!ok) {
        char line[160];snprintf(line,sizeof line,"MIC_SEND_DIAG status=%u ack=%d connected=%u elapsed=%lu uart_errors=%lu\r\n",
            (unsigned)published,acknowledged,(unsigned)network.connected,(unsigned long)(g_uptime_ms-at),
            (unsigned long)platform_uart_errors_total());console(line);
    }
    pending_id=0;acknowledged=0;
    if(!ok)mqtt_failed();
    return ok;
}
int mic_network_poll(void) { return gateway_mqtt_yield(); }
void mic_network_close(void) { gateway_network_close(); }
uint32_t mic_network_epoch(void) { return gateway_epoch(); }
