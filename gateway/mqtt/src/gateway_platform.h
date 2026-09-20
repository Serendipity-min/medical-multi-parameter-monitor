#ifndef GATEWAY_PLATFORM_H
#define GATEWAY_PLATFORM_H
#include <stdint.h>

typedef struct
{
    /* Paho 超时使用启动后的单调毫秒，与采集时间的 UTC 秒基准分离。 */
    uint32_t deadline;
} Timer;
typedef struct Network Network;

struct Network
{
    /* 同步读写适配内部可协作推进 CAN，但不可重入另一次 MQTT 网络调用。 */
    int (*mqttread)(Network *, unsigned char *, int, int);
    int (*mqttwrite)(Network *, unsigned char *, int, int);
};

void TimerInit(Timer *timer);
char TimerIsExpired(Timer *timer);
void TimerCountdownMS(Timer *timer, unsigned int milliseconds);
void TimerCountdown(Timer *timer, unsigned int seconds);
int TimerLeftMS(Timer *timer);
void platform_init(void);
void platform_set_poll(void (*callback)(void));
/* 主循环、AT 等待和 JSON 序列化共用入口，内部提供重入保护。 */
void platform_poll(void);
void console(const char *message);
int console_char(void);
int at_command(const char *command, uint32_t timeout_ms);
const char *at_response(void);
void network_init(Network *network);
void delay_ms(uint32_t milliseconds);
extern volatile uint32_t g_uptime_ms;
#endif
