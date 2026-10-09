/* 新诊断探针的普通Host边界测试；只注入合成周期/时间，不访问设备或网络。 */
#include "probe_events.h"
#include <assert.h>
#include <stdio.h>
#include <stdint.h>

static uint32_t fake_cycle, fake_ms;
static int available = 1, inject_tick;
uint32_t probe_host_cycle(void) { return fake_cycle; }
uint32_t probe_host_ms(void) { return fake_ms; }
int probe_host_clock_available(void) { return available; }
void probe_host_barrier(void)
{
    /* 在快照读途中模拟一次生产者提交；先撤销钩子避免模拟ISR自身再次递归。 */
    if (inject_tick)
    {
        inject_tick = 0;
        fake_cycle += 16000;
        probe_tick(++fake_ms);
    }
}
static void reset(void)
{
    fake_cycle = fake_ms = 0; available = 1; inject_tick = 0;
    probe_init(16000000);
}
static void advance(uint32_t count) { fake_cycle += count; fake_ms += count / 16000U; }
#define PASS(name) puts("PASS " name)

int main(void)
{
    reset();
    assert(sizeof(ProbeState) <= 1536 && probe_state.variant == PROBE_VARIANT_ID);
    assert(probe_state.foreground_flags & PROBE_STACK_BLOCKED);
    PASS("probe_budget_profile_and_stack_blocked");

    ProbeToken token = probe_begin(PROBE_OPEN); advance(160); probe_end(token, 1);
    assert(probe_state.aggregate[PROBE_OPEN].success == 1 && probe_state.aggregate[PROBE_OPEN].max_cycles == 160);
    assert((probe_state.events[0].scope & 0x100U) != 0);
    PASS("span_success_records_real_bound_and_outcome");

    token = probe_begin(PROBE_OPEN); advance(320); probe_end(token, 0);
    assert(probe_state.aggregate[PROBE_OPEN].failure == 1 && (probe_state.events[1].scope & 0x200U));
    PASS("span_failure_is_separate_outcome");

    reset(); token = probe_begin(PROBE_YIELD); probe_end(token, 1);
    assert(probe_state.aggregate[PROBE_YIELD].max_cycles == 0 && probe_state.aggregate[PROBE_YIELD].success == 1);
    PASS("zero_cycle_observation_is_not_failure");

    reset(); ProbeToken parent = probe_begin(PROBE_PUBLISH_Q1); advance(10);
    ProbeToken child = probe_begin(PROBE_LIBRARY_PUBLISH); advance(20);
    ProbeToken grandchild = probe_begin(PROBE_AT_SEND); advance(30); probe_end(grandchild, 1);
    advance(20); probe_end(child, 1); advance(10); probe_end(parent, 1);
    assert(probe_state.aggregate[PROBE_PUBLISH_Q1].inclusive_cycles == 90);
    assert(probe_state.aggregate[PROBE_PUBLISH_Q1].direct_child_cycles == 70);
    assert(probe_state.aggregate[PROBE_LIBRARY_PUBLISH].direct_child_cycles == 30);
    PASS("nested_spans_only_subtract_direct_children");

    reset(); ProbeToken tokens[PROBE_SPAN_DEPTH + 1];
    for (unsigned i = 0; i <= PROBE_SPAN_DEPTH; ++i) tokens[i] = probe_begin(PROBE_OPEN);
    assert(tokens[PROBE_SPAN_DEPTH].index == PROBE_INVALID_TOKEN);
    for (unsigned i = PROBE_SPAN_DEPTH + 1; i > 0; --i) probe_end(tokens[i - 1], 1);
    assert(probe_state.depth == 0 && (probe_state.foreground_flags & PROBE_SPAN_OVERFLOW));
    PASS("span_depth_overflow_never_blocks_business");

    reset(); parent = probe_begin(PROBE_OPEN); child = probe_begin(PROBE_PROCESS);
    probe_end(parent, 1); assert(probe_state.foreground_flags & PROBE_SPAN_MISMATCH);
    probe_end(child, 1); probe_end(parent, 1); assert(probe_state.depth == 0);
    PASS("out_of_order_end_retains_error_and_allows_valid_unwind");

    reset();
    for (unsigned scope = 0; scope < PROBE_SCOPE_COUNT; ++scope)
        for (int outcome = 0; outcome < 2; ++outcome)
        { token = probe_begin(scope); advance(160); probe_end(token, outcome); }
    assert(probe_state.event_count == PROBE_EVENT_CAPACITY && probe_state.dropped_observations == 2U * PROBE_SCOPE_COUNT - PROBE_EVENT_CAPACITY);
    assert(probe_state.aggregate[PROBE_CAN_SERVICE].success == 1);
    PASS("record_class_capacity_counts_loss_without_changing_results");

    reset();
    for (unsigned i = 0; i < 100; ++i) { token = probe_begin(PROBE_OPEN); advance(i); probe_end(token, 1); }
    assert(probe_state.event_count == 1 && probe_state.dropped_observations == 0);
    assert(probe_state.events[0].end - probe_state.events[0].start == 99);
    PASS("maximum_sampling_retains_actual_endpoint_not_fabricated_cycles");

    uint32_t delta;
    assert(probe_cycle_delta(0xfffffff0U, 0x20U, 1, 16000000, &delta) && delta == 48);
    assert(!probe_cycle_delta(0, 0, 300000U, 16000000, &delta));
    assert(!probe_cycle_delta(0, 100000U, 0, 16000000, &delta));
    assert(!probe_cycle_delta(0, 0, 0, 0, &delta));
    PASS("single_wrap_trusted_bound_and_ambiguous_wrap_rejection");

    reset(); fake_cycle = 0xfffffff0U; probe_init(16000000);
    token = probe_begin(PROBE_OPEN); fake_cycle = 0x20U; probe_end(token, 1);
    assert(probe_state.aggregate[PROBE_OPEN].max_cycles == 48);
    PASS("span_across_cycle_wrap_has_finite_delta");

    reset(); available = 0; probe_init(16000000);
    token = probe_begin(PROBE_OPEN); probe_end(token, 0);
    assert(token.index == PROBE_INVALID_TOKEN && probe_state.aggregate[PROBE_OPEN].invalid == 1);
    assert(probe_state.irq_flags & PROBE_CLOCK_UNAVAILABLE);
    PASS("unavailable_dwt_does_not_fail_application");

    reset(); probe_state.clock_seq = 1;
    token = probe_begin(PROBE_OPEN); assert(token.index == PROBE_INVALID_TOKEN);
    assert(probe_state.foreground_flags & PROBE_CLOCK_UNRELIABLE);
    PASS("odd_snapshot_has_bounded_retry_and_no_torn_clock");

    reset(); inject_tick = 1;
    token = probe_begin(PROBE_OPEN); assert(token.index != PROBE_INVALID_TOKEN);
    probe_end(token, 1); assert(probe_state.clock_seq == 2 && probe_state.aggregate[PROBE_OPEN].success == 1);
    PASS("clock_snapshot_retries_concurrent_single_writer_commit");

    reset(); probe_service_arm(0); advance(16000); probe_tick(fake_ms); advance(200);
    probe_service_done(1);
    assert(probe_state.aggregate[PROBE_CAN_SERVICE].max_cycles == 200 && probe_state.tick_head == probe_state.tick_tail);
    PASS("scheduled_tick_pairs_with_same_service_completion");

    reset(); probe_service_arm(0);
    for (unsigned i = 0; i < PROBE_TICK_CAPACITY + 1; ++i) { advance(16000); probe_tick(fake_ms); }
    assert(probe_state.tick_dropped == 1 && probe_state.irq_flags & PROBE_TICKS_LOST);
    probe_service_done(1); assert(probe_state.tick_tail == 1);
    PASS("spsc_full_does_not_overwrite_unconsumed_tick");

    reset(); probe_service_arm(0); probe_state.tick_head = probe_state.tick_tail = 0xffffffffU;
    advance(16000); probe_tick(fake_ms); probe_service_done(1);
    assert(probe_state.tick_head == probe_state.tick_tail);
    probe_service_done(2); assert(probe_state.unmatched_ticks == 1 && probe_state.foreground_flags & PROBE_TICKS_LOST);
    PASS("queue_index_wrap_and_unpaired_service_are_explicit");

    reset(); probe_network_point(PROBE_D_REQUEST); advance(480000000); probe_tick(fake_ms);
    probe_network_point(PROBE_PAUSE_END); probe_network_point(PROBE_CLEANUP_BEGIN);
    advance(32000000); probe_tick(fake_ms); probe_network_point(PROBE_CLEANUP_DELAY_BEGIN);
    advance(32000000); probe_tick(fake_ms); probe_network_point(PROBE_CLEANUP_END); probe_network_point(PROBE_RECOVERY_START);
    advance(16000); probe_tick(fake_ms); probe_network_point(PROBE_TLS_READY); advance(16000); probe_tick(fake_ms); probe_network_point(PROBE_CONNACK);
    probe_frame_result(1, 1, 0, 1, 0); assert(probe_state.live_observed && !(probe_state.network_valid_mask & (1U << PROBE_FIRST_BUSINESS)));
    probe_frame_result(1, 1, 1, 0, 0); assert(!(probe_state.network_valid_mask & (1U << PROBE_FIRST_BUSINESS)));
    probe_frame_result(0, 1, 1, 1, 0); assert(!(probe_state.network_valid_mask & (1U << PROBE_FIRST_BUSINESS)));
    advance(160); probe_frame_result(1, 1, 1, 1, 0);
    assert(probe_state.network_valid_mask & (1U << PROBE_FIRST_BUSINESS));
    assert(probe_state.network_us[PROBE_PAUSE_END] == 30000000);
    assert(probe_state.network_us[PROBE_FIRST_BUSINESS] - probe_state.network_us[PROBE_RECOVERY_START] == 2010);
    PASS("network_clock_stages_exclude_pause_and_invalid_or_status_frames");

    advance(160); probe_frame_result(1, 1, 1, 0, 1);
    assert(probe_state.replay_observed && probe_state.first_live_us < probe_state.first_replay_us);
    probe_cache_snapshot(1, 3, 0, 0, 0); probe_cache_snapshot(0, 32, 203, 5, 0);
    assert(probe_state.cache_after.lost == 203 && !probe_state.cache_drained_observed);
    probe_cache_snapshot(0, 0, 203, 9, 0); assert(probe_state.cache_drained_observed);
    probe_cache_snapshot(0, 2, 204, 10, 0); assert(!probe_state.cache_drained_observed);
    PASS("live_and_replay_endpoints_preserve_loss_and_latest_drain_state");

    probe_heap_peak(100); probe_heap_peak(50); probe_heap_peak(120); probe_heap_enomem();
    assert(probe_state.heap_peak_bytes == 120 && probe_state.heap_enomem_count == 1);
    PASS("heap_peak_is_monotonic_and_enomem_not_zeroed");

    probe_network_point(PROBE_RECOVERY_START);
    assert(!probe_state.live_observed && !probe_state.replay_observed && !(probe_state.network_valid_mask & (1U << PROBE_FIRST_BUSINESS)));
    PASS("new_recovery_cannot_reuse_previous_business_endpoint");

    reset(); token = probe_begin(PROBE_OPEN);
    assert(!probe_window_begin() && probe_state.depth == 1);
    advance(100); probe_end(token, 1);
    uint32_t previous = probe_state.window_generation;
    assert(probe_window_begin() && probe_state.window_generation == previous + 1U);
    assert(probe_state.event_count == 0 && probe_state.aggregate[PROBE_OPEN].success == 0);
    token = probe_begin(PROBE_OPEN); advance(50); probe_end(token, 1);
    assert(probe_state.aggregate[PROBE_OPEN].max_cycles == 50);
    PASS("window_reset_only_at_empty_span_boundary_and_not_cumulative");

    reset(); probe_state.clock_lo = 0xfffffff0U; advance(16000); probe_tick(fake_ms);
    assert(probe_state.clock_hi == 1 && probe_state.clock_lo == 15984);
    PASS("single_writer_clock_carry_is_visible_through_sequence_snapshot");
    return 0;
}
