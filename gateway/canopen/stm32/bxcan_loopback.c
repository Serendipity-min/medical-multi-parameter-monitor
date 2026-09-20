/* F407 内部静默 loopback：经过真实 CAN1 外设，TX 保持未配置。 */
#include "mp_can_driver.h"
#include "gateway_platform.h"
#include "stm32f4xx.h"
#include "stm32f4xx_rcc.h"
#include "stm32f4xx_gpio.h"
#include <string.h>
int mp_bxcan_init(void){
  /* bxCAN 离开初始化仍需在 RX 观察到隐性电平；PA11 仅设 AF 输入上拉。 */
  RCC_AHB1PeriphClockCmd(RCC_AHB1Periph_GPIOA,ENABLE);
  GPIO_InitTypeDef gpio;GPIO_StructInit(&gpio);gpio.GPIO_Pin=GPIO_Pin_11;gpio.GPIO_Mode=GPIO_Mode_AF;gpio.GPIO_PuPd=GPIO_PuPd_UP;
  GPIO_PinAFConfig(GPIOA,GPIO_PinSource11,GPIO_AF_CAN1);GPIO_Init(GPIOA,&gpio);
  RCC_APB1PeriphClockCmd(RCC_APB1Periph_CAN1,ENABLE);
  CAN1->MCR=CAN_MCR_INRQ|CAN_MCR_ABOM;
  uint32_t start=g_uptime_ms;
  while(!(CAN1->MSR&CAN_MSR_INAK))if(g_uptime_ms-start>100)return 0;
  /* APB1=16MHz，预分频2，1+13+2=16 TQ，对应 500 kbit/s。 */
  CAN1->BTR=(3UL<<30)|(1UL<<20)|(12UL<<16)|1UL;
  CAN1->FMR|=CAN_FMR_FINIT;CAN1->FA1R&=~1UL;CAN1->FS1R|=1;CAN1->FM1R&=~1UL;CAN1->FFA1R&=~1UL;
  CAN1->sFilterRegister[0].FR1=0;CAN1->sFilterRegister[0].FR2=0;CAN1->FA1R|=1;CAN1->FMR&=~CAN_FMR_FINIT;
  CAN1->MCR&=~CAN_MCR_INRQ;start=g_uptime_ms;
  while(CAN1->MSR&CAN_MSR_INAK)if(g_uptime_ms-start>100)return 0;
  return 1;
}
void mp_bus_hardware_poll(void){
  unsigned budget=3;
  while((CAN1->RF0R&3)&&budget--){
    MpCanFrame f;uint32_t id=CAN1->sFIFOMailBox[0].RIR;
    f.ident=(uint16_t)(id>>21);f.dlc=CAN1->sFIFOMailBox[0].RDTR&15;
    uint32_t lo=CAN1->sFIFOMailBox[0].RDLR,hi=CAN1->sFIFOMailBox[0].RDHR;
    memcpy(f.data,&lo,4);memcpy(f.data+4,&hi,4);
    CAN1->RF0R=CAN_RF0R_RFOM0;
    if(!(id&(CAN_RI0R_IDE|CAN_RI0R_RTR)))mp_bus_receive(&f);
  }
}
int mp_bus_transmit(MpCanFrame *frame){
  mp_bus_hardware_poll();
  if(!(CAN1->TSR&CAN_TSR_TME0))return 0;
  uint32_t lo,hi;memcpy(&lo,frame->data,4);memcpy(&hi,frame->data+4,4);
  CAN1->sTxMailBox[0].TDTR=frame->dlc;CAN1->sTxMailBox[0].TDLR=lo;CAN1->sTxMailBox[0].TDHR=hi;
  CAN1->sTxMailBox[0].TIR=((uint32_t)frame->ident<<21)|CAN_TI0R_TXRQ;return 1;
}
