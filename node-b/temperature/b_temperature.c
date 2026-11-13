/* UART4只接收PC11；PC10保持输入，不写模块寄存器、不启用发送器。 */
#include "b_temperature.h"
#include "stm32f4xx.h"
#include "stm32f4xx_gpio.h"
#include "stm32f4xx_rcc.h"
#include "stm32f4xx_usart.h"
#include "misc.h"
#include "timer.h"
#include <string.h>
static struct { uint32_t ms; uint8_t byte; } rx[128];
static volatile uint32_t head,tail,broken;
BTempDiag g_b_temp;
void BTemp_Init(void) {
    GPIO_InitTypeDef pin;USART_InitTypeDef uart;NVIC_InitTypeDef irq;
    memset(&g_b_temp,0,sizeof(g_b_temp));head=tail=broken=0;
    RCC_AHB1PeriphClockCmd(RCC_AHB1Periph_GPIOC,ENABLE);
    RCC_APB1PeriphClockCmd(RCC_APB1Periph_UART4,ENABLE);
    GPIO_StructInit(&pin);pin.GPIO_Pin=GPIO_Pin_10;pin.GPIO_Mode=GPIO_Mode_IN;pin.GPIO_PuPd=GPIO_PuPd_UP;
    GPIO_Init(GPIOC,&pin);
    pin.GPIO_Pin=GPIO_Pin_11;pin.GPIO_Mode=GPIO_Mode_AF;
    GPIO_Init(GPIOC,&pin);GPIO_PinAFConfig(GPIOC,GPIO_PinSource11,GPIO_AF_UART4);
    USART_StructInit(&uart);uart.USART_BaudRate=9600;uart.USART_Mode=USART_Mode_Rx;
    USART_Init(UART4,&uart);USART_ITConfig(UART4,USART_IT_RXNE,ENABLE);USART_Cmd(UART4,ENABLE);
    irq.NVIC_IRQChannel=UART4_IRQn;irq.NVIC_IRQChannelPreemptionPriority=3;
    irq.NVIC_IRQChannelSubPriority=1;irq.NVIC_IRQChannelCmd=ENABLE;NVIC_Init(&irq);
}
void UART4_IRQHandler(void) {
    uint32_t status=UART4->SR;
    if (status & (USART_SR_RXNE|USART_SR_ORE|USART_SR_NE|USART_SR_FE|USART_SR_PE)) {
        uint8_t byte=(uint8_t)UART4->DR;
        if (status & (USART_SR_ORE|USART_SR_NE|USART_SR_FE|USART_SR_PE)) {
            g_b_temp.uart_errors++;broken=1;return;
        }
        uint32_t next=(head+1u)%128u;g_b_temp.received++;
        if (next==tail) { g_b_temp.overflow++;broken=1;return; }
        rx[head].byte=byte;rx[head].ms=TimeBase_GetMs();__DMB();head=next;
    }
}
void BTemp_Task(uint32_t now) {
    if (broken) {
        NVIC_DisableIRQ(UART4_IRQn);tail=head;broken=0;NVIC_EnableIRQ(UART4_IRQn);
        g_b_temp.module.used=0;g_b_temp.module.present=0;
    }
    for (unsigned budget=0;tail!=head && budget<32u;budget++) {
        uint8_t byte=rx[tail].byte;uint32_t received=rx[tail].ms;
        tail=(tail+1u)%128u;gy641_feed(&g_b_temp.module,byte,received);
    }
    (void)now;
}
int BTemp_Get(uint32_t now, uint16_t *centi) {
    return !broken && gy641_object(&g_b_temp.module,now,centi);
}
