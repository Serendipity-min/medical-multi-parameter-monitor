/* 原_sbrk行为联测；合成静态数组模拟链接边界，不申请系统brk或接触MCU。 */
#include "probe_events.h"
#include <assert.h>
#include <errno.h>
#include <stddef.h>
#include <stdio.h>
unsigned char diagnostic_test_heap[24576];
__asm__(".global _heap_start\n.set _heap_start, diagnostic_test_heap\n.global _heap_end\n.set _heap_end, diagnostic_test_heap+24576\n");
extern void *_sbrk(ptrdiff_t increment);
uint32_t probe_host_cycle(void) { return 0; }
uint32_t probe_host_ms(void) { return 0; }
int probe_host_clock_available(void) { return 1; }
void probe_host_barrier(void) { }
int main(void)
{
    probe_init(16000000);
    assert(_sbrk(100) == diagnostic_test_heap && probe_state.heap_peak_bytes == 100);
    puts("PASS heap_overlay_preserves_start_and_peak");
    errno = 0;
    assert(_sbrk(-1) == (void *)-1 && errno == ENOMEM && probe_state.heap_enomem_count == 1);
    assert(probe_state.heap_peak_bytes == 100);
    puts("PASS heap_overlay_negative_request_keeps_original_enomem");
    assert(_sbrk(24476) == diagnostic_test_heap + 100 && probe_state.heap_peak_bytes == 24576);
    puts("PASS heap_overlay_exact_reservation_boundary");
    errno = 0;
    assert(_sbrk(1) == (void *)-1 && errno == ENOMEM && probe_state.heap_peak_bytes == 24576);
    assert(probe_state.heap_enomem_count == 2);
    puts("PASS heap_overlay_rejects_overflow_without_advance");
    return 0;
}
