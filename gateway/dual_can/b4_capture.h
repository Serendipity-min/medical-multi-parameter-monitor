#ifndef B4_CAPTURE_H
#define B4_CAPTURE_H
#include <stdint.h>
#define B4_CAPTURE_BYTES 32u
enum { B4_CAP_RX=1, B4_CAP_TX_QUEUE=2, B4_CAP_TX_ACK=3, B4_CAP_TX_FAIL=4,
       B4_CAP_DIAG=5, B4_CAP_STOP=6, B4_CAP_BOOT=7, B4_CAP_MODEL=8,
       B4_CAP_START=9, B4_CAP_MODEL_TIME=10 };
typedef struct { uint32_t enqueued, dropped, sent, bytes, high_water, sequence; } B4CaptureDiag;
extern volatile B4CaptureDiag g_b4_capture;
void b4_capture_init(void);
uint16_t b4_capture_crc(const uint8_t *data, unsigned size);
int b4_capture_emit(unsigned kind, unsigned bus, unsigned id, unsigned dlc,
                    const uint8_t *data, uint32_t tick, uint32_t flags);
void b4_capture_drain(unsigned budget);
int b4_capture_pending(void);
/* 主循环仅发布包和唤醒TXE；硬件目标只允许USART1中断消费，不能并发轮询同一尾指针。 */
void b4_capture_uart_wake(void);
/* 仅硬件封装访问USART1；返回0表示忙，不阻塞或忙等。Host替身覆盖此边界。 */
int b4_capture_uart_put(uint8_t value);
void b4_capture_uart_init(void);
int b4_capture_uart_get(void);
/* 唯一接收命令是完整行B4START；每次启动只允许接受一次，不含复位/写内存路径。 */
int b4_capture_arm_byte(uint8_t byte);
#endif
