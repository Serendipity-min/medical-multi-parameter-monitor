#ifndef MQTT_HOST_PLATFORM_H
#define MQTT_HOST_PLATFORM_H

#include <stddef.h>

/* 仅内存回调与固定计时值；测试程序没有 socket、串口或硬件入口。 */
typedef struct Timer {
    unsigned int remaining_ms;
} Timer;

typedef struct Network Network;
struct Network {
    int (*mqttread)(Network *, unsigned char *, int, int);
    int (*mqttwrite)(Network *, unsigned char *, int, int);
    const unsigned char *input;
    size_t input_size;
    size_t input_offset;
    unsigned int read_calls;
    unsigned int write_calls;
};

#endif
