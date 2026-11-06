/* 将库的字节/向量接口桥接到已有 ESP AT，同一报文只执行一次 CIPSEND。 */
#include "mqtt_transport_adapter.h"
#include "gateway_platform.h"
#include <string.h>

uint32_t mqtt_adapter_time(void)
{
    platform_poll();
    return g_uptime_ms;
}

void mqtt_adapter_reset(NetworkContext_t *network)
{
    memset(network, 0, sizeof(*network));
    network->connected = true;
}

void mqtt_adapter_begin(NetworkContext_t *network, uint32_t timeout_ms)
{
    network->deadline = g_uptime_ms + timeout_ms;
}

void mqtt_adapter_close(NetworkContext_t *network)
{
    network->connected = false;
#ifdef MP_FINAL_UNIFIED
    memset(network->tx,0,sizeof network->tx);
    network->queued=0;network->collect=network->flush_requested=false;
#endif
}

/* 小于 2^31 ms 的预算用有符号差处理 SysTick 回绕。 */
static uint32_t remaining(NetworkContext_t *network)
{
    int32_t value = (int32_t)(network->deadline - g_uptime_ms);
    return value > 0 ? (uint32_t)value : 0;
}

#ifdef MP_FINAL_UNIFIED
bool mqtt_adapter_room(NetworkContext_t *network,size_t length)
{
    if(length>sizeof network->tx-network->queued){network->flush_requested=true;return false;}
    return true;
}

int mqtt_adapter_flush(NetworkContext_t *network)
{
    size_t sent=0,length=network->queued;
    /* 完整报文串在同一TCP流上；短写继续剩余字节，不重发前缀。 */
    while(sent<length){
        uint32_t budget=remaining(network);
        if(!budget)break;
        int n=esp_mqtt_send(network->tx+sent,(int)(length-sent),budget);
        if(n<=0 || (size_t)n>length-sent)break;
        sent+=(size_t)n;
    }
    memset(network->tx,0,length);network->queued=0;network->flush_requested=false;
    if(sent!=length){network->connected=false;return 0;}
    return 1;
}
#endif

static int32_t send_bytes(NetworkContext_t *network, const void *data, size_t length)
{
    if (!network || !network->connected || (length && !data) || length > sizeof(network->tx))
        return -1;
    if (!length)
        return 0;
#ifdef MP_FINAL_UNIFIED
    if(network->collect){
        if(!mqtt_adapter_room(network,length))return -1;
        if(!network->queued)network->queued_at=g_uptime_ms;
        memcpy(network->tx+network->queued,data,length);network->queued+=length;
        return (int32_t)length;
    }
#endif
    uint32_t budget = remaining(network);
    if (!budget)
        return -1;
    int result = esp_mqtt_send(data, (int)length, budget);
    /* 短写的字节数交回 coreMQTT 重试；负值和不可能的长度明确失败。 */
    if (result < 0 || (size_t)result > length)
    {
        network->connected = false;
        return -1;
    }
    return result;
}

static int32_t recv_bytes(NetworkContext_t *network, void *data, size_t length)
{
    if (!network || !network->connected || (length && !data) || length > 512U)
        return -1;
    if (!length)
        return 0;
    uint32_t budget = remaining(network);
    if (!budget)
        return 0;
#ifdef MP_FINAL_UNIFIED
    if(network->buffered_receive_only)return 0;
#endif
    /* 5ms只是推进切片；platform持有未完成AT事务，不重发或丢掉其回复。 */
    int result = esp_mqtt_recv(data, (int)length, budget > 5U ? 5U : budget);
    if (result < 0 || (size_t)result > length)
    {
        network->connected = false;
        return -1;
    }
    return result;
}

static int32_t send_vectors(NetworkContext_t *network, TransportOutVector_t *vectors, size_t count)
{
    if (!network || !network->connected || !vectors)
        return -1;
    size_t total = 0;
    for (size_t i = 0; i < count; ++i)
    {
        if ((vectors[i].iov_len && !vectors[i].iov_base)
            || vectors[i].iov_len > sizeof(network->tx) - total)
            return -1;
        total += vectors[i].iov_len;
    }
#ifdef MP_FINAL_UNIFIED
    if(network->collect){
        if(!mqtt_adapter_room(network,total))return -1;
        if(!network->queued)network->queued_at=g_uptime_ms;
        for(size_t i=0;i<count;i++){
            if(vectors[i].iov_len)memcpy(network->tx+network->queued,vectors[i].iov_base,vectors[i].iov_len);
            network->queued+=vectors[i].iov_len;
        }
        return (int32_t)total;
    }
#endif
    size_t offset = 0;
    for (size_t i = 0; i < count; ++i)
    {
        if (vectors[i].iov_len)
            memcpy(network->tx + offset, vectors[i].iov_base, vectors[i].iov_len);
        offset += vectors[i].iov_len;
    }
    int32_t result = send_bytes(network, network->tx, total);
    /* CONNECT 含认证字段；同步发送结束即清除副本，禁止输出原始二进制内容。 */
    volatile unsigned char *erase = network->tx;
    for (size_t i = 0; i < total; ++i)
        erase[i] = 0;
    return result;
}

TransportInterface_t mqtt_adapter_interface(NetworkContext_t *network)
{
    TransportInterface_t interface = {recv_bytes, send_bytes, send_vectors, network};
    return interface;
}
