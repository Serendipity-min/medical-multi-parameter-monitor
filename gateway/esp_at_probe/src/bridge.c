/* 临时串口桥仅用于本机 TLS 配置诊断，不能替代最终 STM32 MQTT 客户端。 */
#include "main.h"
#include "stm32f4xx_gpio.h"
#include "stm32f4xx_rcc.h"
#include "stm32f4xx_usart.h"
#include <stdint.h>
#define CAPACITY 8192U
static volatile uint8_t incoming[2][CAPACITY];
static volatile uint32_t head[2], tail[2], errors;
static void receive(USART_TypeDef *uart, unsigned int channel)
{
  uint32_t status = uart->SR;
  if (!(status & (USART_SR_RXNE | USART_SR_ORE | USART_SR_NE | USART_SR_FE))) return;
  uint8_t value = (uint8_t)uart->DR;
  if (status & (USART_SR_ORE | USART_SR_NE | USART_SR_FE)) errors++;
  if (status & USART_SR_RXNE) {
    uint32_t next = (head[channel] + 1U) % CAPACITY;
    if (next == tail[channel]) errors++;
    else { incoming[channel][head[channel]] = value; head[channel] = next; }
  }
}
void USART1_IRQHandler(void) { receive(USART1, 0); }
void USART3_IRQHandler(void) { receive(USART3, 1); }
static void init_uart(void)
{
  GPIO_InitTypeDef gpio;
  USART_InitTypeDef uart;
  RCC_AHB1PeriphClockCmd(RCC_AHB1Periph_GPIOA | RCC_AHB1Periph_GPIOB, ENABLE);
  RCC_APB2PeriphClockCmd(RCC_APB2Periph_USART1, ENABLE);
  RCC_APB1PeriphClockCmd(RCC_APB1Periph_USART3, ENABLE);
  GPIO_StructInit(&gpio);
  gpio.GPIO_Pin = GPIO_Pin_9 | GPIO_Pin_10;
  gpio.GPIO_Mode = GPIO_Mode_AF;
  gpio.GPIO_OType = GPIO_OType_PP;
  gpio.GPIO_PuPd = GPIO_PuPd_UP;
  gpio.GPIO_Speed = GPIO_Speed_50MHz;
  GPIO_PinAFConfig(GPIOA, GPIO_PinSource9, GPIO_AF_USART1);
  GPIO_PinAFConfig(GPIOA, GPIO_PinSource10, GPIO_AF_USART1);
  GPIO_Init(GPIOA, &gpio);
  gpio.GPIO_Pin = GPIO_Pin_10 | GPIO_Pin_11;
  GPIO_PinAFConfig(GPIOB, GPIO_PinSource10, GPIO_AF_USART3);
  GPIO_PinAFConfig(GPIOB, GPIO_PinSource11, GPIO_AF_USART3);
  GPIO_Init(GPIOB, &gpio);
  USART_StructInit(&uart);
  uart.USART_BaudRate = 115200;
  USART_Init(USART1, &uart);
  USART_Init(USART3, &uart);
  USART_Cmd(USART1, ENABLE);
  USART_Cmd(USART3, ENABLE);
  USART_ITConfig(USART1, USART_IT_RXNE, ENABLE);
  USART_ITConfig(USART3, USART_IT_RXNE, ENABLE);
  NVIC_EnableIRQ(USART1_IRQn);
  NVIC_EnableIRQ(USART3_IRQn);
}

int main(void)
{
  init_uart();
  /* 接收放在中断，发送仅在 TXE 时取一个字节，两个方向互不阻塞。
     环形队列边界使用单生产者/单消费者索引，避免复制完整缓冲。 */
  while (1) {
    if (tail[0] != head[0] && (USART3->SR & USART_SR_TXE)) {
      USART3->DR = incoming[0][tail[0]];
      tail[0] = (tail[0] + 1U) % CAPACITY;
    }
    if (tail[1] != head[1] && (USART1->SR & USART_SR_TXE)) {
      USART1->DR = incoming[1][tail[1]];
      tail[1] = (tail[1] + 1U) % CAPACITY;
    }
    /* 发生溢出时停止转发，强制上位机超时；不得悄悄把残缺数据当成成功。 */
    if (errors) while (1) { }
  }
}
