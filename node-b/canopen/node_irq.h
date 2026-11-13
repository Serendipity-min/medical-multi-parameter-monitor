#ifndef NODE_CAN_IRQ_H
#define NODE_CAN_IRQ_H
#include <stdint.h>
/* 共用嵌套计数，跨 CAN/EMCY/OD 锁嵌套时仅最外层恢复调用前 PRIMASK。 */
typedef struct { uint32_t depth, saved; } NodeCanIrq;
static inline void node_irq_lock(NodeCanIrq *state) {
    uint32_t previous=__get_PRIMASK(); __disable_irq();
    if (state->depth++ == 0u) state->saved=previous;
}
static inline void node_irq_unlock(NodeCanIrq *state) {
    if (state->depth && --state->depth == 0u) __set_PRIMASK(state->saved);
}
#endif
