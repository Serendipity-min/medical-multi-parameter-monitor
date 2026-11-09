/* 单线程队列：网络等待期间只允许生产，取出帧复制给发布者直到传输结果返回。 */
#include "router.h"
#include "../data_model/roles.h"
#include <string.h>
#ifdef MP_B5_EGRESS_FINAL
extern volatile uint32_t g_uptime_ms;
extern uint64_t gateway_epoch_milliseconds(void);
#endif

void mp_router_init(MpRouter *r)
{
    memset(r, 0, sizeof(*r));
}

static void cache(MpRouter *r, const MpFrame *f)
{
    /* 状态只保留当下语义，不能补传旧 ONLINE/OFFLINE 覆盖当前状态。 */
    if (f->stream == MP_NODE_STATUS || f->stream == MP_GATEWAY_STATUS)
        return;
#ifdef MP_B5_EGRESS_FINAL
    r->historized[f->stream]++;
#endif
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

/* 波形按次FIFO；允许合并的状态/标量保留队位，避免慢流长期饥饿。 */
void mp_router_put(MpRouter *r, const MpFrame *f)
{
#ifdef MP_B5_EGRESS_FINAL
    r->enqueued[f->stream]++;
    if(f->node==mp_role_node(MP_TEMP) && f->stream==MP_TEMP) {
        if(r->temp_written-r->temp_reported>=8){r->temp_reported++;r->temp_trace_lost++;}
        r->temp_entry[r->temp_written++%8]=(B5TempEntry){f->timestamp,gateway_epoch_milliseconds(),f->seq,f->epoch,f->boot,f->values[0],f->valid};
    }
#endif
    if (!r->online)
    {
        cache(r, f);
        return;
    }
    /* 每流保留最新待发帧并保持排队位置，防止高频波形反复挤走标量/状态。 */
    for (unsigned i = 0; i < r->ln; i++)
    {
        MpFrame *pending = &r->live[(r->lh + i) % MP_LIVE_CAPACITY];
        if (pending->node == f->node && pending->stream == f->stream
#ifdef MP_B5_CLOUD_CANDIDATE
            /* B5遥测按次FIFO；短突发不能把仍有实时队列空间的前项变成历史。 */
            && !(!f->replay &&
                 (f->stream == MP_ECG || f->stream == MP_RESP || f->stream == MP_PPG ||
                  f->stream == MP_HR || f->stream == MP_RR || f->stream == MP_TEMP) &&
                  f->node == mp_role_node((MpStream)f->stream))
#endif
           )
        {
#ifdef MP_B5_EGRESS_FINAL
            if(f->stream==MP_NODE_STATUS || f->stream==MP_GATEWAY_STATUS)r->status_coalesced++;
            else r->live_replaced++;
            r->put_tick[(r->lh+i)%MP_LIVE_CAPACITY]=g_uptime_ms;
#endif
            cache(r, pending);
            *pending = *f;
            return;
        }
    }
    if (r->ln == MP_LIVE_CAPACITY)
    {
#ifdef MP_B5_EGRESS_FINAL
        r->live_overflow++;
#endif
        cache(r, &r->live[r->lh]);
        r->lh = (r->lh + 1) % MP_LIVE_CAPACITY;
        r->ln--;
    }
    r->live[(r->lh + r->ln) % MP_LIVE_CAPACITY] = *f;
#ifdef MP_B5_EGRESS_FINAL
    r->put_tick[(r->lh+r->ln)%MP_LIVE_CAPACITY]=g_uptime_ms;
#endif
    r->ln++;
#ifdef MP_B5_EGRESS_FINAL
    if(r->ln>r->high_water)r->high_water=r->ln;
#endif
}

static bool take_history(MpRouter *r,MpFrame *out,uint32_t now) {
    bool turn=!r->ln || r->live_credit>=8;
    uint32_t interval=r->ln?2000u:500u;
    if(!turn || !r->ready_for_replay || !r->cn || (uint32_t)(now-r->last_replay)<interval)return false;
    *out=r->cache[r->ch];out->replay=true;
    r->ch=(r->ch+1)%MP_CACHE_CAPACITY;r->cn--;
    r->last_replay=now;r->live_credit=0;
    return true;
}

#ifdef MP_B5_EGRESS_FINAL
bool mp_router_take_egress(MpRouter *r,MpFrame *out,uint32_t now,uint64_t utc,bool pending) {
    if(!r->online)return false;
    /* 补传用原配额；给实时5秒期限留半窗余量，并保留两个突发槽。 */
    bool replay_safe=!pending && r->ln<MP_LIVE_CAPACITY-2;
    for(unsigned i=0;replay_safe && i<r->ln;i++) {
        const MpFrame *f=&r->live[(r->lh+i)%MP_LIVE_CAPACITY];
        if(mp_realtime_yield_due(utc,f->timestamp,true))replay_safe=false;
    }
    if(replay_safe && take_history(r,out,now)){r->taken[out->stream]++;return true;}
    unsigned chosen=MP_LIVE_CAPACITY;int best=100;
#ifdef MP_ABC_TRI_CANDIDATE
    uint64_t oldest=UINT64_MAX;
#endif
    for(unsigned i=0;i<r->ln;i++) {
        MpFrame *f=&r->live[(r->lh+i)%MP_LIVE_CAPACITY];
        bool wave=f->rate && !f->replay;
        if(pending && !wave)continue;
        /* 状态先行；标量/波形交替，组内FIFO，不能让快流或心跳饿死另一组。 */
        bool status=f->stream==MP_NODE_STATUS || f->stream==MP_GATEWAY_STATUS;
        int rank=status?0:wave==(r->fair_wave!=0)?1:2;
        if(rank<best
#ifdef MP_ABC_TRI_CANDIDATE
           /* A最新值替换会保留队位；同级标量按原时间先后，避免新值越过老的B温度。 */
           || (rank==best && !wave && f->timestamp<oldest)
#endif
          ){
            best=rank;chosen=i;
#ifdef MP_ABC_TRI_CANDIDATE
            oldest=f->timestamp;
#endif
        }
    }
    if(chosen!=MP_LIVE_CAPACITY) {
        *out=r->live[(r->lh+chosen)%MP_LIVE_CAPACITY];
        b5_latency_add(&r->residence,(uint32_t)(now-r->put_tick[(r->lh+chosen)%MP_LIVE_CAPACITY]));
        for(unsigned i=chosen;i+1<r->ln;i++) {
            r->live[(r->lh+i)%MP_LIVE_CAPACITY]=r->live[(r->lh+i+1)%MP_LIVE_CAPACITY];
            r->put_tick[(r->lh+i)%MP_LIVE_CAPACITY]=r->put_tick[(r->lh+i+1)%MP_LIVE_CAPACITY];
        }
        r->ln--;r->taken[out->stream]++;
        if(out->stream!=MP_NODE_STATUS && out->stream!=MP_GATEWAY_STATUS)r->fair_wave=!r->fair_wave;
        if(utc>=out->timestamp)b5_latency_add(&r->source_age,(uint32_t)(utc-out->timestamp));
        if(utc>out->timestamp && utc-out->timestamp>MP_REALTIME_DEADLINE_MS)r->expired++;
        return true;
    }
    return false;
}
#endif

/* now 使用单调毫秒计数，与帧的采集时间独立；历史出队只改变副本的 replay 标记。 */
bool mp_router_take(MpRouter *r, MpFrame *out, uint32_t now)
{
    if (!r->online)
        return false;
    /* 实时优先采用有界配额，避免持续满载让历史永久饿死：忙时至少8条实时后补1条，且间隔>=2s。 */
    if (take_history(r,out,now))
        return true;
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
