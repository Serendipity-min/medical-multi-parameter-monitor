/* 编译真实b4_bxcan.c；只用RAM寄存器替身验证配置、完成资格及STOP，不代表实板验收。 */
#include "../b4_bxcan.h"
#include "../b4_capture.h"
#include "bxcan_mmio_shim.h"
#include <assert.h>
#include <string.h>
CAN_TypeDef b4_test_can[2];
uint32_t b4_test_clock=42000000u;
unsigned b4_test_transmit_calls,b4_test_clock_calls;
static unsigned acked,failed;
static uint32_t tick;
uint32_t b4_hw_time(void) { return tick; }
int b4_capture_emit(unsigned kind,unsigned bus,unsigned id,unsigned dlc,
                    const uint8_t *data,uint32_t at,uint32_t flags) {
    (void)bus;(void)id;(void)dlc;(void)data;(void)at;(void)flags;
    acked+=kind==B4_CAP_TX_ACK; failed+=kind==B4_CAP_TX_FAIL;return 1;
}
void b4_gateway_link(B4Gateway *g,unsigned bus,bool online) { g->segments[bus].link_up=online; }
void b4_gateway_receive(B4Gateway *g,unsigned bus,MpCanFrame *f,uint32_t at) {
    (void)g;(void)bus;(void)f;(void)at;
}
int main(void) {
    B4Gateway g={0};MpCanFrame heartbeat={0};heartbeat.ident=0x703;heartbeat.dlc=1;heartbeat.data[0]=5;
    /* 未初始化便STOP不能触碰未开时钟的寄存器；随后显式初始化才能开始软件目标。 */
    b4_hw_stop();assert(!b4_test_clock_calls && !b4_test_can[0].TSR);
    assert(b4_hw_init()==0);assert(!(CAN1->MCR&CAN_MCR_NART) && !(CAN2->MCR&CAN_MCR_NART));
    assert(b4_bus_transmit(1,&heartbeat));
    /* NART=0时首次仲裁失败不完成请求；真正ACK后才允许记为发送完成。 */
    CAN2->TSR=4u;tick++;b4_hw_poll(&g);assert(!acked && !failed);
    CAN2->TSR=3u|CAN_TSR_TME0;tick++;b4_hw_poll(&g);
    assert(acked==1 && !failed && b4_hw_diag[1].tx_acked==1);
    /* 原0x1c000005仍须如实记录失败，不能靠解码器忽略ALST来制造PASS。 */
    CAN2->TSR=CAN_TSR_TME0;assert(b4_bus_transmit(1,&heartbeat));
    CAN2->TSR=0x1c000005u;tick++;b4_hw_poll(&g);assert(failed==1 && b4_hw_diag[1].tx_failed==1);
    CAN2->TSR=CAN_TSR_TME0;assert(b4_bus_transmit(1,&heartbeat));
    CAN2->TSR=0x1c000009u;tick++;b4_hw_poll(&g);assert(failed==2 && b4_hw_diag[1].tx_failed==2);
    unsigned clocks=b4_test_clock_calls, sent=b4_test_transmit_calls;
    CAN1->TSR=CAN2->TSR=0;b4_hw_stop();
    const uint32_t aborts=CAN_TSR_ABRQ0|CAN_TSR_ABRQ1|CAN_TSR_ABRQ2;
    assert(CAN1->TSR==aborts && CAN2->TSR==aborts);
    assert((CAN1->MCR&CAN_MCR_NART) && (CAN2->MCR&CAN_MCR_NART));
    assert(!(CAN1->MCR&~CAN_MCR_NART) && !(CAN2->MCR&~CAN_MCR_NART));
    assert(!b4_bus_transmit(1,&heartbeat));b4_hw_poll(&g);b4_hw_stop();
    assert(b4_test_clock_calls==clocks && b4_test_transmit_calls==sent);
    assert(!g.segments[0].link_up);return 0;
}
