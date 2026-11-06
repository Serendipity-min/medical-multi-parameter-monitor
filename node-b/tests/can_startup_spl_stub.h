#ifndef CAN_STARTUP_SPL_STUB_H
#define CAN_STARTUP_SPL_STUB_H
#include <stdint.h>
typedef struct { volatile uint32_t MCR, MSR, TSR, RF0R, ESR, IER; } CAN_TypeDef;
extern CAN_TypeDef startup_can;
#define CAN1 (&startup_can)
#define GPIOA ((void *)1)
#define ENABLE 1
#define DISABLE 0
#define CAN_MCR_INRQ 1u
#define CAN_MSR_INAK 1u
#define CAN_MSR_ERRI 4u
#define CAN_RF0R_FMP0 3u
#define CAN_RF0R_FOVR0 16u
#define CAN_TSR_RQCP0 1u
#define CAN_TSR_RQCP1 256u
#define CAN_TSR_RQCP2 65536u
#define CAN_TSR_TME0 (1u<<26)
#define CAN_TSR_TME1 (1u<<27)
#define CAN_TSR_TME2 (1u<<28)
#define CAN_IT_TME 1u
#define CAN_IT_FMP0 2u
#define CAN_IT_FOV0 8u
#define CAN_IT_ERR 32768u
#define CAN1_RX0_IRQn 20u
#define CAN1_TX_IRQn 19u
#define CAN1_SCE_IRQn 22u
#define CAN_InitStatus_Success 1u
#define CAN_TxStatus_NoMailBox 4u
#define CAN_Id_Standard 0u
#define CAN_RTR_Data 0u
#define CAN_RTR_Remote 2u
#define CAN_Mode_Normal 0u
#define CAN_SJW_1tq 0u
#define CAN_BS1_11tq 10u
#define CAN_BS2_2tq 1u
#define CAN_FIFO0 0u
#define CAN_Filter_FIFO0 0u
#define CAN_FilterMode_IdMask 0u
#define CAN_FilterScale_32bit 1u
#define GPIO_PinSource11 11u
#define GPIO_PinSource12 12u
#define GPIO_Pin_11 (1u<<11)
#define GPIO_Pin_12 (1u<<12)
#define GPIO_AF_CAN1 9u
#define GPIO_Mode_AF 2u
#define GPIO_Speed_50MHz 2u
#define GPIO_OType_PP 0u
#define GPIO_PuPd_UP 1u
#define RCC_AHB1Periph_GPIOA 1u
#define RCC_APB1Periph_CAN1 (1u<<25)
typedef struct { uint32_t GPIO_Pin, GPIO_Mode, GPIO_Speed, GPIO_OType, GPIO_PuPd; } GPIO_InitTypeDef;
typedef struct {
    uint32_t CAN_TTCM, CAN_ABOM, CAN_AWUM, CAN_NART, CAN_RFLM, CAN_TXFP;
    uint32_t CAN_Mode, CAN_SJW, CAN_BS1, CAN_BS2, CAN_Prescaler;
} CAN_InitTypeDef;
typedef struct {
    uint32_t CAN_FilterNumber, CAN_FilterMode, CAN_FilterScale, CAN_FilterIdHigh, CAN_FilterIdLow;
    uint32_t CAN_FilterMaskIdHigh, CAN_FilterMaskIdLow, CAN_FilterFIFOAssignment, CAN_FilterActivation;
} CAN_FilterInitTypeDef;
typedef struct {
    uint32_t NVIC_IRQChannel, NVIC_IRQChannelPreemptionPriority, NVIC_IRQChannelSubPriority, NVIC_IRQChannelCmd;
} NVIC_InitTypeDef;
typedef struct { uint32_t StdId, ExtId; uint8_t IDE, RTR, DLC, Data[8]; } CanRxMsg;
typedef CanRxMsg CanTxMsg;
void RCC_APB1PeriphClockCmd(uint32_t peripheral, int enabled);
void RCC_AHB1PeriphClockCmd(uint32_t peripheral, int enabled);
void GPIO_PinAFConfig(void *port, unsigned pin, unsigned alternate);
void GPIO_Init(void *port, GPIO_InitTypeDef *config);
unsigned CAN_Init(CAN_TypeDef *port, CAN_InitTypeDef *config);
void CAN_FilterInit(CAN_FilterInitTypeDef *config);
void CAN_ITConfig(CAN_TypeDef *port, uint32_t mask, int enabled);
void NVIC_Init(NVIC_InitTypeDef *config);
void CAN_Receive(CAN_TypeDef *port, unsigned fifo, CanRxMsg *frame);
uint8_t CAN_Transmit(CAN_TypeDef *port, CanTxMsg *frame);
static inline unsigned __get_PRIMASK(void) { return 0; }
static inline void __disable_irq(void) {}
static inline void __set_PRIMASK(unsigned value) { (void)value; }
#endif
