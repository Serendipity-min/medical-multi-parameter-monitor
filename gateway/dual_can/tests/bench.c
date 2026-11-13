/* 全部输入为离线合成；测试本地TIME、隔离总线、失效与有界RAM行为，不冒充实板。 */
#include "b4_bench.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>

static B4Bench bench;
static unsigned tx[2], times, nmts;
static uint32_t time_ms;
int b4_bus_transmit(unsigned bus, const MpCanFrame *f) {
    assert(bus == 1); tx[bus]++;
    if (f->ident == 0) { assert(f->dlc == 2 && f->data[1] == 2); nmts++; }
    if (f->ident == 0x100) {
        uint16_t days; memcpy(&time_ms, f->data, 4); memcpy(&days, f->data + 4, 2);
        assert(f->dlc == 6 && days == (B4_BENCH_EPOCH - 441763200u) / 86400u);
        times++;
    }
    return 1;
}
static void inject(unsigned id, const void *data, unsigned n, uint32_t tick) {
    MpCanFrame f = {0}; f.ident = id; f.dlc = n; memcpy(f.data, data, n);
    b4_gateway_receive(&bench.gateway, 1, &f, tick);
}
int main(void) {
    assert(b4_bench_init(&bench, 0) == 0);
    for (uint32_t now = 0; now < 40000; now++) {
        b4_bench_step(&bench, now);
        if (now % 1000 == 0) {
            uint8_t hb = 5; inject(0x702, &hb, 1, now);
            uint32_t quality[2] = {0x8000000fu, 1}; inject(0x682, quality, 8, now);
            uint32_t anchor[2] = {B4_BENCH_EPOCH + now / 1000u, now}; inject(0x482, anchor, 8, now);
            uint16_t vitals[4] = {6000, 2000, 0, 0}; inject(0x382, vitals, 8, now);
        }
        if (now % 4 == 0) { uint32_t sample[2] = {now, now}; inject(0x182, sample, 8, now); }
        if (now % 20 == 0) { uint32_t sample[2] = {now, now}; inject(0x282, sample, 8, now); }
    }
    assert(!tx[0] && times == 4 && nmts == 1);
    assert(bench.diag.test_time_only && bench.diag.records > B4_BENCH_RING);
    assert(bench.diag.overwritten == bench.diag.records - B4_BENCH_RING);
    unsigned valid = 0;
    for (unsigned i = 0; i < B4_BENCH_RING; i++) {
        MpFrame *f = &bench.records[i];
        assert(f->timestamp >= (uint64_t)B4_BENCH_EPOCH * 1000);
        if (f->valid) { assert(f->node == 2 && f->synthetic); valid++; }
        if (f->stream == MP_TEMP) assert(!f->valid);
    }
    assert(valid > 0 && bench.gateway.wave_gaps == 0);
    b4_bench_step(&bench, B4_BENCH_LIMIT_MS);
    unsigned sent = tx[1]; assert(bench.diag.stopped && !bench.gateway.utc_valid);
    b4_bench_step(&bench, B4_BENCH_LIMIT_MS + 1); assert(tx[1] == sent);
    b4_gateway_close(&bench.gateway);

    /* 非零起点及tick回绕不能破坏TIME毫秒或提前结束窗口。 */
    memset(tx, 0, sizeof(tx)); times = nmts = 0;
    uint32_t start = UINT32_MAX - 5000u;
    assert(b4_bench_init(&bench, start) == 0);
    b4_bench_step(&bench, start);
    for (uint32_t delta = 1; delta <= 10001; delta++) b4_bench_step(&bench, start + delta);
    assert(bench.diag.elapsed_ms == 10001 && !bench.diag.stopped && times == 2);
    assert(time_ms == 10000 && !tx[0]);
    b4_gateway_close(&bench.gateway);
    printf("BENCH PASS: local TIME, B-only NMT/TIME, tick wrap, bounded RAM, %us stop; synthetic only\n",B4_BENCH_LIMIT_MS/1000u);
    return 0;
}
