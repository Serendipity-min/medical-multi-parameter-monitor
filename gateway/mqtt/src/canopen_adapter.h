#ifndef CANOPEN_ADAPTER_H
#define CANOPEN_ADAPTER_H
#include <stdint.h>
/* 预留 CANopen 数据入口；本阶段不冻结 OD/PDO，也不声称已有真实采集。 */
typedef struct {
  const char *node_id;
  const char *stream;
  uint64_t timestamp_ms;
  uint32_t sequence;
  const char *validity;
  const char *unit;
  const float *samples;
  unsigned int sample_count;
  float scalar;
} GatewayInput;
#endif
