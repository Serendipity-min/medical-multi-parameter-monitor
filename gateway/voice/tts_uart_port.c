#include "tts_uart_port.h"
#if defined(MP_TTS_BENCH) || defined(MP_CLOUD_VOICE) || defined(MP_TTS_BROADCAST)
#include "stm32f4xx.h"
#include "stm32f4xx_gpio.h"
#include "stm32f4xx_rcc.h"
#include "stm32f4xx_usart.h"
#include <stdatomic.h>

#define RX_CAPACITY 32u
static uint8_t rx[RX_CAPACITY];
static _Atomic uint32_t head, tail;
static volatile uint32_t errors, overflow;
_Static_assert(ATOMIC_INT_LOCK_FREE == 2, "ISR queue requires lock-free 32-bit atomics");

void USART2_IRQHandler(void)
{
    uint32_t sr = USART2->SR;
    if (!(sr & (USART_SR_RXNE | USART_SR_ORE | USART_SR_NE | USART_SR_FE | USART_SR_PE))) return;
    uint8_t byte = (uint8_t)USART2->DR;
    if (sr & (USART_SR_ORE | USART_SR_NE | USART_SR_FE | USART_SR_PE)) { errors++; return; }
    uint32_t h = atomic_load_explicit(&head, memory_order_relaxed);
    uint32_t t = atomic_load_explicit(&tail, memory_order_acquire);
    if ((uint32_t)(h - t) >= RX_CAPACITY) { overflow++; return; }
    rx[h % RX_CAPACITY] = byte;
    atomic_store_explicit(&head, h + 1, memory_order_release);
}

int tts_uart_receive(void)
{
    uint32_t t = atomic_load_explicit(&tail, memory_order_relaxed);
    if (t == atomic_load_explicit(&head, memory_order_acquire)) return -1;
    int c = rx[t % RX_CAPACITY];
    atomic_store_explicit(&tail, t + 1, memory_order_release); return c;
}

static int write_byte(void *context, uint8_t c)
{
    (void)context;
    if (!(USART2->SR & USART_SR_TXE)) return 0;
    USART2->DR = c; return 1; /* 单步有界，不等发送器腾空，不打印日志。 */
}
static bool tx_idle(void *context) { (void)context; return (USART2->SR & USART_SR_TC) != 0; }
static void abort_tx(void *context)
{
    (void)context;
    /* 可能截断最后一字节；因此STOP仅为有界尝试，未收到确认绝不标为静音成功。 */
    USART2->CR1 &= ~USART_CR1_TE; USART2->CR1 |= USART_CR1_TE;
}
TtsIo tts_uart_io(void) { return (TtsIo){NULL, write_byte, tx_idle, abort_tx}; }
uint32_t tts_uart_errors(void) { return errors; }
uint32_t tts_uart_overflow(void) { return overflow; }

void tts_uart_init(void)
{
    RCC_AHB1PeriphClockCmd(RCC_AHB1Periph_GPIOA, ENABLE);
    RCC_APB1PeriphClockCmd(RCC_APB1Periph_USART2, ENABLE);
    GPIO_InitTypeDef gpio; GPIO_StructInit(&gpio);
    gpio.GPIO_Pin = GPIO_Pin_2 | GPIO_Pin_3; gpio.GPIO_Mode = GPIO_Mode_AF;
    gpio.GPIO_OType = GPIO_OType_PP; gpio.GPIO_PuPd = GPIO_PuPd_UP; gpio.GPIO_Speed = GPIO_Speed_25MHz;
    GPIO_Init(GPIOA, &gpio);
    GPIO_PinAFConfig(GPIOA, GPIO_PinSource2, GPIO_AF_USART2);
    GPIO_PinAFConfig(GPIOA, GPIO_PinSource3, GPIO_AF_USART2);
    USART_InitTypeDef uart; USART_StructInit(&uart); uart.USART_BaudRate = 9600;
    USART_Init(USART2, &uart); USART_Cmd(USART2, ENABLE);
    /* 优先级15低于CAN=1、ESP=0；中断仅入队，发送由主循环有界推进。 */
    NVIC_SetPriority(USART2_IRQn, 15); NVIC_EnableIRQ(USART2_IRQn);
    USART_ITConfig(USART2, USART_IT_RXNE, ENABLE);
}
#endif
