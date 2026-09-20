#ifndef MP_ROUTER_H
#define MP_ROUTER_H
#include "../data_model/model.h"
#define MP_LIVE_CAPACITY 16
#define MP_CACHE_CAPACITY 32

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
} MpRouter;

void mp_router_init(MpRouter *r);
void mp_router_online(MpRouter *r, bool online);
void mp_router_put(MpRouter *r, const MpFrame *f);
bool mp_router_take(MpRouter *r, MpFrame *out, uint32_t now);
/* success 是 MQTT 传输层结果，QoS0 成功不等同于 Broker 或 Backend 已处理。 */
void mp_router_ack(MpRouter *r, const MpFrame *f, bool success);
#endif
