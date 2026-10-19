#include "physical.h"

/* 仅启动及本地 G 调用：先让 bxCAN 清空旧队列并就绪，再单次排入广播 START。
 * 成功仅代表入队；物理 ACK 仍由驱动 TXOK 判定，网络重连不调用此入口。 */
int physical_gateway_open(MpStack *s,bool restart) {
    int rc=restart?mp_stack_restart(s,3):mp_stack_init(s,0);
    if(rc) return rc;
    if(!mp_bxcan_init()) {physical_invalidate();return -10;}
    MpNode *g=&s->nodes[2];
    /* 共享驱动离线丢弃时也可能返回 NO，故必须先核对物理就绪和端口状态。 */
    if(!physical_link_ready || !g->co || !g->port.enabled || !g->co->CANmodule->CANnormal) {
        physical_invalidate();return -11;
    }
    if(CO_NMT_sendCommand(g->co->NMT,CO_NMT_ENTER_OPERATIONAL,0)!=CO_ERROR_NO) {
        physical_invalidate();return -12;
    }
    return 0;
}
