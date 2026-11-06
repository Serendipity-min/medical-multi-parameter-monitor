/* 每段一个Node3协议端口，同一业务Gateway；仅汇聚数据模型，不桥接CAN报文。 */
#include "b4_gateway.h"
#include <string.h>

static void invalidate(B4Segment *s) {
    memset(s->seen, 0, sizeof(s->seen)); memset(s->wave, 0, sizeof(s->wave));
    memset(s->have_tick, 0, sizeof(s->have_tick)); s->observed_boot++;
    s->nibp_emitted = false;
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
        /* 两个OD各只消费本段节点；错误路由不得让另一段HB误报在线。 */
        mp_od_write(&s->od, 0x1016, bus == 0 ? 2 : 1, 0);
        for (unsigned i = 0; i < 10; i++) if (i / 5 != bus)
            mp_od_write(&s->od, 0x1400 + i, 1, 0x80000000u | mp_pdo_id(i / 5 + 1, i % 5));
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
    if (node < 1 || node > 2) return false;
    if (!g->segments[node - 1].link_up) return false;
    CO_HBconsumer_t *hb = g->segments[node - 1].co->HBcons;
    CO_NMT_internalState_t state;
    return CO_HBconsumer_getState(hb, node - 1) == CO_HBconsumer_ACTIVE &&
        CO_HBconsumer_getNmtState(hb, node - 1, &state) == 0 && state == CO_NMT_OPERATIONAL;
}
void b4_gateway_link(B4Gateway *g, unsigned bus, bool online) {
    if (bus > 1) return;
    B4Segment *s = &g->segments[bus];
    if (s->link_up != online) { invalidate(s); s->link_up = online; }
    b4_bus_online(bus, online);
}
int b4_gateway_nmt(B4Gateway *g, unsigned node, CO_NMT_command_t cmd) {
    if (node < 1 || node > 2) return -1;
    return CO_NMT_sendCommand(g->segments[node - 1].co->NMT, cmd, node);
}
static bool fresh(B4Segment *s, unsigned pdo, uint32_t now) {
    return s->seen[pdo] && (uint32_t)(now - s->seen_at[pdo]) <= 1500u;
}
static uint64_t sample_utc(B4Gateway *g, B4Segment *s, unsigned base, uint32_t tick, uint32_t arrival) {
    if (!g->utc_valid || (uint32_t)(g->now - g->utc_at) > 30000u || !fresh(s, 3, g->now)) return 0;
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
static void emit(B4Gateway *g, B4Segment *s, MpFrame *f) {
#ifdef MP_B5_CLOUD_CANDIDATE
    /* SKX原始质量位未标合成；B5在出口强制来源，不改原CAN帧/有效位/时间。 */
    f->synthetic = true;
    f->epoch = g->session;
    f->boot = s->observed_boot;
#endif
    f->seq = ++s->seq[f->stream];
    /* Backend拒绝0时间戳；未授时只计入本机诊断，绝不改成发送时刻伪装采集UTC。 */
    if (!f->timestamp) {
        g->unstamped++;
#ifdef MP_FINAL_UNIFIED
        g->unstamped_stream[f->stream]++;
#endif
        return;
    }
    mp_router_put(&g->router, f);
}
static void wave_boundary(B4Gateway *g, unsigned bus, unsigned pdo) {
    B4Segment *s=&g->segments[bus];MpFrame *f=&s->wave[pdo];
#ifdef MP_FINAL_UNIFIED
    /* 短段保留原末点时间和质量；不跨真实间断拼接，也不补点。 */
    if(bus==0 && f->count){
        g->ppg_partial_batches++;g->ppg_partial_samples+=f->count;
        emit(g,s,f);f->count=0;return;
    }
    g->flow_discarded[bus][pdo]+=f->count;
#endif
    g->partial_discarded+=f->count;f->count=0;
}
static void waveform(B4Gateway *g, unsigned bus, unsigned pdo, uint32_t arrival) {
    B4Segment *s = &g->segments[bus]; unsigned base = 0x3100 + bus * 0x100;
    if (pdo == 1 && bus == 0) return; /* A的TPDO2是NIBP完成时间，不是第二路波形。 */
    uint32_t tick = mp_od_read(&s->od, base + 0x10 + pdo, 2);
    int32_t value = (int32_t)mp_od_read(&s->od, base + 0x10 + pdo, 1);
    uint32_t quality = mp_od_read(&s->od, base + 0x30, 1);
    bool valid = fresh(s, 4, g->now) && b4_gateway_online(g, bus + 1) && (quality & (1u << pdo));
    uint64_t utc = sample_utc(g, s, base, tick, arrival);
    MpFrame *f = &s->wave[pdo]; unsigned rate = bus == 1 && pdo == 0 ? 250 : 50;
    bool synthetic = (quality >> 31) != 0;
    if (!utc) valid = false;
    if (s->have_tick[pdo]) {
        int32_t delta = (int32_t)(tick - s->last_tick[pdo]);
        int32_t step = (int32_t)(1000u / rate);
        int32_t phase = (int32_t)(tick - s->first_tick[pdo]) - (int32_t)(f->count * 1000u / rate);
        /* 真实250SPS内部ADC时钟与整数毫秒域有3/4/5ms量化；不能当作缺帧。
         * 单步和整批相位均限±1ms，8ms丢点/重复/倒序仍清批，不伪造重采样点。 */
        if (delta < step - 1 || delta > step + 1 || (f->count && (phase < -1 || phase > 1))) {
            wave_boundary(g,bus,pdo);
#ifdef MP_FINAL_UNIFIED
            g->flow_gaps[bus][pdo]++;
#endif
            f->count = 0; g->wave_gaps++;
        }
    }
    if (f->count && (f->valid != valid || f->synthetic != synthetic)) {
        wave_boundary(g,bus,pdo);g->quality_resets++;
#ifdef MP_FINAL_UNIFIED
        g->flow_quality[bus][pdo]++;
#endif
        f->count=0;
    }
    s->have_tick[pdo] = true; s->last_tick[pdo] = tick;
    if (!f->count) s->first_tick[pdo] = tick;
    f->node = bus + 1; f->stream = bus == 0 ? MP_PPG : pdo == 0 ? MP_ECG : MP_RESP;
    f->rate = rate; f->valid = valid; f->synthetic = synthetic;
    f->timestamp = utc; f->epoch = s->observed_boot; f->boot = s->generation;
    f->values[f->count++] = value;
    /* 250Hz ECG每100点出批；最坏int32数值仍可放入2048B JSON，绝不截断。 */
    if (f->count == (rate == 250 ? B4_ECG_BATCH : 50u)) { emit(g, s, f); f->count = 0; }
}
static void scalars(B4Gateway *g, unsigned bus, uint32_t arrival, bool vitals) {
    B4Segment *s = &g->segments[bus]; unsigned base = 0x3100 + bus * 0x100;
    uint32_t flags = mp_od_read(&s->od, base + 0x30, 1);
    uint32_t tick = mp_od_read(&s->od, base, 2);
    uint64_t utc = sample_utc(g, s, base, tick, arrival);
    unsigned count = vitals ? (bus ? 3 : 2) : 0; /* A血压必须走完成tick审计，不把旧镜像当新结果。 */
    for (unsigned i = 0; i < count; i++) {
        MpFrame f = {0}; f.node = bus + 1; f.count = 1;
        f.stream = bus ? (i == 0 ? MP_HR : i == 1 ? MP_RR : MP_TEMP) : (i == 0 ? MP_SPO2 : MP_PR);
        f.timestamp = utc; f.epoch = s->observed_boot; f.boot = s->generation; f.synthetic = flags >> 31;
        f.valid = utc && fresh(s, 4, g->now) && b4_gateway_online(g, bus + 1) && (flags & (1u << (i + (bus ? 2 : 1))));
        if (bus && i==2) {
            uint32_t age=mp_od_read(&s->od,base+0x20,4);
            /* utc是节点标量报告秒锚；帧龄只撤销过旧读数，不冒充精确测温UTC。 */
            f.valid=f.valid && age<=2500u;
        }
        f.values[0] = (int32_t)mp_od_read(&s->od, base + 0x20, i + 1);
        emit(g, s, &f);
    }
    /* 沿用H3完成时间扩展：只发新的同值SYS/DIA代次，旧值/缺扩展不能伪装实时血压。 */
    if (!bus && utc && fresh(s, 1, g->now) && fresh(s, 4, g->now) &&
        b4_gateway_online(g, 1) && (flags & (1u << 3)) && (flags & (1u << 9))) {
        uint32_t completion = mp_od_read(&s->od, base + 0x11, 1);
        uint32_t packed = mp_od_read(&s->od, base + 0x11, 2);
        uint32_t anchor = mp_od_read(&s->od, base, 2);
        int32_t age = (int32_t)(anchor - completion);
        uint32_t sys = mp_od_read(&s->od, base + 0x20, 3), dia = mp_od_read(&s->od, base + 0x20, 4);
        if (age >= 0 && age <= 90000 && packed == (sys | (dia << 16)) && sys && dia &&
            (!s->nibp_emitted || s->nibp_tick != completion)) {
            MpFrame f = {0}; f.node = 1; f.stream = MP_NIBP; f.count = 2; f.valid = true;
            f.timestamp = utc - (uint32_t)age; f.epoch = s->observed_boot; f.boot = s->generation;
            f.synthetic = flags >> 31; f.values[0] = sys; f.values[1] = dia;
            emit(g, s, &f); s->nibp_tick = completion; s->nibp_emitted = true;
        }
    }
}
void b4_gateway_receive(B4Gateway *g, unsigned bus, MpCanFrame *f, uint32_t arrival) {
    if (bus > 1 || f->dlc > 8 || f->ident > 0x7ff || (int32_t)(g->now - arrival) < 0) { g->malformed++; return; }
    unsigned remote = bus + 1, wrong = 2 - bus;
    /* 节点身份和物理入口同时校验；任一段收到另一节点流都拒绝，不做隐式桥接。 */
    if (f->ident == 0x700 + wrong || f->ident == 0x580 + wrong || f->ident == 0x80 + wrong) { g->wrong_bus++; return; }
    for (unsigned p = 0; p < 5; p++) if (f->ident == mp_pdo_id(wrong, p)) { g->wrong_bus++; return; }
    B4Segment *s = &g->segments[bus]; int pdo = -1;
    if (f->ident == 0x700 + remote) {
        if (f->dlc != 1 || (f->data[0] != 0 && f->data[0] != 4 && f->data[0] != 5 && f->data[0] != 127)) { g->malformed++; return; }
        if (f->data[0] == 0 || f->data[0] != 5) invalidate(s);
    }
    if (f->ident == 0x80 + remote) {
        if (f->dlc != 8) { g->malformed++; return; }
        MpFrame event = {0}; event.node = remote; event.stream = MP_FAULT; event.count = 1;
        event.values[0] = (int32_t)f->data[0] | ((int32_t)f->data[1] << 8);
        event.timestamp = g->utc_valid ? (uint64_t)g->epoch * 1000 + g->utc_fraction + (uint32_t)(arrival - g->utc_at) : 0;
        event.valid = g->utc_valid; event.epoch = s->observed_boot; event.boot = s->generation;
        event.synthetic = mp_od_read(&s->od, 0x3130 + bus * 0x100, 1) >> 31;
        emit(g, s, &event);
    }
    for (unsigned p = 0; p < 5; p++) if (f->ident == mp_pdo_id(remote, p)) pdo = (int)p;
    if (pdo >= 0) {
        if (f->dlc != 8) { g->malformed++; return; }
        if (pdo == 4) {
            uint32_t generation; memcpy(&generation, f->data + 4, 4);
            if (!generation) { g->malformed++; return; }
            if (generation != s->generation) { invalidate(s); s->generation = generation; }
        }
        s->seen[pdo] = true; s->seen_at[pdo] = arrival;
    }
    /* 每帧交付后立即处理RPDO；否则多个样本会在CANopenNode单PDO槽内互相覆盖。 */
    b4_bus_receive(bus, f); CO_process_RPDO(s->co, false, 0, NULL);
    if (pdo == 0 || pdo == 1) waveform(g, bus, (unsigned)pdo, arrival);
    if (pdo == 2) scalars(g, bus, arrival, true);
    /* 完成时间可能先于本秒UTC锚到达；锚/质量后到时再核对同值身份，不漏发新结果。 */
    if (!bus && (pdo == 3 || pdo == 4)) scalars(g, bus, arrival, false);
}
void b4_gateway_tick(B4Gateway *g, uint32_t now) {
    uint32_t elapsed = now - g->now; g->now = now;
    for (unsigned bus = 0; bus < 2; bus++) {
        B4Segment *s = &g->segments[bus];
        if (CO_process(s->co, false, elapsed > 1000 ? 1000000 : elapsed * 1000, NULL) != CO_RESET_NOT) {
            invalidate(s); g->resets++; s->port.enabled = false;
        }
        CO_process_RPDO(s->co, false, 0, NULL);
        bool online = b4_gateway_online(g, bus + 1);
        if (!s->status_sent || online != s->last_online || now - s->status_at >= 5000u) {
            MpFrame f = {0}; f.node = bus + 1; f.stream = MP_NODE_STATUS; f.count = 1;
            f.valid = online; f.epoch = s->observed_boot; f.boot = s->generation;
            f.timestamp = g->utc_valid ? (uint64_t)g->epoch * 1000 + g->utc_fraction + (uint32_t)(now - g->utc_at) : 0;
            f.synthetic = mp_od_read(&s->od, 0x3130 + bus * 0x100, 1) >> 31;
            emit(g, s, &f); s->status_sent = true; s->last_online = online; s->status_at = now;
        }
    }
#ifdef MP_FINAL_UNIFIED
    /* 输入静默时提交尾段，时间戳仍是最后一个真实点，不等下一批凑满。 */
    if(g->segments[0].wave[0].count && now-g->segments[0].seen_at[0]>=100u)
        wave_boundary(g,0,0);
#endif
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
