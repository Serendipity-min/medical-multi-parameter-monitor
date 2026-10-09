/* 新overlay联测：原客户端+合成ESP，检查早返回/ACK等待/结果不变，不复跑原42项。 */
#include "gateway_transport.h"
#include "mock_esp.h"
#include "probe_events.h"
#include <assert.h>
#include <stdio.h>

uint32_t probe_host_cycle(void) { return g_uptime_ms * 16000U; }
uint32_t probe_host_ms(void) { return g_uptime_ms; }
int probe_host_clock_available(void) { return 1; }
void probe_host_barrier(void) { }
#define PASS(name) puts("PASS " name)
static void reset_probe(void) { probe_init(16000000); }
static MpFrame scalar(void)
{
    MpFrame frame = {0}; frame.node = 1; frame.stream = MP_SPO2;
    frame.timestamp = 1800000000000ULL; frame.seq = 7; frame.epoch = 1800000000U;
    frame.boot = 1; frame.valid = frame.synthetic = true; frame.values[0] = 9700;
    return frame;
}
static int connect_good(void)
{
    mock_reset(); reset_probe();
    assert(gateway_network_open());
    MpFrame will = scalar(); will.node = 3; will.stream = MP_GATEWAY_STATUS; will.valid = false;
    return gateway_mqtt_open(&will);
}
int main(void)
{
    mock_reset(); reset_probe();
    assert(!gateway_mqtt_open(NULL));
    assert(probe_state.aggregate[PROBE_OPEN].failure == 1 && probe_state.depth == 0);
    PASS("overlay_open_serialization_early_return_is_closed");

    assert(connect_good());
    assert(probe_state.aggregate[PROBE_OPEN].success == 1);
    assert(probe_state.network_valid_mask & (1U << PROBE_TLS_READY));
    assert(probe_state.network_valid_mask & (1U << PROBE_CONNACK));
    PASS("overlay_success_connection_records_tls_and_connack_without_result_change");

    MpFrame frame = scalar(); frame.count = 251;
    assert(!gateway_mqtt_publish(&frame));
    assert(probe_state.aggregate[PROBE_PUBLISH_Q1].failure == 1 && probe_state.depth == 0);
    PASS("overlay_publish_invalid_frame_early_return_is_closed");

    assert(connect_good()); frame = scalar(); mock_delay_ms = 30;
    assert(gateway_mqtt_publish(&frame));
    assert(probe_state.aggregate[PROBE_PUBLISH_Q1].success == 1);
    assert(probe_state.aggregate[PROBE_PUBLISH_Q1].max_cycles >= 30U * 16000U);
    assert(probe_state.aggregate[PROBE_LIBRARY_PUBLISH].success == 1);
    PASS("overlay_parent_publish_span_includes_actual_mock_puback_wait");

    assert(connect_good()); frame = scalar(); mock_ack_mode = ACK_NONE;
    assert(!gateway_mqtt_publish(&frame));
    assert(probe_state.aggregate[PROBE_PUBLISH_Q1].failure == 1 && probe_state.depth == 0);
    PASS("overlay_missing_ack_returns_original_failure_and_closes_span");

    assert(connect_good()); frame = scalar(); frame.stream = MP_ECG; frame.rate = 250; frame.count = 2;
    assert(gateway_mqtt_publish(&frame));
    assert(probe_state.aggregate[PROBE_PUBLISH_Q0].success == 1 && probe_state.depth == 0);
    PASS("overlay_qos0_return_is_preserved_and_has_distinct_scope");

    assert(connect_good()); (void)gateway_mqtt_yield();
    assert(probe_state.aggregate[PROBE_YIELD].success + probe_state.aggregate[PROBE_YIELD].failure == 1);
    assert(probe_state.depth == 0);
    PASS("overlay_yield_has_single_complete_outer_span");

    assert(connect_good());
    frame = scalar(); frame.valid = false; frame.stream = MP_RR; frame.node = 2;
    assert(gateway_mqtt_publish(&frame));
    assert(!(probe_state.network_valid_mask & (1U << PROBE_FIRST_BUSINESS)));
    frame = scalar(); assert(gateway_mqtt_publish(&frame));
    assert(probe_state.network_valid_mask & (1U << PROBE_FIRST_BUSINESS));
    assert(probe_state.first_business_id.node == 1 && probe_state.first_business_id.stream == MP_SPO2
           && probe_state.first_business_id.seq == 7);
    PASS("overlay_rr_invalid_not_first_valid_business_frame");
    return 0;
}
