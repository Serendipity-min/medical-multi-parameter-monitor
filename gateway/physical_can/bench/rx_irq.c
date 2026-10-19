/* 中断只释放硬件FIFO并发布固定大小项；没有UART、堆、协议回调或Router操作。 */
#include "rx_irq.h"
#ifdef MP_CAN_RX_IRQ
#include "gateway_platform.h"
#else
#include "bench.h"
#endif
#include <limits.h>

_Static_assert((BENCH_RX_CAPACITY&(BENCH_RX_CAPACITY-1u))==0,"power-of-two queue required");
_Static_assert(ATOMIC_INT_LOCK_FREE==2,"ISR queue requires lock-free word atomics");
BenchRxPath bench_rx_path;

static uint32_t status_and_flags(void) {
    uint32_t status=bench_hw_rx_status();
    uint32_t flags=status&(BENCH_FIFO_FULL|BENCH_FIFO_OVERRUN);
    if(status&BENCH_FIFO_FULL) bench_rx_path.hw_full++;
    if(status&BENCH_FIFO_OVERRUN) {
        bench_rx_path.hw_overrun++;bench_rx_path.fault_bits|=BENCH_RX_HW_LOSS;
    }
    /* FULL/FOVR是写1清除，不能用读改写顺手释放FIFO或重复清除其他状态。 */
    if(flags) bench_hw_rx_clear(flags);
    uint32_t depth=status&BENCH_FIFO_PENDING;
    if(depth>bench_rx_path.fifo_depth_max) bench_rx_path.fifo_depth_max=depth;
    return status;
}
void bench_rx_irq(void) {
    uint32_t started=bench_clock_cycles();bench_rx_path.isr_calls++;
    unsigned budget=32;
    while((status_and_flags()&BENCH_FIFO_PENDING) && budget--) {
        BenchRxItem item;uint32_t flags;
        item.at_ms=g_uptime_ms;item.at_cycles=bench_clock_cycles();
        bench_hw_rx_read(&item.frame,&flags);
        bench_hw_rx_release();bench_rx_path.isr_frames++;
        if(flags || item.frame.ident>0x7ffu || item.frame.dlc>8u) {
            bench_rx_path.bad++;bench_rx_path.fault_bits|=BENCH_RX_BAD_FRAME;continue;
        }
        /* 首个丢失后锁止协议准入，继续快速释放硬件帧，另记故障后丢弃，避免伪装正常。 */
        if(bench_rx_path.fault_bits) {bench_rx_path.fault_discard++;continue;}
        uint32_t head=atomic_load_explicit(&bench_rx_path.head,memory_order_relaxed);
        uint32_t tail=atomic_load_explicit(&bench_rx_path.tail,memory_order_acquire);
        uint32_t used=head-tail;
        if(used>=BENCH_RX_CAPACITY) {
            bench_rx_path.sw_overrun++;bench_rx_path.fault_bits|=BENCH_RX_SW_LOSS;continue;
        }
        bench_rx_path.items[head&(BENCH_RX_CAPACITY-1u)]=item;
        atomic_store_explicit(&bench_rx_path.head,head+1u,memory_order_release);
        if(used+1u>bench_rx_path.high_water) bench_rx_path.high_water=used+1u;
    }
    uint32_t elapsed=bench_clock_cycles()-started;
    if(elapsed>bench_rx_path.isr_cycles_max) bench_rx_path.isr_cycles_max=elapsed;
}
bool bench_rx_peek(BenchRxItem *item) {
    uint32_t tail=atomic_load_explicit(&bench_rx_path.tail,memory_order_relaxed);
    uint32_t head=atomic_load_explicit(&bench_rx_path.head,memory_order_acquire);
    if(head==tail) return false;
    *item=bench_rx_path.items[tail&(BENCH_RX_CAPACITY-1u)];return true;
}
bool bench_rx_take(BenchRxItem *item) {
    uint32_t tail=atomic_load_explicit(&bench_rx_path.tail,memory_order_relaxed);
    uint32_t head=atomic_load_explicit(&bench_rx_path.head,memory_order_acquire);
    if(head==tail) return false;
    *item=bench_rx_path.items[tail&(BENCH_RX_CAPACITY-1u)];
    atomic_store_explicit(&bench_rx_path.tail,tail+1u,memory_order_release);
    return true;
}
uint32_t bench_rx_depth(void) {
    uint32_t head=atomic_load_explicit(&bench_rx_path.head,memory_order_acquire);
    return head-atomic_load_explicit(&bench_rx_path.tail,memory_order_relaxed);
}
void bench_rx_discard_pending(void) {
    uint32_t head=atomic_load_explicit(&bench_rx_path.head,memory_order_relaxed);
    uint32_t tail=atomic_load_explicit(&bench_rx_path.tail,memory_order_relaxed);
    bench_rx_path.reinit_discard+=head-tail;
    atomic_store_explicit(&bench_rx_path.tail,head,memory_order_release);
}
