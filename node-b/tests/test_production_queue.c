#include <stdio.h>
#include <string.h>
#include "ecg_frame_queue.h"
static uint32_t checks, failures;
#define CHECK(x) do { checks++; if (!(x)) { failures++; printf("FAIL line %u\n", (unsigned)__LINE__); } } while (0)

int main(void)
{
    uint32_t i, round;
    EcgQueuedFrame in, out;
    memset(&in, 0, sizeof(in));
    EcgQueue_Reset();
    CHECK(sizeof(EcgQueuedFrame) == 24);
    CHECK(!EcgQueue_Pop(&out));
    CHECK(!EcgQueue_Push(0));
    CHECK(!EcgQueue_Pop(0));
    /* 充满并尝试溢出：确认拒绝新帧没有改写任何已排队负载。 */
    for (i = 0; i < ECG_QUEUE_CAPACITY; i++) {
        memset(in.bytes, (int)(i & 255), 9);
        in.flags = (uint8_t)(i & 1); in.irq_sequence = i; in.irq_cycles = i * 672000u; in.irq_ms = i * 4u;
        CHECK(EcgQueue_Push(&in));
    }
    CHECK(EcgQueue_Count() == ECG_QUEUE_CAPACITY);
    in.irq_sequence = 999; CHECK(!EcgQueue_Push(&in));
    for (i = 0; i < ECG_QUEUE_CAPACITY; i++) {
        CHECK(EcgQueue_Pop(&out)); CHECK(out.irq_sequence == i); CHECK(out.flags == (i & 1));
        CHECK(out.irq_cycles == i * 672000u && out.irq_ms == i * 4u);
        CHECK(out.bytes[0] == (i & 255) && out.bytes[8] == (i & 255));
    }
    CHECK(!EcgQueue_Pop(&out));
    /* 交错消费与生产，多次槽索引回绕；不把此顺序测试声称为多线程并发验证。 */
    for (round = 0; round < 5; round++) {
        for (i = 0; i < 93; i++) { in.irq_sequence = round * 1000u + i; CHECK(EcgQueue_Push(&in)); }
        for (i = 0; i < 93; i++) { CHECK(EcgQueue_Pop(&out)); CHECK(out.irq_sequence == round * 1000u + i); }
        CHECK(EcgQueue_Count() == 0);
    }
    /* 强制计数器跨 UINT32_MAX，验证无符号距离与槽号的回绕语义。 */
    EcgQueue_TestSeedEmpty(UINT32_MAX - 5u);
    for (i = 0; i < ECG_QUEUE_CAPACITY; i++) { in.irq_sequence = i; CHECK(EcgQueue_Push(&in)); }
    CHECK(!EcgQueue_Push(&in));
    for (i = 0; i < ECG_QUEUE_CAPACITY; i++) { CHECK(EcgQueue_Pop(&out)); CHECK(out.irq_sequence == i); }
    CHECK(EcgQueue_Count() == 0);
    printf("checks=%u failures=%u\n", (unsigned)checks, (unsigned)failures);
    return failures ? 1 : 0;
}
