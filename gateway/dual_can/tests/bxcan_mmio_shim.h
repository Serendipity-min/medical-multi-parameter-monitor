#ifndef B4_BXCAN_MMIO_SHIM_H
#define B4_BXCAN_MMIO_SHIM_H
/* 仅供Host编译真实驱动：寄存器为普通RAM，任何函数均不访问设备。 */
#include <stdint.h>
#include <stdatomic.h>
#define __DMB() atomic_thread_fence(memory_order_seq_cst)
typedef struct { uint32_t MCR,TSR,ESR,RF0R,FMR,FA1R; } CAN_TypeDef;
extern CAN_TypeDef b4_test_can[2];
#define CAN1 (&b4_test_can[0])
#define CAN2 (&b4_test_can[1])
#define ENABLE 1
#define DISABLE 0
#define CAN_MCR_NART 0x10u
#define CAN_TSR_TME0 (1u<<26)
#define CAN_TSR_TME1 (1u<<27)
#define CAN_TSR_TME2 (1u<<28)
#define CAN_TSR_ABRQ0 (1u<<7)
#define CAN_TSR_ABRQ1 (1u<<15)
#define CAN_TSR_ABRQ2 (1u<<23)
#define CAN_ESR_BOFF 4u
#define CAN_RF0R_FOVR0 0x10u
#define CAN_FMR_FINIT 1u
#define CAN_FIFO0 0u
#define CAN_Id_Standard 0u
#define CAN_RTR_Data 0u
#define CAN_TxStatus_NoMailBox 4u
#define CAN_InitStatus_Success 1u
#define CAN_Mode_Normal 0u
#define CAN_SJW_1tq 0u
#define CAN_BS1_13tq 12u
#define CAN_BS1_11tq 10u
#define CAN_BS2_2tq 1u
#define CAN_FilterMode_IdMask 0u
#define CAN_FilterScale_32bit 1u
#define CAN_Filter_FIFO0 0u
#define CAN_IT_FMP0 1u
#define CAN_IT_FOV0 2u
#define CAN1_RX0_IRQn 20u
#define CAN2_RX0_IRQn 63u
#define RCC_APB1Periph_CAN1 1u
#define RCC_APB1Periph_CAN2 2u
#define RCC_AHB1Periph_GPIOA 1u
#define RCC_AHB1Periph_GPIOB 2u
#define GPIOA ((void*)1)
#define GPIOB ((void*)2)
#define GPIO_Mode_AF 2u
#define GPIO_OType_PP 0u
#define GPIO_PuPd_UP 1u
#define GPIO_Speed_50MHz 2u
#define GPIO_Pin_11 (1u<<11)
#define GPIO_Pin_12 (1u<<12)
#define GPIO_Pin_13 (1u<<13)
#define GPIO_PinSource11 11u
#define GPIO_PinSource12 12u
#define GPIO_PinSource13 13u
#define GPIO_AF_CAN1 9u
#define GPIO_AF_CAN2 9u
typedef struct { uint32_t PCLK1_Frequency; } RCC_ClocksTypeDef;
typedef struct { uint32_t GPIO_Mode,GPIO_OType,GPIO_PuPd,GPIO_Speed,GPIO_Pin; } GPIO_InitTypeDef;
typedef struct { uint32_t CAN_ABOM,CAN_NART,CAN_RFLM,CAN_TXFP,CAN_Mode,CAN_SJW,CAN_BS1,CAN_BS2,CAN_Prescaler; } CAN_InitTypeDef;
typedef struct { uint32_t CAN_FilterNumber,CAN_FilterMode,CAN_FilterScale,CAN_FilterMaskIdLow,CAN_FilterFIFOAssignment,CAN_FilterActivation; } CAN_FilterInitTypeDef;
typedef struct { uint32_t NVIC_IRQChannel,NVIC_IRQChannelPreemptionPriority,NVIC_IRQChannelSubPriority,NVIC_IRQChannelCmd; } NVIC_InitTypeDef;
typedef struct { uint32_t StdId,IDE,RTR,DLC; uint8_t Data[8]; } CanRxMsg;
typedef CanRxMsg CanTxMsg;
extern uint32_t b4_test_clock;
extern unsigned b4_test_transmit_calls,b4_test_clock_calls;
static inline void RCC_GetClocksFreq(RCC_ClocksTypeDef *x) { x->PCLK1_Frequency=b4_test_clock; }
static inline void RCC_APB1PeriphClockCmd(unsigned p,unsigned en) { (void)p;(void)en;b4_test_clock_calls++; }
static inline void RCC_AHB1PeriphClockCmd(unsigned p,unsigned en) { (void)p;(void)en; }
static inline void GPIO_StructInit(GPIO_InitTypeDef *x) { (void)x; }
static inline void GPIO_Init(void *p,GPIO_InitTypeDef *x) { (void)p;(void)x; }
static inline void GPIO_PinAFConfig(void *p,unsigned pin,unsigned af) { (void)p;(void)pin;(void)af; }
static inline void CAN_StructInit(CAN_InitTypeDef *x) { *x=(CAN_InitTypeDef){0}; }
static inline unsigned CAN_Init(CAN_TypeDef *c,CAN_InitTypeDef *x) {
    c->MCR=x->CAN_NART?CAN_MCR_NART:0; c->TSR=CAN_TSR_TME0|CAN_TSR_TME1|CAN_TSR_TME2;
    return CAN_InitStatus_Success;
}
static inline void CAN_SlaveStartBank(unsigned bank) { (void)bank; }
static inline void CAN_FilterInit(CAN_FilterInitTypeDef *f) { (void)f; }
static inline void CAN_ITConfig(CAN_TypeDef *c,unsigned m,unsigned en) { (void)c;(void)m;(void)en; }
static inline void NVIC_Init(NVIC_InitTypeDef *n) { (void)n; }
static inline unsigned CAN_MessagePending(CAN_TypeDef *c,unsigned fifo) { (void)c;(void)fifo;return 0; }
static inline void CAN_Receive(CAN_TypeDef *c,unsigned fifo,CanRxMsg *m) { (void)c;(void)fifo;(void)m; }
static inline uint8_t CAN_Transmit(CAN_TypeDef *c,CanTxMsg *m) {
    (void)m;b4_test_transmit_calls++;c->TSR&=~CAN_TSR_TME0;return 0;
}
#endif
