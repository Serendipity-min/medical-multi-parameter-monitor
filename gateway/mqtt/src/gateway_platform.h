#ifndef GATEWAY_PLATFORM_H
#define GATEWAY_PLATFORM_H
#include <stdint.h>
typedef struct { uint32_t deadline; } Timer;
typedef struct Network Network;
struct Network {
  int (*mqttread)(Network *, unsigned char *, int, int);
  int (*mqttwrite)(Network *, unsigned char *, int, int);
};
void TimerInit(Timer *timer);
char TimerIsExpired(Timer *timer);
void TimerCountdownMS(Timer *timer, unsigned int milliseconds);
void TimerCountdown(Timer *timer, unsigned int seconds);
int TimerLeftMS(Timer *timer);
void platform_init(void);
void console(const char *message);
int console_char(void);
int at_command(const char *command, uint32_t timeout_ms);
const char *at_response(void);
void network_init(Network *network);
void delay_ms(uint32_t milliseconds);
extern volatile uint32_t g_uptime_ms;
#endif
