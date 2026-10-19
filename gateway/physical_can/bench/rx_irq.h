#ifndef MP_BENCH_RX_IRQ_H
#define MP_BENCH_RX_IRQ_H
#include "physical.h"
#include <stdatomic.h>

#define BENCH_RX_CAPACITY 128u
enum { BENCH_FIFO_PENDING=3u, BENCH_FIFO_FULL=8u, BENCH_FIFO_OVERRUN=16u };
enum { BENCH_RX_HW_LOSS=1u, BENCH_RX_SW_LOSS=2u, BENCH_RX_BAD_FRAME=4u };
typedef struct {
    MpCanFrame frame;
    uint32_t at_ms,at_cycles;
} BenchRxItem;
typedef struct {
    /* 一个ISR生产者、一个主循环消费者；release/acquire发布完整帧，不靠volatile充当屏障。 */
    _Atomic uint32_t head,tail;
    BenchRxItem items[BENCH_RX_CAPACITY];
    volatile uint32_t hw_overrun,hw_full,sw_overrun,bad,fault_bits;
    volatile uint32_t high_water,isr_calls,isr_frames,isr_cycles_max,fifo_depth_max;
    volatile uint32_t reinit_discard,fault_discard;
} BenchRxPath;
extern BenchRxPath bench_rx_path;
void bench_rx_irq(void);
/* 消费前查看IRQ时刻；仅单消费者读取，不推进tail，避免提前覆盖RPDO。 */
bool bench_rx_peek(BenchRxItem *item);
bool bench_rx_take(BenchRxItem *item);
uint32_t bench_rx_depth(void);
/* 仅在CAN RX IRQ已禁用时清空待处理项；保留累计丢失、故障和高水位。 */
void bench_rx_discard_pending(void);

/* 固定CAN1的薄寄存器边界；Host替身实现W1C/释放FIFO语义，ARM实现只做MMIO。 */
uint32_t bench_hw_rx_status(void);
void bench_hw_rx_read(MpCanFrame *frame,uint32_t *type_flags);
void bench_hw_rx_release(void);
void bench_hw_rx_clear(uint32_t flags);
uint32_t bench_clock_cycles(void);
#endif
