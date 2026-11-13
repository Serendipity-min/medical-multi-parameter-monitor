/* 普通真实 Broker 夹具：生产 MQTT/Router 源码 + 本机 POSIX TCP；不代表 ESP AT/TLS。 */
#define _POSIX_C_SOURCE 200809L
#include "gateway_transport.h"
#include "gateway_config.h"
#include "../../storage/router.h"
#include <arpa/inet.h>
#include <errno.h>
#include <poll.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/socket.h>
#include <time.h>
#include <unistd.h>

const GatewayConfig gateway_test_config = {
    GATEWAY_CONFIG_MAGIC, 1700000000U, "synthetic-wifi", "synthetic-wifi-password",
    "mqtt.example.invalid", "synthetic-user", "synthetic-mqtt-password", "synthetic-client"
};
volatile uint32_t g_uptime_ms;
static int socket_fd = -1, port;
static unsigned char tx_trace[4096], rx_trace[512];
static size_t tx_length, rx_length;
static uint16_t published_id, received_id;
static uint32_t ack_at, ping_count;

void platform_poll(void)
{
    struct timespec now;
    clock_gettime(CLOCK_MONOTONIC, &now);
    g_uptime_ms = (uint32_t)((uint64_t)now.tv_sec * 1000U + (uint32_t)now.tv_nsec / 1000000U);
}
void mp_model_poll(void) { platform_poll(); }
void console(const char *message) { (void)message; }
void delay_ms(uint32_t duration)
{
    struct timespec delay = {(time_t)(duration / 1000U), (long)(duration % 1000U) * 1000000L};
    nanosleep(&delay, NULL);
    platform_poll();
}
static void close_socket(void)
{
    if (socket_fd >= 0) close(socket_fd);
    socket_fd = -1;
}
const char *at_response(void) { return "+SYSTIMESTAMP:1800000000"; }
int at_command(const char *command, uint32_t timeout)
{
    (void)timeout;
    if (!strcmp(command, "AT+CIPCLOSE")) close_socket();
    if (!strncmp(command, "AT+CIPSTART=", 12))
    {
        /* 目标硬编码为 loopback；命令中的生产式 TLS 参数只做调用兼容，不执行 TLS。 */
        struct sockaddr_in address = {0};
        address.sin_family = AF_INET;
        address.sin_port = htons((uint16_t)port);
        address.sin_addr.s_addr = htonl(INADDR_LOOPBACK);
        socket_fd = socket(AF_INET, SOCK_STREAM, 0);
        return socket_fd >= 0 && !connect(socket_fd, (struct sockaddr *)&address, sizeof(address));
    }
    return 1;
}
void esp_mqtt_reset(void)
{
    tx_length = rx_length = 0;
    published_id = received_id = 0;
}

/* 仅从正常测试报文记录 packet ID/时间，不输出 CONNECT、密码或原始字节。 */
static void trace_packet(unsigned char *buffer, size_t *used, const void *data, size_t count, int sending)
{
    size_t capacity = sending ? sizeof(tx_trace) : sizeof(rx_trace);
    if (count > capacity - *used) { *used = 0; return; }
    memcpy(buffer + *used, data, count);
    *used += count;
    while (*used >= 2)
    {
        size_t index = 1, remaining = 0, multiplier = 1;
        do {
            if (index >= *used || index > 4) return;
            remaining += (buffer[index] & 127U) * multiplier;
            multiplier *= 128U;
        } while (buffer[index++] & 128U);
        if (remaining > *used - index) return;
        if (sending && (buffer[0] & 0xf0U) == 0x30U)
        {
            published_id = 0;
            if ((buffer[0] & 6U) == 2U && remaining >= 4)
            {
                size_t topic_length = ((size_t)buffer[index] << 8) | buffer[index + 1];
                size_t offset = index + 2 + topic_length;
                if (offset + 2 <= index + remaining)
                    published_id = (uint16_t)((buffer[offset] << 8) | buffer[offset + 1]);
            }
        }
        if (sending && buffer[0] == 0xc0U) ping_count++;
        if (!sending && buffer[0] == 0x40U && remaining == 2)
        {
            received_id = (uint16_t)((buffer[index] << 8) | buffer[index + 1]);
            platform_poll(); ack_at = g_uptime_ms;
        }
        memmove(buffer, buffer + index + remaining, *used - index - remaining);
        *used -= index + remaining;
    }
}
int esp_mqtt_send(const unsigned char *data, int length, uint32_t timeout)
{
    struct pollfd fd = {socket_fd, POLLOUT, 0};
    if (socket_fd < 0 || poll(&fd, 1, (int)timeout) <= 0) return -1;
    ssize_t sent = send(socket_fd, data, (size_t)length, MSG_NOSIGNAL);
    if (sent > 0) trace_packet(tx_trace, &tx_length, data, (size_t)sent, 1);
    platform_poll();
    return (int)sent;
}
int esp_mqtt_recv(unsigned char *data, int length, uint32_t timeout)
{
    struct pollfd fd = {socket_fd, POLLIN, 0};
    int ready = socket_fd < 0 ? -1 : poll(&fd, 1, (int)timeout);
    platform_poll();
    if (ready < 0) return -1;
    if (!ready) return 0;
    ssize_t received = recv(socket_fd, data, (size_t)length, 0);
    if (received <= 0) return -1;
    trace_packet(rx_trace, &rx_length, data, (size_t)received, 0);
    return (int)received;
}

#ifdef P5_P4_BASELINE_TEST
#include "mocks/p4_platform_for_broker.h"
/* 固定 P4 的 Timer/Network 只桥接同一 POSIX 字节流，不改 Paho 或原 Gateway 逻辑。 */
void TimerInit(Timer *timer) { platform_poll(); timer->deadline = g_uptime_ms; }
char TimerIsExpired(Timer *timer) { platform_poll(); return (int32_t)(g_uptime_ms - timer->deadline) >= 0; }
void TimerCountdownMS(Timer *timer, unsigned ms) { platform_poll(); timer->deadline = g_uptime_ms + ms; }
void TimerCountdown(Timer *timer, unsigned seconds) { TimerCountdownMS(timer, seconds * 1000U); }
int TimerLeftMS(Timer *timer)
{
    platform_poll(); int32_t left = (int32_t)(timer->deadline - g_uptime_ms);
    return left > 0 ? left : 0;
}
static int p4_read(Network *network, unsigned char *data, int length, int timeout)
{ (void)network; return esp_mqtt_recv(data, length, (uint32_t)timeout); }
static int p4_write(Network *network, unsigned char *data, int length, int timeout)
{ (void)network; return esp_mqtt_send(data, length, (uint32_t)timeout); }
void network_init(Network *network)
{ esp_mqtt_reset(); network->mqttread = p4_read; network->mqttwrite = p4_write; }
#endif

static MpFrame frame_for(const char *command)
{
    MpFrame frame = {0};
    frame.timestamp = 1800000000123ULL; frame.epoch = 1800000000U;
    frame.seq = 17; frame.boot = 1; frame.valid = true; frame.synthetic = true;
    frame.count = 1; frame.node = 1; frame.stream = MP_SPO2; frame.values[0] = 9800;
    if (!strcmp(command, "status")) { frame.node = 0; frame.stream = MP_GATEWAY_STATUS; }
    if (!strcmp(command, "wave") || !strcmp(command, "replay"))
    {
        frame.node = 2; frame.stream = MP_ECG; frame.rate = 250; frame.count = 4;
        frame.values[0] = 120000; frame.values[1] = -120000; frame.values[2] = 0; frame.values[3] = 50000;
        frame.replay = !strcmp(command, "replay");
    }
    return frame;
}

int main(int argc, char **argv)
{
    if (argc != 2 || (port = atoi(argv[1])) <= 1024 || port > 65535) return 64;
    setvbuf(stdout, NULL, _IOLBF, 0);
    platform_poll();
    MpFrame will = frame_for("status"); will.valid = false;
    if (!gateway_config_valid() || !gateway_network_open() || !gateway_mqtt_open(&will)) return 2;
    MpRouter router; mp_router_init(&router); mp_router_online(&router, true);
    MpFrame online = frame_for("status");
    if (!gateway_mqtt_publish(&online)) return 3;
    puts("{\"ready\":true}");
    for (;;)
    {
        struct pollfd input = {STDIN_FILENO, POLLIN, 0};
        if (poll(&input, 1, 5) > 0)
        {
            char command[32];
            if (!fgets(command, sizeof(command), stdin)) break;
            command[strcspn(command, "\r\n")] = 0;
            if (!strcmp(command, "close")) break;
            if (strcmp(command, "scalar") && strcmp(command, "wave") && strcmp(command, "replay")) return 65;
            MpFrame frame = frame_for(command), sent;
            mp_router_put(&router, &frame);
            if (!mp_router_take(&router, &sent, g_uptime_ms)) return 66;
            platform_poll(); uint32_t start = g_uptime_ms;
            received_id = 0;
            int ok = gateway_mqtt_publish(&sent);
            platform_poll(); uint32_t end = g_uptime_ms;
            mp_router_ack(&router, &sent, ok != 0);
            printf("{\"command\":\"%s\",\"ok\":%s,\"elapsed_ms\":%lu,\"published_id\":%u,"
                   "\"puback_id\":%u,\"puback_before_return\":%s,\"pings\":%lu,\"cache\":%u,"
                   "\"router_online\":%s,\"seq\":%lu,\"timestamp\":%llu}\n",
                   command, ok ? "true" : "false", (unsigned long)(end - start), published_id,
                   received_id, published_id && received_id == published_id && (int32_t)(end - ack_at) >= 0
                   ? "true" : "false", (unsigned long)ping_count, router.cn,
                   router.online ? "true" : "false", (unsigned long)sent.seq,
                   (unsigned long long)sent.timestamp);
            if (!ok) break;
        }
        if (!gateway_mqtt_yield()) break;
    }
    gateway_network_close();
    return 0;
}
