/* 独立正常 CAN1 目标，不替换/编译原 bxcan_loopback.c。仅本机 ARM 构建，未烧录。 */
#include "physical.h"
#include "link_policy.h"
#include "gateway_platform.h"
#include "stm32f4xx.h"
#include "stm32f4xx_rcc.h"
#include "stm32f4xx_gpio.h"
#include <string.h>
#ifdef CAN_ONLY_BENCH
#include "bench.h"
#endif
static PhysicalTx tx;
uint32_t physical_rx_overflow,physical_bad_frame;
static int wait_init(bool enabled) {
    uint32_t started=g_uptime_ms;
    /* Tick 和 CPU 预算双重有界，初始化故障不能锁死网络/诊断主循环。 */
    for(unsigned i=0;i<1000000u;i++) {
        if(((CAN1->MSR&CAN_MSR_INAK)!=0)==enabled) return 1;
        if((uint32_t)(g_uptime_ms-started)>=100u) break;
    }
    return 0;
}
int mp_bxcan_init(void) {
    physical_invalidate();memset(&tx,0,sizeof(tx));
    RCC_ClocksTypeDef clocks;RCC_GetClocksFreq(&clocks);uint32_t btr;
    if(!physical_btr(clocks.PCLK1_Frequency,&btr)) return 0;
    RCC_AHB1PeriphClockCmd(RCC_AHB1Periph_GPIOA,ENABLE);RCC_APB1PeriphClockCmd(RCC_APB1Periph_CAN1,ENABLE);
    GPIO_InitTypeDef gpio;GPIO_StructInit(&gpio);gpio.GPIO_Pin=GPIO_Pin_11|GPIO_Pin_12;
    gpio.GPIO_Mode=GPIO_Mode_AF;gpio.GPIO_OType=GPIO_OType_PP;gpio.GPIO_Speed=GPIO_Speed_50MHz;gpio.GPIO_PuPd=GPIO_PuPd_UP;
    GPIO_PinAFConfig(GPIOA,GPIO_PinSource11,GPIO_AF_CAN1);GPIO_PinAFConfig(GPIOA,GPIO_PinSource12,GPIO_AF_CAN1);GPIO_Init(GPIOA,&gpio);
    CAN1->MCR=CAN_MCR_INRQ|CAN_MCR_ABOM;
    if(!wait_init(true)) return 0;
    CAN1->BTR=btr; /* 正常模式：不得置 SILM/LBKM。 */
    CAN1->FMR|=CAN_FMR_FINIT;CAN1->FA1R&=~1u;CAN1->FS1R|=1u;CAN1->FM1R&=~1u;CAN1->FFA1R&=~1u;
    CAN1->sFilterRegister[0].FR1=0;CAN1->sFilterRegister[0].FR2=0;CAN1->FA1R|=1u;CAN1->FMR&=~CAN_FMR_FINIT;
    CAN1->MCR&=~CAN_MCR_INRQ;if(!wait_init(false)) return 0;
    mp_bus_set_online(true);physical_link_ready=true;
#ifdef CAN_ONLY_BENCH
    /* 仅离线bench观测真实寄存器；完整候选编译时不包含这些钩子。 */
    bench_observe_registers(clocks.PCLK1_Frequency,CAN1->BTR,CAN1->ESR,CAN1->TSR,physical_rx_overflow,physical_bad_frame);
#endif
    return 1;
}
static void fail_link(void) { CAN1->TSR=CAN_TSR_ABRQ0;physical_invalidate(); }
void mp_bus_hardware_poll(void) {
#ifdef CAN_ONLY_BENCH
    bench_observe_registers(bench_stats.pclk,CAN1->BTR,CAN1->ESR,CAN1->TSR,physical_rx_overflow,physical_bad_frame);
#endif
    if(CAN1->ESR&CAN_ESR_BOFF) {tx.fault=true;fail_link();return;}
    if(CAN1->RF0R&CAN_RF0R_FOVR0) {physical_rx_overflow++;CAN1->RF0R=CAN_RF0R_FOVR0;}
    unsigned budget=3;
    while((CAN1->RF0R&3u) && budget--) {
        MpCanFrame f;uint32_t id=CAN1->sFIFOMailBox[0].RIR;
        f.ident=(uint16_t)(id>>21);f.dlc=CAN1->sFIFOMailBox[0].RDTR&15u;
        uint32_t lo=CAN1->sFIFOMailBox[0].RDLR,hi=CAN1->sFIFOMailBox[0].RDHR;memcpy(f.data,&lo,4);memcpy(f.data+4,&hi,4);
        CAN1->RF0R=CAN_RF0R_RFOM0;
        if(!(id&(CAN_RI0R_IDE|CAN_RI0R_RTR)) && f.dlc<=8) {
#ifdef CAN_ONLY_BENCH
            bench_observe_rx(&f);
#endif
            physical_receive(&f);
        } else physical_bad_frame++;
    }
}
int mp_bus_transmit(MpCanFrame *f) {
    uint32_t tsr=CAN1->TSR;
    unsigned action=physical_tx_step(&tx,g_uptime_ms,(tsr&CAN_TSR_TME0)!=0,(tsr&CAN_TSR_RQCP0)!=0,
        (tsr&CAN_TSR_TXOK0)!=0,(tsr&CAN_TSR_TERR0)!=0,(CAN1->ESR&CAN_ESR_BOFF)!=0);
    if(action==LINK_FAULT) {fail_link();return 0;}
    if(action==LINK_ACK) {
#ifdef CAN_ONLY_BENCH
        bench_observe_tx(f,true); /* 只在真实TSR.TXOK判定后记录成功。 */
#endif
        CAN1->TSR=CAN_TSR_RQCP0;return 1;
    }
    if(action==LINK_START) {
#ifdef CAN_ONLY_BENCH
        bench_observe_tx(f,false);
#endif
        uint32_t lo,hi;memcpy(&lo,f->data,4);memcpy(&hi,f->data+4,4);CAN1->TSR=CAN_TSR_RQCP0;
        CAN1->sTxMailBox[0].TDTR=f->dlc;CAN1->sTxMailBox[0].TDLR=lo;CAN1->sTxMailBox[0].TDHR=hi;
        CAN1->sTxMailBox[0].TIR=((uint32_t)f->ident<<21)|CAN_TI0R_TXRQ;
    }
    return 0;
}
