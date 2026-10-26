/* 真实coreMQTT等待 + 真实bxCAN ISR/主循环；字节I/O和寄存器为Host夹具，不代表ESP实物时序。 */
#include "../mqtt/tests/mocks/mock_esp.h"
#include "../dual_can/b4_bxcan.h"
#include "../dual_can/tests/bxcan_mmio_shim.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>
CAN_TypeDef b4_test_can[2];uint32_t b4_test_clock=8000000;
unsigned b4_test_transmit_calls,b4_test_clock_calls,b5_rx_pending,b5_mode[2];
CanRxMsg b5_rx_message;
static B4Gateway gateway;
static uint32_t produced;static int stall;
extern void (*mock_poll_callback)(void);
void CAN2_RX0_IRQHandler(void);
uint32_t b4_hw_time(void){return g_uptime_ms;}
int b5_network_stopped(void){return 0;}
static void inject(unsigned id,uint32_t a,uint32_t b,unsigned dlc) {
    b5_rx_message=(CanRxMsg){0};b5_rx_message.StdId=id;b5_rx_message.DLC=dlc;
    memcpy(b5_rx_message.Data,&a,4);memcpy(b5_rx_message.Data+4,&b,4);
    b5_rx_pending=1;CAN2_RX0_IRQHandler();
}
static void service(void) {
    while(produced<g_uptime_ms) {
        produced++;
        if(produced%500==0)inject(0x702,5,0,1);
        if(produced%1000==0) {
            inject(0x682,5,1,8);inject(0x482,1800000000+produced/1000,produced,8);
            inject(0x382,6000,0,8);
        }
        if(produced%4==0)inject(0x182,123,produced,8);
        if(produced%20==0)inject(0x282,456,produced,8);
    }
    if(!stall) {
        CAN2->TSR=CAN_TSR_TME0|CAN_TSR_TME1|CAN_TSR_TME2;
        b4_gateway_tick(&gateway,g_uptime_ms);b4_hw_poll(&gateway);
    }
}
int main(void) {
    mock_connect();assert(!b4_gateway_init(&gateway) && !b4_hw_init());
    assert(b5_mode[0]==CAN_Mode_Silent && b5_mode[1]==CAN_Mode_Normal);
    assert(!(CAN2->MCR&CAN_MCR_NART));
    MpCanFrame f={0};f.ident=0x703;f.dlc=1;assert(!b4_bus_transmit(0,&f));
    b4_gateway_link(&gateway,0,false);produced=g_uptime_ms;
    b4_gateway_sync(&gateway,1800000000,g_uptime_ms);gateway.session=1;
    mock_poll_callback=service;mock_delay_ms=700;
    MpFrame scalar=mock_frame(MP_HR,0,false);
    assert(gateway_mqtt_publish(&scalar));
    mock_ack_mode=ACK_NONE;assert(!gateway_mqtt_publish(&scalar));
    assert(b4_hw_diag[1].received>1700 && b4_hw_diag[1].overflow==0 && b4_hw_diag[1].high_water<10);
    printf("COOPERATIVE_AT_5S RX=%lu HIGH_WATER=%lu OVERFLOW=0\n",(unsigned long)b4_hw_diag[1].received,(unsigned long)b4_hw_diag[1].high_water);
    /* 反例：同样的ISR输入，主循环被完全饿死350ms应真实溢出，不能把总是零当测试。 */
    stall=1;for(unsigned i=0;i<350;i++){g_uptime_ms++;service();}
    assert(b4_hw_diag[1].overflow>0);b4_hw_stop();assert(!b4_bus_transmit(1,&f));
    printf("STARVATION_NEGATIVE_OVERFLOW=%lu STOP_BLOCKS_TX\n",(unsigned long)b4_hw_diag[1].overflow);
    b4_gateway_close(&gateway);return 0;
}
