#ifndef GATEWAY_ESP_IO_METRICS_H
#define GATEWAY_ESP_IO_METRICS_H
#include <stdint.h>
#ifdef MP_B5_EGRESS_FINAL
#include "../../b5/egress_metrics.h"
enum { ESP_AT_IDLE,ESP_AT_COMMAND,ESP_AT_WAIT_PROMPT,ESP_AT_DATA,
       ESP_AT_WAIT_SEND_OK,ESP_AT_WAIT_PUBACK,ESP_AT_UNSYNCED,ESP_AT_CLOSED };
#endif

/* 仅IRQ候选收集AT边界数字；不保存命令、MQTT载荷或外部连接配置。累计不随重连清零。 */
typedef struct {
    uint32_t tx_calls,tx_confirmed,tx_length,tx_ms,tx_phase;
    uint32_t rx_queries,rx_empty,rx_hint,rx_bytes,rx_reads;
#ifdef MP_B5_EGRESS_FINAL
    volatile uint32_t at_phase,phase_at,required,written,unsynced,budget_refused;
    uint32_t wait_reason,reply_bytes,reply_flags;
    B5Latency command,prompt,data,send_ok;
#endif
} EspIoMetrics;
void platform_io_snapshot(EspIoMetrics *out);
#ifdef MP_B5_EGRESS_FINAL
int platform_at_synchronized(void);
int platform_at_unsynced(void);
#endif
#endif
