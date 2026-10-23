#ifndef NODE_CAN_POLICY_H
#define NODE_CAN_POLICY_H
#include <stdint.h>
/* 本接口的 UTC 只能来自已同步 Gateway 的 CANopen TIME，不能读取屏幕软 RTC。 */
typedef struct { uint32_t epoch, anchor, received; uint8_t valid; } NodeClock;
static inline void node_clock_set(NodeClock *c,uint32_t ms,uint16_t days,uint32_t now) {
    uint64_t epoch=441763200ULL+(uint64_t)days*86400u+ms/1000u;
    c->valid=(ms<86400000u && epoch>=1577836800u && epoch<=4102444800ULL);
    c->epoch=c->valid?(uint32_t)epoch:0u;c->anchor=now-ms%1000u;c->received=now;
}
static inline void node_clock_read(const NodeClock *c,uint32_t now,uint32_t *epoch,uint32_t *anchor) {
    /* unsigned 差处理 32 位 tick 回绕，30s 未授时即撤销可信身份。 */
    uint32_t elapsed=now-c->anchor;
    if (!c->valid || (uint32_t)(now-c->received)>30000u) { *epoch=0;*anchor=now;return; }
    *epoch=c->epoch+elapsed/1000u;*anchor=now-elapsed%1000u;
}
/* 20ms 网格为显式线性重采样；每个输出必须由两点真实接收时间夹住，禁止外推。 */
typedef struct { int32_t left,right; uint32_t lt,rt,next,inputs,outputs,gaps; uint8_t have,pending; } NodeResampler;
static inline void node_wave_input(NodeResampler *s,int32_t value,uint32_t tick) {
    s->inputs++;
    if (!s->have || (uint32_t)(tick-s->lt)>100u || tick==s->lt) {
        if(s->have) s->gaps++;
        s->left=value;s->lt=tick;s->next=tick+20u;s->have=1;s->pending=0;return;
    }
    s->right=value;s->rt=tick;s->pending=1;
}
static inline uint8_t node_wave_output(NodeResampler *s,int32_t *value,uint32_t *tick) {
    if (!s->pending) return 0;
    uint32_t span=s->rt-s->lt, offset=s->next-s->lt;
    if (offset>span) { s->left=s->right;s->lt=s->rt;s->pending=0;return 0; }
    *value=s->left+(int32_t)(((int64_t)s->right-s->left)*offset/span);
    *tick=s->next;s->next+=20u;s->outputs++;return 1;
}
#endif
