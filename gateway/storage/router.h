#ifndef MP_ROUTER_H
#define MP_ROUTER_H
#include "../data_model/model.h"
#ifdef MP_B5_EGRESS_FINAL
#include "../b5/egress_metrics.h"
typedef struct { uint64_t report_utc,arrival_utc;uint32_t seq,epoch,boot;int32_t centi;uint32_t valid; } B5TempEntry;
#endif
/* 旧目标容量不变；B4以100点帧节省RAM后可独立扩大历史队列。 */
#ifndef MP_LIVE_CAPACITY
#define MP_LIVE_CAPACITY 16
#endif
#ifndef MP_CACHE_CAPACITY
#define MP_CACHE_CAPACITY 32
#endif

typedef struct
{
    /* 两个环形队列均按帧计容量，不能直接等同于可缓存的秒数。 */
    MpFrame live[MP_LIVE_CAPACITY], cache[MP_CACHE_CAPACITY];
    /* lh/ch 为队首下标，ln/cn 为当前项数；出队后发送者持有自己的副本。 */
    unsigned lh, ln, ch, cn;
    /* 累计丢弃/入历史/补传成功计数，以及最近补传的毫秒调度时间。 */
    uint32_t dropped, stored, replayed, last_replay;
    bool online, ready_for_replay;
    /* 饱和至 8 的实时成功配额，给持续负载下的历史帧保留发送机会。 */
    uint8_t live_credit;
#ifdef MP_B5_EGRESS_FINAL
    uint32_t enqueued[MP_STREAMS], taken[MP_STREAMS], historized[MP_STREAMS];
    uint32_t live_replaced, live_overflow, expired, high_water;
    uint32_t status_coalesced,put_tick[MP_LIVE_CAPACITY];
    uint8_t fair_wave;
    B5Latency residence,source_age;
    B5TempEntry temp_entry[8];uint32_t temp_written,temp_reported,temp_trace_lost;
#endif
} MpRouter;

void mp_router_init(MpRouter *r);
void mp_router_online(MpRouter *r, bool online);
void mp_router_put(MpRouter *r, const MpFrame *f);
bool mp_router_take(MpRouter *r, MpFrame *out, uint32_t now);
#ifdef MP_B5_EGRESS_FINAL
/* QoS1在途时只取实时QoS0；队列内其余帧及原始身份不动。 */
bool mp_router_take_egress(MpRouter *r,MpFrame *out,uint32_t now,uint64_t utc,bool qos1_pending);
#endif
/* success 是 MQTT 传输层结果，QoS0 成功不等同于 Broker 或 Backend 已处理。 */
void mp_router_ack(MpRouter *r, const MpFrame *f, bool success);
#endif
