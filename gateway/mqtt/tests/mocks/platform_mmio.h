#ifndef PLATFORM_MMIO_H
#define PLATFORM_MMIO_H
#include <stdint.h>
typedef struct { volatile uint32_t SR,DR; } TestUsart;
extern TestUsart platform_usart[2];
#define USART1 (&platform_usart[0])
#define USART3 (&platform_usart[1])
#define USART_SR_RXNE 0x20u
#define USART_SR_TXE 0x80u
#define USART_SR_ORE 8u
#define USART_SR_NE 4u
#define USART_SR_FE 2u
#define __disable_irq() ((void)0)
#define __enable_irq() ((void)0)
void platform_test_tx(unsigned char byte);
#endif
