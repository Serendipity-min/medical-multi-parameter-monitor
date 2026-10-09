#ifndef H16_PROBE_EVENTS_H
#define H16_PROBE_EVENTS_H
#include <stdint.h>
#include "probe_config.h"

enum ProbeScope
{
    PROBE_OPEN, PROBE_PUBLISH_Q0, PROBE_PUBLISH_Q1, PROBE_YIELD,
    PROBE_LIBRARY_PUBLISH, PROBE_PROCESS, PROBE_AT_SEND, PROBE_AT_RECV,
    PROBE_CAN_SERVICE, PROBE_CAN_CALLBACK, PROBE_SCOPE_COUNT
};
enum ProbeNetworkPoint
{
    PROBE_D_REQUEST, PROBE_PAUSE_END, PROBE_CLEANUP_BEGIN, PROBE_CLEANUP_DELAY_BEGIN, PROBE_CLEANUP_END,
    PROBE_RECOVERY_START, PROBE_TLS_READY, PROBE_CONNACK, PROBE_FIRST_BUSINESS,
    PROBE_NETWORK_COUNT
};
enum ProbeFlags
{
    PROBE_CLOCK_UNAVAILABLE = 1U, PROBE_CLOCK_UNRELIABLE = 2U,
    PROBE_SPAN_OVERFLOW = 4U, PROBE_SPAN_MISMATCH = 8U,
    PROBE_RECORDS_LOST = 16U, PROBE_TICKS_LOST = 32U,
    PROBE_STACK_BLOCKED = 64U
};
typedef struct { uint32_t index, serial; } ProbeToken;
typedef struct
{
    uint32_t success, failure, invalid, min_cycles, max_cycles, reserved;
    uint64_t inclusive_cycles, direct_child_cycles;
} ProbeAggregate;
typedef struct
{
    uint32_t cycle, millisecond, scope, serial, generation, reserved;
    uint64_t direct_child_cycles;
} ProbeSpan;
typedef struct { uint32_t tick, cycle; } ProbeTick;
typedef struct { uint32_t scope, start, end, bound_ms; } ProbeEvent;
typedef struct { uint32_t cache, lost, replay, drop; } ProbeCache;
typedef struct { uint32_t node, stream, seq, epoch, boot; } ProbeFrameId;
typedef struct
{
    /* 时钟和队列字段仅SysTick写；seq保护多字读，head发布前DMB，tail仅主线程写。
       其它聚合仅主线程写；不要对IRQ与前台共享字段做双方RMW。 */
    uint32_t magic, profile, variant, marker_address, core_hz, initialized;
    volatile uint32_t irq_flags, clock_seq, clock_lo, clock_hi, last_cycle, last_ms;
    volatile uint32_t tick_head, tick_tail, tick_dropped, tick_armed;
    ProbeTick ticks[PROBE_TICK_CAPACITY];
    uint32_t foreground_flags, dropped_observations, unmatched_ticks, serial, depth;
    uint32_t window_generation, window_start_ms, boundary_skipped_ticks, heap_error_base, tick_drop_base;
    ProbeSpan spans[PROBE_SPAN_DEPTH];
    ProbeAggregate aggregate[PROBE_SCOPE_COUNT];
    uint32_t event_count;
    ProbeEvent events[PROBE_EVENT_CAPACITY];
    uint64_t network_us[PROBE_NETWORK_COUNT];
    uint32_t network_valid_mask, recovery_generation;
    ProbeFrameId first_business_id;
    ProbeCache cache_before, cache_after;
    uint32_t cache_snapshot_mask, cache_drained_observed;
    uint64_t first_live_us, first_replay_us;
    uint32_t live_observed, replay_observed;
    uint32_t heap_peak_bytes, heap_enomem_count;
} ProbeState;

extern volatile ProbeState probe_state;
extern const char probe_build_marker[];
void probe_init(uint32_t core_hz);
void probe_tick(uint32_t tick);
void probe_service_arm(uint32_t tick);
void probe_service_done(uint32_t tick);
int probe_window_begin(void);
ProbeToken probe_begin(uint32_t scope);
void probe_end(ProbeToken token, int success);
void probe_network_point(uint32_t point);
void probe_frame_result(int success, int synthetic, int business, int valid, int replay);
void probe_first_business_id(uint32_t node, uint32_t stream, uint32_t seq, uint32_t epoch, uint32_t boot);
void probe_cache_snapshot(int before, uint32_t cache, uint32_t lost, uint32_t replay, uint32_t drop);
void probe_heap_peak(uint32_t bytes);
void probe_heap_enomem(void);
int probe_cycle_delta(uint32_t start, uint32_t end, uint32_t elapsed_ms, uint32_t hz, uint32_t *delta);
/* 只读观察结构的数值；没有JSON/串口输出、主动设备控制或接受连接配置的API。 */

#ifdef PROBE_HOST_TEST
uint32_t probe_host_cycle(void);
uint32_t probe_host_ms(void);
int probe_host_clock_available(void);
void probe_host_barrier(void);
#endif
#endif
