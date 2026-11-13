/* 合成信号只检查软件回归与协议，不计入实物/临床验收。 */
#include "CANopen.h"
#include "OD.h"
#include "b_canopen_app.h"
#include "bio_v2.h"
#include <assert.h>
#include <math.h>
#include <stdio.h>
#ifdef B_TEMP_ENABLED
#include "b_temperature.h"
extern uint32_t TimeBase_GetMs(void);
BTempDiag g_b_temp;
static uint32_t last_feed = UINT32_MAX;
void BTemp_Init(void) { gy641_init(&g_b_temp.module); }
void BTemp_Task(uint32_t now) {
    now = TimeBase_GetMs();
    /* 只替代UART字节到达边界；30..36s停帧，真实解析器/过期与生产者不替换。 */
    if (now % 1000u || last_feed == now || (now >= 30000u && now < 36000u)) return;
    static const uint8_t frame[12] = {0xa4,3,7,7,0x62,0x0c,0xeb,0x0c,0x3f,0x0e,0x20,0x87};
    for (unsigned i = 0; i < sizeof(frame); i++) gy641_feed(&g_b_temp.module, frame[i], now);
    last_feed = now;
}
int BTemp_Get(uint32_t now, uint16_t *value) { return gy641_object(&g_b_temp.module, now, value); }
#endif
extern void b4_host_now(uint32_t tick);
extern void b4_host_wire(FILE *f);
extern void b4_host_block(int value);
extern void b4_host_receive(uint32_t id, uint8_t dlc, const uint8_t *data);
extern unsigned b4_host_sdo(CO_CANtx_t *out);
static void sync_time(uint32_t now) {
    uint64_t relative = 1792713600000ULL + now - 441763200000ULL;
    uint32_t ms = relative % 86400000u; uint16_t days = relative / 86400000u;
    uint8_t data[6]; CO_setUint32(data, ms); CO_setUint16(data + 4, days);
    b4_host_receive(0x100, 6, data);
}
static void sample(uint32_t now, uint32_t sequence) {
    double t = now / 1000.0, phase = fmod(t + .2, 1.0) - .5;
    int32_t ecg = (int32_t)(200000 + 10000 * exp(-.5 * pow(phase / .012, 2)) +
        1800 * exp(-.5 * pow((phase - .23) / .055, 2)) + 700 * exp(-.5 * pow((phase + .16) / .035, 2)));
    int32_t resp = (int32_t)(640000 + 1200 * sin(2 * 3.141592653589793 * .25 * t));
    BioV2_Process(ecg, resp, now, sequence, 0); BCan_Sample(now, sequence, 0);
}
int main(int argc, char **argv) {
    assert(argc == 2 || argc == 3); bool jitter = argc == 3;
    FILE *f = fopen(argv[1], "w"); assert(f); b4_host_wire(f);
    BioV2_Init(0);
#ifdef B_TEMP_ENABLED
    BTemp_Init();
#endif
    CanOpen_Init(); assert(!g_b_can.error);
    uint32_t seq = 0, next_sample = 0;
    for (uint32_t now = 0; now < 90000; now++) {
        b4_host_now(now); if (now % 10000 == 0) sync_time(now);
        if (now == next_sample) {
            sample(now, ++seq);
            next_sample += 4u + (jitter && seq % 900u == 0); /* 约278ppm，与历史非4ms间隔量级相符。 */
        }
        CanOpen_Task(now);
    }
    assert(g_bio_v2.samples == seq && g_bio_v2.discontinuities == 0);
    assert(g_bio_v2.hr_valid && g_bio_v2.rpm_valid);
    assert(g_b_can.sent_ecg == seq && g_b_can.sent_resp == seq / 5 && !g_b_can.overflow);
#ifdef B_TEMP_ENABLED
    assert(OD_RAM.x2120_vitals.TEMP == 3307 && g_b_temp.module.frames == 84);
    assert(OD_RAM.x2130_validity_generation.data_valid_flags == 31);
#else
    assert(OD_RAM.x2120_vitals.TEMP == 0 && !(OD_RAM.x2130_validity_generation.data_valid_flags & 16));
    assert(OD_RAM.x2130_validity_generation.data_valid_flags == 15);
#endif
    b4_host_wire(NULL); fclose(f);
    /* SDO仅响应新Node2地址，身份可读，应用快照拒绝远端写入。 */
    CO_CANtx_t reply; unsigned responses = b4_host_sdo(&reply);
    uint8_t request[8] = {0x40, 0x18, 0x10, 2, 0, 0, 0, 0};
    b4_host_receive(0x603, 8, request); CanOpen_Task(89999);
    assert(b4_host_sdo(&reply) == responses);
    b4_host_receive(0x602, 8, request); CanOpen_Task(89999);
    assert(b4_host_sdo(&reply) == responses + 1 && reply.data[0] == 0x43 && CO_getUint32(reply.data + 4) == 0x4d504d42u);
    request[0] = 0x2b; request[1] = 0x20; request[2] = 0x21; request[3] = 1;
    b4_host_receive(0x602, 8, request); CanOpen_Task(89999);
    assert(b4_host_sdo(&reply) == responses + 2 && reply.data[0] == 0x80 && CO_getUint32(reply.data + 4) == 0x06010002u);
    /* 模拟邮箱长时间不可用，采样仍250SPS推进；过期点必须丢弃且计数。 */
    b4_host_block(1);
    uint32_t before = seq;
    for (uint32_t now = 90000; now < 93000; now++) {
        b4_host_now(now); if (now % 4 == 0) sample(now, ++seq); CanOpen_Task(now);
    }
    b4_host_block(0); CanOpen_Task(93000);
    assert(g_bio_v2.samples == before + 750 && !g_bio_v2.discontinuities && g_b_can.expired > 600);
    /* TIME过期只能撤销CAN有效资格，不得停止或重置BIO。 */
    b4_host_now(120001); CanOpen_Task(120001);
    assert(OD_RAM.x2130_validity_generation.data_valid_flags == 0 && g_bio_v2.samples == before + 750);
    uint8_t nmt[2] = {130, 2}; b4_host_receive(0, 2, nmt); CanOpen_Task(120002);
    assert(g_b_can.comm_reset == 1 && g_bio_v2.samples == before + 750);
    nmt[0] = 129; b4_host_receive(0, 2, nmt); CanOpen_Task(120003);
    assert(g_b_can.app_reset_rejected == 1 && g_bio_v2.samples == before + 750);
    printf("B2 actual CANopenNode: %u ECG/%u RESP samples, jitter=%u, TIME expiry, congestion, NMT isolation PASS\n",
        before, before / 5, jitter);
    return 0;
}
