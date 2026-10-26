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
#endif
