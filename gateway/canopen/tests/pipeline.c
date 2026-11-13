/* 从真实 RPDO OD 到统一模型/路由，验证缓存不是简单重发当前值。 */
#include "mp_adapter.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>
static MpStack s;
static MpAdapter a;
static MpRouter r;

static void run(unsigned n)
{
    while (n--)
    {
        mp_stack_tick(&s);
        mp_adapter_poll(&a, &s, &r);
    }
}

int main(void)
{
    assert(!mp_stack_init(&s, 1790000000));
    mp_adapter_init(&a);
    mp_router_init(&r);
    run(2200);
    assert(r.cn > 5 && !r.online);
    MpFrame oldest = r.cache[r.ch];
    mp_router_online(&r, true);
    MpFrame f;
    assert(!mp_router_take(&r, &f, s.milliseconds));
    run(2000);
    assert(mp_router_take(&r, &f, s.milliseconds));
    assert(!f.replay);
    mp_router_ack(&r, &f, true);
    r.last_replay = s.milliseconds;
    while (r.ln)
    {
        assert(mp_router_take(&r, &f, s.milliseconds));
        assert(!f.replay);
        mp_router_ack(&r, &f, true);
    }
    assert(mp_router_take(&r, &f, s.milliseconds + 500));
    assert(f.replay);
    assert(f.timestamp == oldest.timestamp && f.seq == oldest.seq && f.boot == oldest.boot);
    mp_router_ack(&r, &f, true);
    assert(!mp_router_take(&r, &f, s.milliseconds + 500));
    /* QoS1 失败将已取出的独立副本归入缓存，等待期间新帧不会覆盖它。 */
    MpFrame failed = oldest;
    failed.seq = 123456;
    mp_router_put(&r, &failed);
    assert(mp_router_take(&r, &f, s.milliseconds + 501));
    mp_router_ack(&r, &f, false);
    assert(!r.online);
    bool found = false;
    for (unsigned i = 0; i < r.cn; i++)
        if (r.cache[(r.ch + i) % MP_CACHE_CAPACITY].seq == 123456)
            found = true;
    assert(found);
    run(10000);
    assert(r.cn == MP_CACHE_CAPACITY && r.dropped > 0);
    mp_router_online(&r, true);
    run(2000);
    bool ecg = false, rr = false, spo2 = false;
    while (mp_router_take(&r, &f, s.milliseconds))
    {
        char json[2048], topic[128];
        assert(mp_json(&f, json, sizeof(json)));
        assert(mp_topic(&f, topic, sizeof(topic)));
        assert(!mp_json(&f, json, 10));
        if (f.stream == MP_ECG)
        {
            ecg = true;
            assert(f.count == 250 && f.rate == 250);
            for (unsigned i = 1; i < f.count; i++)
                assert(f.values[i] - f.values[i - 1] == 4 || f.values[i] - f.values[i - 1] == -996);
        }
        if (f.stream == MP_RR)
        {
            rr = true;
            assert(!f.valid);
        }
        if (f.stream == MP_SPO2)
        {
            spo2 = true;
            assert(f.values[0] == 9700);
        }
        assert(f.synthetic);
        mp_router_ack(&r, &f, true);
    }
    assert(ecg && rr && spo2);
    assert(!mp_stack_restart(&s, 3));
    run(1);
    while (mp_router_take(&r, &f, s.milliseconds))
    {
        assert(f.synthetic);
        mp_router_ack(&r, &f, true);
    }
    /* LIVE 仅在质量位明确清除时成立；单元夹具不发布到生产云端。 */
    f = oldest;
    f.synthetic = false;
    f.replay = false;
    char json[2048];
    assert(mp_json(&f, json, sizeof(json)));
    assert(strstr(json, "\"source\":\"LIVE\""));
    f.replay = true;
    assert(mp_json(&f, json, sizeof(json)));
    assert(strstr(json, "\"source\":\"REPLAY\""));
    /* 队列持续有实时流时，仍在8条实时之后得到一次低优先历史机会。 */
    static MpRouter busy;
    mp_router_init(&busy);
    mp_router_put(&busy, &oldest);
    mp_router_online(&busy, true);
    for (unsigned i = 0; i < 8; i++)
    {
        mp_router_put(&busy, &oldest);
        assert(mp_router_take(&busy, &f, 1000 + i * 250));
        assert(!f.replay);
        mp_router_ack(&busy, &f, true);
    }
    mp_router_put(&busy, &oldest);
    assert(mp_router_take(&busy, &f, 3000) && f.replay && busy.ln == 1);
    mp_router_ack(&busy, &f, true);
    assert(mp_router_take(&busy, &f, 3000) && !f.replay);
    printf(
        "{\"pipeline_checks\":11,\"cache_capacity\":%u,\"overflow_dropped\":%u,\"frame_bytes\":%u,\"router_bytes\":%u}\n",
        MP_CACHE_CAPACITY, r.dropped, (unsigned)sizeof(MpFrame), (unsigned)sizeof(MpRouter));
    mp_stack_close(&s);
    return 0;
}
