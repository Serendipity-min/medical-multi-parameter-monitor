/* 正常 MQTT 字节流的固定合成夹具；只替换 ESP I/O，客户端、序列化和 Router 均为真源码。 */
#include "mock_esp.h"
#include "gateway_config.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>

const GatewayConfig gateway_test_config = {
    GATEWAY_CONFIG_MAGIC, 1700000000U, "synthetic-wifi", "synthetic-wifi-password",
    "mqtt.example.invalid", "synthetic-user", "synthetic-mqtt-password", "synthetic-client"
};
volatile uint32_t g_uptime_ms;
int mock_ack_mode, mock_delay_ms, mock_read_limit, mock_send_limit;
int mock_send_error, mock_send_zero, mock_connack_code, mock_drop_ping;
int mock_drop_connack;
int mock_tls_started, mock_ping_count;
uint16_t mock_last_id, mock_old_id;
unsigned char mock_packet[2048];
size_t mock_packet_length;
const char *mock_fail_at;
MpRouter *mock_router_probe;
static unsigned char wire[2048], rx[1024], ack[12];
static size_t wire_length, rx_length, rx_offset, ack_length;
static uint32_t ack_at;

void platform_poll(void) { g_uptime_ms++; }
void mp_model_poll(void) { platform_poll(); }
void console(const char *text) { (void)text; }
void delay_ms(uint32_t ms) { g_uptime_ms += ms; }
const char *at_response(void) { return "+SYSTIMESTAMP:1800000000"; }
int at_command(const char *command, uint32_t timeout)
{
    (void)timeout;
    if (mock_fail_at && !strcmp(command, mock_fail_at)) return 0;
    if (!strncmp(command, "AT+CIPSTART=", 12)) mock_tls_started = 1;
    /* 假配置中只允许 SSL:8883，名称命令绑定同一合成主机。 */
    if (!strncmp(command, "AT+CIPSTART=", 12))
        assert(strstr(command, "\"SSL\",\"mqtt.example.invalid\",8883"));
    if (!strncmp(command, "AT+CIPSSLCCN=", 13) || !strncmp(command, "AT+CIPSSLCSNI=", 13))
        assert(strstr(command, "mqtt.example.invalid"));
    return 1;
}

void esp_mqtt_reset(void)
{
    wire_length = rx_length = rx_offset = ack_length = 0;
}

void mock_queue(const unsigned char *packet, size_t length)
{
    assert(length <= sizeof(rx) - rx_length);
    memcpy(rx + rx_length, packet, length);
    rx_length += length;
}

static size_t header_size(const unsigned char *packet, size_t *remaining)
{
    size_t offset = 1, multiplier = 1;
    *remaining = 0;
    do {
        *remaining += (packet[offset] & 127U) * multiplier;
        multiplier *= 128U;
    } while (packet[offset++] & 128U);
    return offset;
}

static void sent_packet(void)
{
    memcpy(mock_packet, wire, wire_length);
    mock_packet_length = wire_length;
    unsigned type = wire[0] & 0xf0U;
    if (type == 0x10)
    {
        unsigned char connack[] = {0x20, 2, 0, (unsigned char)mock_connack_code};
        if (!mock_drop_connack) mock_queue(connack, sizeof(connack));
    }
    else if (type == 0xc0)
    {
        mock_ping_count++;
        unsigned char ping[] = {0xd0, 0};
        if (!mock_drop_ping) mock_queue(ping, sizeof(ping));
    }
    else if (type == 0x30 && (wire[0] & 6U) == 2U)
    {
        size_t remaining, start = header_size(wire, &remaining);
        size_t topic_length = ((size_t)wire[start] << 8) | wire[start + 1];
        size_t id_offset = start + 2 + topic_length;
        mock_last_id = (uint16_t)((wire[id_offset] << 8) | wire[id_offset + 1]);
        uint16_t ack_id = mock_ack_mode == ACK_WRONG ? (uint16_t)(mock_last_id + 1) : mock_last_id;
        if (mock_ack_mode == ACK_OLD) ack_id = mock_old_id;
        ack[0] = 0x40; ack[1] = 2; ack[2] = (unsigned char)(ack_id >> 8); ack[3] = (unsigned char)ack_id;
        ack_length = mock_ack_mode == ACK_NONE ? 0 : mock_ack_mode == ACK_HALF ? 2 : 4;
        if (mock_ack_mode == ACK_DUPLICATE)
        {
            memcpy(ack + 4, ack, 4); ack_length = 8;
        }
        if (mock_ack_mode == ACK_INBOUND)
        {
            unsigned char publish[] = {0x30, 4, 0, 1, 'x', 'y'};
            memcpy(ack, publish, sizeof(publish)); ack_length = sizeof(publish);
        }
        if (mock_ack_mode == ACK_INBOUND_QOS1)
        {
            unsigned char publish[] = {0x32, 6, 0, 1, 'x', 0, 19, 'y'};
            memcpy(ack, publish, sizeof(publish)); ack_length = sizeof(publish);
        }
        ack_at = g_uptime_ms + (uint32_t)mock_delay_ms;
    }
    wire_length = 0;
}

int esp_mqtt_send(const unsigned char *data, int length, uint32_t timeout)
{
    assert(timeout > 0);
    platform_poll();
    if (mock_send_error) return -1;
    if (mock_send_zero) return 0;
    int sent = mock_send_limit && length > mock_send_limit ? mock_send_limit : length;
    assert((size_t)sent <= sizeof(wire) - wire_length);
    memcpy(wire + wire_length, data, (size_t)sent);
    wire_length += (size_t)sent;
    if (wire_length >= 2)
    {
        size_t remaining = 0, header = 1;
        /* 先等变长长度的最后一字节，短写中间不把报文当成完整。 */
        while (header < wire_length && (wire[header] & 128U)) header++;
        if (header < wire_length)
        {
            header = header_size(wire, &remaining);
            if (wire_length == header + remaining) sent_packet();
        }
    }
    return sent;
}

int esp_mqtt_recv(unsigned char *data, int length, uint32_t timeout)
{
    platform_poll();
    if (mock_router_probe)
        assert(!mock_router_probe->ready_for_replay && !mock_router_probe->replayed);
    if (ack_length && (int32_t)(g_uptime_ms - ack_at) >= 0)
    {
        mock_queue(ack, ack_length); ack_length = 0;
    }
    size_t count = rx_length - rx_offset;
    if (count > (size_t)length) count = (size_t)length;
    if (mock_read_limit && count > (size_t)mock_read_limit) count = (size_t)mock_read_limit;
    if (count)
    {
        memcpy(data, rx + rx_offset, count);
        rx_offset += count;
        if (rx_offset == rx_length) rx_offset = rx_length = 0;
    }
    else g_uptime_ms += timeout;
    return (int)count;
}

void mock_reset(void)
{
    g_uptime_ms = 100000;
    mock_ack_mode = ACK_MATCH;
    mock_delay_ms = mock_read_limit = mock_send_limit = 0;
    mock_send_error = mock_send_zero = mock_connack_code = mock_drop_ping = 0;
    mock_drop_connack = 0;
    mock_tls_started = mock_ping_count = 0;
    mock_last_id = mock_old_id = 0;
    mock_fail_at = NULL;
    mock_router_probe = NULL;
    mock_packet_length = 0;
    esp_mqtt_reset();
}

MpFrame mock_frame(MpStream stream, uint16_t rate, bool replay)
{
    MpFrame frame = {0};
    frame.timestamp = 1800000000000ULL;
    frame.epoch = 1800000000U;
    frame.seq = 7; frame.boot = 1;
    frame.node = stream == MP_SPO2 || stream == MP_PPG ? 1 : stream == MP_GATEWAY_STATUS ? 0 : 2;
    frame.stream = (uint8_t)stream;
    frame.count = 1; frame.rate = rate; frame.values[0] = 72;
    frame.valid = stream != MP_RR; frame.synthetic = true; frame.replay = replay;
    return frame;
}

void mock_connect(void)
{
    mock_reset();
    assert(gateway_config_valid());
    assert(gateway_network_open());
    MpFrame will = mock_frame(MP_GATEWAY_STATUS, 0, false);
    will.valid = false;
    assert(gateway_mqtt_open(&will));
}
