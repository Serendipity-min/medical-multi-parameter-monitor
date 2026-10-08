/* 复用第一阶段已验证的 ESP SSL/CA/时间校验，只在外部配置中保存凭据。 */
#include "gateway_transport.h"
#include "gateway_config.h"
#include "core_mqtt.h"
#include "mqtt_transport_adapter.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

/* 一个串行发布者、一个在途 QoS1 记录；总 TX/RX 容量沿用 P4，不分配堆。 */
static NetworkContext_t network;
static MQTTContext_t client;
static MQTTPubAckInfo_t outgoing[1];
static unsigned char rx_buffer[512];
static uint16_t pending_id, next_packet_seed = 1;
static int acknowledged, session_error, mqtt_online, partial_waiting;
static uint32_t partial_since;
static uint32_t epoch, epoch_tick;
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
    return config->magic == GATEWAY_CONFIG_MAGIC && !config->host[64] && !config->ssid[32] &&
           !config->wifi_password[64] && !config->password[64] && !config->username[32] &&
           !config->client_id[40];
}

/* SNTP 提供秒级基准，后续用无符号毫秒差推进，兼容一次 SysTick 计数回绕。 */
uint32_t gateway_epoch(void)
{
    return epoch + (uint32_t)(g_uptime_ms - epoch_tick) / 1000;
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
    if (context != &client || (packet->type & 0xf0U) == MQTT_PACKET_TYPE_PUBLISH)
    {
        mqtt_failed();
        return;
    }
    if (packet->type == MQTT_PACKET_TYPE_PUBACK && decoded->deserializationResult == MQTTSuccess
        && pending_id && decoded->packetIdentifier == pending_id)
        acknowledged = 1;
    else
        mqtt_failed();
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
            mqtt_failed();
    }
    else if (status != MQTTSuccess)
        mqtt_failed();
    else if (!client.index)
        partial_waiting = 0;
    return !session_error && network.connected;
}

/* 重连清空 context/记录和 RX；包标识在本次开机中继续递增，拒绝旧会话迟到 ACK。 */
int gateway_mqtt_open(const MpFrame *will_frame)
{
    char will[512];
    if (!mp_json(will_frame, will, sizeof(will)))
    {
        /* 序列化失败时也可能已有部分内容，返回前清除整个临时缓冲区。 */
        secure_memzero(will, sizeof(will));
        return 0;
    }
    session_error = acknowledged = partial_waiting = mqtt_online = 0;
    pending_id = 0;
    memset(outgoing, 0, sizeof(outgoing));
    memset(rx_buffer, 0, sizeof(rx_buffer));
    TransportInterface_t transport = mqtt_adapter_interface(&network);
    MQTTFixedBuffer_t buffer = {rx_buffer, sizeof(rx_buffer)};
    MQTTStatus_t status = MQTT_Init(&client, &transport, mqtt_adapter_time, mqtt_event, &buffer);
    if (status == MQTTSuccess)
        status = MQTT_InitStatefulQoS(&client, outgoing, 1, NULL, 0);
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
    will_info.pTopicName = "mpm/v1/GW-C-001/status";
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
    if (!mqtt_online || !network.connected)
        return 0;
    static char payload[2048];
    char topic[120];
    int length = mp_json(frame, payload, sizeof(payload));
    if (!length || !mp_topic(frame, topic, sizeof(topic)))
        return 0;
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
    int ok = MQTT_Publish(&client, &message, pending_id) == MQTTSuccess;
    if (message.qos == MQTTQoS1)
    {
        /* Publish/SEND OK 只是发送结果；匹配 PUBACK 到达后才允许 Router 成功 ACK。 */
        while (ok && !acknowledged && (uint32_t)(g_uptime_ms - start) < 5000U)
            ok = process_once();
        ok = ok && acknowledged;
    }
    ok = ok && !session_error && network.connected && (uint32_t)(g_uptime_ms - start) < 5000U;
    pending_id = 0;
    acknowledged = 0;
    if (!ok)
        mqtt_failed();
    return ok;
}

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
    (void)at_command("AT+CIPCLOSE", 2000);
}

/* 固定顺序为 AT 配置、入网、可信时间、证书名称校验、TLS；任何失败由外层重试。 */
int gateway_network_open(void)
{
    char command[256];
    mqtt_failed();
    esp_mqtt_reset();
    if (!step("AT", "AT", 2000) || !step("ECHO", "ATE0", 2000) ||
        !step("VOLATILE", "AT+SYSSTORE=0", 2000) || !step("STA", "AT+CWMODE=1", 3000))
        return 0;
    /* 对有效配置生成相同命令；显式字段边界也让 host 编译器证明不会跨字段读取。 */
    (void)snprintf(command, sizeof(command), "AT+CWJAP=\"%.*s\",\"%.*s\"",
                   (int)sizeof(config->ssid) - 1, config->ssid,
                   (int)sizeof(config->wifi_password) - 1, config->wifi_password);
    int wifi_ok = step("WIFI", command, 30000);
    /* 先清除 SSID/口令再分支，Wi-Fi 失败及后续提前返回都不残留该命令。 */
    secure_memzero(command, sizeof(command));
    if (!wifi_ok)
        return 0;
    (void)at_command("AT+CIPCLOSE", 2000);
    if (!step("SINGLE", "AT+CIPMUX=0", 2000) || !step("PASSIVE", "AT+CIPRECVMODE=1", 2000))
        return 0;
    /* 模块时间必须有效；不能用过时的编译时间冒充采集时间。 */
    (void)at_command("AT+CIPSNTPCFG=1,0", 2000);
    int time_ok = 0;
    for (unsigned int attempt = 0; attempt < 15U; ++attempt)
    {
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
        delay_ms(1000);
    }
    if (!time_ok)
    {
        console("GW FAIL TIME\r\n");
        return 0;
    }
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
    (void)snprintf(command, sizeof(command), "AT+CIPSTART=\"SSL\",\"%s\",8883", config->host);
    int ok = step("TLS", command, 30000);
    secure_memzero(command, sizeof(command));
    if (ok)
        mqtt_adapter_reset(&network);
    return ok;
}
