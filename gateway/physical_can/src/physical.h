#ifndef MP_PHYSICAL_CAN_H
#define MP_PHYSICAL_CAN_H
#include "mp_stack.h"
/* 实板候选只持有 Gateway 协议实例；帧观测元数据不构造任何 A/B 采样。 */
typedef struct { uint32_t at[5],generation,session_generation; bool seen[5]; } PhysicalNode;
extern PhysicalNode physical_nodes[2];
extern bool physical_link_ready;
extern uint32_t physical_malformed;
void physical_receive(MpCanFrame *frame);
#if defined(CAN_BENCH_IRQ) || defined(MP_CAN_RX_IRQ)
/* 仅IRQ bench使用入队时刻，避免软件排队延迟被错误计为新的采集新鲜度。 */
void physical_receive_at(MpCanFrame *frame,uint32_t received_ms);
/* 仅协议时钟已到达的入队帧可交给单份RPDO缓冲，回绕按短区间差值判断。 */
bool physical_receive_due(uint32_t received_ms);
#endif
bool physical_fresh(unsigned node,unsigned pdo,uint32_t now);
void physical_invalidate(void);
uint64_t physical_now(const MpStack *stack);
void physical_sync_utc(MpStack *stack,uint64_t trusted_ms);
int mp_bxcan_init(void);
/* false 为首次启动，true 为本地显式重初始化；返回0仅表示 START 已入队。 */
int physical_gateway_open(MpStack *stack,bool restart);
#endif
