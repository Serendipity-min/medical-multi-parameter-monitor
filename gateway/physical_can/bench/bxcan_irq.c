/* H2R专属驱动；原完整物理候选/内部回环仍链接原实现，不修改第三方驱动。 */
#include "bench.h"
#include "rx_irq.h"
#include "link_policy.h"
#include "gateway_platform.h"
#include "stm32f4xx.h"
#include "stm32f4xx_rcc.h"
#include "stm32f4xx_gpio.h"
#include <string.h>

static PhysicalTx tx;
static bool initialized;
static uint32_t last_poll_cycles;
uint32_t physical_rx_overflow,physical_bad_frame;
_Static_assert(CAN_RF0R_FOVR0==BENCH_FIFO_OVERRUN,"FOVR W1C mask mismatch");
_Static_assert(CAN_RF0R_FULL0==BENCH_FIFO_FULL,"FULL W1C mask mismatch");

uint32_t bench_clock_cycles(void) {return DWT->CYCCNT;}
uint32_t bench_hw_rx_status(void) {return CAN1->RF0R;}
void bench_hw_rx_read(MpCanFrame *f,uint32_t *flags) {
    uint32_t raw=CAN1->sFIFOMailBox[0].RIR;
    f->ident=(uint16_t)(raw>>21);f->dlc=CAN1->sFIFOMailBox[0].RDTR&15u;
    *flags=raw&(CAN_RI0R_IDE|CAN_RI0R_RTR);
    uint32_t lo=CAN1->sFIFOMailBox[0].RDLR,hi=CAN1->sFIFOMailBox[0].RDHR;
    memcpy(f->data,&lo,4);memcpy(f->data+4,&hi,4);
}
void bench_hw_rx_release(void) {CAN1->RF0R=CAN_RF0R_RFOM0;}
void bench_hw_rx_clear(uint32_t flags) {CAN1->RF0R=flags&(CAN_RF0R_FULL0|CAN_RF0R_FOVR0);}
void CAN1_RX0_IRQHandler(void) {bench_rx_irq();}

void bench_update_rx_metrics(void) {
    physical_rx_overflow=bench_rx_path.hw_overrun;physical_bad_frame=bench_rx_path.bad;
    bench_stats.rx_sw_overflow=bench_rx_path.sw_overrun;
    bench_stats.rx_high_water=bench_rx_path.high_water;bench_stats.rx_depth=bench_rx_depth();
    bench_stats.rx_full=bench_rx_path.hw_full;bench_stats.rx_fifo_depth=bench_rx_path.fifo_depth_max;
    bench_stats.rx_isr_calls=bench_rx_path.isr_calls;bench_stats.rx_isr_frames=bench_rx_path.isr_frames;
    bench_stats.rx_isr_cycles=bench_rx_path.isr_cycles_max;
    bench_stats.rx_reinit_discard=bench_rx_path.reinit_discard;
    bench_stats.rx_fault_discard=bench_rx_path.fault_discard;
    bench_observe_registers(bench_stats.pclk,CAN1->BTR,CAN1->ESR,CAN1->TSR,physical_rx_overflow,physical_bad_frame);
}
static int wait_init(bool enabled) {
    uint32_t at=g_uptime_ms;
    for(unsigned i=0;i<1000000u;i++) {
        if(((CAN1->MSR&CAN_MSR_INAK)!=0)==enabled) return 1;
        if((uint32_t)(g_uptime_ms-at)>=100u) break;
    }
    return 0;
}
int mp_bxcan_init(void) {
    NVIC_DisableIRQ(CAN1_RX0_IRQn);
    /* 显式重初始化清待处理项但绝不清累计故障；丢失后不能靠G恢复为PASS。 */
    if(initialized) {bench_rx_irq();bench_rx_discard_pending();}
    if(bench_rx_path.fault_bits) return 0;
    physical_invalidate();memset(&tx,0,sizeof(tx));
    RCC_ClocksTypeDef clocks;RCC_GetClocksFreq(&clocks);uint32_t btr;
    if(!physical_btr(clocks.PCLK1_Frequency,&btr)) return 0;
    RCC_AHB1PeriphClockCmd(RCC_AHB1Periph_GPIOA,ENABLE);RCC_APB1PeriphClockCmd(RCC_APB1Periph_CAN1,ENABLE);
    CAN1->IER=0;
    GPIO_InitTypeDef gpio;GPIO_StructInit(&gpio);gpio.GPIO_Pin=GPIO_Pin_11|GPIO_Pin_12;
    gpio.GPIO_Mode=GPIO_Mode_AF;gpio.GPIO_OType=GPIO_OType_PP;gpio.GPIO_Speed=GPIO_Speed_50MHz;gpio.GPIO_PuPd=GPIO_PuPd_UP;
    GPIO_PinAFConfig(GPIOA,GPIO_PinSource11,GPIO_AF_CAN1);GPIO_PinAFConfig(GPIOA,GPIO_PinSource12,GPIO_AF_CAN1);GPIO_Init(GPIOA,&gpio);
    CAN1->MCR=CAN_MCR_INRQ|CAN_MCR_ABOM;
    if(!wait_init(true)) return 0;
    CAN1->BTR=btr;
    CAN1->FMR|=CAN_FMR_FINIT;CAN1->FA1R&=~1u;CAN1->FS1R|=1u;CAN1->FM1R&=~1u;CAN1->FFA1R&=~1u;
    CAN1->sFilterRegister[0].FR1=0;CAN1->sFilterRegister[0].FR2=0;CAN1->FA1R|=1u;CAN1->FMR&=~CAN_FMR_FINIT;
    CAN1->MCR&=~CAN_MCR_INRQ;if(!wait_init(false)) return 0;
    initialized=true;bench_stats.pclk=clocks.PCLK1_Frequency;
    NVIC_ClearPendingIRQ(CAN1_RX0_IRQn);NVIC_SetPriority(CAN1_RX0_IRQn,1);
    CAN1->IER=CAN_IER_FMPIE0|CAN_IER_FFIE0|CAN_IER_FOVIE0;NVIC_EnableIRQ(CAN1_RX0_IRQn);
    mp_bus_set_online(true);physical_link_ready=true;bench_update_rx_metrics();return 1;
}
static void fail_link(void) {CAN1->TSR=CAN_TSR_ABRQ0;physical_invalidate();}
void mp_bus_hardware_poll(void) {
    uint32_t now=bench_clock_cycles();
    if(last_poll_cycles && now-last_poll_cycles>bench_stats.main_gap_cycles)
        bench_stats.main_gap_cycles=now-last_poll_cycles;
    last_poll_cycles=now;bench_update_rx_metrics();
    if((CAN1->ESR&CAN_ESR_BOFF) || bench_rx_path.fault_bits) {
        if(bench_rx_path.fault_bits) bench_stats.fault=6;
        tx.fault=true;fail_link();return;
    }
    BenchRxItem item;unsigned budget=32;
    while(budget-- && bench_rx_take(&item)) {
        if(bench_rx_path.fault_bits) {bench_stats.fault=6;tx.fault=true;fail_link();return;}
        uint32_t lag=bench_clock_cycles()-item.at_cycles;
        if(lag>bench_stats.rx_lag_cycles) bench_stats.rx_lag_cycles=lag;
        /* 失效窗口不延长；过旧的排队项丢弃并锁止，不给旧帧重新盖新鲜时间。 */
        if((uint32_t)(g_uptime_ms-item.at_ms)>1500u) {
            bench_stats.rx_stale_discard++;bench_stats.fault=7;tx.fault=true;fail_link();return;
        }
        bench_observe_rx_at(&item.frame,item.at_ms);
        physical_receive_at(&item.frame,item.at_ms);
    }
    bench_update_rx_metrics();
    if(bench_rx_path.fault_bits) {bench_stats.fault=6;tx.fault=true;fail_link();}
}
int mp_bus_transmit(MpCanFrame *f) {
    uint32_t tsr=CAN1->TSR;
    unsigned action=physical_tx_step(&tx,g_uptime_ms,(tsr&CAN_TSR_TME0)!=0,(tsr&CAN_TSR_RQCP0)!=0,
        (tsr&CAN_TSR_TXOK0)!=0,(tsr&CAN_TSR_TERR0)!=0,(CAN1->ESR&CAN_ESR_BOFF)!=0);
    if(action==LINK_FAULT) {fail_link();return 0;}
    if(action==LINK_ACK) {bench_observe_tx(f,true);CAN1->TSR=CAN_TSR_RQCP0;return 1;}
    if(action==LINK_START) {
        bench_observe_tx(f,false);uint32_t lo,hi;
        memcpy(&lo,f->data,4);memcpy(&hi,f->data+4,4);CAN1->TSR=CAN_TSR_RQCP0;
        CAN1->sTxMailBox[0].TDTR=f->dlc;CAN1->sTxMailBox[0].TDLR=lo;CAN1->sTxMailBox[0].TDHR=hi;
        CAN1->sTxMailBox[0].TIR=((uint32_t)f->ident<<21)|CAN_TI0R_TXRQ;
    }
    return 0;
}
