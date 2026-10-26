/* CH340 USART1：PA9原始取证发送，PA10只接受一次固定START，不支持控制台/复位命令。 */
#include "b4_capture.h"
#include "stm32f4xx.h"
#include "stm32f4xx_gpio.h"
#include "stm32f4xx_rcc.h"
#include "stm32f4xx_usart.h"
#include "misc.h"
void b4_capture_uart_init(void) {
    RCC_AHB1PeriphClockCmd(RCC_AHB1Periph_GPIOA,ENABLE);
    RCC_APB2PeriphClockCmd(RCC_APB2Periph_USART1,ENABLE);
    GPIO_PinAFConfig(GPIOA,GPIO_PinSource9,GPIO_AF_USART1);
    GPIO_PinAFConfig(GPIOA,GPIO_PinSource10,GPIO_AF_USART1);
    GPIO_InitTypeDef gpio; GPIO_StructInit(&gpio);
    gpio.GPIO_Pin=GPIO_Pin_9 | GPIO_Pin_10; gpio.GPIO_Mode=GPIO_Mode_AF;
    gpio.GPIO_OType=GPIO_OType_PP; gpio.GPIO_PuPd=GPIO_PuPd_UP;
    gpio.GPIO_Speed=GPIO_Speed_50MHz; GPIO_Init(GPIOA,&gpio);
    USART_InitTypeDef uart; USART_StructInit(&uart);
    /* 230400为原始帧和重建校验留余量，不能让115200接近满载反向阻塞CAN主循环。 */
    uart.USART_BaudRate=230400; uart.USART_Mode=USART_Mode_Tx | USART_Mode_Rx;
    USART_Init(USART1,&uart); USART_Cmd(USART1,ENABLE);
    /* 字节服务独立于CANopen/模型主循环；优先级低于CAN接收，不在中断中格式化或复制包。 */
    NVIC_InitTypeDef nvic; nvic.NVIC_IRQChannel=USART1_IRQn;
    nvic.NVIC_IRQChannelPreemptionPriority=4; nvic.NVIC_IRQChannelSubPriority=0;
    nvic.NVIC_IRQChannelCmd=ENABLE; NVIC_Init(&nvic);
}
void b4_capture_uart_wake(void) {
    if (b4_capture_pending()) USART_ITConfig(USART1,USART_IT_TXE,ENABLE);
}
void USART1_IRQHandler(void) {
    if ((USART1->CR1 & USART_CR1_TXEIE) && (USART1->SR & USART_SR_TXE)) {
        b4_capture_drain(2);
        /* 空队列立即关TXE，避免无数据时中断风暴；生产者下次发布后会重新唤醒。 */
        if (!b4_capture_pending()) USART_ITConfig(USART1,USART_IT_TXE,DISABLE);
    }
}
int b4_capture_uart_get(void) {
    if (!(USART1->SR & USART_SR_RXNE)) return -1;
    return (int)(USART1->DR & 0xffu);
}
int b4_capture_uart_put(uint8_t byte) {
    if (!(USART1->SR & USART_SR_TXE)) return 0;
    USART1->DR=byte; return 1;
}
