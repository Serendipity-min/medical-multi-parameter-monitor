#include "ecg_frame_queue.h"
#ifdef ECG_QUEUE_HOST_TEST
#define ECG_BARRIER() __sync_synchronize()
#else
#include "stm32f4xx.h"
#define ECG_BARRIER() __DMB()
#endif

#if (ECG_QUEUE_CAPACITY & (ECG_QUEUE_CAPACITY - 1u)) != 0
#error ECG_QUEUE_CAPACITY_must_be_power_of_two
#endif
static EcgQueuedFrame slots[ECG_QUEUE_CAPACITY];
static volatile uint32_t head, tail;

void EcgQueue_Reset(void) { head = 0; tail = 0; }

uint8_t EcgQueue_Push(const EcgQueuedFrame *frame)
{
    uint32_t next = head;
    if (frame == 0) { return 0; }
    /* 满时拒绝新帧，保留已排队帧顺序；调用者必须显式计数，不能覆盖旧证据。 */
    if ((uint32_t)(next - tail) >= ECG_QUEUE_CAPACITY) { return 0; }
    slots[next & (ECG_QUEUE_CAPACITY - 1u)] = *frame;
    ECG_BARRIER(); /* 帧内容先完成，再向消费者发布 head。 */
    head = next + 1u;
    return 1;
}

uint8_t EcgQueue_Pop(EcgQueuedFrame *frame)
{
    uint32_t current = tail;
    if (frame == 0 || current == head) { return 0; }
    ECG_BARRIER(); /* 看到已发布 head 后读取内容，避免编译器/总线提前取数据。 */
    *frame = slots[current & (ECG_QUEUE_CAPACITY - 1u)];
    ECG_BARRIER(); /* 完成复制后才释放槽；ISR 不能覆盖正在复制的帧。 */
    tail = current + 1u;
    return 1;
}

uint32_t EcgQueue_Count(void) { return (uint32_t)(head - tail); }
#ifdef ECG_QUEUE_HOST_TEST
void EcgQueue_TestSeedEmpty(uint32_t value) { head = value; tail = value; }
#endif
