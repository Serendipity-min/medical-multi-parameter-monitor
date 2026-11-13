#ifndef P4_PLATFORM_FOR_BROKER_H
#define P4_PLATFORM_FOR_BROKER_H
#include "gateway_platform.h"
/* 仅给固定 P4 源的普通 Broker 对照提供原 Paho 平台 ABI，不进入 P5 固件。 */
typedef struct { uint32_t deadline; } Timer;
typedef struct Network Network;
struct Network
{
    int (*mqttread)(Network *, unsigned char *, int, int);
    int (*mqttwrite)(Network *, unsigned char *, int, int);
};
void TimerInit(Timer *);
char TimerIsExpired(Timer *);
void TimerCountdownMS(Timer *, unsigned int);
void TimerCountdown(Timer *, unsigned int);
int TimerLeftMS(Timer *);
void network_init(Network *);
#endif
