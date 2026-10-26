#ifndef GATEWAY_PLATFORM_H
#define GATEWAY_PLATFORM_H
#include <stdint.h>
/* 与 MQTT 库无关的 ESP 二进制接口；长度与实际读写结果不转换成布尔值。 */
int esp_mqtt_send(const unsigned char *data, int length, uint32_t timeout_ms);
int esp_mqtt_recv(unsigned char *data, int length, uint32_t timeout_ms);
void esp_mqtt_reset(void);

void platform_init(void);
void platform_set_poll(void (*callback)(void));
/* 主循环、AT 等待和 JSON 序列化共用入口，内部提供重入保护。 */
void platform_poll(void);
/* C网络诊断只读接口：累计UART错误不随重连清零，控制台忙时避免递归输出。 */
uint32_t platform_uart_errors_total(void);
int platform_console_busy(void);
void console(const char *message);
#ifdef MP_CAN_RX_IRQ
/* 仅供低频诊断延后输出；不能借此暂停CAN接收或模型轮询。 */
int platform_console_busy(void);
#endif
int console_char(void);
/* UART当前门禁与累计错误分离；累计值供H3隔离窗口比较。 */
uint32_t platform_uart_errors_total(void);
int at_command(const char *command, uint32_t timeout_ms);
const char *at_response(void);
void delay_ms(uint32_t milliseconds);
extern volatile uint32_t g_uptime_ms;
#endif
