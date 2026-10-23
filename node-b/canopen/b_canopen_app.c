/* B2静态CANopenNode适配。采集/算法/双屏不受NMT重建通信栈影响。 */
#include "CANopen.h"
#include "OD.h"
#include "b_canopen_app.h"
#include "bio_v2.h"
#include "node_policy.h"
#include "ecg_units.h"
#include <limits.h>
#include <string.h>
#ifndef B4_HOST
#include "stm32f4xx.h"
#include "timer.h"
#define B_CAN_PTR CAN1
#else
extern uint32_t TimeBase_GetMs(void);
#define B_CAN_PTR ((void *)1)
#endif

typedef struct { int32_t ecg, resp; uint32_t tick, sequence; uint8_t resp_due, flags; } Sample;
static Sample queue[128];
static unsigned head, tail, count;
static CO_t *co;
static NodeClock clock_anchor;
static uint32_t generation, last_task, last_flags, last_sequence;
static uint8_t running, first, have_sequence;
BCanDiag g_b_can;
extern void CO_CANinterrupt(CO_CANmodule_t *module);

static void time_received(void *object) {
    CO_TIME_t *time = (CO_TIME_t *)object;
    node_clock_set(&clock_anchor, CO_getUint32(time->timeStamp), CO_getUint16(time->timeStamp + 4), TimeBase_GetMs());
}

static void stack_init(void) {
    uint32_t error = 0;
    running = 0; head = tail = count = 0; first = 1; have_sequence = 0;
    memset(&clock_anchor, 0, sizeof(clock_anchor));
    if (!co) { g_b_can.error = 1; return; }
    CO_CANmodule_disable(co->CANmodule);
    CO_ReturnError_t rc = CO_CANinit(co, B_CAN_PTR, B_CAN_BITRATE);
    if (rc == CO_ERROR_NO) rc = CO_CANopenInit(co, NULL, NULL, OD, OD_ENTRY_H1001,
        CO_NMT_STARTUP_TO_OPERATIONAL, 500, 500, 500, false, B_CAN_NODE_ID, &error);
    if (rc == CO_ERROR_NO) rc = CO_CANopenInitPDO(co, co->em, OD, B_CAN_NODE_ID, &error);
    if (rc != CO_ERROR_NO) { g_b_can.error = (uint32_t)(-(int32_t)rc); return; }
    CO_TIME_initCallbackPre(co->TIME, co->TIME, time_received);
    OD_RAM.x2130_validity_generation.boot_generation = ++generation;
    OD_RAM.x2130_validity_generation.data_valid_flags = 0;
    OD_RAM.x2100_epoch_tick.epoch = 0;
    last_flags = 0; running = 1; g_b_can.error = 0;
    CO_CANsetNormalMode(co->CANmodule);
}

void CanOpen_Init(void) {
    memset(&g_b_can, 0, sizeof(g_b_can));
    co = CO_new(NULL, NULL); /* CO_USE_GLOBALS，固定内存，无动态分配。 */
    stack_init();
}

void BCan_Sample(uint32_t tick, uint32_t sequence, uint8_t flags) {
    g_b_can.offered++;
    if (!running) return;
    /* 源缺口只使通信资格失效并可观测，绝不清除/重置已验收的算法。 */
    if (have_sequence && sequence != last_sequence + 1u) g_b_can.discontinuities++;
    last_sequence = sequence; have_sequence = 1;
    if (count == 128u) { g_b_can.overflow++; return; }
    Sample *s = &queue[head];
    /* BIO显示量=h*1e6/2^23；按已核验CH2增益4和名义2.42V转微伏，非绝对标定。
     * RESP只保留显示相对量，百万分之一单位，明确不能解释成欧姆。 */
    s->ecg = b4_ecg_display_to_uv(BioV2_EcgWave());
    int64_t resp = (int64_t)BioV2_RespWave() * 1000;
    s->resp = resp > INT32_MAX ? INT32_MAX : resp < INT32_MIN ? INT32_MIN : (int32_t)resp;
    s->tick = tick; s->sequence = sequence; s->flags = flags;
    s->resp_due = (sequence % 5u) == 0u; /* 250SPS真实点抽取至50Hz，不插值也不改ADC。 */
    head = (head + 1u) % 128u; count++; g_b_can.enqueued++;
    if (count > g_b_can.high_water) g_b_can.high_water = count;
}

static uint8_t produce(uint32_t now) {
    uint32_t epoch, anchor;
    NodeClock clock;
    node_can_lock(); clock = clock_anchor; node_can_unlock();
    node_clock_read(&clock, now, &epoch, &anchor);
    OD_RAM.x2100_epoch_tick.epoch = epoch; OD_RAM.x2100_epoch_tick.tick = anchor;
    uint16_t hr = 0, rr = 0;
    uint8_t hr_ok = BioV2_GetHeart(&hr, now), rr_ok = BioV2_GetResp(&rr, now);
    OD_RAM.x2120_vitals.HR = hr_ok ? (uint16_t)(hr * 100u) : 0;
    OD_RAM.x2120_vitals.RR = rr_ok ? (uint16_t)(rr * 100u) : 0;
    OD_RAM.x2120_vitals.TEMP = 0; /* 尚无温度采集接口：保持无效，不伪造36.5。 */
    OD_RAM.x2120_vitals.reserved = 0;
    uint32_t flags = 0;
    if (epoch && g_bio_v2.samples && (uint32_t)(now - g_bio_v2.last_sample_ms) <= 100u) {
        /* CAN有效波形采用本通道算法资格，噪声/无周期仍传原值但标INVALID。 */
        if (hr_ok && !g_bio_v2.hr_reason) flags |= 1u;
        if (rr_ok && !g_bio_v2.rpm_reason) flags |= 2u;
        if (hr_ok) flags |= 4u;
        if (rr_ok) flags |= 8u;
    }
    OD_RAM.x2130_validity_generation.data_valid_flags = flags;
    if (flags != last_flags) { last_flags = flags; CO_TPDOsendRequest(&co->TPDO[4]); }
    /* 每轮最多丢弃8个过期点，避免通信积压反过来饿死采集/屏幕。 */
    for (unsigned budget = 0; count && budget < 8u; budget++) {
        Sample *s = &queue[tail];
        if ((uint32_t)(now - s->tick) > 100u || s->flags || !epoch) {
            tail = (tail + 1u) % 128u; count--; g_b_can.expired++; continue;
        }
        /* 单PDO缓冲尚未实际发走时保留队首，禁止覆盖尚在邮箱等待的旧点。 */
        if (co->TPDO[0].CANtxBuff->bufferFull || (s->resp_due && co->TPDO[1].CANtxBuff->bufferFull)) return 0;
        OD_RAM.x2110_ecg_waveform.ecg_uV = s->ecg;
        OD_RAM.x2110_ecg_waveform.sample_tick = s->tick;
        CO_TPDOsendRequest(&co->TPDO[0]); g_b_can.sent_ecg++;
        uint8_t request = 1;
        if (s->resp_due) {
            OD_RAM.x2111_resp_waveform.resp_relative = s->resp;
            OD_RAM.x2111_resp_waveform.sample_tick = s->tick;
            CO_TPDOsendRequest(&co->TPDO[1]); g_b_can.sent_resp++; request |= 2;
        }
        tail = (tail + 1u) % 128u; count--; return request;
    }
    return 0;
}

void CanOpen_Task(uint32_t now) {
    if (!running) return;
    uint32_t elapsed = first ? 0u : now - last_task;
    first = 0; last_task = now;
    for (unsigned budget = 0; budget < 8u; budget++) {
        uint32_t diff = budget ? 0u : elapsed > 1000u ? 1000000u : elapsed * 1000u;
        CO_NMT_reset_cmd_t reset = CO_process(co, false, diff, NULL);
        if (reset == CO_RESET_COMM) { g_b_can.comm_reset++; stack_init(); return; }
        if (reset != CO_RESET_NOT) {
            /* 远端NMT不得重启MCU，更不能让屏幕/ADC/算法复位。 */
            g_b_can.app_reset_rejected++; running = 0;
            CO_CANmodule_disable(co->CANmodule); return;
        }
        uint8_t requests = produce(now);
        bool_t configured[2] = {co->TPDO[0].PDO_common.valid, co->TPDO[1].PDO_common.valid};
        for (unsigned i = 0; i < 2; i++) if (!(requests & (1u << i))) co->TPDO[i].PDO_common.valid = false;
        bool_t sync = CO_process_SYNC(co, diff, NULL);
        CO_process_RPDO(co, sync, diff, NULL); CO_process_TPDO(co, sync, diff, NULL);
        for (unsigned i = 0; i < 2; i++) co->TPDO[i].PDO_common.valid = configured[i];
        if (!count) break;
    }
}

void BCan_Interrupt(void) { if (running && co) CO_CANinterrupt(co->CANmodule); }
#ifndef B4_HOST
void CAN1_RX0_IRQHandler(void) { BCan_Interrupt(); }
void CAN1_TX_IRQHandler(void) { BCan_Interrupt(); }
void CAN1_SCE_IRQHandler(void) { BCan_Interrupt(); }
#endif
