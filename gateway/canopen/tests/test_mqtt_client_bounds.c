#include <assert.h>
#include <stdio.h>
#include <string.h>

#include "MQTTClient.h"

/* cycle 是实际生产实现中的入口；不复制实现、不向公共 API 添加测试接口。 */
extern int cycle(MQTTClient *client, Timer *timer);

void TimerInit(Timer *timer)
{
    timer->remaining_ms = 0;
}

char TimerIsExpired(Timer *timer)
{
    return timer->remaining_ms == 0;
}

void TimerCountdownMS(Timer *timer, unsigned int milliseconds)
{
    timer->remaining_ms = milliseconds;
}

void TimerCountdown(Timer *timer, unsigned int seconds)
{
    timer->remaining_ms = seconds * 1000;
}

int TimerLeftMS(Timer *timer)
{
    return (int)timer->remaining_ms;
}

static int memory_read(Network *network, unsigned char *buffer, int length, int timeout)
{
    (void)timeout;
    ++network->read_calls;
    assert(length >= 0);
    if ((size_t)length > network->input_size - network->input_offset)
        return 0;
    memcpy(buffer, network->input + network->input_offset, (size_t)length);
    network->input_offset += (size_t)length;
    return length;
}

static int memory_write(Network *network, unsigned char *buffer, int length, int timeout)
{
    (void)buffer;
    (void)timeout;
    ++network->write_calls;
    return length;
}

static void load_input(Network *network, const unsigned char *input, size_t size)
{
    network->mqttread = memory_read;
    network->mqttwrite = memory_write;
    network->input = input;
    network->input_size = size;
    network->input_offset = 0;
    network->read_calls = 0;
    network->write_calls = 0;
}

static unsigned int handler_calls;

static void message_handler(MessageData *message)
{
    (void)message;
    ++handler_calls;
}

int main(void)
{
    MQTTClient client;
    Network network;
    Timer timer = {1000};
    unsigned char sendbuf[64], readbuf[64];
    const unsigned char valid_ack[] = {0x40, 2, 0, 42};
    const unsigned char truncated_length[] = {0x40, 0x80};
    const unsigned char five_byte_length[] = {0x40, 0x80, 0x80, 0x80, 0x80, 0x80};
    const unsigned char short_payload[] = {0x40, 2, 0};
    const unsigned char declared_too_long[] = {0x40, 100, 0, 42};
    const unsigned char inbound_publish[] = {0x30, 7, 0, 1, 't', 'd', 'a', 't', 'a'};

    /* 非零旧内存模拟重复初始化，防止依赖静态对象恰好默认清零。 */
    memset(&client, 0xa5, sizeof(client));
    load_input(&network, valid_ack, sizeof(valid_ack));
    MQTTClientInit(&client, &network, 1000, sendbuf, sizeof(sendbuf), readbuf, sizeof(readbuf));
    assert(client.read_packet_len == 0);
    client.keepAliveInterval = 0;
    assert(cycle(&client, &timer) == PUBACK);
    assert(client.read_packet_len == sizeof(valid_ack));

    /* 前一包有效、下一包超时；不得留下上一包实际长度。 */
    assert(cycle(&client, &timer) == 0);
    assert(client.read_packet_len == 0);

    client.read_packet_len = sizeof(valid_ack);
    load_input(&network, truncated_length, sizeof(truncated_length));
    assert(cycle(&client, &timer) == FAILURE);
    assert(client.read_packet_len == 0 && network.read_calls == 3);

    client.read_packet_len = sizeof(valid_ack);
    load_input(&network, five_byte_length, sizeof(five_byte_length));
    assert(cycle(&client, &timer) == FAILURE);
    assert(client.read_packet_len == 0 && network.read_calls == 5);

    client.read_packet_len = sizeof(valid_ack);
    load_input(&network, short_payload, sizeof(short_payload));
    assert(cycle(&client, &timer) == FAILURE);
    assert(client.read_packet_len == 0);

    client.read_packet_len = sizeof(valid_ack);
    load_input(&network, declared_too_long, sizeof(declared_too_long));
    assert(cycle(&client, &timer) == BUFFER_OVERFLOW);
    assert(client.read_packet_len == 0 && network.read_calls == 2);

    /* 相同正常 ACK、零容量和单字节容量验证前缀写入之前的边界门禁。 */
    load_input(&network, valid_ack, sizeof(valid_ack));
    client.readbuf_size = 0;
    assert(cycle(&client, &timer) == FAILURE);
    assert(client.read_packet_len == 0 && network.read_calls == 0);
    readbuf[1] = 0xa5;
    client.readbuf_size = 1;
    assert(cycle(&client, &timer) == BUFFER_OVERFLOW);
    assert(client.read_packet_len == 0 && readbuf[1] == 0xa5);

    /* 冻结 publish-only 语义：合法下行 PUBLISH 也必须失败并关闭 MQTT 会话。
     * 同时注册匹配回调和默认回调，确保任何分派路径均未被调用。 */
    client.readbuf_size = sizeof(readbuf);
    client.isconnected = 1;
    client.cleansession = 1;
    client.ping_outstanding = 1;
    client.defaultMessageHandler = message_handler;
    assert(MQTTSetMessageHandler(&client, "t", message_handler) == SUCCESS);
    load_input(&network, inbound_publish, sizeof(inbound_publish));
    assert(cycle(&client, &timer) == FAILURE);
    assert(!MQTTIsConnected(&client) && client.ping_outstanding == 0);
    assert(client.messageHandlers[0].topicFilter == NULL);
    assert(handler_calls == 0 && network.write_calls == 0);
    puts("PASS: 10 fixed MQTTClient lifecycle/rejection cases");
    return 0;
}
