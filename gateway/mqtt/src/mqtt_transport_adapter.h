#ifndef MQTT_TRANSPORT_ADAPTER_H
#define MQTT_TRANSPORT_ADAPTER_H
#include "transport_interface.h"
#include <stdbool.h>
#include <stdint.h>

/* 单一主线程独占；TX 容量沿用 P4 的 2048 字节，不新增堆分配。 */
struct NetworkContext
{
    unsigned char tx[2048];
    uint32_t deadline;
    bool connected;
#ifdef MP_FINAL_UNIFIED
    size_t queued;
    uint32_t queued_at;
    bool collect, flush_requested, buffered_receive_only;
#endif
};

void mqtt_adapter_reset(NetworkContext_t *network);
void mqtt_adapter_begin(NetworkContext_t *network, uint32_t timeout_ms);
void mqtt_adapter_close(NetworkContext_t *network);
TransportInterface_t mqtt_adapter_interface(NetworkContext_t *network);
uint32_t mqtt_adapter_time(void);
#ifdef MP_FINAL_UNIFIED
bool mqtt_adapter_room(NetworkContext_t *network, size_t length);
int mqtt_adapter_flush(NetworkContext_t *network);
#endif
#endif
