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
#ifndef GATEWAY_AUDIO_SLOTS
#define GATEWAY_AUDIO_SLOTS 3u
#endif
int gateway_mqtt_admit(void);
int gateway_mqtt_begin(const MpFrame *frame);
int gateway_mqtt_progress(void);
int gateway_mqtt_pending(void);
int gateway_network_retryable(void);
#ifdef MP_FINAL_UNIFIED
#ifndef GATEWAY_TELEMETRY_SLOTS
#define GATEWAY_TELEMETRY_SLOTS 5u
#endif
#define GATEWAY_PUBLISH_SLOTS (GATEWAY_TELEMETRY_SLOTS+2u)
/* QoS0票据等整批SEND成功，QoS1票据继续等自身PUBACK；入队不等于传输成功。 */
uint16_t gateway_mqtt_ticket(void);
int gateway_mqtt_slots_full(void);
int gateway_mqtt_ticket_result(uint16_t id);
#endif
typedef struct { uint32_t q0_sent,q1_sent,q1_acked,failed; B5Latency json,send,ack; } GatewayMqttMetrics;
void gateway_mqtt_metrics(GatewayMqttMetrics *out);
#endif
#endif
