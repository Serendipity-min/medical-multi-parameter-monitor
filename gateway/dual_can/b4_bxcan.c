/* 双bxCAN独立候选驱动；受限台架与正式H3的部署身份分别管理。 */
#include "b4_bxcan.h"
#include "b4_resources.h"
#if defined(B4_BXCAN_MMIO_TEST)
#include "tests/bxcan_mmio_shim.h"
#else
#include "stm32f4xx.h"
#include "stm32f4xx_can.h"
#include "stm32f4xx_gpio.h"
#include "stm32f4xx_rcc.h"
#include "misc.h"
#endif
#if defined(B4_CAPTURE_SERIAL)
#include "b4_capture.h"
/* 邮箱中的原始内容由主循环保存，与随后TXOK/失败分别关联；入邮箱不算ACK。 */
static MpCanFrame capture_tx[2][3];
static uint8_t capture_tx_valid[2][3];
#endif
typedef struct { MpCanFrame frame; uint32_t tick; } Item;
/* 单生产者ISR/单消费者主循环，各段各自96槽；先写数据再发布head。 */
static Item rx[2][96];
static volatile unsigned head[2], tail[2];
static uint8_t hw_clocks_ready, hw_stopped;
volatile B4HwDiag b4_hw_diag[2];
extern uint32_t b4_hw_time(void);
static CAN_TypeDef *controller(unsigned bus) { return bus ? CAN2 : CAN1; }
static void irq(unsigned bus) {
    CAN_TypeDef *can = controller(bus);
    for (unsigned budget = 0; budget < 3 && CAN_MessagePending(can, CAN_FIFO0); budget++) {
        CanRxMsg message; CAN_Receive(can, CAN_FIFO0, &message);
        if (message.IDE != CAN_Id_Standard || message.RTR != CAN_RTR_Data || message.DLC > 8) {
            b4_hw_diag[bus].malformed++; continue;
        }
        unsigned next = (head[bus] + 1) % 96;
        if (next == tail[bus]) { b4_hw_diag[bus].overflow++; continue; }
        Item *item = &rx[bus][head[bus]];
        item->tick = b4_hw_time(); item->frame.ident = message.StdId; item->frame.dlc = message.DLC;
        for (unsigned i = 0; i < 8; i++) item->frame.data[i] = message.Data[i];
        __DMB(); head[bus] = next; b4_hw_diag[bus].received++;
        unsigned count = (next + 96 - tail[bus]) % 96;
        if (count > b4_hw_diag[bus].high_water) b4_hw_diag[bus].high_water = count;
    }
    if (can->RF0R & CAN_RF0R_FOVR0) { b4_hw_diag[bus].overflow++; can->RF0R = CAN_RF0R_FOVR0; }
}
void CAN1_RX0_IRQHandler(void) { irq(0); }
void CAN2_RX0_IRQHandler(void) { irq(1); }
int b4_hw_init(void) {
    hw_clocks_ready = hw_stopped = 0;
    RCC_ClocksTypeDef clocks; RCC_GetClocksFreq(&clocks);
    /* 冻结H3使用8MHz HSE；B使用42MHz APB1，不能套用同一prescaler。 */
    if (clocks.PCLK1_Frequency != 42000000u && clocks.PCLK1_Frequency != 8000000u) return -1;
    /* CAN2共享CAN1控制的过滤器时钟；初始化/重连不得关闭或复位CAN1。 */
    RCC_APB1PeriphClockCmd(RCC_APB1Periph_CAN1 | RCC_APB1Periph_CAN2, ENABLE);
    hw_clocks_ready = 1;
    RCC_AHB1PeriphClockCmd(RCC_AHB1Periph_GPIOA | RCC_AHB1Periph_GPIOB, ENABLE);
    GPIO_InitTypeDef gpio; GPIO_StructInit(&gpio); gpio.GPIO_Mode = GPIO_Mode_AF;
    gpio.GPIO_OType = GPIO_OType_PP; gpio.GPIO_PuPd = GPIO_PuPd_UP; gpio.GPIO_Speed = GPIO_Speed_50MHz;
    gpio.GPIO_Pin = GPIO_Pin_11 | GPIO_Pin_12; GPIO_Init(GPIOA, &gpio);
    GPIO_PinAFConfig(GPIOA, GPIO_PinSource11, GPIO_AF_CAN1); GPIO_PinAFConfig(GPIOA, GPIO_PinSource12, GPIO_AF_CAN1);
    gpio.GPIO_Pin = GPIO_Pin_12 | GPIO_Pin_13; GPIO_Init(GPIOB, &gpio);
    GPIO_PinAFConfig(GPIOB, GPIO_PinSource12, GPIO_AF_CAN2); GPIO_PinAFConfig(GPIOB, GPIO_PinSource13, GPIO_AF_CAN2);
    for (unsigned bus = 0; bus < 2; bus++) {
        CAN_InitTypeDef can; CAN_StructInit(&can);
        /* 常规仲裁失败必须保留发送请求，不能把与低COB-ID波形竞争当成丢弃心跳的理由。
         * NART=0由硬件在总线可用时重传；台架结束由b4_hw_stop有界取消所有待发请求。 */
        can.CAN_ABOM = ENABLE; can.CAN_NART = DISABLE; can.CAN_RFLM = ENABLE;
        can.CAN_TXFP = ENABLE; /* 同一COB-ID按请求次序，避免多邮箱并发造成倒序。 */
        can.CAN_Mode = CAN_Mode_Normal; can.CAN_SJW = CAN_SJW_1tq;
#if defined(MP_B5_CLOUD_CANDIDATE) && !defined(MP_ABC_TRI_CANDIDATE)
        /* CAN2仍需CAN1共享时钟；首轮A段只保留静默控制器，不收发/ACK A。 */
        if (!bus) can.CAN_Mode = CAN_Mode_Silent;
#endif
        can.CAN_BS1 = clocks.PCLK1_Frequency == 8000000u ? CAN_BS1_13tq : CAN_BS1_11tq;
        can.CAN_BS2 = CAN_BS2_2tq; can.CAN_Prescaler = clocks.PCLK1_Frequency == 8000000u ? 1 : 6;
        if (CAN_Init(controller(bus), &can) != CAN_InitStatus_Success) return -2;
    }
    /* 只配置一次共享分界：0..13 CAN1，14..27 CAN2。两个bank分别分配FIFO0。 */
    CAN1->FMR |= CAN_FMR_FINIT;
    CAN1->FA1R = 0; /* 此独立目标拥有两组全部过滤器；清除旧入口，随后一次配置两段。 */
    CAN_SlaveStartBank(B4_CAN2_FILTER_START);
    for (unsigned bus = 0; bus < 2; bus++) {
        CAN_FilterInitTypeDef filter = {0}; filter.CAN_FilterNumber = bus ? B4_CAN2_FILTER_START : 0;
        filter.CAN_FilterMode = CAN_FilterMode_IdMask; filter.CAN_FilterScale = CAN_FilterScale_32bit;
        filter.CAN_FilterMaskIdLow = 6; /* IDE=0、RTR=0，其余在协议入口按节点/总线过滤。 */
        filter.CAN_FilterFIFOAssignment = CAN_Filter_FIFO0; filter.CAN_FilterActivation = ENABLE;
#if defined(MP_B5_CLOUD_CANDIDATE) && !defined(MP_ABC_TRI_CANDIDATE)
        if (!bus) filter.CAN_FilterActivation = DISABLE;
#endif
        CAN_FilterInit(&filter);
        CAN_ITConfig(controller(bus), CAN_IT_FMP0 | CAN_IT_FOV0, ENABLE);
        NVIC_InitTypeDef nvic; nvic.NVIC_IRQChannel = bus ? CAN2_RX0_IRQn : CAN1_RX0_IRQn;
        nvic.NVIC_IRQChannelPreemptionPriority = 3; nvic.NVIC_IRQChannelSubPriority = bus;
        nvic.NVIC_IRQChannelCmd = ENABLE;
#if defined(MP_B5_CLOUD_CANDIDATE) && !defined(MP_ABC_TRI_CANDIDATE)
        if (!bus) nvic.NVIC_IRQChannelCmd = DISABLE;
#endif
        NVIC_Init(&nvic);
    }
    return 0;
}
static void completed(unsigned bus) {
    CAN_TypeDef *can=controller(bus);
    /* 入邮箱不等于收到ACK；分别保留真实完成/失败计数，避免把无ACK当发送通过。 */
    uint32_t status = can->TSR;
    for (unsigned mailbox = 0; mailbox < 3; mailbox++) {
        uint32_t complete = 1u << (mailbox * 8u);
        if (status & complete) {
            if (status & (complete << 1)) b4_hw_diag[bus].tx_acked++;
            else b4_hw_diag[bus].tx_failed++;
#if defined(B4_CAPTURE_SERIAL)
            if (capture_tx_valid[bus][mailbox]) {
                MpCanFrame *f=&capture_tx[bus][mailbox];
                b4_capture_emit((status&(complete<<1))?B4_CAP_TX_ACK:B4_CAP_TX_FAIL,
                    bus,f->ident,f->dlc,f->data,b4_hw_time(),status);
                capture_tx_valid[bus][mailbox]=0;
            }
#endif
            can->TSR = complete;
        }
    }
}
int b4_bus_transmit(unsigned bus, const MpCanFrame *frame) {
    if (hw_stopped || bus > 1 || frame->ident > 0x7ff || frame->dlc > 8) return 0;
#if defined(MP_B5_CLOUD_CANDIDATE) && !defined(MP_ABC_TRI_CANDIDATE)
    if (!bus) return 0;
#endif
    CAN_TypeDef *can = controller(bus);
    /* 先结算已完成邮箱，随后才能记录该邮箱的新原始帧。 */
    completed(bus);
    if ((can->ESR & CAN_ESR_BOFF) || !(can->TSR & (CAN_TSR_TME0 | CAN_TSR_TME1 | CAN_TSR_TME2))) {
        b4_hw_diag[bus].tx_busy++; return 0;
    }
    CanTxMsg message = {0}; message.StdId = frame->ident; message.IDE = CAN_Id_Standard;
    message.RTR = CAN_RTR_Data; message.DLC = frame->dlc;
    for (unsigned i = 0; i < 8; i++) message.Data[i] = frame->data[i];
    uint8_t mailbox=CAN_Transmit(can, &message);
#if defined(B4_CAPTURE_SERIAL)
    if (mailbox<3) {
        capture_tx[bus][mailbox]=*frame; capture_tx_valid[bus][mailbox]=1;
        b4_capture_emit(B4_CAP_TX_QUEUE,bus,frame->ident,frame->dlc,frame->data,b4_hw_time(),mailbox);
    }
#endif
    return mailbox != CAN_TxStatus_NoMailBox;
}
void b4_hw_stop(void) {
    /* 初始化失败前未开CAN时钟则不碰外设；停止幂等，不复位共享CAN1时钟/过滤器。
     * 先禁止新软件请求，再禁止继续自动重传并取消全部邮箱；在途帧最多结束当前一次尝试。
     * 控制器仍可ACK对端，不因台架STOP额外制造B端无ACK/BOFF。此函数不自动重新武装。 */
    hw_stopped = 1;
    if (!hw_clocks_ready) return;
    for (unsigned bus = 0; bus < 2; bus++) {
        CAN_TypeDef *can = controller(bus);
        b4_hw_diag[bus].esr = can->ESR;
        completed(bus);
        can->MCR |= CAN_MCR_NART;
        can->TSR = CAN_TSR_ABRQ0 | CAN_TSR_ABRQ1 | CAN_TSR_ABRQ2;
    }
}
void b4_hw_idle(void) {
    for (unsigned bus=0;bus<2;bus++) {
        for (unsigned budget=0;tail[bus]!=head[bus] && budget<16;budget++)
            tail[bus]=(tail[bus]+1)%96;
    }
}
void b4_hw_poll(B4Gateway *g) {
    if (hw_stopped) return;
    for (unsigned bus = 0; bus < 2; bus++) {
        CAN_TypeDef *can = controller(bus);
        b4_hw_diag[bus].esr = can->ESR;
        completed(bus);
        /* 同一控制器指针同时供正常目标和可选取证使用，避免非取证构建留下无用变量。 */
        bool up = b4_hw_protocol_link_up(bus,!(can->ESR & CAN_ESR_BOFF));
        if (!up && g->segments[bus].link_up) b4_hw_diag[bus].busoff++;
        b4_gateway_link(g, bus, up);
        for (unsigned budget = 0; tail[bus] != head[bus] && budget < 16; budget++) {
            __DMB(); Item item = rx[bus][tail[bus]];
            /* ISR可能在本轮tick之后推进到下一毫秒；留在队首等下一轮，不能丢成坏帧。 */
            if ((int32_t)(g->now - item.tick) < 0) break;
            tail[bus] = (tail[bus] + 1) % 96;
#if defined(B4_CAPTURE_SERIAL)
            b4_capture_emit(B4_CAP_RX,bus,item.frame.ident,item.frame.dlc,item.frame.data,item.tick,can->ESR);
#endif
            if (up) b4_gateway_receive(g, bus, &item.frame, item.tick);
        }
    }
}
