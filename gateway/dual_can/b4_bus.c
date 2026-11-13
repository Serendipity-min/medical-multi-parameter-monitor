/* 两个独立有界总线；驱动边界在主循环交付接收帧，协议回调不在硬件ISR中执行。 */
#include "b4_bus.h"
#include <string.h>
typedef struct { MpCanFrame frames[128]; unsigned head, tail, count; bool online; } Bus;
static Bus buses[2];
static B4Port *ports[2][3];
 B4BusDiag b4_bus_diag[2];
void b4_bus_reset(void) {
    memset(buses, 0, sizeof(buses)); memset(ports, 0, sizeof(ports)); memset(b4_bus_diag, 0, sizeof(b4_bus_diag));
    buses[0].online = buses[1].online = true;
}
void b4_bus_online(unsigned bus, bool online) {
    if (bus > 1) return;
    buses[bus].online = online;
    if (!online) {
        b4_bus_diag[bus].offline_drop += buses[bus].count;
        buses[bus].count = buses[bus].head = buses[bus].tail = 0;
    }
}
void b4_bus_receive(unsigned bus, MpCanFrame *frame) {
    if (bus > 1 || !buses[bus].online || frame->dlc > 8 || frame->ident > 0x7ff) return;
    for (unsigned node = 0; node < 3; node++) {
        B4Port *p = ports[bus][node];
        if (!p || !p->enabled || !p->module->CANnormal) continue;
        for (unsigned i = 0; i < p->module->rxSize; i++) {
            CO_CANrx_t *r = &p->module->rxArray[i];
            if (r->CANrx_callback && !((r->ident ^ frame->ident) & r->mask)) {
                r->CANrx_callback(r->object, frame); break;
            }
        }
    }
}
/* Host覆盖此边界；生产MMIO驱动提供强符号。无接口时返回忙，禁止伪造发送成功。 */
__attribute__((weak)) int b4_bus_transmit(unsigned bus, const MpCanFrame *frame) {
    (void)bus; (void)frame; return 0;
}
void b4_bus_poll(void) {
    for (unsigned bus = 0; bus < 2; bus++) {
        Bus *b = &buses[bus];
        /* 每路独立预算，CAN2阻塞不能饿死CAN1；没有跨路重投递。 */
        for (unsigned budget = 0; b->online && b->count && budget < 16; budget++) {
            if (!b4_bus_transmit(bus, &b->frames[b->tail])) break;
            b->tail = (b->tail + 1) % 128; b->count--; b4_bus_diag[bus].sent++;
        }
    }
}
void CO_CANsetConfigurationMode(void *ptr) { (void)ptr; }
void CO_CANsetNormalMode(CO_CANmodule_t *m) { m->CANnormal = true; }
CO_ReturnError_t CO_CANmodule_init(CO_CANmodule_t *m, void *ptr, CO_CANrx_t rx[], uint16_t nr,
                                 CO_CANtx_t tx[], uint16_t nt, uint16_t rate) {
    B4Port *p = ptr;
    if (!m || !p || !rx || !tx || rate != 500 || p->node < 1 || p->node > 3 || p->bus > 1)
        return CO_ERROR_ILLEGAL_ARGUMENT;
    if (ports[p->bus][p->node - 1] && ports[p->bus][p->node - 1] != p) return CO_ERROR_ILLEGAL_ARGUMENT;
    memset(m, 0, sizeof(*m)); memset(rx, 0, nr * sizeof(*rx)); memset(tx, 0, nt * sizeof(*tx));
    m->CANptr = p; m->rxArray = rx; m->rxSize = nr; m->txArray = tx; m->txSize = nt;
    p->module = m; ports[p->bus][p->node - 1] = p; return CO_ERROR_NO;
}
void CO_CANmodule_disable(CO_CANmodule_t *m) {
    if (!m) return;
    m->CANnormal = false;
    B4Port *p = m->CANptr;
    if (p && p->bus < 2 && p->node >= 1 && p->node <= 3 && ports[p->bus][p->node - 1] == p)
        ports[p->bus][p->node - 1] = NULL;
}
CO_ReturnError_t CO_CANrxBufferInit(CO_CANmodule_t *m, uint16_t i, uint16_t id, uint16_t mask,
                                  bool_t rtr, void *object, void (*callback)(void *, void *)) {
    if (!m || i >= m->rxSize || !callback) return CO_ERROR_ILLEGAL_ARGUMENT;
    m->rxArray[i] = (CO_CANrx_t){id | (rtr ? 0x800 : 0), mask | 0x800, object, callback}; return CO_ERROR_NO;
}
CO_CANtx_t *CO_CANtxBufferInit(CO_CANmodule_t *m, uint16_t i, uint16_t id, bool_t rtr, uint8_t dlc, bool_t sync) {
    if (!m || i >= m->txSize || dlc > 8) return NULL;
    CO_CANtx_t *tx = &m->txArray[i]; memset(tx, 0, sizeof(*tx));
    tx->ident = id | (rtr ? 0x800 : 0); tx->DLC = dlc; tx->syncFlag = sync; return tx;
}
CO_ReturnError_t CO_CANsend(CO_CANmodule_t *m, CO_CANtx_t *tx) {
    B4Port *p = m->CANptr;
    if (!p || !p->enabled || p->bus > 1 || tx->DLC > 8 || tx->ident > 0x7ff) return CO_ERROR_ILLEGAL_ARGUMENT;
    Bus *b = &buses[p->bus]; B4BusDiag *d = &b4_bus_diag[p->bus];
    if (!b->online) { d->offline_drop++; return CO_ERROR_TX_OVERFLOW; }
    if (b->count == 128) { d->overflow++; m->CANerrorStatus |= CO_CAN_ERRTX_OVERFLOW; return CO_ERROR_TX_OVERFLOW; }
    MpCanFrame *f = &b->frames[b->head]; f->ident = tx->ident; f->dlc = tx->DLC;
    memcpy(f->data, tx->data, 8); b->head = (b->head + 1) % 128; b->count++; d->queued++;
    if (b->count > d->high_water) d->high_water = b->count;
    return CO_ERROR_NO;
}
void CO_CANclearPendingSyncPDOs(CO_CANmodule_t *m) { (void)m; }
void CO_CANmodule_process(CO_CANmodule_t *m) {
    B4Port *p = m->CANptr;
    if (p && !buses[p->bus].online) m->CANerrorStatus |= CO_CAN_ERRTX_BUS_OFF;
    else m->CANerrorStatus &= (uint16_t)~CO_CAN_ERRTX_BUS_OFF;
}
