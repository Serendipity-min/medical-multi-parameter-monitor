#ifndef GATEWAY_ESP_IO_METRICS_H
#define GATEWAY_ESP_IO_METRICS_H
#include <stdint.h>

/* 仅IRQ候选收集AT边界数字；不保存命令、MQTT载荷或外部连接配置。累计不随重连清零。 */
typedef struct {
    uint32_t tx_calls,tx_confirmed,tx_length,tx_ms,tx_phase;
    uint32_t rx_queries,rx_empty,rx_hint,rx_bytes,rx_reads;
} EspIoMetrics;
void platform_io_snapshot(EspIoMetrics *out);
#endif
