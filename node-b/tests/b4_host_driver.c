/* 仅Host边界替身：真实CANopenNode/B应用保持不变，帧保存为明确的合成夹具。 */
#include "CANopen.h"
#include <stdio.h>
#include <string.h>
static CO_CANmodule_t *active;
static FILE *wire;
static uint32_t now;
static int blocked;
static CO_CANtx_t last_sdo;
static unsigned sdo_count;
unsigned b4_host_sdo(CO_CANtx_t *out) { *out = last_sdo; return sdo_count; }
uint32_t TimeBase_GetMs(void) { return now; }
void b4_host_now(uint32_t tick) { now = tick; }
void b4_host_wire(FILE *file) { wire = file; }
void node_can_lock(void) {}
void node_can_unlock(void) {}
void CO_CANsetConfigurationMode(void *ptr) { (void)ptr; }
void CO_CANsetNormalMode(CO_CANmodule_t *m) { m->CANnormal = true; }
void CO_CANmodule_disable(CO_CANmodule_t *m) { if (m) m->CANnormal = false; }
CO_ReturnError_t CO_CANmodule_init(CO_CANmodule_t *m, void *ptr, CO_CANrx_t rx[], uint16_t nr,
                                 CO_CANtx_t tx[], uint16_t nt, uint16_t rate) {
    if (rate != 500) return CO_ERROR_ILLEGAL_BAUDRATE;
    memset(m, 0, sizeof(*m)); memset(rx, 0, nr * sizeof(*rx)); memset(tx, 0, nt * sizeof(*tx));
    m->CANptr = ptr; m->rxArray = rx; m->rxSize = nr; m->txArray = tx; m->txSize = nt; active = m;
    return CO_ERROR_NO;
}
CO_ReturnError_t CO_CANrxBufferInit(CO_CANmodule_t *m, uint16_t i, uint16_t id, uint16_t mask,
                                  bool_t rtr, void *obj, void (*callback)(void *, void *)) {
    if (i >= m->rxSize) return CO_ERROR_ILLEGAL_ARGUMENT;
    m->rxArray[i] = (CO_CANrx_t){id | (rtr ? 0x800 : 0), mask | 0x800, obj, callback}; return CO_ERROR_NO;
}
CO_CANtx_t *CO_CANtxBufferInit(CO_CANmodule_t *m, uint16_t i, uint16_t id, bool_t rtr, uint8_t dlc, bool_t sync) {
    if (i >= m->txSize || dlc > 8) return NULL;
    CO_CANtx_t *tx = &m->txArray[i]; memset(tx, 0, sizeof(*tx));
    tx->ident = id | (rtr ? 0x800 : 0); tx->DLC = dlc; tx->syncFlag = sync; return tx;
}
static void output(CO_CANtx_t *tx) {
    if (tx->ident == 0x582) { last_sdo = *tx; sdo_count++; }
    if (!wire) return;
    fprintf(wire, "%u %u %u", now, (unsigned)tx->ident, tx->DLC);
    for (unsigned i = 0; i < tx->DLC; i++) fprintf(wire, " %u", tx->data[i]);
    fputc('\n', wire);
}
CO_ReturnError_t CO_CANsend(CO_CANmodule_t *m, CO_CANtx_t *tx) {
    (void)m;
    if (tx->bufferFull) return CO_ERROR_TX_OVERFLOW;
    if (blocked) { tx->bufferFull = true; return CO_ERROR_NO; }
    output(tx); return CO_ERROR_NO;
}
void CO_CANclearPendingSyncPDOs(CO_CANmodule_t *m) { (void)m; }
void CO_CANmodule_process(CO_CANmodule_t *m) { (void)m; }
void CO_CANinterrupt(CO_CANmodule_t *m) { (void)m; }
void b4_host_block(int value) {
    blocked = value;
    if (!value && active) for (unsigned i = 0; i < active->txSize; i++) {
        if (active->txArray[i].bufferFull) { output(&active->txArray[i]); active->txArray[i].bufferFull = false; }
    }
}
void b4_host_receive(uint32_t id, uint8_t dlc, const uint8_t *data) {
    CO_CANrxMsg_t msg = {0}; msg.ident = id; msg.DLC = dlc; memcpy(msg.data, data, dlc);
    if (!active || !active->CANnormal) return;
    for (unsigned i = 0; i < active->rxSize; i++) {
        CO_CANrx_t *r = &active->rxArray[i];
        if (r->CANrx_callback && !((r->ident ^ id) & r->mask)) { r->CANrx_callback(r->object, &msg); return; }
    }
}
