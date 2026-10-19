/* 独立实板候选：复用 P4 Router/格式化，增加外部 PDO 新鲜度和时间门控。 */
/* Adapter 不拼 MQTT JSON：只从 Gateway RPDO 映射区读取并产出统一帧。 */
#include "mp_adapter.h"
#include "physical.h"
#include <string.h>

void mp_adapter_init(MpAdapter *a)
{
    memset(a, 0, sizeof(*a));
    a->status_tick = 0u - 5000u; /* 缺席 B 从首次有可信时间即报告 OFFLINE。 */
}

/* 统一建立帧身份；node=3 专用于网关状态，物理网关状态不标记为合成采样。 */
static MpFrame frame(MpAdapter *a, MpStack *s, unsigned node, MpStream stream, uint64_t timestamp)
{
    MpFrame f = {0};
    f.node = node;
    f.stream = stream;
    f.timestamp = timestamp;
    f.epoch = s->epoch;
    f.boot = (s->nodes[2].boot << 16) | (node <= 2 ? (a->boot[node - 1] & 65535U) : 0);
    f.seq = ++a->seq[node - 1][stream];
    f.synthetic = node == 3 ? false : (a->quality[node - 1] & 0x80000000U) != 0;
    return f;
}

/* PDO 同时携带秒级时间和采样时钟锚点；用同一节点的 tick 差还原采集毫秒。 */
/* 跨秒的负 tick 差必须按有符号解释；不把前一秒末采样推到 49 天之后。 */
static uint64_t capture(MpOD *od,unsigned base,uint32_t tick,uint64_t now)
{
    uint32_t epoch=mp_od_read(od,base,1),anchor=mp_od_read(od,base,2);
    int32_t delta=(int32_t)(tick-anchor);
    int64_t stamp=(int64_t)epoch*1000+delta;
    if(!epoch || delta < -2000 || delta > 2000 || stamp < 0 || stamp > (int64_t)now+1000 || stamp < (int64_t)now-5000) return 0;
    return (uint64_t)stamp;
}

/* 只读取 Gateway 已收到的 RPDO 镜像，按采样率积累完整一秒批次后交给 Router。 */
static void wave(MpAdapter *a, MpStack *s, MpRouter *r, unsigned node, unsigned channel)
{
    MpOD *od = &s->nodes[2].od;
    unsigned base = 0x3000 + node * 0x100, index = base + 0x10 + channel;
    uint32_t tick = mp_od_read(od, index, 2);
    unsigned pdo=channel;
    if (!physical_fresh(node,pdo,s->milliseconds) || !tick || tick == a->tick[node - 1][channel])
        return;
    MpFrame *f = &a->waves[node == 1 ? 0 : channel + 1];
    unsigned rate = node == 2 && channel == 0 ? 250 : 50;
    MpStream stream = node == 1 ? MP_PPG : channel == 0 ? MP_ECG : MP_RESP;
    bool valid = (a->quality[node - 1] & (1U << channel)) != 0;
    /* 采样时钟不连续、有效性变化或节点重启时丢弃未完成的小批次，不能拼接伪连续波形。 */
    if ((uint32_t)(tick - a->tick[node - 1][channel]) != 1000 / rate || f->valid != valid
        || f->synthetic != ((a->quality[node-1]&0x80000000u)!=0))
        f->count = 0;
    a->tick[node - 1][channel] = tick;
    uint64_t stamp=capture(od,base,tick,physical_now(s));
    if(!stamp) { f->count=0;return; }
    if (!f->count)
    {
        *f = frame(a, s, node, stream, stamp);
        f->rate = rate;
        f->valid = valid;
    }
    f->values[f->count++] = (int32_t)mp_od_read(od, index, 1);
    if (f->count == rate)
    {
        /* 云端既有波形轴以批次末样本为 timestamp，按采样率向前还原每一点。 */
        f->timestamp = stamp;
        mp_router_put(r, f);
        f->count = 0;
    }
}

/* 一次轮询分别推进 A/B 状态、EMCY、波形和标量；缺少时间或质量基准时不伪造有效采样。 */
void mp_adapter_poll(MpAdapter *a, MpStack *s, MpRouter *r)
{
    if (!s->epoch)
        return; /* 未获得可信时间前不向云端伪造时间戳。 */
    uint64_t now = physical_now(s);
    MpOD *od = &s->nodes[2].od;
    for (unsigned node = 1; node <= 2; node++)
    {
        unsigned base = 0x3000 + node * 0x100;
        /* 外部 boot-up 也更新观察代次，不能只依赖对端掉电会清零的 RAM generation。 */
        uint32_t boot = physical_nodes[node-1].session_generation;
        bool online = mp_stack_online(s, node);
        /* Gateway 通信复位会清空镜像；未重新收到质量PDO时保留已知来源，不能把零值误报为LIVE。 */
        if (boot && physical_fresh(node,4,s->milliseconds))
            a->quality[node - 1] = mp_od_read(od, base + 0x30, 1);
        else
            a->quality[node - 1] = 0;
        if (boot != a->boot[node - 1])
        {
            a->boot[node - 1] = boot;
            memset(a->seq[node - 1], 0, sizeof(a->seq[0]));
            a->anchor[node - 1] = 0;
            a->tick[node - 1][0] = a->tick[node - 1][1] = 0;
            a->waves[node == 1 ? 0 : 1].count = 0;
            if (node == 2)
                a->waves[2].count = 0;
        }
        if (online != a->online[node - 1] || s->milliseconds - a->status_tick >= 5000)
        {
            MpFrame f = frame(a, s, node, MP_NODE_STATUS, now);
            f.valid = online;
            mp_router_put(r, &f);
            a->online[node - 1] = online;
        }
        if (s->emcy[node - 1] != a->fault[node - 1])
        {
            a->fault[node - 1] = s->emcy[node - 1];
            MpFrame f = frame(a, s, node, MP_FAULT, now);
            f.valid = true;
            f.values[0] = (int32_t)s->emcy[node - 1];
            mp_router_put(r, &f);
        }
        if (!online || !boot || !physical_fresh(node,4,s->milliseconds) || !physical_fresh(node,3,s->milliseconds) || !mp_od_read(od,base,1)) {
            a->waves[node==1?0:1].count=0;
            if(node==2) a->waves[2].count=0;
            continue;
        }
        wave(a, s, r, node, 0);
        if (node == 2)
            wave(a, s, r, node, 1);
        uint32_t anchor = mp_od_read(od, base, 2);
        if (!physical_fresh(node,2,s->milliseconds) || (anchor == a->anchor[node - 1] && a->seq[node-1][node==1?MP_SPO2:MP_HR]))
            continue;
        a->anchor[node - 1] = anchor;
        /* CAN 标量仍为 1Hz；云端按 2 秒合并发送，为实时波形和补传留出串口带宽。 */
        if (s->milliseconds % 2000 >= 1000)
            continue;
        const MpStream streams[2][3] = {{MP_SPO2, MP_PR, MP_NIBP}, {MP_HR, MP_RR, MP_TEMP}};
        for (unsigned j = 0; j < 3; j++)
        {
            uint64_t stamp=capture(od,base,anchor,now);
            if(!stamp) continue;
            MpFrame f = frame(a, s, node, streams[node - 1][j], stamp);
            unsigned bit = node == 1 ? j + 1 : (j == 0 ? 2 : j == 1 ? 3 : 4);
            f.valid = (a->quality[node - 1] & (1U << bit)) != 0;
            f.count = j == 2 && node == 1 ? 2 : 1;
            f.values[0] = (int32_t)mp_od_read(od, base + 0x20, j + 1);
            if (f.stream == MP_TEMP)
                f.values[0] = (int16_t)f.values[0];
            if (f.count == 2)
                f.values[1] = (int32_t)mp_od_read(od, base + 0x20, 4);
            mp_router_put(r, &f);
        }
    }
    if (s->milliseconds - a->status_tick >= 5000)
    {
        MpFrame f = frame(a, s, 3, MP_GATEWAY_STATUS, now);
        f.valid = true;
        mp_router_put(r, &f);
        a->status_tick = s->milliseconds;
    }
}
