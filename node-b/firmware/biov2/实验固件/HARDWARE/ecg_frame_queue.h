#ifndef ECG_FRAME_QUEUE_H
#define ECG_FRAME_QUEUE_H
#include <stdint.h>

#define ECG_QUEUE_CAPACITY 128u
/* 保存真实帧和 IRQ 入口信息；时间不是软件消费时刻，也不是外部探头测量。 */
typedef struct {
    uint8_t bytes[9];
    uint8_t flags; /* bit0：IRQ间隔异常，需要断段而非拼接旧滤波历史。 */
    uint32_t irq_sequence;
    uint32_t irq_cycles;
    uint32_t irq_ms;
} EcgQueuedFrame;

/* Reset 仅在 DRDY 生产者未启用时调用；一生产者 ISR、一消费者主循环。 */
void EcgQueue_Reset(void);
uint8_t EcgQueue_Push(const EcgQueuedFrame *frame);
uint8_t EcgQueue_Pop(EcgQueuedFrame *frame);
uint32_t EcgQueue_Count(void);
#ifdef ECG_QUEUE_HOST_TEST
/* 仅普通 Host 回绕测试使用，目标固件不包含该接口。 */
void EcgQueue_TestSeedEmpty(uint32_t value);
#endif
#endif
