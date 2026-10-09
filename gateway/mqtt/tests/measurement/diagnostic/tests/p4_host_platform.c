/* P4诊断联测的纯合成I/O shim；真实Paho和插桩Gateway仍参与测试，没有网络socket。 */
#include "gateway_platform.h"
extern int esp_mqtt_send(const unsigned char *, int, unsigned int);
extern int esp_mqtt_recv(unsigned char *, int, unsigned int);
extern void esp_mqtt_reset(void);

void TimerInit(Timer *timer) { timer->deadline = g_uptime_ms; }
char TimerIsExpired(Timer *timer) { return (int32_t)(g_uptime_ms - timer->deadline) >= 0; }
void TimerCountdownMS(Timer *timer, unsigned int ms) { timer->deadline = g_uptime_ms + ms; }
void TimerCountdown(Timer *timer, unsigned int seconds) { TimerCountdownMS(timer, seconds * 1000U); }
int TimerLeftMS(Timer *timer)
{
    int32_t left = (int32_t)(timer->deadline - g_uptime_ms);
    return left > 0 ? left : 0;
}
static int write_bytes(Network *network, unsigned char *data, int length, int timeout)
{
    (void)network;
    return esp_mqtt_send(data, length, (unsigned int)timeout);
}
static int read_bytes(Network *network, unsigned char *data, int length, int timeout)
{
    (void)network;
    int copied = 0;
    uint32_t deadline = g_uptime_ms + (uint32_t)(timeout > 0 ? timeout : 1);
    /* P4读契约累积到请求长度或截止；合成无数据轮询短等待，不能一次假跳5s吞掉延迟ACK。 */
    while (copied < length && (int32_t)(deadline - g_uptime_ms) > 0)
    {
        uint32_t budget = deadline - g_uptime_ms;
        int count = esp_mqtt_recv(data + copied, length - copied, budget > 10U ? 10U : budget);
        if (count < 0)
            return count;
        copied += count;
    }
    return copied;
}
void network_init(Network *network)
{
    network->mqttwrite = write_bytes;
    network->mqttread = read_bytes;
    esp_mqtt_reset();
}
