#ifndef MP_PHYSICAL_LINK_POLICY_H
#define MP_PHYSICAL_LINK_POLICY_H
#include <stdbool.h>
#include <stdint.h>
/* PCLK1 不假定相同；500k，采样点落在 80–88%，无 SILM/LBKM 位。 */
static inline bool physical_btr(uint32_t pclk,uint32_t *btr) {
    for(unsigned tq=16;tq>=8;tq--) {
        unsigned bs2=2,bs1=tq-3;
        if(pclk%(500000u*tq)==0 && (tq-bs2)*100u/tq>=80u && (tq-bs2)*100u/tq<=88u) {
            unsigned brp=pclk/(500000u*tq);
            if(brp && brp<=1024) { *btr=((bs2-1u)<<20)|((bs1-1u)<<16)|(brp-1u);return true; }
        }
    }
    return false;
}
typedef struct { bool waiting,fault;uint32_t started,acked,failed; } PhysicalTx;
enum { LINK_WAIT,LINK_START,LINK_ACK,LINK_FAULT };
static inline unsigned physical_tx_step(PhysicalTx *s,uint32_t now,bool mailbox_free,bool complete,bool txok,bool error,bool bus_off) {
    if(s->fault) return LINK_FAULT;
    /* 队首仅 TXOK 后才可出队；超时/Bus-off 锁止，需本地显式重初始化。 */
    if(bus_off || (s->waiting && (error || (uint32_t)(now-s->started)>=100u))) {s->fault=true;s->failed++;return LINK_FAULT;}
    if(s->waiting) {
        if(complete && txok) {s->waiting=false;s->acked++;return LINK_ACK;}
        return LINK_WAIT;
    }
    if(mailbox_free) {s->waiting=true;s->started=now;return LINK_START;}
    return LINK_WAIT;
}
#endif
