#ifndef MP_PHYSICAL_CAN_H
#define MP_PHYSICAL_CAN_H
#include "mp_stack.h"
/* 实板候选只持有 Gateway 协议实例；帧观测元数据不构造任何 A/B 采样。 */
typedef struct { uint32_t at[5],generation,session_generation; bool seen[5]; } PhysicalNode;
extern PhysicalNode physical_nodes[2];
extern bool physical_link_ready;
extern uint32_t physical_malformed;
void physical_receive(MpCanFrame *frame);
bool physical_fresh(unsigned node,unsigned pdo,uint32_t now);
void physical_invalidate(void);
int mp_bxcan_init(void);
#endif
