/* 每段一个Node3协议端口，同一业务Gateway；仅汇聚数据模型，不桥接CAN报文。 */
#include "b4_gateway.h"
#include <string.h>
#include "../data_model/roles.h"

#ifdef MP_FIVE_NODE
#define REMOTE_COUNT 2u
#else
#define REMOTE_COUNT 1u
#endif
static unsigned remote_id(unsigned bus, unsigned slot) {
    return slot ? (bus ? 4u : 5u) : bus + 1u;
}
static unsigned mirror_slot(unsigned bus, unsigned slot) {
#ifdef MP_FIVE_NODE
    (void)bus; return slot;
#else
    (void)slot; return bus;
#endif
}
static unsigned mirror_base(unsigned bus, unsigned slot) { return 0x3100u + mirror_slot(bus, slot) * 0x100u; }
static int locate(unsigned node, unsigned *bus, unsigned *slot) {
    for (unsigned b=0;b<2;b++) for(unsigned n=0;n<REMOTE_COUNT;n++)
        if(remote_id(b,n)==node){*bus=b;*slot=n;return 1;}
    return 0;
}

static void invalidate(B4Segment *s, B4Remote *n) {
    memset(n->seen, 0, sizeof(n->seen)); memset(n->have_tick, 0, sizeof(n->have_tick));
    if (n == &s->remote[0]) memset(s->wave, 0, sizeof(s->wave));
    n->observed_boot++;
#ifndef MP_FIVE_NODE
    n->nibp_emitted = false;
#endif
}
void b4_gateway_close(B4Gateway *g) {
    for (unsigned bus = 0; bus < 2; bus++) {
        B4Segment *s = &g->segments[bus];
        if (s->co) { CO_CANmodule_disable(s->co->CANmodule); CO_delete(s->co); s->co = NULL; }
    }
    b4_bus_reset();
}
int b4_gateway_init(B4Gateway *g) {
    memset(g, 0, sizeof(*g)); b4_bus_reset(); mp_router_init(&g->router);
    for (unsigned bus = 0; bus < 2; bus++) {
        B4Segment *s = &g->segments[bus]; uint32_t error = 0;
        s->port = (B4Port){3, bus, true, NULL};
        s->link_up = true;
        if (mp_od_init(&s->od, 3, &s->config)) goto fail;
        /* 复用两个静态镜像槽；每段仅消费自己的节点和角色。 */
        for (unsigned i=0;i<2;i++) mp_od_write(&s->od,0x1016,i+1,0);
        for (unsigned i=0;i<10;i++) mp_od_write(&s->od,0x1400+i,1,0x80000000u|mp_pdo_id(i/5+1,i%5));
        for (unsigned slot=0;slot<REMOTE_COUNT;slot++) {
            unsigned node=remote_id(bus,slot), mirror=mirror_slot(bus,slot);
            mp_od_write(&s->od,0x1016,mirror+1,(node<<16)|1500u);
            for(unsigned p=0;p<5;p++) {
                bool enabled=p>=2 || (node==1 && p==0) || node==2 || (node==5 && p==1);
#ifndef MP_FIVE_NODE
                enabled=true;
#endif
                mp_od_write(&s->od,0x1400+mirror*5+p,1,mp_pdo_id(node,p)|(enabled?0:0x80000000u));
            }
        }
        mp_od_write(&s->od,0x1280,1,0x600u+bus+1u);
        mp_od_write(&s->od,0x1280,2,0x580u+bus+1u);
        mp_od_write(&s->od,0x1280,3,bus+1u);
        s->co = CO_new(&s->config, NULL);
        if (!s->co || CO_CANinit(s->co, &s->port, 500) != CO_ERROR_NO) goto fail;
        if (CO_CANopenInit(s->co, NULL, NULL, &s->od.od, NULL, CO_NMT_STARTUP_TO_OPERATIONAL,
            100, 1000, 1000, false, 3, &error) != CO_ERROR_NO) goto fail;
        if (CO_CANopenInitPDO(s->co, s->co->em, &s->od.od, 3, &error) != CO_ERROR_NO) goto fail;
        CO_CANsetNormalMode(s->co->CANmodule);
    }
    return 0;
fail:
    b4_gateway_close(g); return -1;
}
void b4_gateway_sync(B4Gateway *g, uint32_t epoch, uint32_t now) {
    g->epoch = epoch; g->utc_at = now; g->utc_valid = epoch >= 1577836800u && epoch <= 4102444800u;
    g->time_sent = now - 10000u;
    g->utc_fraction = 0;
}
void b4_gateway_sync_ms(B4Gateway *g, uint64_t utc_ms, uint32_t now) {
    b4_gateway_sync(g, (uint32_t)(utc_ms / 1000u), now);
    g->utc_fraction = (uint32_t)(utc_ms % 1000u);
}
bool b4_gateway_online(B4Gateway *g, unsigned node) {
    unsigned bus,slot;
    if(!locate(node,&bus,&slot) || !g->segments[bus].link_up) return false;
    CO_HBconsumer_t *hb=g->segments[bus].co->HBcons;
    CO_NMT_internalState_t state;
    unsigned index=mirror_slot(bus,slot);
    return CO_HBconsumer_getState(hb,index)==CO_HBconsumer_ACTIVE &&
        CO_HBconsumer_getNmtState(hb,index,&state)==0 && state==CO_NMT_OPERATIONAL;
}
void b4_gateway_link(B4Gateway *g, unsigned bus, bool online) {
    if (bus>1) return;
    B4Segment *s=&g->segments[bus];
    if(s->link_up!=online){for(unsigned i=0;i<REMOTE_COUNT;i++)invalidate(s,&s->remote[i]);s->link_up=online;}
    b4_bus_online(bus,online);
}
int b4_gateway_nmt(B4Gateway *g,unsigned node,CO_NMT_command_t cmd) {
    unsigned bus,slot;
    if(!locate(node,&bus,&slot))return -1;
    return CO_NMT_sendCommand(g->segments[bus].co->NMT,cmd,node);
}
static bool fresh(B4Remote *n, unsigned pdo, uint32_t now) {
    return n->seen[pdo] && (uint32_t)(now - n->seen_at[pdo]) <= 1500u;
}
static uint64_t sample_utc(B4Gateway *g, B4Segment *s, B4Remote *n, unsigned base, uint32_t tick, uint32_t arrival) {
    if (!g->utc_valid || (uint32_t)(g->now - g->utc_at) > 30000u || !fresh(n, 3, g->now)) return 0;
    uint32_t epoch = mp_od_read(&s->od, base, 1), anchor = mp_od_read(&s->od, base, 2);
    int32_t delta = (int32_t)(tick - anchor);
    if (!epoch || delta < -2000 || delta > 2000) return 0;
    int64_t utc = (int64_t)epoch * 1000 + delta;
#ifdef MP_FINAL_UNIFIED
    /* IRQ帧可早于新校时锚点；保留有符号时间差，避免绕回约49天。 */
    int64_t current = (int64_t)g->epoch * 1000 + g->utc_fraction + (int32_t)(arrival - g->utc_at);
#else
    int64_t current = (int64_t)g->epoch * 1000 + g->utc_fraction + (uint32_t)(arrival - g->utc_at);
#endif
    return utc >= current - 5000 && utc <= current + 1000 ? (uint64_t)utc : 0;
}
static void emit(B4Gateway *g, B4Remote *n, MpFrame *f) {
#ifdef MP_B5_CLOUD_CANDIDATE
    /* SKX原始质量位未标合成；B5在出口强制来源，不改原CAN帧/有效位/时间。 */
    f->synthetic = true;
    f->epoch = g->session;
    f->boot = n->observed_boot;
#endif
    f->seq = ++n->seq[f->stream];
    /* Backend拒绝0时间戳；未授时只计入本机诊断，绝不改成发送时刻伪装采集UTC。 */
    if (!f->timestamp) { g->unstamped++; return; }
    mp_router_put(&g->router, f);
}
static void waveform(B4Gateway *g, unsigned bus, unsigned slot, unsigned pdo, uint32_t arrival) {
    B4Segment *s=&g->segments[bus]; B4Remote *n=&s->remote[slot];
    unsigned node=remote_id(bus,slot),base=mirror_base(bus,slot);
    if (pdo == 1 && bus == 0) return; /* A的TPDO2是NIBP完成时间，不是第二路波形。 */
    uint32_t tick = mp_od_read(&s->od, base + 0x10 + pdo, 2);
    int32_t value = (int32_t)mp_od_read(&s->od, base + 0x10 + pdo, 1);
    uint32_t quality = mp_od_read(&s->od, base + 0x30, 1);
    bool valid = fresh(n, 4, g->now) && b4_gateway_online(g, node) && (quality & (1u << pdo));
    uint64_t utc = sample_utc(g, s, n, base, tick, arrival);
    MpFrame *f = &s->wave[pdo]; unsigned rate = bus == 1 && pdo == 0 ? 250 : 50;
    bool synthetic = (quality >> 31) != 0;
    if (!utc) valid = false;
    if (n->have_tick[pdo]) {
        int32_t delta = (int32_t)(tick - n->last_tick[pdo]);
        int32_t step = (int32_t)(1000u / rate);
        int32_t phase = (int32_t)(tick - n->first_tick[pdo]) - (int32_t)(f->count * 1000u / rate);
        /* 真实250SPS内部ADC时钟与整数毫秒域有3/4/5ms量化；不能当作缺帧。
         * 单步和整批相位均限±1ms，8ms丢点/重复/倒序仍清批，不伪造重采样点。 */
        if (delta < step - 1 || delta > step + 1 || (f->count && (phase < -1 || phase > 1))) {
            g->partial_discarded+=f->count;
            f->count = 0; g->wave_gaps++;
        }
    }
    if (f->count && (f->valid != valid || f->synthetic != synthetic)) {
        g->partial_discarded+=f->count;g->quality_resets++;f->count=0;
    }
    n->have_tick[pdo] = true; n->last_tick[pdo] = tick;
    if (!f->count) n->first_tick[pdo] = tick;
    f->node = node; f->stream = bus == 0 ? MP_PPG : pdo == 0 ? MP_ECG : MP_RESP;
    f->rate = rate; f->valid = valid; f->synthetic = synthetic;
    f->timestamp = utc; f->epoch = n->observed_boot; f->boot = n->generation;
    f->values[f->count++] = value;
    /* 250Hz ECG每100点出批；最坏int32数值仍可放入2048B JSON，绝不截断。 */
    if (f->count == (rate == 250 ? B4_ECG_BATCH : 50u)) { emit(g, n, f); f->count = 0; }
}
static void scalars(B4Gateway *g, unsigned bus, unsigned slot, uint32_t arrival, bool vitals) {
    B4Segment *s=&g->segments[bus]; B4Remote *n=&s->remote[slot];
    unsigned node=remote_id(bus,slot),base=mirror_base(bus,slot);
    uint32_t flags = mp_od_read(&s->od, base + 0x30, 1);
    uint32_t tick = mp_od_read(&s->od, base, 2);
    uint64_t utc = sample_utc(g, s, n, base, tick, arrival);
    unsigned count=vitals?(node==1?2:node==2?2:node==4?1:0):0;
#ifndef MP_FIVE_NODE
    if(vitals && node==2)count=3;
#endif
    for(unsigned i=0;i<count;i++) {
        MpFrame f={0};f.node=node;f.count=1;
        f.stream=node==1?(i?MP_PR:MP_SPO2):node==4?MP_TEMP:i==0?MP_HR:i==1?MP_RR:MP_TEMP;
        unsigned sub=f.stream==MP_TEMP?3:i+1;
        unsigned bit=f.stream==MP_TEMP?4:node==1?i+1:i+2;
        f.timestamp=utc;f.epoch=n->observed_boot;f.boot=n->generation;f.synthetic=flags>>31;
        f.valid=utc && fresh(n,4,g->now) && b4_gateway_online(g,node) && (flags&(1u<<bit));
        if(f.stream==MP_TEMP)f.valid=f.valid && mp_od_read(&s->od,base+0x20,4)<=2500u;
        f.values[0]=(int32_t)mp_od_read(&s->od,base+0x20,sub);
        emit(g,n,&f);
    }
    /* 沿用H3完成时间扩展：只发新的同值SYS/DIA代次，旧值/缺扩展不能伪装实时血压。 */
    if (node==mp_role_node(MP_NIBP) && utc && fresh(n, 1, g->now) && fresh(n, 4, g->now) &&
        b4_gateway_online(g, node) && (flags & (1u << 3)) && (flags & (1u << 9))) {
        uint32_t completion = mp_od_read(&s->od, base + 0x11, 1);
        uint32_t packed = mp_od_read(&s->od, base + 0x11, 2);
        uint32_t anchor = mp_od_read(&s->od, base, 2);
        int32_t age = (int32_t)(anchor - completion);
        uint32_t sys = mp_od_read(&s->od, base + 0x20, 3), dia = mp_od_read(&s->od, base + 0x20, 4);
        if (age >= 0 && age <= 90000 && packed == (sys | (dia << 16)) && sys && dia &&
            (!n->nibp_emitted || n->nibp_tick != completion || n->nibp_generation != n->generation)) {
            MpFrame f = {0}; f.node = node; f.stream = MP_NIBP; f.count = 2; f.valid = true;
            f.timestamp = utc - (uint32_t)age; f.epoch = n->observed_boot; f.boot = n->generation;
            f.synthetic = flags >> 31; f.values[0] = sys; f.values[1] = dia;
            emit(g, n, &f); n->nibp_tick = completion; n->nibp_generation = n->generation; n->nibp_emitted = true;
        }
    }
}
void b4_gateway_receive(B4Gateway *g, unsigned bus, MpCanFrame *f, uint32_t arrival) {
    if (bus > 1 || f->dlc > 8 || f->ident > 0x7ff || (int32_t)(g->now - arrival) < 0) { g->malformed++; return; }
    unsigned remote=0,slot=0;
    for(unsigned b=0;b<2;b++) for(unsigned n=0;n<REMOTE_COUNT;n++) {
        unsigned candidate=remote_id(b,n);bool match=f->ident==0x700+candidate || f->ident==0x580+candidate || f->ident==0x80+candidate;
        for(unsigned p=0;p<5;p++)match=match || f->ident==mp_pdo_id(candidate,p);
        if(match){if(b!=bus){g->wrong_bus++;return;}remote=candidate;slot=n;}
    }
    /* 未配置的节点不能借同段其他节点的心跳获得身份。 */
    if(!remote){g->wrong_bus++;return;}
    B4Segment *s=&g->segments[bus];B4Remote *n=&s->remote[slot];int pdo=-1;
    if (f->ident == 0x700 + remote) {
        if (f->dlc != 1 || (f->data[0] != 0 && f->data[0] != 4 && f->data[0] != 5 && f->data[0] != 127)) { g->malformed++; return; }
        if (f->data[0] != 5) { invalidate(s,n); if(!f->data[0])n->generation=0; }
    }
    if (f->ident == 0x80 + remote) {
        if (f->dlc != 8) { g->malformed++; return; }
        MpFrame event = {0}; event.node = remote; event.stream = MP_FAULT; event.count = 1;
        event.values[0] = (int32_t)f->data[0] | ((int32_t)f->data[1] << 8);
        event.timestamp = g->utc_valid ? (uint64_t)g->epoch * 1000 + g->utc_fraction + (uint32_t)(arrival - g->utc_at) : 0;
        event.valid = g->utc_valid; event.epoch = n->observed_boot; event.boot = n->generation;
        event.synthetic = mp_od_read(&s->od, mirror_base(bus,slot)+0x30, 1) >> 31;
        emit(g, n, &event);
    }
    for (unsigned p = 0; p < 5; p++) if (f->ident == mp_pdo_id(remote, p)) pdo = (int)p;
    if (pdo >= 0) {
        if (f->dlc != 8) { g->malformed++; return; }
#ifdef MP_FIVE_NODE
        if ((pdo<2 && !((remote==1 && pdo==0) || remote==2 || (remote==5 && pdo==1)))) {g->wrong_bus++;return;}
        if (pdo==4) {
            uint32_t flags;memcpy(&flags,f->data,4);
            if((remote==1 && (flags&(1u<<3))) || (remote==2 && (flags&(1u<<4))) ||
               (remote==4 && (flags&15u)) || (remote==5 && (flags&7u))) {g->wrong_bus++;return;}
        }
#endif
        if (pdo == 4) {
            uint32_t generation; memcpy(&generation, f->data + 4, 4);
            if (!generation) { g->malformed++; return; }
            if (n->generation && (int32_t)(generation-n->generation)<0) {g->malformed++;return;}
            if (generation != n->generation) { invalidate(s,n); n->generation = generation; }
        }
        n->seen[pdo] = true; n->seen_at[pdo] = arrival;
    }
    /* 每帧交付后立即处理RPDO；否则多个样本会在CANopenNode单PDO槽内互相覆盖。 */
    b4_bus_receive(bus, f); CO_process_RPDO(s->co, false, 0, NULL);
    if ((remote==1 && pdo==0) || (remote==2 && (pdo==0 || pdo==1))) waveform(g,bus,slot,(unsigned)pdo,arrival);
    if (pdo == 2) scalars(g,bus,slot,arrival,true);
    /* 完成时间可能先于本秒UTC锚到达；锚/质量后到时再核对同值身份，不漏发新结果。 */
    if (remote==mp_role_node(MP_NIBP) && (pdo==3 || pdo==4)) scalars(g,bus,slot,arrival,false);
}
void b4_gateway_tick(B4Gateway *g, uint32_t now) {
    uint32_t elapsed = now - g->now; g->now = now;
    for (unsigned bus = 0; bus < 2; bus++) {
        B4Segment *s = &g->segments[bus];
        if (CO_process(s->co,false,elapsed>1000?1000000:elapsed*1000,NULL)!=CO_RESET_NOT) {
            for(unsigned i=0;i<REMOTE_COUNT;i++)invalidate(s,&s->remote[i]);
            g->resets++;s->port.enabled=false;
        }
        CO_process_RPDO(s->co,false,0,NULL);
        for(unsigned slot=0;slot<REMOTE_COUNT;slot++) {
            unsigned node=remote_id(bus,slot);B4Remote *n=&s->remote[slot];
            bool online=b4_gateway_online(g,node);
            if(n->last_online && !online)invalidate(s,n);
            if(!n->status_sent || online!=n->last_online || now-n->status_at>=5000u) {
                MpFrame f={0};f.node=node;f.stream=MP_NODE_STATUS;f.count=1;
                f.valid=online;f.epoch=n->observed_boot;f.boot=n->generation;
                f.timestamp=g->utc_valid?(uint64_t)g->epoch*1000+g->utc_fraction+(uint32_t)(now-g->utc_at):0;
                f.synthetic=mp_od_read(&s->od,mirror_base(bus,slot)+0x30,1)>>31;
                emit(g,n,&f);n->status_sent=true;n->last_online=online;n->status_at=now;
            }
        }
    }
    if (g->utc_valid && now - g->utc_at > 30000u) g->utc_valid = false;
    if (g->utc_valid && now - g->time_sent >= 10000u) {
        uint64_t relative = (uint64_t)g->epoch * 1000 + g->utc_fraction + (uint32_t)(now - g->utc_at) - 441763200000ULL;
        uint32_t ms = relative % 86400000u; uint16_t days = relative / 86400000u;
        for (unsigned bus = 0; bus < 2; bus++) {
            CO_CANtx_t tx = {0}; tx.ident = 0x100; tx.DLC = 6;
            memcpy(tx.data, &ms, 4); memcpy(tx.data + 4, &days, 2);
            (void)CO_CANsend(g->segments[bus].co->CANmodule, &tx);
        }
        g->time_sent = now;
    }
    b4_bus_poll();
}
