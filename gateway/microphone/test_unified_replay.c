/* 真实bxCAN队列、CANopen/RPDO与Gateway；只有MMIO为RAM替身。 */
#include "../dual_can/b4_bxcan.h"
#include "../dual_can/tests/bxcan_mmio_shim.h"
#include <stdio.h>
#include <stdlib.h>
CAN_TypeDef b4_test_can[2];
uint32_t b4_test_clock=8000000u;
unsigned b4_test_transmit_calls,b4_test_clock_calls;
unsigned abc_mode[2],abc_pending[2],abc_filter_enabled[28],abc_irq_enabled[2],abc_filter_split,abc_clock_mask;
CanRxMsg abc_rx[2];unsigned final_can_mask;
static uint32_t tick;static unsigned checks;
volatile uint32_t g_uptime_ms;
uint64_t gateway_epoch_milliseconds(void){return 1800000000000ULL+tick;}
#define CHECK(x) do{if(!(x)){fprintf(stderr,"FAIL line=%d\n",__LINE__);exit(3);}checks++;}while(0)
uint32_t b4_hw_time(void){return tick;}
int main(void){
    B4Gateway g;CHECK(b4_gateway_init(&g)==0);CHECK(b4_hw_init()==0);
    for(unsigned b=0;b<2;b++){b4_gateway_link(&g,b,false);CHECK(abc_mode[b]==CAN_Mode_Silent && !abc_irq_enabled[b]);}
    CHECK(b4_hw_set_replay(true));
    for(unsigned n=0;n<1000;n++){tick+=5;g_uptime_ms=tick;b4_gateway_tick(&g,tick);b4_hw_poll(&g);}
    for(unsigned b=0;b<2;b++){
        CHECK(b4_replayed[b]==2000 && !b4_hw_diag[b].received && !b4_hw_diag[b].overflow && b4_hw_diag[b].high_water==2);
        CHECK(!g.segments[b].link_up && !b4_gateway_online(&g,b+1));
        CHECK(mp_od_read(&g.segments[b].od,0x3130+b*0x100,1)==0x80000000u);
    }
    CHECK(!b4_test_transmit_calls);
    for(unsigned k=MP_ECG;k<=MP_TEMP;k++)CHECK(!g.router.enqueued[k]);
    CHECK(b4_hw_set_replay(false));tick+=5;b4_hw_poll(&g);CHECK(b4_replayed[0]==2000);
    final_can_mask=2;CHECK(!b4_hw_set_replay(true));final_can_mask=0;
    b4_hw_stop();CHECK(!b4_hw_set_replay(true));b4_gateway_close(&g);
    printf("C_ONLY_CAN_SOFTWARE_REPLAY_PASS checks=%u frames=4000 real_RX=0 real_TX=0 measurement_frames=0 hardware=NOT_RUN\n",checks);
    return 0;
}
