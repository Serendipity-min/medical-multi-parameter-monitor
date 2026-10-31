/* 实际双CAN驱动，寄存器仅Host RAM；不代替实板证据。 */
#include "../b4_bxcan.h"
#include "bxcan_mmio_shim.h"
#include <assert.h>
CAN_TypeDef b4_test_can[2];
uint32_t b4_test_clock=42000000u;
unsigned b4_test_transmit_calls,b4_test_clock_calls;
unsigned abc_mode[2],abc_pending[2],abc_filter_enabled[28],abc_irq_enabled[2],abc_filter_split,abc_clock_mask;
CanRxMsg abc_rx[2];
static unsigned consumed[2];
static uint32_t tick;
void CAN1_RX0_IRQHandler(void);
void CAN2_RX0_IRQHandler(void);
uint32_t b4_hw_time(void){return tick;}
void b4_gateway_link(B4Gateway *g,unsigned bus,bool up){g->segments[bus].link_up=up;}
void b4_gateway_receive(B4Gateway *g,unsigned bus,MpCanFrame *f,uint32_t at){
    (void)g;(void)at;assert(f->ident==0x701u+bus);consumed[bus]++;
}
int main(void){
    B4Gateway g={0};MpCanFrame hb={0};hb.ident=0x703;hb.dlc=1;
    assert(b4_hw_init()==0);
    assert(abc_mode[0]==CAN_Mode_Normal && abc_mode[1]==CAN_Mode_Normal);
    assert(abc_filter_enabled[0] && abc_filter_enabled[14] && abc_filter_split==14);
    assert(abc_irq_enabled[0] && abc_irq_enabled[1] && b4_test_clock_calls==1 && abc_clock_mask==3);
    for(unsigned b=0;b<2;b++){
        abc_rx[b].StdId=0x701+b;abc_rx[b].DLC=1;abc_pending[b]=1;
        if(b)CAN2_RX0_IRQHandler();else CAN1_RX0_IRQHandler();
    }
    b4_hw_poll(&g);assert(consumed[0]==1 && consumed[1]==1);
    assert(b4_bus_transmit(0,&hb) && b4_bus_transmit(1,&hb));
    CAN1->ESR=CAN_ESR_BOFF;tick++;b4_hw_poll(&g);
    assert(!g.segments[0].link_up && g.segments[1].link_up && b4_hw_diag[0].busoff==1);
    CAN2->TSR=CAN_TSR_TME0;assert(b4_bus_transmit(1,&hb));
    unsigned clocks=b4_test_clock_calls;b4_hw_stop();
    assert(b4_test_clock_calls==clocks && !b4_bus_transmit(0,&hb) && !b4_bus_transmit(1,&hb));
    assert((CAN1->MCR&CAN_MCR_NART) && (CAN2->MCR&CAN_MCR_NART));
    return 0;
}
