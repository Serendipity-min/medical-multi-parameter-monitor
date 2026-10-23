/* 双总线合成台架：A使用真实CANopenNode生产，B输入来自生产B适配器的真实编码。
 * 不访问硬件、不启动MQTT网络；格式化/Router使用正式实现。 */
#include "b4_gateway.h"
#include <assert.h>
#include <limits.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "core_mqtt_serializer.h"
static B4Gateway gateway;
static struct { MpOD od; CO_config_t config; CO_t *co; B4Port port; } a;
static unsigned blocked[2], traffic[2][2048], frames[MP_STREAMS], valid[MP_STREAMS], max_json;
static uint32_t sequence[3][MP_STREAMS];
static unsigned replayed;
static FILE *canonical;
int b4_bus_transmit(unsigned bus, const MpCanFrame *frame) {
    if (blocked[bus]) return 0;
    MpCanFrame f = *frame; traffic[bus][f.ident]++;
    b4_gateway_receive(&gateway, bus, &f, gateway.now); return 1;
}
static void a_init(void) {
    uint32_t error = 0; memset(&a, 0, sizeof(a)); a.port = (B4Port){1, 0, true, NULL};
    assert(mp_od_init(&a.od, 1, &a.config) == 0); a.co = CO_new(&a.config, NULL); assert(a.co);
    assert(CO_CANinit(a.co, &a.port, 500) == CO_ERROR_NO);
    assert(CO_CANopenInit(a.co, NULL, NULL, &a.od.od, NULL, CO_NMT_STARTUP_TO_OPERATIONAL,
        100, 1000, 1000, false, 1, &error) == CO_ERROR_NO);
    assert(CO_CANopenInitPDO(a.co, a.co->em, &a.od.od, 1, &error) == CO_ERROR_NO);
    CO_CANsetNormalMode(a.co->CANmodule);
}
static void a_tick(uint32_t now) {
    assert(CO_process(a.co, false, 1000, NULL) == CO_RESET_NOT);
    if (now % 1000 == 0) {
        mp_od_write(&a.od, 0x2100, 1, 1792713600u + now / 1000);
        mp_od_write(&a.od, 0x2100, 2, now - now % 1000);
        mp_od_write(&a.od, 0x2130, 1, 0x8000020fu); mp_od_write(&a.od, 0x2130, 2, 1);
        mp_od_write(&a.od, 0x2120, 1, 9800); mp_od_write(&a.od, 0x2120, 2, 6000);
        mp_od_write(&a.od, 0x2120, 3, 1200); mp_od_write(&a.od, 0x2120, 4, 800);
        mp_od_write(&a.od, 0x2111, 1, now); mp_od_write(&a.od, 0x2111, 2, 1200 | (800u << 16));
        for (unsigned i = 1; i < 5; i++) CO_TPDOsendRequest(&a.co->TPDO[i]);
    }
    bool_t configured = a.co->TPDO[0].PDO_common.valid;
    if (now % 20 == 0) {
        mp_od_write(&a.od, 0x2110, 1, (uint32_t)(now % 1000) * 1000);
        mp_od_write(&a.od, 0x2110, 2, now); CO_TPDOsendRequest(&a.co->TPDO[0]);
    } else a.co->TPDO[0].PDO_common.valid = false;
    CO_process_TPDO(a.co, false, 1000, NULL); a.co->TPDO[0].PDO_common.valid = configured;
}
static void drain(uint32_t now) {
    MpFrame f; char json[2048], topic[128];
    while (mp_router_take(&gateway.router, &f, now)) {
        int n = mp_json(&f, json, sizeof(json)); assert(n > 0 && n < 2048 && json[n] == 0);
        assert(mp_topic(&f, topic, sizeof(topic)) > 0);
        if (canonical) fprintf(canonical, "%s\t%s\n", topic, json);
        if ((unsigned)n > max_json) max_json = n;
        assert(f.node >= 1 && f.node <= 2);
        if (!f.replay) { assert(f.seq > sequence[f.node][f.stream]); sequence[f.node][f.stream] = f.seq; }
        else replayed++;
        frames[f.stream]++; if (f.valid) valid[f.stream]++;
        if (f.stream == MP_ECG) assert(f.rate == 250 && f.count == 100);
        if (f.stream == MP_RESP || f.stream == MP_PPG) assert(f.rate == 50 && f.count == 50);
        if (f.stream == MP_TEMP) assert(!f.valid && strstr(json, "\"value\":null"));
        mp_router_ack(&gateway.router, &f, true);
    }
}
static void inject(unsigned bus, unsigned id, unsigned dlc, const uint8_t *data) {
    MpCanFrame f = {0}; f.ident = id; f.dlc = dlc; if (dlc <= 8) memcpy(f.data, data, dlc);
    b4_gateway_receive(&gateway, bus, &f, gateway.now);
}
static void json_bounds(void) {
    MpFrame f = {0}; f.node = 2; f.stream = MP_ECG; f.valid = true; f.rate = 250;
    f.timestamp = UINT64_C(4102444800000); f.seq = f.epoch = f.boot = UINT32_MAX;
    for (unsigned i = 0; i < MP_FRAME_MAX_SAMPLES; i++) f.values[i] = INT32_MIN;
    char guarded[2050]; memset(guarded, 'X', sizeof(guarded)); f.count = 250;
    assert(mp_json(&f, guarded + 1, 2048) == 0); assert(guarded[0] == 'X' && guarded[2049] == 'X');
    /* 容量保护是对正式分批路径的最坏值测试，而非仅给格式化器更大缓冲区。 */
    f.count = 100; int n = mp_json(&f, guarded + 1, 2048); assert(n > 0 && n < 2048);
    char topic[128]; assert(mp_topic(&f, topic, sizeof(topic)));
    MQTTPublishInfo_t publish = {0}; publish.qos = MQTTQoS0;
    publish.pTopicName = topic; publish.topicNameLength = (uint16_t)strlen(topic);
    publish.pPayload = guarded + 1; publish.payloadLength = (size_t)n;
    size_t remaining, packet; uint8_t network[2048]; MQTTFixedBuffer_t buffer = {network, sizeof(network)};
    assert(MQTT_GetPublishPacketSize(&publish, &remaining, &packet) == MQTTSuccess && packet <= sizeof(network));
    assert(MQTT_SerializePublish(&publish, 0, remaining, &buffer) == MQTTSuccess);
    printf("actual coreMQTT worst PUBLISH=%u bytes\n", (unsigned)packet);
    printf("worst ECG100 JSON=%d bytes; ECG250 rejected without overrun\n", n);
    f.timestamp = 0;
    assert(mp_json(&f, guarded + 1, 2048) > 0 && strstr(guarded + 1, "\"timestamp\":0,"));
}
int main(int argc, char **argv) {
    assert(argc == 2 || argc == 3); bool pressure = argc == 3;
    const char *output = getenv("B4_CANONICAL_OUT");
    if (output) { canonical = fopen(output, "w"); assert(canonical); }
    assert(b4_gateway_init(&gateway) == 0);
    mp_router_online(&gateway.router, true); a_init(); b4_gateway_sync(&gateway, 1792713600, 0);
    FILE *wire = fopen(argv[1], "r"); assert(wire);
    unsigned at, id, dlc, bytes[8]; int scanned = fscanf(wire, "%u %u %u", &at, &id, &dlc);
    for (uint32_t now = 0; now < 90000; now++) {
        if (now % 10000 == 0) b4_gateway_sync(&gateway, 1792713600 + now / 1000, now);
        b4_gateway_tick(&gateway, now); a_tick(now); b4_bus_poll();
        while (scanned == 3 && at == now) {
            MpCanFrame f = {0}; f.ident = id; f.dlc = dlc; assert(dlc <= 8);
            for (unsigned i = 0; i < dlc; i++) { assert(fscanf(wire, "%u", &bytes[i]) == 1); f.data[i] = bytes[i]; }
            /* 夹具保留B生产者实码；进入离线模拟器时显式标记合成来源，绝不发布LIVE。 */
            if (id == 0x682) f.data[3] |= 0x80;
            traffic[1][id]++; b4_gateway_receive(&gateway, 1, &f, now);
            scanned = fscanf(wire, "%u %u %u", &at, &id, &dlc);
        }
        /* 模拟正式传输最大5秒等待：CAN仍按毫秒处理，只有发布消费者暂停。 */
        if (!pressure || now < 30000 || now >= 35000) drain(now);
    }
    assert(scanned == EOF); fclose(wire);
    assert(gateway.wave_gaps == 0); /* 真实量化间隔夹具不得被误判为缺帧。 */
    assert(frames[MP_ECG] >= (pressure ? 210u : 220u) && frames[MP_RESP] >= 85 && frames[MP_PPG] >= 85);
    assert(valid[MP_HR] > 20 && valid[MP_RR] > 20 && !valid[MP_TEMP]);
    printf("normal NIBP_valid=%u router_drop=%u malformed=%u\n", valid[MP_NIBP], gateway.router.dropped, gateway.malformed); fflush(stdout);
    assert(valid[MP_NIBP] > 80 && gateway.malformed == 0);
    if (pressure) assert(gateway.router.dropped == 0 && replayed > 0);
    else assert(gateway.router.dropped == 0);
    printf("five-second publishing stall=%u dropped=%u replayed=%u live=%u cache=%u\n", pressure,
        gateway.router.dropped, replayed, gateway.router.ln, gateway.router.cn);
    assert(traffic[0][0x181] && traffic[1][0x182] && !traffic[0][0x182] && !traffic[1][0x181]);
    assert(traffic[0][0x703] && traffic[1][0x703] && traffic[0][0x100] && traffic[1][0x100]);
    /* 定向NMT：仅Node2的物理段产生该命令，广播身份不会变成另一段转发器。 */
    unsigned nmt0 = traffic[0][0], nmt1 = traffic[1][0];
    assert(b4_gateway_nmt(&gateway, 2, CO_NMT_ENTER_PRE_OPERATIONAL) == 0); b4_bus_poll();
    assert(traffic[0][0] == nmt0 && traffic[1][0] == nmt1 + 1);
    uint8_t data[8] = {5}; unsigned wrong = gateway.wrong_bus;
    inject(0, 0x702, 1, data); inject(1, 0x181, 8, data); assert(gateway.wrong_bus == wrong + 2);
    unsigned malformed = gateway.malformed; inject(1, 0x182, 7, data); inject(1, 0x702, 2, data);
    assert(gateway.malformed == malformed + 2);
    /* 8ms真缺点与重复tick仍须清除部分批次，不能被±1ms量化容差放过。 */
    B4Segment *segment = &gateway.segments[1]; unsigned gaps = gateway.wave_gaps;
    uint32_t next_tick = segment->last_tick[0] + 8u;
    memcpy(data + 4, &next_tick, 4); inject(1, 0x182, 8, data);
    assert(gateway.wave_gaps == gaps + 1 && segment->wave[0].count == 1);
    inject(1, 0x182, 8, data);
    assert(gateway.wave_gaps == gaps + 2 && segment->wave[0].count == 1);
    /* EMCY是独立事件，不得解释成新的生命体征；缺少完整8B应拒绝。 */
    unsigned faults = gateway.segments[1].seq[MP_FAULT];
    data[0] = 0x10; data[1] = 0x81; inject(1, 0x82, 8, data);
    assert(gateway.segments[1].seq[MP_FAULT] == faults + 1);
    /* 相同RAM generation=1的重启仍清空会话与部分波形，不能续接旧批次。 */
    gateway.segments[1].wave[0].count = 12; unsigned boot = gateway.segments[1].observed_boot;
    data[0] = 0; inject(1, 0x702, 1, data);
    assert(gateway.segments[1].wave[0].count == 0 && gateway.segments[1].observed_boot == boot + 1);
    /* 总线2邮箱持续忙：总线1心跳继续，容量溢出显式计数且内存不增长。 */
    blocked[1] = 1; CO_CANtx_t tx = {0}; tx.ident = 0x602; tx.DLC = 8;
    for (unsigned i = 0; i < 200; i++) (void)CO_CANsend(gateway.segments[1].co->CANmodule, &tx);
    assert(b4_bus_diag[1].overflow >= 72 && b4_bus_diag[1].high_water == 128);
    unsigned sent0 = b4_bus_diag[0].sent;
    for (uint32_t now = 90000; now < 92000; now++) { b4_gateway_tick(&gateway, now); a_tick(now); b4_bus_poll(); drain(now); }
    assert(b4_bus_diag[0].sent > sent0 && b4_bus_diag[0].overflow == 0);
    b4_bus_online(1, false); assert(b4_bus_diag[1].offline_drop >= 128);
    b4_bus_online(1, true); blocked[1] = 0;
    /* MQTT断连的Router固定容量：溢出可观测；恢复后发送保留原时间/会话。 */
    MpFrame frame = {0}; frame.node = 2; frame.stream = MP_ECG; frame.rate = 250; frame.count = 100;
    mp_router_online(&gateway.router, false);
    for (unsigned i = 0; i < 1000; i++) { frame.seq = i + 1000; mp_router_put(&gateway.router, &frame); }
    assert(gateway.router.cn <= MP_CACHE_CAPACITY && gateway.router.ln <= MP_LIVE_CAPACITY && gateway.router.dropped > 900);
    json_bounds();
    printf("dualbus actual B wire: ECG=%u RESP=%u A_PPG=%u HR_valid=%u RR_valid=%u NIBP_valid=%u maxJSON=%u PASS\n",
        frames[MP_ECG], frames[MP_RESP], frames[MP_PPG], valid[MP_HR], valid[MP_RR], valid[MP_NIBP], max_json);
    CO_CANmodule_disable(a.co->CANmodule); CO_delete(a.co); b4_gateway_close(&gateway);
    if (canonical) fclose(canonical);
    return 0;
}
