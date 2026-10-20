#ifndef MP_HOST_STM32_MMIO_H
#define MP_HOST_STM32_MMIO_H
#include <stdint.h>
/* 仅Host寄存器边界替身；W1C/硬件完成由测试显式注入，绝不作为实板证据。 */
typedef struct {volatile uint32_t TIR,TDTR,TDLR,TDHR;} HostTxMailbox;
typedef struct {volatile uint32_t RIR,RDTR,RDLR,RDHR;} HostRxMailbox;
typedef struct {volatile uint32_t FR1,FR2;} HostFilter;
typedef struct {
    volatile uint32_t MCR,MSR,TSR,RF0R,IER,ESR,BTR,FMR,FA1R,FS1R,FM1R,FFA1R;
    HostTxMailbox sTxMailBox[3];HostRxMailbox sFIFOMailBox[2];HostFilter sFilterRegister[28];
} HostCan;
typedef struct {volatile uint32_t DEMCR;} HostDebug;
typedef struct {volatile uint32_t CTRL,CYCCNT;} HostDwt;
extern HostCan host_can;
extern HostDebug host_debug;
extern HostDwt host_dwt;
#define CAN1 (&host_can)
#define CoreDebug (&host_debug)
#define DWT (&host_dwt)
#define CoreDebug_DEMCR_TRCENA_Msk (1u<<24)
#define DWT_CTRL_CYCCNTENA_Msk 1u
#define CAN1_RX0_IRQn 20
#define CAN_RI0R_IDE 4u
#define CAN_RI0R_RTR 2u
#define CAN_RF0R_RFOM0 32u
#define CAN_RF0R_FULL0 8u
#define CAN_RF0R_FOVR0 16u
#define CAN_MSR_INAK 1u
#define CAN_MCR_INRQ 1u
#define CAN_MCR_NART 16u
#define CAN_MCR_ABOM 64u
#define CAN_FMR_FINIT 1u
#define CAN_IER_FMPIE0 2u
#define CAN_IER_FFIE0 4u
#define CAN_IER_FOVIE0 8u
#define CAN_TSR_RQCP0 1u
#define CAN_TSR_TXOK0 2u
#define CAN_TSR_ALST0 4u
#define CAN_TSR_TERR0 8u
#define CAN_TSR_ABRQ0 128u
#define CAN_TSR_TME0 (1u<<26)
#define CAN_ESR_BOFF 4u
#define CAN_TI0R_TXRQ 1u
static inline void NVIC_DisableIRQ(int n) {(void)n;}
static inline void NVIC_EnableIRQ(int n) {(void)n;}
static inline void NVIC_ClearPendingIRQ(int n) {(void)n;}
static inline void NVIC_SetPriority(int n,int priority) {(void)n;(void)priority;}
#endif
