/* H3完整联网IRQ候选：复用H2R固定队列及TXOK策略，不链接bench平台/测试时钟。 */
#include "rx_metrics.h"
#include "rx_irq.h"
#include "link_policy.h"
#include "peer_tx.h"
#include "gateway_platform.h"
#include "stm32f4xx.h"
#include "stm32f4xx_rcc.h"
#include "stm32f4xx_gpio.h"
#include <string.h>

PhysicalRxMetrics physical_rx_metrics;
static PeerTx tx;
static bool initialized;
static uint32_t last_poll_cycles;
static volatile bool peer_seen;
/* ISR唯一写入、主循环只读；对齐32位访问在M4上原子，只用于心跳事件代次。 */
static volatile uint32_t peer_sequence;
bool physical_peer_seen(void) {return peer_seen;}
bool physical_peer_waiting(void) {return tx.peer_wait;}
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
    /* 隔离下载时A断电：先让正常模式C应答A的首次心跳，再允许前台发送排队NMT。
       ISR只置就绪位，OP/质量/时间判定仍由前台协议完成。 */
    if(!*flags && f->ident==0x701 && f->dlc==1 &&
       (f->data[0]==0 || f->data[0]==4 || f->data[0]==5 || f->data[0]==127)) {
        peer_seen=true;peer_sequence++;physical_rx_metrics.heartbeat_a++;
        if(f->data[0]==0)physical_rx_metrics.bootup_a++;
    }
    if(!*flags && f->dlc==8) {
        const uint16_t ids[4]={0x181,0x381,0x481,0x681};
        for(unsigned i=0;i<4;i++)if(f->ident==ids[i])physical_rx_metrics.pdo_a[i]++;
    }
}
void bench_hw_rx_release(void) {CAN1->RF0R=CAN_RF0R_RFOM0;}
void bench_hw_rx_clear(uint32_t flags) {CAN1->RF0R=flags&(CAN_RF0R_FULL0|CAN_RF0R_FOVR0);}
void CAN1_RX0_IRQHandler(void) {bench_rx_irq();}

void physical_rx_update_metrics(void) {
    physical_rx_metrics.esr=CAN1->ESR;
    physical_rx_overflow=bench_rx_path.hw_overrun;physical_bad_frame=bench_rx_path.bad;
    physical_rx_metrics.rx_sw_overflow=bench_rx_path.sw_overrun;
    physical_rx_metrics.rx_high_water=bench_rx_path.high_water;physical_rx_metrics.rx_depth=bench_rx_depth();
    physical_rx_metrics.rx_full=bench_rx_path.hw_full;physical_rx_metrics.rx_fifo_depth=bench_rx_path.fifo_depth_max;
    physical_rx_metrics.rx_isr_calls=bench_rx_path.isr_calls;physical_rx_metrics.rx_isr_frames=bench_rx_path.isr_frames;
    physical_rx_metrics.rx_isr_cycles=bench_rx_path.isr_cycles_max;
    physical_rx_metrics.rx_reinit_discard=bench_rx_path.reinit_discard;
    physical_rx_metrics.rx_fault_discard=bench_rx_path.fault_discard;

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
    /* DWT不在重初始化时清零；按真实平台时钟解释周期。 */
    CoreDebug->DEMCR|=CoreDebug_DEMCR_TRCENA_Msk;DWT->CTRL|=DWT_CTRL_CYCCNTENA_Msk;
    NVIC_DisableIRQ(CAN1_RX0_IRQn);
    peer_seen=false;peer_sequence=0;
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
    /* A可能独立断电；单次发送避免缺ACK时硬件持续重发。真实BOFF仍由软件锁止。 */
    CAN1->MCR=CAN_MCR_INRQ|CAN_MCR_ABOM|CAN_MCR_NART;
    if(!wait_init(true)) return 0;
    CAN1->BTR=btr;
    CAN1->FMR|=CAN_FMR_FINIT;CAN1->FA1R&=~1u;CAN1->FS1R|=1u;CAN1->FM1R&=~1u;CAN1->FFA1R&=~1u;
    CAN1->sFilterRegister[0].FR1=0;CAN1->sFilterRegister[0].FR2=0;CAN1->FA1R|=1u;CAN1->FMR&=~CAN_FMR_FINIT;
    CAN1->MCR&=~CAN_MCR_INRQ;if(!wait_init(false)) return 0;
    initialized=true;physical_rx_metrics.pclk=clocks.PCLK1_Frequency;
    NVIC_ClearPendingIRQ(CAN1_RX0_IRQn);NVIC_SetPriority(CAN1_RX0_IRQn,1);
    CAN1->IER=CAN_IER_FMPIE0|CAN_IER_FFIE0|CAN_IER_FOVIE0;NVIC_EnableIRQ(CAN1_RX0_IRQn);
    mp_bus_set_online(true);physical_link_ready=true;physical_rx_update_metrics();return 1;
}
static void fail_link(void) {CAN1->TSR=CAN_TSR_ABRQ0;physical_invalidate();}
static void latch_fault(uint32_t reason) {
    if(!physical_rx_metrics.fault) {
        physical_rx_metrics.fault=reason;physical_rx_metrics.fault_esr=CAN1->ESR;
        physical_rx_metrics.fault_tsr=CAN1->TSR;physical_rx_metrics.fault_at_ms=g_uptime_ms;
    }
    tx.fault=true;fail_link();
}
void physical_protocol_fault(unsigned reset) {
    physical_rx_metrics.protocol_reset=reset;latch_fault(9);
}
void mp_bus_hardware_poll(void) {
    uint32_t now=bench_clock_cycles();
    if(last_poll_cycles && now-last_poll_cycles>physical_rx_metrics.main_gap_cycles)
        physical_rx_metrics.main_gap_cycles=now-last_poll_cycles;
    last_poll_cycles=now;physical_rx_update_metrics();
    if((CAN1->ESR&CAN_ESR_BOFF) || bench_rx_path.fault_bits) {
        latch_fault(bench_rx_path.fault_bits?6:8);return;
    }
    if(peer_tx_resume(&tx,peer_sequence)) {
        /* 先丢旧队列再接收新Boot-up，不让旧TIME/NMT在新应用会话重发。 */
        physical_rx_metrics.tx_peer_discard+=mp_bus_discard_pending();
        physical_rx_metrics.peer_wait=0;physical_rx_metrics.peer_returns++;
        physical_peer_returned();
    }
    BenchRxItem item;unsigned budget=1;
    /* 一个协议tick消费一帧；先RPDO/Adapter再读下一帧，保留排队波形点。 */
    while(budget-- && bench_rx_peek(&item) && physical_receive_due(item.at_ms) && bench_rx_take(&item)) {
        if(bench_rx_path.fault_bits) {latch_fault(6);return;}
        uint32_t lag=bench_clock_cycles()-item.at_cycles;
        if(lag>physical_rx_metrics.rx_lag_cycles) physical_rx_metrics.rx_lag_cycles=lag;
        /* 失效窗口不延长；过旧的排队项丢弃并锁止，不给旧帧重新盖新鲜时间。 */
        if((uint32_t)(g_uptime_ms-item.at_ms)>1500u) {
            physical_rx_metrics.rx_stale_discard++;latch_fault(7);return;
        }
        physical_receive_at(&item.frame,item.at_ms);
    }
    physical_rx_update_metrics();
    if(bench_rx_path.fault_bits)latch_fault(6);
}
int mp_bus_transmit(MpCanFrame *f) {
    uint32_t tsr=CAN1->TSR;
    uint32_t esr=CAN1->ESR;
    unsigned action=peer_tx_step(&tx,g_uptime_ms,peer_sequence,(tsr&CAN_TSR_TME0)!=0,(tsr&CAN_TSR_RQCP0)!=0,
        (tsr&CAN_TSR_TXOK0)!=0,(tsr&CAN_TSR_TERR0)!=0,(tsr&CAN_TSR_ALST0)!=0,(esr>>4)&7u,(esr&CAN_ESR_BOFF)!=0);
    if(action==PEER_TX_FAULT) {if(physical_link_ready)physical_rx_metrics.tx_failed++;latch_fault(8);return 0;}
    if(action==PEER_TX_NO_ACK) {
        physical_rx_metrics.tx_failed++;physical_rx_metrics.tx_no_ack++;
        physical_rx_metrics.peer_wait=1;physical_rx_metrics.peer_losses++;
        physical_rx_metrics.peer_event_esr=esr;physical_rx_metrics.peer_event_tsr=tsr;
        physical_rx_metrics.peer_event_at_ms=g_uptime_ms;
        physical_peer_lost();CAN1->TSR=CAN_TSR_RQCP0;
    }
    if(action==PEER_TX_NO_ACK || action==PEER_TX_DISCARD) {
        physical_rx_metrics.tx_peer_discard++;return MP_CAN_TX_DISCARD;
    }
    if(action==PEER_TX_ACK) {
        /* 只在真实TXOK后累计；入队或请求发送都不能计作NMT/TIME已到总线。 */
        physical_rx_metrics.tx_acked++;
        if(f->ident==0 && f->dlc==2 && f->data[0]==1)physical_rx_metrics.nmt_start_acked++;
        if(f->ident==0x100)physical_rx_metrics.time_acked++;
        CAN1->TSR=CAN_TSR_RQCP0;return 1;
    }
    if(action==PEER_TX_START) {
        uint32_t lo,hi;
        /* RM0090允许软件把LEC设为7；仅标记本次请求前无新错误，不改TEC/REC计数。
         * 防止上次ACK错误遗留的LEC=3误把本次其他错误归为对端缺席。 */
        CAN1->ESR=7u<<4;
        memcpy(&lo,f->data,4);memcpy(&hi,f->data+4,4);CAN1->TSR=CAN_TSR_RQCP0;
        CAN1->sTxMailBox[0].TDTR=f->dlc;CAN1->sTxMailBox[0].TDLR=lo;CAN1->sTxMailBox[0].TDHR=hi;
        CAN1->sTxMailBox[0].TIR=((uint32_t)f->ident<<21)|CAN_TI0R_TXRQ;
    }
    return 0;
}
