/* 正式默认端口保持8883；独立H3隔离构建才使用单独TLS监听，不改变配置结构布局。 */
#ifndef MP_MQTT_TLS_PORT
#define MP_MQTT_TLS_PORT 8883
#endif
/* 复用第一阶段已验证的 ESP SSL/CA/时间校验，只在外部配置中保存凭据。 */
#include "gateway_transport.h"
#include "gateway_config.h"
#ifdef MP_H3_PERSISTENT_CONFIG
#include "persistent_config.h"
#endif
#include "core_mqtt.h"
#include "mqtt_transport_adapter.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#ifdef MP_FINAL_UNIFIED
#include "unified_audio.h"
#include "mic_protocol.h"
#include "b5_policy.h"
static MQTTPubAckInfo_t incoming[1];
static uint16_t audio_subscription;
static uint32_t audio_subscription_at;
static int audio_subscribed, audio_pending, audio_result, audio_acknowledged;
static uint16_t audio_packet_id;
static uint32_t audio_started;
static GatewayConfig unified_config;
#define AUDIO_INPUT "mpm/mic/v1/in"
#define AUDIO_OUTPUT "mpm/mic/v1/out"
#endif
#ifdef MP_B5_CLOUD_CANDIDATE
#include "b5_policy.h"
#endif
#ifdef MP_CAN_RX_IRQ
#include "at_version.h"
#include "esp_io_metrics.h"
#endif
#if defined(MP_CAN_RX_IRQ) || defined(MP_FIVE_FIELD01)
#include "wifi_status.h"
#endif
#if defined(MP_B5_EGRESS_FINAL) && !defined(MP_CAN_RX_IRQ)
#include "esp_io_metrics.h"
#endif
#ifdef MP_H3_FRESH_SNTP
#include "sntp_sample.h"
#endif

/* 单一串行客户端；统一目标固定三遥测槽加一音频槽，默认目标仍一槽；不分配堆。 */
static NetworkContext_t network;
static MQTTContext_t client;
#ifdef MP_FINAL_UNIFIED
static MQTTPubAckInfo_t outgoing[GATEWAY_TELEMETRY_SLOTS+1];
typedef struct {uint16_t id;uint32_t at;int result;unsigned ack;} TelemetryPending;
static TelemetryPending telemetry[GATEWAY_TELEMETRY_SLOTS];
static uint16_t last_ticket;
#ifdef MP_FIVE_FIELD01
static uint32_t ack_at[GATEWAY_TELEMETRY_SLOTS],reclaim_count,reclaim_total,reclaim_max;
void field01_mqtt_reclaim(uint32_t *count,uint32_t *total,uint32_t *max){
    *count=reclaim_count;*total=reclaim_total;*max=reclaim_max;
}
#endif
#else
static MQTTPubAckInfo_t outgoing[1];
#endif
static unsigned char rx_buffer[512];
static uint16_t pending_id, next_packet_seed = 1;
static int acknowledged, session_error, mqtt_online, partial_waiting;
#ifdef MP_CAN_RX_IRQ
/* 失败时只输出阶段/枚举/耗时，不输出Topic、载荷、口令或原始AT回复。 */
static void mqtt_diagnostic(unsigned stage, MQTTStatus_t status, uint32_t elapsed)
{
    char line[128];
    (void)snprintf(line,sizeof(line),"GW MQTT_ERROR stage=%u status=%d elapsed=%lu ack=%d connected=%d\r\n",
                   stage,(int)status,(unsigned long)elapsed,acknowledged,network.connected);
    console(line);
}
#endif
static uint32_t partial_since;
static uint32_t epoch, epoch_tick;
#ifdef MP_B5_EGRESS_FINAL
static uint32_t pending_started;
static int opening_ntp_retry;
static GatewayMqttMetrics mqtt_metrics;
int gateway_network_retryable(void){return opening_ntp_retry;}
void gateway_mqtt_metrics(GatewayMqttMetrics *out){*out=mqtt_metrics;}
int gateway_mqtt_pending(void){
#ifdef MP_FINAL_UNIFIED
    return telemetry[0].id || telemetry[1].id || telemetry[2].id;
#else
    return pending_id!=0;
#endif
}
#ifdef MP_FINAL_UNIFIED
uint16_t gateway_mqtt_ticket(void){return last_ticket;}
int gateway_mqtt_slots_full(void){return telemetry[0].id && telemetry[1].id && telemetry[2].id;}
int gateway_mqtt_ticket_result(uint16_t id){
    for(unsigned i=0;i<GATEWAY_TELEMETRY_SLOTS;i++)if(telemetry[i].id==id && id){
        int result=telemetry[i].result;
        if(result==GW_COMPLETE){
#ifdef MP_FIVE_FIELD01
            uint32_t elapsed=g_uptime_ms-ack_at[i];
            reclaim_count++;reclaim_total+=elapsed;
            if(elapsed>reclaim_max)reclaim_max=elapsed;
#endif
            telemetry[i].id=0;
        }
        return result;
    }
    return GW_FAILED;
}
#endif
#ifdef MP_FINAL_UNIFIED
static uint32_t send_budget(void) {
    uint32_t budget=5000u,age;
#ifdef MP_FINAL_UNIFIED
    for(unsigned i=0;i<GATEWAY_TELEMETRY_SLOTS;i++)if(telemetry[i].id && telemetry[i].result==GW_PENDING){
        age=g_uptime_ms-telemetry[i].at;if(age>=5000u)return 0;if(5000u-age<budget)budget=5000u-age;
    }
#else
    if(pending_id){age=g_uptime_ms-pending_started;if(age>=5000u)return 0;budget=5000u-age;}
#endif
#ifdef MP_FINAL_UNIFIED
    if(audio_pending){age=g_uptime_ms-audio_started;if(age>=5000u)return 0;if(5000u-age<budget)budget=5000u-age;}
#endif
    return budget;
}
#endif
#endif
#ifdef MP_H3_FRESH_SNTP
/* 新鲜SNTP样本保留小数秒；仅独立H3候选启用，旧目标时间公式不变。 */
static uint32_t epoch_fraction;
#endif
#ifdef GATEWAY_MQTT_HOST_TEST
/* 普通 host 测试仅注入明确合成配置，生产仍使用固定 sector7 的同一结构。 */
extern const GatewayConfig gateway_test_config;
static const GatewayConfig *config = &gateway_test_config;
#else
static const GatewayConfig *config = GATEWAY_CONFIG;
#endif
_Static_assert(sizeof(GatewayConfig) == 312, "configuration layout changed");

/* Flash 配置按固定长度读取；先校验魔数和字符串末尾，避免 AT 拼接越界读取。 */
int gateway_config_valid(void)
{
#ifdef MP_H3_PERSISTENT_CONFIG
    /* 冷启动只读完整提交记录；损坏/未写配置不回退sector7/11或旧RAM。 */
    if(!h3_config_record_valid((const H3ConfigRecord *)H3_CONFIG_ADDRESS))return 0;
#endif
    return config->magic == GATEWAY_CONFIG_MAGIC && !config->host[64] && !config->ssid[32] &&
           !config->wifi_password[64] && !config->password[64] && !config->username[32] &&
           !config->client_id[40]
#ifdef MP_B5_CLOUD_CANDIDATE
           && b5_identity_allowed(config->client_id, config->username)
#endif
           ;
}

/* SNTP 提供秒级基准，后续用无符号毫秒差推进，兼容一次 SysTick 计数回绕。 */
uint32_t gateway_epoch(void)
{
#ifdef MP_H3_FRESH_SNTP
    return (uint32_t)(gateway_epoch_milliseconds()/1000u);
#else
    return epoch + (uint32_t)(g_uptime_ms - epoch_tick) / 1000;
#endif
}

uint64_t gateway_epoch_milliseconds(void)
{
    return (uint64_t)epoch*1000u+(uint32_t)(g_uptime_ms-epoch_tick)
#ifdef MP_H3_FRESH_SNTP
        +epoch_fraction
#endif
        ;
}

/* 日志只输出固定步骤名；command 可能含凭据，不能连同原始回复一起记录。 */
static int step(const char *name, const char *command, uint32_t timeout)
{
    int ok = at_command(command, timeout);
    console(ok ? "GW OK " : "GW FAIL ");
    console(name);
    console("\r\n");
    return ok;
}

static inline void secure_memzero(void *ptr, size_t len)
{
    volatile unsigned char *p = (volatile unsigned char *)ptr;
    while (len--)
        *p++ = 0;
    __asm__ __volatile__("" : : "r"(ptr) : "memory");
}

static void mqtt_failed(void)
{
#ifdef MP_FINAL_UNIFIED
    audio_pending=audio_acknowledged=0;audio_packet_id=0;audio_result=GW_FAILED;audio_subscribed=0;
    memset(telemetry,0,sizeof telemetry);last_ticket=0;
#endif
    mqtt_online = 0;
    session_error = 1;
    acknowledged = 0;
    pending_id = 0;
    mqtt_adapter_close(&network);
}

/* 仅确认本次在途标识；未知下行业务立即使连接失败，不消费或执行载荷。 */
static void mqtt_event(MQTTContext_t *context, MQTTPacketInfo_t *packet,
                       MQTTDeserializedInfo_t *decoded)
{
#ifdef MP_FINAL_UNIFIED
    if(context==&client && decoded->deserializationResult==MQTTSuccess) {
        if(packet->type==MQTT_PACKET_TYPE_SUBACK && decoded->packetIdentifier==audio_subscription) {
            uint8_t *codes=NULL;size_t count=0;
            audio_subscribed=MQTT_GetSubAckStatusCodes(packet,&codes,&count)==MQTTSuccess && count==1 && codes[0]==1?1:-1;
            return;
        }
        if((packet->type&0xf0u)==MQTT_PACKET_TYPE_PUBLISH) {
            MQTTPublishInfo_t *p=decoded->pPublishInfo;
            if(p && p->qos==MQTTQoS1 && !p->retain && p->topicNameLength==sizeof(AUDIO_OUTPUT)-1 &&
               !memcmp(p->pTopicName,AUDIO_OUTPUT,sizeof(AUDIO_OUTPUT)-1) && p->payloadLength<=
#ifdef MP_FIVE_APPLIANCE
               MIC_FACT_REPLY_MAX
#else
               76u
#endif
              )
                unified_audio_reply(p->pPayload,p->payloadLength);
            return;
        }
    }
#endif
#ifdef MP_FINAL_UNIFIED
    if(context==&client && packet->type==MQTT_PACKET_TYPE_PUBACK && decoded->deserializationResult==MQTTSuccess &&
       audio_pending && decoded->packetIdentifier==audio_packet_id){audio_acknowledged=1;return;}
#endif
    if (context != &client || (packet->type & 0xf0U) == MQTT_PACKET_TYPE_PUBLISH)
    {
#ifdef MP_CAN_RX_IRQ
        mqtt_diagnostic(1,decoded->deserializationResult,0);
#endif
        mqtt_failed();
        return;
    }
#ifdef MP_FINAL_UNIFIED
    if(packet->type==MQTT_PACKET_TYPE_PUBACK && decoded->deserializationResult==MQTTSuccess){
        for(unsigned i=0;i<GATEWAY_TELEMETRY_SLOTS;i++)if(telemetry[i].id && decoded->packetIdentifier==telemetry[i].id){
#ifdef MP_FIVE_FIELD01
            if(!telemetry[i].ack)ack_at[i]=g_uptime_ms;
#endif
            telemetry[i].ack=1;return;
        }
    }
#ifdef MP_CAN_RX_IRQ
    mqtt_diagnostic(2,decoded->deserializationResult,packet->type);
#endif
    mqtt_failed();
#else
    if (packet->type == MQTT_PACKET_TYPE_PUBACK && decoded->deserializationResult == MQTTSuccess
        && pending_id && decoded->packetIdentifier == pending_id)
        acknowledged = 1;
    else
    {
#ifdef MP_CAN_RX_IRQ
        mqtt_diagnostic(2,decoded->deserializationResult,packet->type);
#endif
        mqtt_failed();
    }
#endif
}

/* 不完整包可在多次 ProcessLoop 间继续，但总装配时间有限，不能无限续活连接。 */
static int process_once(void)
{
    MQTTStatus_t status = MQTT_ProcessLoop(&client);
    if (status == MQTTNeedMoreBytes)
    {
        if (!partial_waiting)
        {
            partial_waiting = 1;
            partial_since = g_uptime_ms;
        }
        if ((uint32_t)(g_uptime_ms - partial_since) >= 5000U)
        {
#ifdef MP_CAN_RX_IRQ
            mqtt_diagnostic(3,status,g_uptime_ms-partial_since);
#endif
            mqtt_failed();
        }
    }
    else if (status != MQTTSuccess)
    {
#ifdef MP_CAN_RX_IRQ
        mqtt_diagnostic(4,status,0);
#endif
        mqtt_failed();
    }
    else if (!client.index)
        partial_waiting = 0;
    return !session_error && network.connected;
}

/* 重连清空 context/记录和 RX；包标识在本次开机中继续递增，拒绝旧会话迟到 ACK。 */
int gateway_mqtt_open(const MpFrame *will_frame)
{
    char will[512];
    char will_topic[120];
    if (!mp_topic(will_frame, will_topic, sizeof(will_topic))) return 0;
    if (!mp_json(will_frame, will, sizeof(will)))
    {
        /* 序列化失败时也可能已有部分内容，返回前清除整个临时缓冲区。 */
        secure_memzero(will, sizeof(will));
        return 0;
    }
    session_error = acknowledged = partial_waiting = mqtt_online = 0;
    pending_id = 0;
#ifdef MP_FINAL_UNIFIED
    audio_pending=audio_acknowledged=0;audio_packet_id=0;audio_result=GW_DEFERRED;audio_subscribed=0;audio_subscription=0;
    memset(telemetry,0,sizeof telemetry);last_ticket=0;
    memset(incoming,0,sizeof incoming);
#endif
    memset(outgoing, 0, sizeof(outgoing));
    memset(rx_buffer, 0, sizeof(rx_buffer));
    TransportInterface_t transport = mqtt_adapter_interface(&network);
    MQTTFixedBuffer_t buffer = {rx_buffer, sizeof(rx_buffer)};
    MQTTStatus_t status = MQTT_Init(&client, &transport, mqtt_adapter_time, mqtt_event, &buffer);
    if (status == MQTTSuccess)
        status = MQTT_InitStatefulQoS(&client, outgoing, sizeof outgoing/sizeof outgoing[0],
#ifdef MP_FINAL_UNIFIED
                                     incoming, 1);
#else
                                     NULL, 0);
#endif
    client.nextPacketId = next_packet_seed;
    MQTTConnectInfo_t options = {0};
    options.keepAliveSeconds = 15;
    options.cleanSession = true;
    options.pClientIdentifier = config->client_id;
    options.clientIdentifierLength = (uint16_t)strlen(config->client_id);
    options.pUserName = config->username;
    options.userNameLength = (uint16_t)strlen(config->username);
    options.pPassword = config->password;
    options.passwordLength = (uint16_t)strlen(config->password);
    MQTTPublishInfo_t will_info = {0};
    will_info.qos = MQTTQoS1;
    will_info.retain = true;
    /* 遗嘱与遥测使用同一编译期身份；不能把测试遗嘱发到正式Gateway主题。 */
    will_info.pTopicName = will_topic;
    will_info.topicNameLength = (uint16_t)strlen(will_info.pTopicName);
    will_info.pPayload = will;
    will_info.payloadLength = strlen(will);
    bool session_present = false;
    uint32_t start = g_uptime_ms;
    mqtt_adapter_begin(&network, 5000);
    if (status == MQTTSuccess && network.connected)
        status = MQTT_Connect(&client, &options, &will_info, 5000, &session_present);
    int ok = status == MQTTSuccess && network.connected && !session_present
             && (uint32_t)(g_uptime_ms - start) < 5000U;
    if (ok)
        mqtt_online = 1;
    else
        mqtt_failed();
    secure_memzero(will, sizeof(will));
    console(ok ? "GW MQTT_CONNECTED\r\n" : "GW FAIL MQTT_CONNECT\r\n");
    return ok;
}

/* 序列化失败直接返回给 Router 回存；不能把截断的 JSON 当作成功消息发送。 */
int gateway_mqtt_publish(const MpFrame *frame)
{
#ifdef MP_FINAL_UNIFIED
    int result=gateway_mqtt_begin(frame);uint16_t id=last_ticket;
    while(result==GW_PENDING){if(gateway_mqtt_progress()==GW_FAILED)return 0;result=gateway_mqtt_ticket_result(id);}
    return result==GW_COMPLETE;
#else
    if (!mqtt_online || !network.connected)
        return 0;
    static char payload[2048];
    char topic[120];
    int length = mp_json(frame, payload, sizeof(payload));
    if (!length || !mp_topic(frame, topic, sizeof(topic)))
    {
#ifdef MP_CAN_RX_IRQ
        mqtt_diagnostic(5,MQTTBadParameter,0);
#endif
        return 0;
    }
    MQTTPublishInfo_t message = {0};
    message.qos = frame->rate && !frame->replay ? MQTTQoS0 : MQTTQoS1;
    /* 沿用实时波形 QoS0；标量/状态/REPLAY 使用 QoS1。只有 QoS1 成功意味着 PUBACK。 */
    message.retain = frame->stream == MP_NODE_STATUS || frame->stream == MP_GATEWAY_STATUS;
    message.pTopicName = topic;
    message.topicNameLength = (uint16_t)strlen(topic);
    message.pPayload = payload;
    message.payloadLength = (size_t)length;
    acknowledged = 0;
    pending_id = message.qos == MQTTQoS1 ? MQTT_GetPacketId(&client) : 0;
    next_packet_seed = client.nextPacketId;
    uint32_t start = g_uptime_ms;
    mqtt_adapter_begin(&network, 5000);
    MQTTStatus_t publish_status=MQTT_Publish(&client, &message, pending_id);
#ifdef MP_CAN_RX_IRQ
    uint32_t sent_at=g_uptime_ms;
#endif
    int ok = publish_status == MQTTSuccess;
    if (message.qos == MQTTQoS1)
    {
        /* Publish/SEND OK 只是发送结果；匹配 PUBACK 到达后才允许 Router 成功 ACK。 */
        while (ok && !acknowledged && (uint32_t)(g_uptime_ms - start) < 5000U)
            ok = process_once();
        ok = ok && acknowledged;
    }
    ok = ok && !session_error && network.connected && (uint32_t)(g_uptime_ms - start) < 5000U;
#ifdef MP_CAN_RX_IRQ
    /* 保留原5000ms/PUBACK门禁；诊断放在清在途状态之前，以区分发送与确认失败。 */
    if(!ok) {
        char diagnostic[256];
        uint32_t failed_at=g_uptime_ms;
        mqtt_diagnostic(6,publish_status,failed_at-start);
        /* 只在失败后输出，不给正常逐包发布增加UART延迟；保留发送/确认阶段界限。 */
        EspIoMetrics io;platform_io_snapshot(&io);
        (void)snprintf(diagnostic,sizeof(diagnostic),"GW MQTT_BUDGET send_ms=%lu wait_ms=%lu buffered=%lu\r\n",
            (unsigned long)(sent_at-start),(unsigned long)(failed_at-sent_at),(unsigned long)client.index);console(diagnostic);
        (void)snprintf(diagnostic,sizeof(diagnostic),"GW MQTT_IO tx_calls=%lu tx_ok=%lu tx_len=%lu tx_ms=%lu phase=%lu queries=%lu empty=%lu hint=%lu rx_bytes=%lu reads=%lu\r\n",
            (unsigned long)io.tx_calls,(unsigned long)io.tx_confirmed,(unsigned long)io.tx_length,
            (unsigned long)io.tx_ms,(unsigned long)io.tx_phase,(unsigned long)io.rx_queries,
            (unsigned long)io.rx_empty,(unsigned long)io.rx_hint,(unsigned long)io.rx_bytes,(unsigned long)io.rx_reads);console(diagnostic);
        /* QoS0本来就没有PUBACK，必须记录实际QoS才能把总预算失败归因于确认等待。 */
        (void)snprintf(diagnostic,sizeof(diagnostic),"GW MQTT_PENDING id=%u qos=%u node=%u stream=%u seq=%lu replay=%u\r\n",
            pending_id,(unsigned)message.qos,frame->node,frame->stream,(unsigned long)frame->seq,(unsigned)frame->replay);
        console(diagnostic);
    }
#endif
    pending_id = 0;
    acknowledged = 0;
    if (!ok)
        mqtt_failed();
    return ok;
#endif
}

#ifdef MP_B5_EGRESS_FINAL
int gateway_mqtt_admit(void) {
#ifdef MP_FINAL_UNIFIED
    if(!mqtt_online || !network.connected)return GW_FAILED;
    uint32_t budget=send_budget();
    if(!budget)return GW_FAILED;
    return platform_send_admissible(2048,budget)?GW_COMPLETE:GW_DEFERRED;

#else
    if(!mqtt_online || !network.connected)return GW_FAILED;
    uint32_t age=(uint32_t)(g_uptime_ms-pending_started);
    if(pending_id && age>=5000u)return GW_FAILED;
    return platform_send_admissible(2048,pending_id?5000u-age:5000u)?GW_COMPLETE:GW_DEFERRED;

#endif
}
int gateway_mqtt_begin(const MpFrame *frame) {
#ifdef MP_FINAL_UNIFIED
    if(!mqtt_online || !network.connected)return GW_FAILED;
    bool qos1=!frame->rate || frame->replay;
#ifdef MP_FINAL_UNIFIED
    unsigned slot=0;while(slot<GATEWAY_TELEMETRY_SLOTS && telemetry[slot].id)slot++;
    if(qos1 && slot==GATEWAY_TELEMETRY_SLOTS)return GW_DEFERRED;
#else
    if(qos1 && pending_id)return GW_FAILED;
#endif
    if(!send_budget())return GW_FAILED;
    static char payload[2048];char topic[120];
    uint32_t json_at=g_uptime_ms;
    int length=mp_json(frame,payload,sizeof(payload));
    if(!length || !mp_topic(frame,topic,sizeof(topic)))return GW_FAILED;
#ifdef MP_FIVE_FIELD01
    mqtt_metrics.field01_json_ms+=g_uptime_ms-json_at;
#endif
    b5_latency_add(&mqtt_metrics.json,g_uptime_ms-json_at);
    MQTTPublishInfo_t m={0};m.qos=qos1?MQTTQoS1:MQTTQoS0;
    m.retain=frame->stream==MP_NODE_STATUS || frame->stream==MP_GATEWAY_STATUS;
    m.pTopicName=topic;m.topicNameLength=(uint16_t)strlen(topic);m.pPayload=payload;m.payloadLength=(size_t)length;
    uint16_t id=0;uint32_t start=g_uptime_ms,budget=5000;
    budget=send_budget();if(!budget)return GW_FAILED;
    /* coreMQTT调用前拒绝新事务；未发送不等于失败或已确认。 */
    if(!platform_send_admissible((unsigned)length+(unsigned)m.topicNameLength+9u,budget))return GW_DEFERRED;
    if(qos1){
        id=MQTT_GetPacketId(&client);next_packet_seed=client.nextPacketId;
#ifdef MP_FINAL_UNIFIED
        telemetry[slot]=(TelemetryPending){id,start,GW_PENDING,0};last_ticket=id;
#else
        acknowledged=0;pending_id=id;pending_started=start;
#endif
    }
    platform_tx_context(m.qos,frame->stream,frame->seq,pending_id,pending_id?start-pending_started:0,budget);
    mqtt_adapter_begin(&network,budget);
    MQTTStatus_t status=MQTT_Publish(&client,&m,id);
    b5_latency_add(&mqtt_metrics.send,g_uptime_ms-start);
    if(status!=MQTTSuccess || !network.connected || session_error || (uint32_t)(g_uptime_ms-start)>=budget) {
        char diagnostic[48];(void)snprintf(diagnostic,sizeof(diagnostic),"GW PUBLISH_FAIL status=%u\r\n",(unsigned)status);console(diagnostic);
        mqtt_metrics.failed++;mqtt_failed();return GW_FAILED;
    }
    if(qos1){mqtt_metrics.q1_sent++;return GW_PENDING;}
    mqtt_metrics.q0_sent++;return GW_COMPLETE;

#else
    if(!mqtt_online || !network.connected)return GW_FAILED;
    bool qos1=!frame->rate || frame->replay;
    if(qos1 && pending_id) {
#ifdef MP_FINAL_UNIFIED
        if(audio_pending)return GW_DEFERRED;
#endif
        return GW_FAILED;
    }
    if(pending_id && (uint32_t)(g_uptime_ms-pending_started)>=5000u)return GW_FAILED;
    static char payload[2048];char topic[120];
    uint32_t json_at=g_uptime_ms;
    int length=mp_json(frame,payload,sizeof(payload));
    if(!length || !mp_topic(frame,topic,sizeof(topic)))return GW_FAILED;
#ifdef MP_FIVE_FIELD01
    mqtt_metrics.field01_json_ms+=g_uptime_ms-json_at;
#endif
    b5_latency_add(&mqtt_metrics.json,g_uptime_ms-json_at);
    MQTTPublishInfo_t m={0};m.qos=qos1?MQTTQoS1:MQTTQoS0;
    m.retain=frame->stream==MP_NODE_STATUS || frame->stream==MP_GATEWAY_STATUS;
    m.pTopicName=topic;m.topicNameLength=(uint16_t)strlen(topic);m.pPayload=payload;m.payloadLength=(size_t)length;
    uint16_t id=0;uint32_t start=g_uptime_ms,budget=5000;
    if(pending_id && (uint32_t)(start-pending_started)>=5000u)return GW_FAILED;
    if(pending_id)budget=5000u-(uint32_t)(start-pending_started);
    /* coreMQTT调用前拒绝新事务；未发送不等于失败或已确认。 */
    if(!platform_send_admissible((unsigned)length+(unsigned)m.topicNameLength+9u,budget))return GW_DEFERRED;
    if(qos1){acknowledged=0;pending_id=id=MQTT_GetPacketId(&client);next_packet_seed=client.nextPacketId;pending_started=start;}
    platform_tx_context(m.qos,frame->stream,frame->seq,pending_id,pending_id?start-pending_started:0,budget);
    mqtt_adapter_begin(&network,budget);
    MQTTStatus_t status=MQTT_Publish(&client,&m,id);
    b5_latency_add(&mqtt_metrics.send,g_uptime_ms-start);
    if(status!=MQTTSuccess || !network.connected || session_error || (uint32_t)(g_uptime_ms-start)>=budget) {
        char diagnostic[48];(void)snprintf(diagnostic,sizeof(diagnostic),"GW PUBLISH_FAIL status=%u\r\n",(unsigned)status);console(diagnostic);
        mqtt_metrics.failed++;mqtt_failed();return GW_FAILED;
    }
    if(qos1){mqtt_metrics.q1_sent++;return GW_PENDING;}
    mqtt_metrics.q0_sent++;return GW_COMPLETE;

#endif
}
int gateway_mqtt_progress(void) {
#ifdef MP_FINAL_UNIFIED
    if(!mqtt_online || !network.connected)return GW_FAILED;
    uint32_t budget=send_budget();
    if(!budget){mqtt_metrics.failed++;mqtt_failed();return GW_FAILED;}
    mqtt_adapter_begin(&network,budget);
    if(!process_once()){mqtt_metrics.failed++;return GW_FAILED;}
    if(!send_budget()){mqtt_metrics.failed++;mqtt_failed();return GW_FAILED;}
#ifdef MP_FINAL_UNIFIED
    if(audio_pending && audio_acknowledged) {
        b5_latency_add(&mqtt_metrics.ack,g_uptime_ms-audio_started);
        audio_pending=audio_acknowledged=0;audio_packet_id=0;audio_result=GW_COMPLETE;
    }
#endif
#ifdef MP_FINAL_UNIFIED
    for(unsigned i=0;i<GATEWAY_TELEMETRY_SLOTS;i++)if(telemetry[i].id && telemetry[i].result==GW_PENDING && telemetry[i].ack){
        b5_latency_add(&mqtt_metrics.ack,g_uptime_ms-telemetry[i].at);mqtt_metrics.q1_acked++;telemetry[i].result=GW_COMPLETE;
    }
#else
    if(pending_id) {
        if(!acknowledged)return GW_PENDING;
        b5_latency_add(&mqtt_metrics.ack,g_uptime_ms-pending_started);
        mqtt_metrics.q1_acked++;pending_id=0;acknowledged=0;
    }
#endif
    return GW_COMPLETE;

#else
    if(!mqtt_online || !network.connected)return GW_FAILED;
    if(pending_id && (uint32_t)(g_uptime_ms-pending_started)>=5000u) {
        mqtt_metrics.failed++;mqtt_failed();return GW_FAILED;
    }
    /* 接收切片仍为5ms；ProcessLoop保活发送不能误用5ms作为整包预算。 */
    uint32_t budget=pending_id?5000u-(uint32_t)(g_uptime_ms-pending_started):5000u;
    mqtt_adapter_begin(&network,budget);
    if(!process_once()){mqtt_metrics.failed++;return GW_FAILED;}
    if(pending_id) {
        if((uint32_t)(g_uptime_ms-pending_started)>=5000u){mqtt_metrics.failed++;mqtt_failed();return GW_FAILED;}
        if(!acknowledged) {
#ifdef MP_FINAL_UNIFIED
            if(audio_pending)return GW_COMPLETE;
#endif
            return GW_PENDING;
        }
        b5_latency_add(&mqtt_metrics.ack,g_uptime_ms-pending_started);
#ifdef MP_FINAL_UNIFIED
        if(audio_pending){audio_pending=0;audio_result=GW_COMPLETE;}
        else {mqtt_metrics.q1_acked++;}
#else
        mqtt_metrics.q1_acked++;
#endif
        pending_id=0;acknowledged=0;
    }
    return GW_COMPLETE;

#endif
}
#endif

#ifdef MP_FINAL_UNIFIED
/* 仅统一候选使用易失副本；不改Flash配置/授时来源或原B5配置判据。 */
int gateway_audio_configure(const uint8_t *p,size_t n) {
    if(mqtt_online || !mic_config_packet_valid(p,n) || !gateway_config_valid())return 0;
    if(p[36] || p[101] || p[142] || p[175] || p[240] ||
       !b5_identity_allowed((const char *)p+102,(const char *)p+4))return 0;
    unified_config=*config;
    memcpy(unified_config.username,p+4,33);memcpy(unified_config.password,p+37,65);
    memcpy(unified_config.client_id,p+102,41);memcpy(unified_config.ssid,p+143,33);
    memcpy(unified_config.wifi_password,p+176,65);
    config=&unified_config;return 1;
}
int gateway_audio_subscribe(void) {
    if(!mqtt_online || pending_id)return GW_FAILED;
    audio_subscription=MQTT_GetPacketId(&client);next_packet_seed=client.nextPacketId;
    audio_subscription_at=g_uptime_ms;audio_subscribed=0;
    MQTTSubscribeInfo_t s={MQTTQoS1,AUDIO_OUTPUT,sizeof(AUDIO_OUTPUT)-1};
    mqtt_adapter_begin(&network,5000);
    if(MQTT_Subscribe(&client,&s,1,audio_subscription)!=MQTTSuccess){audio_subscribed=-1;return GW_FAILED;}
    return GW_PENDING;
}
int gateway_audio_ready(void) {
    if(!mqtt_online || !network.connected)return 0;
    if(!audio_subscribed && (uint32_t)(g_uptime_ms-audio_subscription_at)>=5000u)audio_subscribed=-1;
    return audio_subscribed==1;
}
int gateway_audio_result(void) {return audio_result;}
int gateway_audio_pending(void) {return audio_pending;}
int gateway_audio_begin(const uint8_t packet[544]) {
    if(!gateway_audio_ready())return GW_FAILED;
    uint32_t budget=send_budget();
    if(!budget)return GW_FAILED;
    if(audio_pending || !platform_send_admissible(544+sizeof(AUDIO_INPUT)+9,budget))return GW_DEFERRED;
    MQTTPublishInfo_t p={0};p.qos=MQTTQoS1;p.pTopicName=AUDIO_INPUT;
    p.topicNameLength=sizeof(AUDIO_INPUT)-1;p.pPayload=packet;p.payloadLength=544;
    audio_packet_id=MQTT_GetPacketId(&client);next_packet_seed=client.nextPacketId;
    audio_acknowledged=0;audio_pending=1;audio_result=GW_PENDING;audio_started=g_uptime_ms;
    mqtt_adapter_begin(&network,budget);
    if(MQTT_Publish(&client,&p,audio_packet_id)!=MQTTSuccess || !network.connected || session_error) {
        mqtt_failed();return GW_FAILED;
    }
    return GW_PENDING;
}
#endif

/* 没有业务帧时仍处理 MQTT 保活和接收，避免空闲连接被 Broker 关闭。 */
int gateway_mqtt_yield(void)
{
    if (!mqtt_online || !network.connected)
        return 0;
    mqtt_adapter_begin(&network, 5000);
    return process_once();
}

void gateway_network_close(void)
{
    mqtt_failed();
#ifdef MP_B5_EGRESS_FINAL
    if(platform_at_unsynced()){console("GW CLOSE_UNSYNCED_MANUAL_POWER_REQUIRED\r\n");return;}
#endif
#ifdef MP_B5_EGRESS_FINAL
    if(!at_command("AT+CIPCLOSE",2000))console("GW CLOSE_NOT_CONFIRMED_MANUAL_POWER_REQUIRED\r\n");
#else
    (void)at_command("AT+CIPCLOSE", 2000);
#endif
}

/* 固定顺序为 AT 配置、入网、可信时间、证书名称校验、TLS；任何失败由外层重试。 */
#ifdef MP_H3_FRESH_SNTP
/* 单个配置端点不可达时，下次外层重连轮换；每次仍只发一个有界请求。 */
static unsigned sntp_server_cursor;
#ifdef MP_B5_EGRESS_FINAL
static int sntp_prepare_command(const char *command,uint32_t start) {
    uint32_t used=g_uptime_ms-start;
    if(used>28000u){console("GW SNTP_PREP_BUDGET\r\n");return -1;}
    return at_command(command,2000u);
}
static char sntp_targets[3][65];
static unsigned sntp_target_count;
static uint32_t epoch_query_ms;
static int sntp_time_consistent(uint64_t sample,uint32_t tick,uint32_t rtt) {
    uint64_t coarse=(uint64_t)epoch*1000u+(uint32_t)(tick-epoch_tick);
    uint32_t uncertainty=rtt/2u+1u;
    /* 秒级量化、实际查询耗时和新鲜包半程误差共同形成区间，不重写任一路时间。 */
    return epoch_query_ms<=2000u && sample+uncertainty>=coarse &&
           sample<=coarse+1000u+epoch_query_ms+uncertainty;
}
static int sntp_load_targets(uint32_t start) {
    if(!sntp_target_count) {
        if(sntp_prepare_command("AT+CIPSNTPCFG?",start)<=0)return 0;
        /* 冷启动未启用时只回:0；先易失启用并读回列表，再按原流程显式选择。 */
        if(strstr(at_response(),"+CIPSNTPCFG:0\r\n") &&
           (sntp_prepare_command("AT+CIPSNTPCFG=1,0",start)<=0 ||
            sntp_prepare_command("AT+CIPSNTPCFG?",start)<=0))return 0;
        while(sntp_target_count<3 && sntp_server_at(at_response(),sntp_target_count,sntp_targets[sntp_target_count]))sntp_target_count++;
    }
    return sntp_target_count!=0;
}
static int sntp_bootstrap(char line[256]) {
    uint32_t start=g_uptime_ms,queries=0,tried=0;int valid=0;
    if(!sntp_load_targets(start))goto done;
    unsigned first=sntp_server_cursor;
    /* 保留启动时的端点列表，显式选择不会丢掉下一次轮换目标。 */
    for(unsigned turn=0;turn<sntp_target_count;turn++) {
        unsigned index=(first+turn)%sntp_target_count;char server[65];
        if(sntp_prepare_command("AT+CIPSNTPCFG=0",start)<=0)goto done;
        int used=snprintf(line,256,"AT+CIPSNTPCFG=1,0");
        for(unsigned i=0;i<sntp_target_count;i++)used+=snprintf(line+used,256u-(unsigned)used,",\"%s\"",sntp_targets[(index+i)%sntp_target_count]);
        if(sntp_prepare_command(line,start)<=0 || sntp_prepare_command("AT+CIPSNTPCFG?",start)<=0 ||
            !strstr(at_response(),"+CIPSNTPCFG:1,0,"))goto done;
        for(unsigned i=0;i<sntp_target_count;i++)
            if(!sntp_server_at(at_response(),i,server) || strcmp(server,sntp_targets[(index+i)%sntp_target_count]))goto done;
        tried|=1u<<index;
        for(unsigned attempt=0;attempt<(15u+sntp_target_count-1u)/sntp_target_count && queries<15 && g_uptime_ms-start<30000u;attempt++) {
            uint32_t query_start=g_uptime_ms;
            int status=sntp_prepare_command("AT+SYSTIMESTAMP?",start);
            uint32_t query_end=g_uptime_ms;
            if(status<0)goto done;
            queries++;
            if(!status)goto done;
            const char *value=strstr(at_response(),"+SYSTIMESTAMP:");
            if(value)epoch=(uint32_t)strtoul(value+14,NULL,10);
            (void)snprintf(line,256,"GW TIME_SAMPLE query=%lu primary=%u parsed=%u epoch=%lu\r\n",
                (unsigned long)queries,index,(unsigned)(value!=NULL),(unsigned long)(value?epoch:0));console(line);
            if(value && epoch>=config->minimum_epoch){epoch_tick=query_end;epoch_query_ms=query_end-query_start;epoch_fraction=0;sntp_server_cursor=index;valid=1;goto done;}
            if(queries<15){int32_t wait=(int32_t)(start+queries*2000u-g_uptime_ms);if(wait>0)delay_ms((uint32_t)wait);}
        }
    }
done:
    (void)snprintf(line,256,"GW TIME_WAIT queries=%lu elapsed=%lu valid=%u epoch=%lu tried=%lu\r\n",
        (unsigned long)queries,(unsigned long)(g_uptime_ms-start),(unsigned)valid,(unsigned long)epoch,(unsigned long)tried);console(line);
    return valid;
}
#endif
static int fresh_sntp(void) {
    char server[65]={0},command[112];
#ifdef MP_B5_EGRESS_FINAL
    if(!sntp_load_targets(g_uptime_ms)){console("GW FAIL SNTP_SERVER_CONFIG\r\n");return 0;}
    unsigned selected=sntp_server_cursor%sntp_target_count;
    memcpy(server,sntp_targets[selected],sizeof(server));
    sntp_server_cursor=(selected+1u)%sntp_target_count;
#else
    if(!at_command("AT+CIPSNTPCFG?",2000)) {
        console("GW FAIL SNTP_SERVER_CONFIG\r\n");return 0;
    }
    unsigned selected=sntp_server_cursor;
    if(!sntp_server_at(at_response(),selected,server))selected=0;
    if(!sntp_server_at(at_response(),selected,server)) {
        console("GW FAIL SNTP_SERVER_CONFIG\r\n");return 0;
    }
    sntp_server_cursor=(selected+1u)%3u;
#endif
    (void)snprintf(command,sizeof(command),"AT+CIPSTART=\"UDP\",\"%s\",123",server);
    int opened=at_command(command,5000);
    secure_memzero(server,sizeof(server));secure_memzero(command,sizeof(command));
    if(!opened) {console("GW FAIL SNTP_UDP_OPEN\r\n");return 0;}
    unsigned char request[48]={0},reply[48];request[0]=0x23;
    /* 近似epoch只用作请求nonce；实际授时取匹配回复的服务器时间，不信旧RTC值。 */
    sntp_put32(request+40,epoch+2208988800u);sntp_put32(request+44,g_uptime_ms^0x51a7c39du);
    uint32_t start=g_uptime_ms;int sent=esp_mqtt_send(request,48,1000);
    int received=0;
    /* AT适配层可短读；只在同一个有界UDP请求内累积，不能把下一请求旧回复拼入。 */
    while(sent==48 && received<48 && (uint32_t)(g_uptime_ms-start)<1000u) {
        int count=esp_mqtt_recv(reply+received,48-received,1000u-(g_uptime_ms-start));
        if(count<0 || count>48-received) {received=-1;break;}
        received+=count;
    }
    uint32_t rtt=g_uptime_ms-start;uint64_t sample=0;
    int valid=received==48 && sntp_sample(reply,48,request,rtt,config->minimum_epoch,&sample);
#ifdef MP_B5_EGRESS_FINAL
    int time_mismatch=valid && !sntp_time_consistent(sample,start+rtt,rtt);
    if(time_mismatch)valid=0;
#endif
    /* 无论成功或失败均关UDP，后续SSL不继承该socket；原TLS名称/CA设置不变。 */
    int closed=at_command("AT+CIPCLOSE",2000);
    esp_mqtt_reset();
    if(!valid || !closed) {
#ifdef MP_B5_EGRESS_FINAL
        /* 只恢复已完整发送、零回复且UDP确已关闭的既有端点轮换。 */
        opening_ntp_retry=sent==48 && received==0 && closed && platform_at_synchronized();
#endif
        /* 只解释拒绝原因，不改变原授时判定；完整包之前绝不读取未初始化字段。
         * 1发送/2长度/3RTT/4未同步/5RATE KoD/6旧nonce/7其他/8关闭/9其他KoD/10模块与新鲜UTC不一致。 */
        unsigned reason=7;
        if(sent!=48)reason=1;
        else if(received!=48)reason=2;
        else if(rtt>1000u)reason=3;
        else if(memcmp(reply+24,request+40,8))reason=6;
        else if(reply[1]==0)reason=!memcmp(reply+12,"RATE",4)?5:9;
        else if((reply[0]>>6)==3)reason=4;
        else if(valid && !closed)reason=8;
#ifdef MP_B5_EGRESS_FINAL
        else if(time_mismatch)reason=10;
#endif
        char diagnostic[96];
        (void)snprintf(diagnostic,sizeof(diagnostic),"GW SNTP_REJECT reason=%u received=%d rtt_ms=%lu server_index=%u\r\n",
            reason,received,(unsigned long)rtt,selected);console(diagnostic);
        console("GW FAIL SNTP_FRESH_SAMPLE\r\n");return 0;
    }
    #ifdef MP_B5_EGRESS_FINAL
    int64_t time_delta=(int64_t)sample-((int64_t)epoch*1000u+(uint32_t)(start+rtt-epoch_tick));
    char match[96];(void)snprintf(match,sizeof(match),"GW TIME_MATCH delta_ms=%ld query_ms=%lu\r\n",
        (long)time_delta,(unsigned long)epoch_query_ms);console(match);
#endif
    epoch=(uint32_t)(sample/1000u);epoch_fraction=(uint32_t)(sample%1000u);
    epoch_tick=start+rtt;
    /* 成功端点继续使用；只有失败才在下一轮切换，不改变nonce/RTT/TLS门禁。 */
    sntp_server_cursor=selected;
    char line[128];(void)snprintf(line,sizeof(line),"GW SNTP_SAMPLE rtt_ms=%lu uncertainty_ms=%lu epoch=%lu fraction=%lu server_index=%u\r\n",
        (unsigned long)rtt,(unsigned long)(rtt/2u),(unsigned long)epoch,(unsigned long)epoch_fraction,selected);console(line);
    return 1;
}
#endif

#define ESP_AT_SYNC "AT"
#define ESP_AT_ECHO_OFF "ATE0"
#define ESP_AT_VOLATILE "AT+SYSSTORE=0"
#define ESP_AT_GMR "AT+GMR"

static int wifi_join(char *command,size_t size,uint32_t timeout) {
    /* 对有效配置生成相同命令；显式字段边界也让 host 编译器证明不会跨字段读取。 */
    (void)snprintf(command, size, "AT+CWJAP=\"%.*s\",\"%.*s\"",
                   (int)sizeof(config->ssid) - 1, config->ssid,
                   (int)sizeof(config->wifi_password) - 1, config->wifi_password);
    int ok=at_command(command,timeout);
    /* 先清除 SSID/口令再分支，Wi-Fi 失败及后续提前返回都不残留该命令。 */
    secure_memzero(command,size);
    return ok;
}

#ifdef MP_CAN_RX_IRQ
static int esp_version(uint32_t timeout,char version[32]) {
#ifdef MP_TRANSPORT_PROFILE
    if(!at_command(ESP_AT_GMR,timeout))return 0;
    platform_cpu_note_gmr();
    return gateway_at_version(at_response(),version);
#else
    return at_command(ESP_AT_GMR,timeout) && gateway_at_version(at_response(),version);
#endif
}
#endif

#if defined(MP_FIVE_FIELD01) || defined(MP_ESP_UART_230400)
#include "uart_negotiation.inc"
#endif
#ifdef MP_FIVE_FIELD01
#include "field01_preflight.inc"
#endif
#ifdef MP_ESP_UART_230400
#include "production_uart.inc"
#endif

int gateway_network_open(void)
{
    char command[256];
#ifdef MP_B5_EGRESS_FINAL
    opening_ntp_retry=0;
#endif
    mqtt_failed();
    esp_mqtt_reset();
#ifdef MP_ESP_UART_230400
    if(!production_uart_open(command,sizeof command) || !step("STA","AT+CWMODE=1",3000))return 0;
#else
    if (!step("AT", ESP_AT_SYNC, 2000) || !step("ECHO", ESP_AT_ECHO_OFF, 2000) ||
        !step("VOLATILE", ESP_AT_VOLATILE, 2000) || !step("STA", "AT+CWMODE=1", 3000))
        return 0;
#endif
#ifdef MP_CAN_RX_IRQ
    char version[32];
    if(!esp_version(2000,version)) {
        console("GW FAIL AT_VERSION\r\n");return 0;
    }
    (void)snprintf(command,sizeof(command),"GW AT_VERSION value=%s\r\n",version);console(command);
#endif
    int wifi_ok=wifi_join(command,sizeof command,30000);
    if (!wifi_ok) {
#ifdef MP_FIVE_FIELD01
        char code[2]={gateway_wifi_join_code(at_response()),'\0'};
        (void)snprintf(command,sizeof(command),"GW FAIL WIFI code=%s uart_errors=%lu\r\n",
            code[0]?code:"NONE",(unsigned long)platform_uart_errors_total());
        console(command);
#else
        console("GW FAIL WIFI\r\n");
#endif
        return 0;
    }
    console("GW OK WIFI\r\n");
#ifdef MP_CAN_RX_IRQ
    /* 查询结果只报告信号/休眠枚举；SSID、BSSID和原始回复不写控制台。 */
    int channel,rssi;
    if(at_command("AT+CWJAP?",2000) && gateway_wifi_signal(at_response(),&channel,&rssi)) {
        (void)snprintf(command,sizeof(command),"GW WIFI_SIGNAL channel=%d rssi=%d\r\n",channel,rssi);console(command);
    } else console("GW WIFI_SIGNAL_UNAVAILABLE\r\n");
    int sleep_before=at_command("AT+SLEEP?",2000)?gateway_sleep_mode(at_response()):-1;
#ifdef MP_H3_WIFI_AWAKE
    /* 仅显式H3候选关闭无线休眠；不写模块Flash，不改变TLS/5000ms/PUBACK门禁。 */
    if(sleep_before<0 || (sleep_before!=0 && !step("WIFI_AWAKE","AT+SLEEP=0",2000)))return 0;
    int sleep_after=at_command("AT+SLEEP?",2000)?gateway_sleep_mode(at_response()):-1;
    if(sleep_after!=0) {console("GW FAIL WIFI_AWAKE_VERIFY\r\n");return 0;}
#else
    int sleep_after=sleep_before;
#endif
    (void)snprintf(command,sizeof(command),"GW WIFI_SLEEP before=%d after=%d\r\n",sleep_before,sleep_after);console(command);
#endif
    (void)at_command("AT+CIPCLOSE", 2000);
    if (!step("SINGLE", "AT+CIPMUX=0", 2000) || !step("PASSIVE", "AT+CIPRECVMODE=1", 2000))
        return 0;
    /* 模块时间必须有效；不能用过时的编译时间冒充采集时间。 */
#if defined(MP_B5_EGRESS_FINAL) && defined(MP_H3_FRESH_SNTP)
    if(!sntp_bootstrap(command)){console("GW FAIL TIME\r\n");return 0;}
#else
    if(!step("SNTP_ENABLE","AT+CIPSNTPCFG=1,0",2000))return 0;
    int time_ok = 0;
#ifdef MP_B5_EGRESS_FINAL
    uint32_t time_wait_at=g_uptime_ms,time_queries=0;
#endif
    for (unsigned int attempt = 0; attempt < 15U; ++attempt)
    {
#ifdef MP_B5_EGRESS_FINAL
        time_queries++;
#endif
        if (at_command("AT+SYSTIMESTAMP?", 2000))
        {
            const char *value = strstr(at_response(), "+SYSTIMESTAMP:");
            if (value)
            {
                epoch = (uint32_t)strtoul(value + 14, NULL, 10);
                if (epoch >= config->minimum_epoch)
                {
                    epoch_tick = g_uptime_ms;
                    time_ok = 1;
                    break;
                }
            }
        }
#ifdef MP_B5_EGRESS_FINAL
        /* 15次查询按绝对2秒时隙推进，粗授时准备有界30秒；共同就绪60秒不变。 */
        if(attempt<14u){int32_t wait=(int32_t)(time_wait_at+(attempt+1u)*2000u-g_uptime_ms);if(wait>0)delay_ms((uint32_t)wait);}
#else
        delay_ms(1000);
#endif
    }
#ifdef MP_B5_EGRESS_FINAL
    (void)snprintf(command,sizeof(command),"GW TIME_WAIT queries=%lu elapsed=%lu valid=%u epoch=%lu\r\n",
        (unsigned long)time_queries,(unsigned long)(g_uptime_ms-time_wait_at),(unsigned)time_ok,(unsigned long)epoch);console(command);
#endif
    if (!time_ok)
    {
        console("GW FAIL TIME\r\n");
        return 0;
    }
#endif
#ifdef MP_H3_FRESH_SNTP
    if(!fresh_sntp())return 0;
#endif
#ifdef MP_CAN_RX_IRQ
    (void)snprintf(command,sizeof(command),"GW SNTP_VALID epoch=%lu uptime=%lu\r\n",(unsigned long)epoch,(unsigned long)epoch_tick);console(command);
#endif
    if (!step("CA_VERIFY", "AT+CIPSSLCCONF=2,0,0", 2000))
        return 0;
    (void)snprintf(command, sizeof(command), "AT+CIPSSLCCN=\"%s\"", config->host);
    int cert_ok = step("CERT_NAME", command, 2000);
    /* 复用缓冲区中的外部连接配置也在每次使用后清除，不依赖最终成功路径。 */
    secure_memzero(command, sizeof(command));
    if (!cert_ok)
        return 0;
    /* 此模块存在 SNI 优先的行为，两个名称必须绑定同一个外部配置目标。 */
    (void)snprintf(command, sizeof(command), "AT+CIPSSLCSNI=\"%s\"", config->host);
    int sni_ok = step("SNI", command, 2000);
    secure_memzero(command, sizeof(command));
    if (!sni_ok)
        return 0;
    (void)snprintf(command, sizeof(command), "AT+CIPSTART=\"SSL\",\"%s\",%u", config->host, (unsigned)MP_MQTT_TLS_PORT);
    int ok = step("TLS", command, 30000);
    secure_memzero(command, sizeof(command));
    if (ok)
        mqtt_adapter_reset(&network);
    return ok;
}
