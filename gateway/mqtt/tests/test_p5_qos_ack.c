/* 验证真实 coreMQTT 与 Gateway 返回值，再接真实 Router ACK，避免镜像实现式测试。 */
#include "mocks/mock_esp.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>
#define PASS(name) puts("PASS " name)
int main(void)
{
    MpFrame frame = mock_frame(MP_HR, 0, false);
    mock_connect();
    assert(gateway_mqtt_publish(&frame));
    assert(mock_last_id);
    PASS("qos1_matching_puback");

    mock_connect();
    MpRouter router;
    mp_router_init(&router); mp_router_online(&router, true); mp_router_put(&router, &frame);
    MpFrame sent;
    assert(mp_router_take(&router, &sent, g_uptime_ms));
    mock_delay_ms = 700; mock_router_probe = &router;
    uint32_t start = g_uptime_ms;
    bool ok = gateway_mqtt_publish(&sent);
    assert(ok && g_uptime_ms - start >= 700);
    mock_router_probe = NULL;
    mp_router_ack(&router, &sent, ok);
    assert(router.ready_for_replay && router.online && !router.cn);
    PASS("qos1_delayed_puback_precedes_router_ack");

    mock_connect(); mock_ack_mode = ACK_WRONG;
    mp_router_init(&router); mp_router_online(&router, true); mp_router_put(&router, &frame);
    assert(mp_router_take(&router, &sent, g_uptime_ms));
    ok = gateway_mqtt_publish(&sent);
    assert(!ok);
    mp_router_ack(&router, &sent, ok);
    assert(!router.online && router.cn == 1 && router.cache[0].seq == frame.seq
           && router.cache[0].timestamp == frame.timestamp);
    PASS("qos1_wrong_id_failure_returns_router_frame");

    mock_connect(); mock_ack_mode = ACK_NONE;
    start = g_uptime_ms;
    assert(!gateway_mqtt_publish(&frame));
    assert(g_uptime_ms - start >= 5000 && g_uptime_ms - start < 5100);
    assert(!gateway_mqtt_yield());
    PASS("qos1_missing_ack_bounded_timeout");

    mock_connect(); mock_delay_ms = 5500;
    assert(!gateway_mqtt_publish(&frame));
    PASS("qos1_late_ack_is_not_success");

    mock_connect(); mock_read_limit = 1;
    assert(gateway_mqtt_publish(&frame));
    PASS("qos1_partial_puback_assembles");

    mock_connect(); mock_ack_mode = ACK_HALF;
    assert(!gateway_mqtt_publish(&frame));
    PASS("qos1_incomplete_ack_is_not_success");

    mock_connect(); mock_ack_mode = ACK_DUPLICATE;
    assert(gateway_mqtt_publish(&frame));
    mock_ack_mode = ACK_NONE;
    assert(!gateway_mqtt_publish(&frame));
    PASS("qos1_duplicate_ack_cannot_confirm_next_frame");

    mock_connect(); assert(gateway_mqtt_publish(&frame));
    uint16_t previous = mock_last_id;
    gateway_network_close();
    assert(gateway_network_open());
    MpFrame will = mock_frame(MP_GATEWAY_STATUS, 0, false);
    assert(gateway_mqtt_open(&will));
    mock_ack_mode = ACK_OLD; mock_old_id = previous;
    assert(!gateway_mqtt_publish(&frame));
    assert(mock_last_id != previous);
    PASS("qos1_previous_session_ack_rejected");

    mock_connect(); mock_ack_mode = ACK_NONE;
    frame = mock_frame(MP_ECG, 250, false);
    assert(gateway_mqtt_publish(&frame));
    assert((mock_packet[0] & 6U) == 0);
    PASS("qos0_complete_send_without_puback");

    mock_connect(); mock_send_error = 1;
    assert(!gateway_mqtt_publish(&frame));
    PASS("qos0_send_error_propagates");

    mock_connect(); mock_send_zero = 1;
    start = g_uptime_ms;
    assert(!gateway_mqtt_publish(&frame));
    assert(g_uptime_ms - start >= 5000 && g_uptime_ms - start < 5100);
    PASS("qos0_zero_send_has_finite_budget");

    mock_connect(); mock_send_limit = 3;
    assert(gateway_mqtt_publish(&frame));
    PASS("qos0_partial_send_completes_exact_packet");

    mock_connect(); frame.replay = true;
    assert(gateway_mqtt_publish(&frame));
    assert((mock_packet[0] & 6U) == 2U);
    char expected[2048]; int size = mp_json(&frame, expected, sizeof(expected));
    assert(size && mock_packet_length > (size_t)size);
    assert(!memcmp(mock_packet + mock_packet_length - (size_t)size, expected, (size_t)size));
    PASS("replay_qos1_payload_sequence_and_time_unchanged");

    mock_connect(); mock_ack_mode = ACK_INBOUND;
    frame = mock_frame(MP_HR, 0, false);
    assert(!gateway_mqtt_publish(&frame) && !gateway_mqtt_yield());
    PASS("publish_only_inbound_publish_disconnects");

    mock_connect(); mock_ack_mode = ACK_INBOUND_QOS1;
    assert(!gateway_mqtt_publish(&frame) && !gateway_mqtt_yield());
    PASS("publish_only_inbound_qos1_disconnects");

    mock_connect(); g_uptime_ms = UINT32_MAX - 100; mock_delay_ms = 700;
    start = g_uptime_ms;
    assert(gateway_mqtt_publish(&frame) && g_uptime_ms - start >= 700);
    PASS("qos1_wait_survives_tick_wraparound");

    mock_connect(); frame = mock_frame(MP_ECG, 250, false); frame.count = 250;
    for (unsigned i = 0; i < 250; ++i) frame.values[i] = INT32_MAX;
    size_t old_length = mock_packet_length;
    assert(!gateway_mqtt_publish(&frame) && mock_packet_length == old_length);
    PASS("oversize_json_never_sends_truncated_payload");
    return 0;
}
