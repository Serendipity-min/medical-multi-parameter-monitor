#ifndef H16_PROBE_CONFIG_H
#define H16_PROBE_CONFIG_H

/* 单一诊断profile；窗口开始后不扩容、不分配堆，满记录只能降低观察完整性。 */
#define PROBE_PROFILE_ID 0xC2500001U
/* 固定选择口径：每个scope/结果只保留实际最大样本；不冒充全量分布或p95。 */
#define PROBE_RECORD_POLICY_MAX_PER_OUTCOME 1U
#define PROBE_RAM_LIMIT 1536U
#define PROBE_TICK_CAPACITY 16U
#define PROBE_EVENT_CAPACITY 16U
#define PROBE_SPAN_DEPTH 6U
#define PROBE_SNAPSHOT_ATTEMPTS 8U
#define PROBE_INVALID_TOKEN 0xffffffffU
#ifndef PROBE_HOST_TEST
#include "probe_variant.h"
#endif
#ifndef PROBE_VARIANT_ID
#define PROBE_VARIANT_ID 5U
#endif

#endif
