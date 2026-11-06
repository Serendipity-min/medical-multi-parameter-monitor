/* 台架服务只依赖CAN/数据模型；取证旁路可选，不包含网络、持久配置或Flash驱动。 */
#include "b4_bench.h"
#include <string.h>
#if defined(B4_CAPTURE_SERIAL)
#include "b4_capture.h"
static void record_model(const MpFrame *f,uint32_t tick) {
    uint32_t hash=2166136261u;
    for (unsigned i=0;i<f->count;i++) {
        uint32_t v=(uint32_t)f->values[i];
        for (unsigned j=0;j<4;j++) { hash^=(v>>(8*j))&255u; hash*=16777619u; }
    }
    uint32_t last=f->count?(uint32_t)f->values[f->count-1]:0;
    uint8_t data[8];
    for (unsigned i=0;i<4;i++) { data[i]=(uint8_t)(last>>(8*i)); data[i+4]=(uint8_t)(hash>>(8*i)); }
    uint32_t flags=f->node | ((uint32_t)f->valid<<8) | ((uint32_t)f->synthetic<<9)
                   | ((uint32_t)f->replay<<10) | ((uint32_t)f->count<<16);
    unsigned bus=1;
#ifdef B4_FIVE_CAPTURE
    bus=(f->node==1 || f->node==5)?0:1;
#endif
    b4_capture_emit(B4_CAP_MODEL,bus,f->stream,8,data,tick,flags);
    for (unsigned i=0;i<8;i++) data[i]=(uint8_t)(f->timestamp>>(8*i));
    b4_capture_emit(B4_CAP_MODEL_TIME,bus,f->stream,8,data,tick,f->seq);
}
#endif

int b4_bench_init(B4Bench *b, uint32_t tick) {
    memset(b, 0, sizeof(*b));
    if (b4_gateway_init(&b->gateway)) return -1;
    b->last_tick = tick; b->gateway.now = tick;
    b->diag.magic = 0x42344231u; b->diag.test_time_only = 1;
#ifndef B4_FIVE_CAPTURE
    /* 首次联动仅B段。共享CAN1时钟仍保留，但A段协议发送被关闭，不广播NMT。 */
    b4_gateway_link(&b->gateway, 0, false);
#else
    const unsigned nodes[4]={1,2,4,5};
    for(unsigned i=0;i<4;i++) if(b4_gateway_nmt(&b->gateway,nodes[i],CO_NMT_ENTER_OPERATIONAL)) {
        b4_gateway_close(&b->gateway); return -1;
    }
#endif
    mp_router_online(&b->gateway.router, true); /* 此online仅启用本地消费者，不表示网络在线。 */
#if defined(B4_PHY_SMALL_FRAMES)
    /* 先抑制B的PDO，再发送TIME；短观察仅心跳和D的低频温度报文。 */
    if (b4_gateway_nmt(&b->gateway, 2, CO_NMT_ENTER_PRE_OPERATIONAL) ||
        b4_gateway_nmt(&b->gateway, 4, CO_NMT_ENTER_OPERATIONAL)) {
        b4_gateway_close(&b->gateway); return -1;
    }
#endif
    b4_gateway_sync(&b->gateway, B4_BENCH_EPOCH, tick);
#if !defined(B4_PHY_SMALL_FRAMES) && !defined(B4_FIVE_CAPTURE)
    if (b4_gateway_nmt(&b->gateway, 2, CO_NMT_ENTER_OPERATIONAL)) {
        b4_gateway_close(&b->gateway); return -1;
    }
#endif
    return 0;
}
void b4_bench_step(B4Bench *b, uint32_t tick) {
    if (b->diag.stopped) return;
    /* 无符号差值跨过一次32位tick回绕；超过窗口上限不续期，也不自动复位设备。 */
    uint32_t delta = tick - b->last_tick; b->last_tick = tick;
    if (delta >= B4_BENCH_LIMIT_MS - b->diag.elapsed_ms) {
        b->diag.elapsed_ms = B4_BENCH_LIMIT_MS; b->diag.stopped = 1;
        b->gateway.utc_valid = false;
        b4_gateway_link(&b->gateway, 0, false); b4_gateway_link(&b->gateway, 1, false);
        return;
    }
    b->diag.elapsed_ms += delta;
    if (b->diag.elapsed_ms - b->sync_at >= 10000u) {
        /* 周期刷新的是本地测试时基，非SNTP/屏幕RTC；不向固件注入真实凭据。 */
        b4_gateway_sync_ms(&b->gateway, (uint64_t)B4_BENCH_EPOCH * 1000 + b->diag.elapsed_ms,
                           tick);
        b->sync_at = b->diag.elapsed_ms;
    }
    b4_gateway_tick(&b->gateway, tick);
    /* 每步最多取8条，环满保留新记录并显式累计覆盖；不是完整原始帧采集器。 */
    for (unsigned budget = 0; budget < 8; budget++) {
        MpFrame f;
        if (!mp_router_take(&b->gateway.router, &f, b->diag.elapsed_ms)) break;
        unsigned slot = b->diag.records % B4_BENCH_RING;
        b->records[slot] = f;
        if (b->diag.records >= B4_BENCH_RING) b->diag.overwritten++;
        b->diag.records++;
        b->diag.last_node = f.node; b->diag.last_stream = f.stream;
        b->diag.last_valid = f.valid; b->diag.last_count = f.count;
        b->diag.last_test_timestamp = f.timestamp;
#if defined(B4_CAPTURE_SERIAL)
        record_model(&f,tick);
#endif
        mp_router_ack(&b->gateway.router, &f, true); /* 已收至本地RAM，绝不代表MQTT ACK。 */
    }
}
