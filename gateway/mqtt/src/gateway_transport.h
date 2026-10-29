#ifndef GATEWAY_TRANSPORT_H
#define GATEWAY_TRANSPORT_H
#include "gateway_platform.h"
#include "../../data_model/model.h"
int gateway_config_valid(void);
uint32_t gateway_epoch(void);
/* 同一SNTP锚点的毫秒UTC，避免把uptime小数拼到秒级结果上造成未来时间。 */
uint64_t gateway_epoch_milliseconds(void);
int gateway_network_open(void);
int gateway_mqtt_open(const MpFrame *will);
int gateway_mqtt_publish(const MpFrame *frame);
int gateway_mqtt_yield(void);
void gateway_network_close(void);
#ifdef MP_B5_EGRESS_FINAL
#include "../../b5/egress_metrics.h"
enum { GW_FAILED=-1,GW_PENDING=0,GW_COMPLETE=1,GW_DEFERRED=2 };
int gateway_mqtt_admit(void);
int gateway_mqtt_begin(const MpFrame *frame);
int gateway_mqtt_progress(void);
int gateway_mqtt_pending(void);
int gateway_network_retryable(void);
typedef struct { uint32_t q0_sent,q1_sent,q1_acked,failed; B5Latency json,send,ack; } GatewayMqttMetrics;
void gateway_mqtt_metrics(GatewayMqttMetrics *out);
#endif
#endif
