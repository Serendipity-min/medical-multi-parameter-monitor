#ifndef MP_NETWORK_PEER_TX_H
#define MP_NETWORK_PEER_TX_H
#include <stdbool.h>
#include <stdint.h>

enum { PEER_TX_WAIT,PEER_TX_START,PEER_TX_ACK,PEER_TX_NO_ACK,PEER_TX_DISCARD,PEER_TX_FAULT };
typedef struct {
    bool waiting,peer_wait,fault,retry_arbitration;
    uint32_t started,peer_sequence;
} PeerTx;

/* 仅完整联网IRQ目标使用单次发送；ACK缺失暂停TX而不停止正常模式RX。
 * 100ms预算不延长；未知错误、卡邮箱和Bus-off仍锁止，旧bench策略不变。 */
static inline unsigned peer_tx_step(PeerTx *s,uint32_t now,uint32_t sequence,
                                    bool free,bool complete,bool txok,bool error,
                                    bool arbitration_lost,unsigned lec,bool bus_off) {
    if(s->fault || bus_off) {s->fault=true;return PEER_TX_FAULT;}
    if(s->peer_wait)return PEER_TX_DISCARD;
    if(s->waiting) {
        if(complete && error && !txok && lec==3u) {
            s->waiting=false;s->peer_wait=true;s->peer_sequence=sequence;
            return PEER_TX_NO_ACK;
        }
        if(error || (uint32_t)(now-s->started)>=100u) {s->fault=true;return PEER_TX_FAULT;}
        if(complete && txok) {s->waiting=false;s->retry_arbitration=false;return PEER_TX_ACK;}
        if(complete && arbitration_lost) {
            /* NART下仲裁失败要由软件重试同一队首，不能伪计TXOK或重启预算。 */
            s->waiting=false;s->retry_arbitration=true;
        }
        return PEER_TX_WAIT;
    }
    if(s->retry_arbitration && (uint32_t)(now-s->started)>=100u) {s->fault=true;return PEER_TX_FAULT;}
    if(free) {
        if(!s->retry_arbitration)s->started=now;
        s->waiting=true;return PEER_TX_START;
    }
    return PEER_TX_WAIT;
}

/* 只能由本次ACK错误之后新收到的合法A心跳/Boot-up恢复，旧就绪位不作依据。 */
static inline bool peer_tx_resume(PeerTx *s,uint32_t sequence) {
    if(s->fault || !s->peer_wait || sequence==s->peer_sequence)return false;
    s->peer_wait=false;s->waiting=false;s->retry_arbitration=false;
    s->peer_sequence=sequence;return true;
}
#endif
