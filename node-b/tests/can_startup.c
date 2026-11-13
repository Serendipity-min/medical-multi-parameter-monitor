/* 真实B驱动＋SPL寄存器替身：邻板在初始化期间发帧，不接实板。 */
#include "CANopen.h"
#include "can_startup_spl_stub.h"
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

CAN_TypeDef startup_can;
static CO_CANmodule_t module;
static CO_CANrx_t rx[1];
static CO_CANtx_t tx[1];
static unsigned app_running, nvic_rx, callbacks, early_irqs;
extern void CO_CANinterrupt(CO_CANmodule_t *m);

static void deliver_level_irq(void) {
    if (!nvic_rx || !(CAN1->IER & CAN_IT_FMP0)) return;
    for (unsigned i=0; i<256 && (CAN1->RF0R & CAN_RF0R_FMP0); i++) {
        if (app_running) CO_CANinterrupt(&module);
        else early_irqs++;
    }
    if (CAN1->RF0R & CAN_RF0R_FMP0) {
        fprintf(stderr,"EARLY_RX_IRQ_STARVES_MAIN irq=%u app_running=%u\n",early_irqs,app_running);
        exit(23);
    }
}

void RCC_APB1PeriphClockCmd(uint32_t p,int enabled) { (void)p;(void)enabled; }
void RCC_AHB1PeriphClockCmd(uint32_t p,int enabled) { (void)p;(void)enabled; }
void GPIO_PinAFConfig(void *p,unsigned n,unsigned a) { (void)p;(void)n;(void)a; }
void GPIO_Init(void *p,GPIO_InitTypeDef *g) { (void)p;(void)g; }
unsigned CAN_Init(CAN_TypeDef *p,CAN_InitTypeDef *c) { (void)c;p->TSR=CAN_TSR_TME0;return 1; }
void CAN_FilterInit(CAN_FilterInitTypeDef *c) { (void)c;CAN1->RF0R=1;deliver_level_irq(); }
void CAN_ITConfig(CAN_TypeDef *p,uint32_t mask,int enabled) {
    if (enabled) p->IER|=mask; else p->IER&=~mask;
    deliver_level_irq();
}
void NVIC_Init(NVIC_InitTypeDef *c) {
    if (c->NVIC_IRQChannel==CAN1_RX0_IRQn) nvic_rx=c->NVIC_IRQChannelCmd;
    deliver_level_irq();
}
void CAN_Receive(CAN_TypeDef *p,unsigned fifo,CanRxMsg *frame) {
    (void)fifo;memset(frame,0,sizeof(*frame));frame->StdId=0x704;frame->DLC=1;frame->Data[0]=5;p->RF0R=0;
}
uint8_t CAN_Transmit(CAN_TypeDef *p,CanTxMsg *frame) { (void)p;(void)frame;return 0; }
static void received(void *object,void *message) {
    CO_CANrxMsg_t *frame=message;
    assert(object==&module && frame->ident==0x704 && frame->DLC==1 && frame->data[0]==5);
    callbacks++;
}

static void start_on_active_bus(void) {
    app_running=0;
    CO_CANmodule_disable(&module);
    CO_CANsetConfigurationMode(CAN1);
    assert(CO_CANmodule_init(&module,CAN1,rx,1,tx,1,500)==CO_ERROR_NO);
    assert(CO_CANrxBufferInit(&module,0,0x704,0x7ff,false,&module,received)==CO_ERROR_NO);
    app_running=1;
    CO_CANsetNormalMode(&module);
    deliver_level_irq();
    assert(module.CANnormal && !(CAN1->RF0R & CAN_RF0R_FMP0));
}

int main(void) {
    start_on_active_bus();
    assert(callbacks==1 && early_irqs==0);
    start_on_active_bus();
    assert(callbacks==2 && early_irqs==0);
    puts("ACTIVE_BUS_COLD_INIT_AND_COMM_REINIT_PASS pending_frames_delivered=2 early_irq=0");
    return 0;
}
