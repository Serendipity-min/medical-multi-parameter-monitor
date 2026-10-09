/* C2.5隔离诊断探针：只记固定数值，绝不参与AT、MQTT或Router决策。 */
#include "probe_events.h"
#include <stddef.h>
#include <string.h>
#ifdef PROBE_HOST_TEST
#include <stdatomic.h>
#define BARRIER() do { atomic_signal_fence(memory_order_seq_cst); probe_host_barrier(); } while (0)
static uint32_t cycles(void) { return probe_host_cycle(); }
static uint32_t milliseconds(void) { return probe_host_ms(); }
#else
#include "stm32f4xx.h"
extern volatile uint32_t g_uptime_ms;
#define BARRIER() __DMB()
static uint32_t cycles(void) { return DWT->CYCCNT; }
static uint32_t milliseconds(void) { return g_uptime_ms; }
#endif

volatile ProbeState probe_state;
#if PROBE_VARIANT_ID == 4U
const char probe_build_marker[] = "P4_DIAGNOSTIC_C25_PROFILE_1";
#else
const char probe_build_marker[] = "P5_DIAGNOSTIC_C25_PROFILE_1";
#endif
_Static_assert(sizeof(ProbeState) <= PROBE_RAM_LIMIT, "diagnostic probe RAM budget exceeded");

int probe_cycle_delta(uint32_t start, uint32_t end, uint32_t elapsed_ms, uint32_t hz, uint32_t *delta)
{
    if (!hz || !delta)
        return 0;
    /* SysTick量化留2ms余量；只在独立时间上界小于完整DWT回绕时使用模减。
       上界信任前提是IRQ持续服务且无调试暂停，C3仍须核验，不能由Host伪装确认。 */
    uint64_t bound = ((uint64_t)elapsed_ms + 2U) * hz / 1000U;
    uint32_t value = end - start;
    if (bound >= ((uint64_t)1U << 32) || value > bound)
        return 0;
    *delta = value;
    return 1;
}

void probe_init(uint32_t core_hz)
{
    /* 仅在SysTick启用前初始化；不是运行中清空观察或写栈哨兵。 */
    memset((void *)&probe_state, 0, sizeof(probe_state));
    probe_state.magic = 0xC25D1A60U;
    probe_state.profile = PROBE_PROFILE_ID;
    probe_state.variant = PROBE_VARIANT_ID;
    probe_state.core_hz = core_hz;
    probe_state.marker_address = (uint32_t)(uintptr_t)probe_build_marker;
    probe_state.foreground_flags = PROBE_STACK_BLOCKED;
    for (unsigned i = 0; i < PROBE_SCOPE_COUNT; ++i)
        probe_state.aggregate[i].min_cycles = 0xffffffffU;
    int available;
#ifdef PROBE_HOST_TEST
    available = probe_host_clock_available();
#else
    CoreDebug->DEMCR |= CoreDebug_DEMCR_TRCENA_Msk;
    available = !(DWT->CTRL & DWT_CTRL_NOCYCCNT_Msk);
    if (available)
    {
        DWT->CTRL |= DWT_CTRL_CYCCNTENA_Msk;
        __DSB();
        uint32_t first = cycles();
        for (unsigned i = 0; i < 16U && cycles() == first; ++i)
            __NOP();
        available = cycles() != first;
    }
#endif
    if (!available || !core_hz)
        probe_state.irq_flags = PROBE_CLOCK_UNAVAILABLE;
    probe_state.last_cycle = available ? cycles() : 0;
    probe_state.last_ms = milliseconds();
    probe_state.initialized = 1;
}

void probe_tick(uint32_t tick)
{
    if (!probe_state.initialized || (probe_state.irq_flags & PROBE_CLOCK_UNAVAILABLE))
        return;
    uint32_t now = cycles(), delta;
    /* SysTick是唯一clock发布者；奇偶seq使前台不会把lo/hi/last混读。 */
    probe_state.clock_seq++;
    BARRIER();
    if (probe_cycle_delta(probe_state.last_cycle, now, tick - probe_state.last_ms, probe_state.core_hz, &delta))
    {
        uint32_t old = probe_state.clock_lo;
        probe_state.clock_lo = old + delta;
        if (probe_state.clock_lo < old)
            probe_state.clock_hi++;
    }
    else
        probe_state.irq_flags |= PROBE_CLOCK_UNRELIABLE;
    probe_state.last_cycle = now;
    probe_state.last_ms = tick;
    BARRIER();
    probe_state.clock_seq++;
    if (!probe_state.tick_armed)
        return;
    uint32_t head = probe_state.tick_head;
    if (head - probe_state.tick_tail >= PROBE_TICK_CAPACITY)
    {
        probe_state.tick_dropped++;
        probe_state.irq_flags |= PROBE_TICKS_LOST;
        return;
    }
    probe_state.ticks[head % PROBE_TICK_CAPACITY].tick = tick;
    probe_state.ticks[head % PROBE_TICK_CAPACITY].cycle = now;
    BARRIER();
    probe_state.tick_head = head + 1U;
}

static int clock_sample(uint32_t *cycle, uint32_t *ms, uint64_t *total)
{
    if (!probe_state.initialized || probe_state.irq_flags & (PROBE_CLOCK_UNAVAILABLE | PROBE_CLOCK_UNRELIABLE))
        return 0;
    /* 有界重试；IRQ过密只标观察不可靠，不阻止业务前台继续。 */
    for (unsigned attempt = 0; attempt < PROBE_SNAPSHOT_ATTEMPTS; ++attempt)
    {
        uint32_t seq = probe_state.clock_seq;
        if (seq & 1U)
            continue;
        BARRIER();
        uint32_t lo = probe_state.clock_lo, hi = probe_state.clock_hi;
        uint32_t last = probe_state.last_cycle, last_ms = probe_state.last_ms;
        uint32_t now = cycles(), tick = milliseconds();
        BARRIER();
        if (seq != probe_state.clock_seq)
            continue;
        uint32_t delta;
        if (!probe_cycle_delta(last, now, tick - last_ms, probe_state.core_hz, &delta))
            break;
        *cycle = now;
        *ms = tick;
        *total = ((uint64_t)hi << 32) + lo + delta;
        return 1;
    }
    probe_state.foreground_flags |= PROBE_CLOCK_UNRELIABLE;
    return 0;
}

static void aggregate(uint32_t scope, uint32_t count, uint64_t child, int success)
{
    volatile ProbeAggregate *stat = &probe_state.aggregate[scope];
    if (success)
        stat->success++;
    else
        stat->failure++;
    if (count < stat->min_cycles)
        stat->min_cycles = count;
    if (count > stat->max_cycles)
        stat->max_cycles = count;
    stat->inclusive_cycles += count;
    stat->direct_child_cycles += child;
}

static void record(uint32_t scope, uint32_t start, uint32_t end, uint32_t ms, int success)
{
    uint32_t key = scope | (success ? 0x100U : 0x200U);
    /* 保留真正在窗口内发生的最大样本及其起止/上界，不用聚合值伪造时间戳。
       相同类别原地更新，避免1kHz CAN造成必然满缓冲；结果类别数仍有16项硬上限。 */
    for (unsigned i = 0; i < probe_state.event_count; ++i)
    {
        volatile ProbeEvent *previous = &probe_state.events[i];
        if (previous->scope == key)
        {
            if (end - start > previous->end - previous->start)
            {
                previous->start = start;
                previous->end = end;
                previous->bound_ms = ms + 2U;
            }
            return;
        }
    }
    if (probe_state.event_count == PROBE_EVENT_CAPACITY)
    {
        probe_state.dropped_observations++;
        probe_state.foreground_flags |= PROBE_RECORDS_LOST;
        return;
    }
    uint32_t index = probe_state.event_count;
    volatile ProbeEvent *entry = &probe_state.events[index];
    /* 低8位是scope，位8/9明确标成功/失败；不会把失败样本混成成功分布。 */
    entry->scope = key;
    entry->start = start;
    entry->end = end;
    entry->bound_ms = ms + 2U;
    BARRIER();
    probe_state.event_count = index + 1U;
}

ProbeToken probe_begin(uint32_t scope)
{
    ProbeToken token = {PROBE_INVALID_TOKEN, 0};
    if (scope >= PROBE_SCOPE_COUNT)
        return token;
    if (probe_state.depth == PROBE_SPAN_DEPTH)
    {
        probe_state.foreground_flags |= PROBE_SPAN_OVERFLOW;
        probe_state.dropped_observations++;
        return token;
    }
    uint32_t now, ms;
    uint64_t total;
    if (!clock_sample(&now, &ms, &total))
    {
        probe_state.aggregate[scope].invalid++;
        return token;
    }
    token.index = probe_state.depth++;
    token.serial = ++probe_state.serial;
    volatile ProbeSpan *span = &probe_state.spans[token.index];
    span->cycle = now;
    span->millisecond = ms;
    span->scope = scope;
    span->serial = token.serial;
    span->generation = probe_state.window_generation;
    span->direct_child_cycles = 0;
    return token;
}

void probe_end(ProbeToken token, int success)
{
    if (token.index == PROBE_INVALID_TOKEN)
        return;
    if (!probe_state.depth || token.index != probe_state.depth - 1U ||
        probe_state.spans[token.index].serial != token.serial)
    {
        probe_state.foreground_flags |= PROBE_SPAN_MISMATCH;
        probe_state.dropped_observations++;
        return;
    }
    volatile ProbeSpan *span = &probe_state.spans[token.index];
    uint32_t now, ms, delta;
    uint64_t total;
    int valid = clock_sample(&now, &ms, &total) &&
                probe_cycle_delta(span->cycle, now, ms - span->millisecond, probe_state.core_hz, &delta);
    probe_state.depth--;
    if (!valid || span->direct_child_cycles > delta || span->generation != probe_state.window_generation)
    {
        probe_state.aggregate[span->scope].invalid++;
        probe_state.foreground_flags |= PROBE_CLOCK_UNRELIABLE;
        return;
    }
    aggregate(span->scope, delta, span->direct_child_cycles, success);
    record(span->scope, span->cycle, now, ms - span->millisecond, success);
    /* 只加到直接父span；孙span已在子span包容值内，不再重复扣除。IRQ仍包含。 */
    if (probe_state.depth)
        probe_state.spans[probe_state.depth - 1U].direct_child_cycles += delta;
}

void probe_service_arm(uint32_t tick)
{
    (void)tick;
    probe_state.tick_tail = probe_state.tick_head;
    BARRIER();
    probe_state.tick_armed = 1;
}

int probe_window_begin(void)
{
    /* 只在主循环处理D的发布边界开始新窗口；不能在嵌套AT/CAN回调中清掉活动span。
       上一窗口RAM不会自动外传，C3必须先保存其编号/快照；未保存就记缺失样本。 */
    if (probe_state.depth)
    {
        probe_state.foreground_flags |= PROBE_SPAN_MISMATCH;
        probe_state.dropped_observations++;
        return 0;
    }
    for (unsigned scope = 0; scope < PROBE_SCOPE_COUNT; ++scope)
    {
        memset((void *)&probe_state.aggregate[scope], 0, sizeof(ProbeAggregate));
        probe_state.aggregate[scope].min_cycles = 0xffffffffU;
    }
    probe_state.event_count = probe_state.dropped_observations = probe_state.unmatched_ticks = 0;
    probe_state.foreground_flags &= PROBE_STACK_BLOCKED | PROBE_CLOCK_UNRELIABLE;
    probe_state.boundary_skipped_ticks = 0;
    probe_state.window_start_ms = milliseconds();
    probe_state.window_generation++;
    probe_state.tick_drop_base = probe_state.tick_dropped;
    probe_state.heap_error_base = probe_state.heap_enomem_count;
    return 1;
}

void probe_service_done(uint32_t tick)
{
    uint32_t tail = probe_state.tick_tail, head = probe_state.tick_head;
    BARRIER();
    /* 消费时只丢弃过期tick，不追逐不断增长的ISR head；循环最多16项。 */
    unsigned budget = PROBE_TICK_CAPACITY;
    while (tail != head && budget--)
    {
        ProbeTick item = {probe_state.ticks[tail % PROBE_TICK_CAPACITY].tick,
                          probe_state.ticks[tail % PROBE_TICK_CAPACITY].cycle};
        if ((int32_t)(item.tick - tick) > 0)
            break;
        BARRIER();
        probe_state.tick_tail = ++tail;
        if (item.tick == tick)
        {
            if ((int32_t)(tick - probe_state.window_start_ms) < 0)
            {
                probe_state.boundary_skipped_ticks++;
                return;
            }
            uint32_t now, ms, delta;
            uint64_t total;
            if (clock_sample(&now, &ms, &total) &&
                probe_cycle_delta(item.cycle, now, ms - tick, probe_state.core_hz, &delta))
            {
                aggregate(PROBE_CAN_SERVICE, delta, 0, 1);
                record(PROBE_CAN_SERVICE, item.cycle, now, ms - tick, 1);
            }
            else
                probe_state.aggregate[PROBE_CAN_SERVICE].invalid++;
            return;
        }
        probe_state.unmatched_ticks++;
        probe_state.foreground_flags |= PROBE_TICKS_LOST;
    }
    probe_state.unmatched_ticks++;
    probe_state.foreground_flags |= PROBE_TICKS_LOST;
}

void probe_network_point(uint32_t point)
{
    if (point >= PROBE_NETWORK_COUNT)
        return;
    if (point == PROBE_D_REQUEST)
    {
        probe_state.network_valid_mask = 0;
        probe_state.live_observed = probe_state.replay_observed = 0;
        probe_state.cache_snapshot_mask = probe_state.cache_drained_observed = 0;
    }
    if (point == PROBE_RECOVERY_START)
    {
        probe_state.recovery_generation++;
        probe_state.network_valid_mask &= (1U << PROBE_RECOVERY_START) - 1U;
        probe_state.live_observed = probe_state.replay_observed = 0;
        probe_state.first_live_us = probe_state.first_replay_us = 0;
    }
    uint32_t cycle, ms;
    uint64_t total;
    if (!clock_sample(&cycle, &ms, &total))
        return;
    /* 用除法分解避免cycles*1e6溢出；只采用同一MCU时钟，不混主机时间。 */
    uint32_t hz = probe_state.core_hz;
    probe_state.network_us[point] = total / hz * 1000000U + total % hz * 1000000U / hz;
    probe_state.network_valid_mask |= 1U << point;
}

void probe_frame_result(int success, int synthetic, int business, int valid, int replay)
{
    if (!success || !synthetic)
        return;
    uint32_t point = PROBE_FIRST_BUSINESS;
    if (replay)
    {
        if (probe_state.replay_observed)
            return;
        uint32_t cycle, ms; uint64_t total;
        if (!clock_sample(&cycle, &ms, &total))
            return;
        probe_state.first_replay_us = total / probe_state.core_hz * 1000000U +
            total % probe_state.core_hz * 1000000U / probe_state.core_hz;
        probe_state.replay_observed = 1;
    }
    else
    {
        if (!probe_state.live_observed)
        {
            uint32_t cycle, ms; uint64_t total;
            if (clock_sample(&cycle, &ms, &total))
            {
                probe_state.first_live_us = total / probe_state.core_hz * 1000000U +
                    total % probe_state.core_hz * 1000000U / probe_state.core_hz;
                probe_state.live_observed = 1;
            }
        }
        /* M06首条有效业务与M07首条LIVE是两个端点；状态可以提供LIVE优先信用。 */
        if (business && valid && !(probe_state.network_valid_mask & (1U << point)))
            probe_network_point(point);
    }
}

void probe_cache_snapshot(int before, uint32_t cache, uint32_t lost, uint32_t replay, uint32_t drop)
{
    volatile ProbeCache *snapshot = before ? &probe_state.cache_before : &probe_state.cache_after;
    snapshot->cache = cache; snapshot->lost = lost; snapshot->replay = replay; snapshot->drop = drop;
    probe_state.cache_snapshot_mask |= before ? 1U : 2U;
    if (!before)
        probe_state.cache_drained_observed = probe_state.replay_observed && !cache;
}

void probe_first_business_id(uint32_t node, uint32_t stream, uint32_t seq, uint32_t epoch, uint32_t boot)
{
    /* 仅记录由调用方已经判定合成/VALID业务的数值身份，便于后续关联观察；不保存载荷。 */
    probe_state.first_business_id.node = node;
    probe_state.first_business_id.stream = stream;
    probe_state.first_business_id.seq = seq;
    probe_state.first_business_id.epoch = epoch;
    probe_state.first_business_id.boot = boot;
}

void probe_heap_peak(uint32_t bytes)
{
    if (bytes > probe_state.heap_peak_bytes)
        probe_state.heap_peak_bytes = bytes;
}
void probe_heap_enomem(void) { probe_state.heap_enomem_count++; }
