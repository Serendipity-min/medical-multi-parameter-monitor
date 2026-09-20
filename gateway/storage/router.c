/* 单线程队列：网络等待期间只允许生产，取出帧复制给发布者直到传输结果返回。 */
#include "router.h"
#include <string.h>

void mp_router_init(MpRouter *r)
{
    memset(r, 0, sizeof(*r));
}

static void cache(MpRouter *r, const MpFrame *f)
{
    /* 状态只保留当下语义，不能补传旧 ONLINE/OFFLINE 覆盖当前状态。 */
    if (f->stream == MP_NODE_STATUS || f->stream == MP_GATEWAY_STATUS)
        return;
    if (r->cn == MP_CACHE_CAPACITY)
    {
        r->ch = (r->ch + 1) % MP_CACHE_CAPACITY;
        r->cn--;
        r->dropped++;
    }
    r->cache[(r->ch + r->cn) % MP_CACHE_CAPACITY] = *f;
    r->cn++;
    r->stored++;
}

/* 断连时把待发遥测迁入历史；每次新连接都需先成功发送实时帧再开放补传。 */
void mp_router_online(MpRouter *r, bool online)
{
    if (!online || !r->online)
    {
        r->ready_for_replay = false;
        r->live_credit = 0;
    }
    r->online = online;
    if (!online)
        while (r->ln)
        {
            cache(r, &r->live[r->lh]);
            r->lh = (r->lh + 1) % MP_LIVE_CAPACITY;
            r->ln--;
        }
}

/* 同一节点/流仅保留最新待发项；替换内容时保留队列位置，避免慢流长期饥饿。 */
void mp_router_put(MpRouter *r, const MpFrame *f)
{
    if (!r->online)
    {
        cache(r, f);
        return;
    }
    /* 每流保留最新待发帧并保持排队位置，防止高频波形反复挤走标量/状态。 */
    for (unsigned i = 0; i < r->ln; i++)
    {
        MpFrame *pending = &r->live[(r->lh + i) % MP_LIVE_CAPACITY];
        if (pending->node == f->node && pending->stream == f->stream)
        {
            cache(r, pending);
            *pending = *f;
            return;
        }
    }
    if (r->ln == MP_LIVE_CAPACITY)
    {
        cache(r, &r->live[r->lh]);
        r->lh = (r->lh + 1) % MP_LIVE_CAPACITY;
        r->ln--;
    }
    r->live[(r->lh + r->ln) % MP_LIVE_CAPACITY] = *f;
    r->ln++;
}

/* now 使用单调毫秒计数，与帧的采集时间独立；历史出队只改变副本的 replay 标记。 */
bool mp_router_take(MpRouter *r, MpFrame *out, uint32_t now)
{
    if (!r->online)
        return false;
    /* 实时优先采用有界配额，避免持续满载让历史永久饿死：忙时至少8条实时后补1条，且间隔>=2s。 */
    bool history_turn = !r->ln || r->live_credit >= 8;
    uint32_t interval = r->ln ? 2000U : 500U;
    if (history_turn && r->ready_for_replay && r->cn &&
        (uint32_t)(now - r->last_replay) >= interval)
    {
        *out = r->cache[r->ch];
        out->replay = true;
        r->ch = (r->ch + 1) % MP_CACHE_CAPACITY;
        r->cn--;
        r->last_replay = now;
        r->live_credit = 0;
        return true;
    }
    if (r->ln)
    {
        *out = r->live[r->lh];
        r->lh = (r->lh + 1) % MP_LIVE_CAPACITY;
        r->ln--;
        return true;
    }
    return false;
}

void mp_router_ack(MpRouter *r, const MpFrame *f, bool success)
{
    /* 刚重连且实时队列暂时为空，也必须先成功发出新实时帧，才能开始历史补传。 */
    if (success)
    {
        if (f->replay)
            r->replayed++;
        else
        {
            r->ready_for_replay = true;
            if (r->live_credit < 8)
                r->live_credit++;
        }
        return;
    }
    /* 失败可能已到 Broker，重试保留同一序号/时间，由 Backend 去重。 */
    cache(r, f);
    mp_router_online(r, false);
}
