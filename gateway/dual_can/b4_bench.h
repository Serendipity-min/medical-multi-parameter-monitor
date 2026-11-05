#ifndef B4_BENCH_H
#define B4_BENCH_H
#include "b4_gateway.h"

/* 固定测试纪元仅服务隔离台架；不得标成真实UTC，也不进入MQTT/正式数据目录。 */
#define B4_BENCH_EPOCH 1577836800u
#ifndef B4_BENCH_LIMIT_MS
#define B4_BENCH_LIMIT_MS 180000u
#endif
#define B4_BENCH_RING 16u
typedef struct {
    uint32_t magic, test_time_only, elapsed_ms, stopped, records, overwritten;
    uint32_t last_node, last_stream, last_valid, last_count;
    uint64_t last_test_timestamp;
} B4BenchDiag;
typedef struct {
    B4Gateway gateway;
    B4BenchDiag diag;
    MpFrame records[B4_BENCH_RING];
    uint32_t last_tick, sync_at;
} B4Bench;
int b4_bench_init(B4Bench *b, uint32_t tick);
void b4_bench_step(B4Bench *b, uint32_t tick);
#endif
