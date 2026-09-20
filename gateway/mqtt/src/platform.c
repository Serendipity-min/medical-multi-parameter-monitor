/* UART3 中断接收、主循环同步 AT；敏感命令和原始回复不写入控制台。 */
#include "gateway_platform.h"
#include "stm32f4xx.h"
#include "stm32f4xx_gpio.h"
#include "stm32f4xx_rcc.h"
#include "stm32f4xx_usart.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#define CAPACITY 8192U
static volatile unsigned char ring[CAPACITY];
static volatile uint32_t head, tail, errors;
static unsigned char reply[4096], network_bytes[256];
static unsigned int reply_length, network_length, network_offset;
static void (*poll_callback)(void);
static int polling;
void platform_set_poll(void (*callback)(void)){poll_callback=callback;}
void mp_model_poll(void){platform_poll();}
void platform_poll(void){
  /* 回调只跑 CAN/采集/入队，不调用网络，重入保护覆盖控制台诊断。 */
  if(poll_callback&&!polling){polling=1;poll_callback();polling=0;}
}
void USART3_IRQHandler(void)
{
  uint32_t status = USART3->SR;
  if (!(status & (USART_SR_RXNE | USART_SR_ORE | USART_SR_NE | USART_SR_FE))) return;
  unsigned char value = (unsigned char)USART3->DR;
  if (status & (USART_SR_ORE | USART_SR_NE | USART_SR_FE)) errors++;
  if (status & USART_SR_RXNE) {
    uint32_t next = (head + 1U) % CAPACITY;
    if (next == tail) errors++;
    else { ring[head] = value; head = next; }
  }
}
static int receive_byte(void)
{
  if (tail == head) return -1;
  int value = ring[tail]; tail = (tail + 1U) % CAPACITY; return value;
}
static void send_bytes(const unsigned char *data, unsigned int length)
{
  for (unsigned int i = 0; i < length; ++i) {
    while (!(USART3->SR & USART_SR_TXE)) { platform_poll(); }
    USART3->DR = data[i];
  }
}
void console(const char *message)
{
  while (*message) { while (!(USART1->SR & USART_SR_TXE)) { platform_poll(); } USART1->DR = (unsigned char)*message++; }
}
int console_char(void) { return (USART1->SR & USART_SR_RXNE) ? (int)(USART1->DR & 255U) : -1; }
void TimerInit(Timer *timer) { timer->deadline = g_uptime_ms; }
char TimerIsExpired(Timer *timer) { return (int32_t)(g_uptime_ms - timer->deadline) >= 0; }
void TimerCountdownMS(Timer *timer, unsigned int ms) { timer->deadline = g_uptime_ms + ms; }
void TimerCountdown(Timer *timer, unsigned int seconds) { TimerCountdownMS(timer, seconds * 1000U); }
int TimerLeftMS(Timer *timer) { int32_t left = (int32_t)(timer->deadline - g_uptime_ms); return left > 0 ? left : 0; }
void delay_ms(uint32_t ms) { Timer timer; TimerCountdownMS(&timer, ms); while (!TimerIsExpired(&timer)) { platform_poll(); } }
static int ends_with(const char *suffix)
{
  size_t length = strlen(suffix);
  return reply_length >= length && memcmp(reply + reply_length - length, suffix, length) == 0;
}
static int await_reply(uint32_t timeout, int prompt, int sent)
{
  Timer timer; TimerCountdownMS(&timer, timeout); reply_length = 0;
  while (!TimerIsExpired(&timer)) {
    platform_poll();
    if (errors) return 0;
    int value = receive_byte(); if (value < 0) continue;
    if (reply_length >= sizeof(reply) - 1U) return 0;
    reply[reply_length++] = (unsigned char)value; reply[reply_length] = 0;
    /* 尾部按长度判断，不能用 strlen 解析含 NUL 的 MQTT 二进制回复。 */
    if (ends_with("\r\nERROR\r\n") || ends_with("\r\nFAIL\r\n") || ends_with("SEND FAIL\r\n")) return 0;
    if (prompt ? value == '>' : sent ? ends_with("SEND OK\r\n") : ends_with("\r\nOK\r\n")) return 1;
  }
  return 0;
}
int at_command(const char *command, uint32_t timeout)
{
  send_bytes((const unsigned char *)command, strlen(command)); send_bytes((const unsigned char *)"\r\n", 2);
  return await_reply(timeout, strncmp(command, "AT+CIPSEND=", 11) == 0, 0);
}
const char *at_response(void) { return (const char *)reply; }
static int mqtt_write(Network *network, unsigned char *data, int length, int timeout)
{
  (void)network;
  if (length <= 0 || length > 2048) return -1;
  char command[40]; (void)snprintf(command, sizeof(command), "AT+CIPSEND=%d", length);
  if (!at_command(command, (uint32_t)timeout)) { console("GW WRITE_PROMPT_FAIL\r\n"); return -1; }
  send_bytes(data, (unsigned int)length);
  if (!await_reply((uint32_t)timeout, 0, 1)) { console("GW WRITE_SEND_FAIL\r\n"); return -1; }
  if (data[0] == 0x10U) console("GW CONNECT_PACKET_SENT\r\n");
  return length;
}
static int mqtt_read(Network *network, unsigned char *data, int length, int timeout)
{
  (void)network; int copied = 0; Timer timer;
  TimerCountdownMS(&timer, (unsigned int)(timeout > 0 ? timeout : 1));
  while (copied < length) {
    platform_poll();
    if (network_offset < network_length) { data[copied++] = network_bytes[network_offset++]; continue; }
    if (TimerIsExpired(&timer)) break;
    network_offset = network_length = 0;
    /* 此固件在 SSL 尚无数据时读数据返回 ERROR，先查询接收长度再读取。 */
    if (!at_command("AT+CIPRECVLEN?", 1000)) return -1;
    char *available = strstr((char *)reply, "+CIPRECVLEN:");
    if (!available) return -1;
    if (!strtoul(available+12, NULL, 10)) { delay_ms(10); continue; }
    if (!at_command("AT+CIPRECVDATA=256", 1000)) { console("GW READ_AT_FAIL\r\n"); return -1; }
    /* 固件被动接收模式：长度明确，原样保留二进制包；未收到数据不伪造字节。 */
    char *header = strstr((char *)reply, "+CIPRECVDATA:");
    if (!header) { console("GW READ_HEADER_FAIL\r\n"); return -1; }
    char *end = NULL; unsigned long size = strtoul(header + 13, &end, 10);
    if (!end || *end != ',' || size > sizeof(network_bytes) || (unsigned char *)(end+1)+size > reply+reply_length) { console("GW READ_LENGTH_FAIL\r\n"); return -1; }
    memcpy(network_bytes, end+1, size); network_length = (unsigned int)size;
    /* 只报告 CONNACK 状态码，不输出 MQTT CONNECT 内容或通用载荷。 */
    if (size == 4U && network_bytes[0] == 0x20U) {
      char diagnostic[40]; (void)snprintf(diagnostic,sizeof(diagnostic),"GW CONNACK_CODE %u\r\n",network_bytes[3]); console(diagnostic);
    }
    if (!size) delay_ms(5);
  }
  return copied;
}
void network_init(Network *network)
{
  network->mqttread = mqtt_read; network->mqttwrite = mqtt_write;
  network_length = network_offset = 0;
  /* 上一连接留下的异步提示不是新 MQTT 包，建立 SSL 前重新初始化队列。 */
  __disable_irq(); tail = head; errors = 0; __enable_irq();
}
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
  USART_ITConfig(USART3, USART_IT_RXNE, ENABLE);
  NVIC_EnableIRQ(USART3_IRQn);
}

void platform_init(void)
{
  init_uart();
  if (SysTick_Config(SystemCoreClock/1000U)) while (1) { }
}
