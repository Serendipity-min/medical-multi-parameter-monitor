/* 合成正常 CONNACK/PINGRESP，核对实际 CONNECT 字节与 TLS 配置分支。 */
#include "mocks/mock_esp.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>
#define PASS(name) puts("PASS " name)
int main(void)
{
    mock_connect();
    size_t offset = 1;
    while (mock_packet[offset++] & 128U) { }
    assert(mock_packet[0] == 0x10 && !memcmp(mock_packet + offset, "\0\4MQTT\4", 7));
    assert(mock_packet[offset + 7] == 0xee);
    assert(mock_packet[offset + 8] == 0 && mock_packet[offset + 9] == 15);
    assert(mock_tls_started);
    PASS("connect_mqtt311_clean_session_lwt_auth_keepalive15");
    /* 按 MQTT 长度字段逐段核对身份和 Will，原始凭据不输出到日志。 */
    offset += 10;
    const char *fields[] = {"synthetic-client", "mpm/v1/GW-C-001/status", NULL,
                            "synthetic-user", "synthetic-mqtt-password"};
    MpFrame will = mock_frame(MP_GATEWAY_STATUS, 0, false); will.valid = false;
    char will_json[512]; assert(mp_json(&will, will_json, sizeof(will_json))); fields[2] = will_json;
    for (unsigned i = 0; i < 5; ++i)
    {
        size_t length = ((size_t)mock_packet[offset] << 8) | mock_packet[offset + 1]; offset += 2;
        assert(length == strlen(fields[i]) && !memcmp(mock_packet + offset, fields[i], length));
        offset += length;
    }
    assert(offset == mock_packet_length);
    PASS("connect_exact_client_credentials_will_topic_payload");

    mock_reset(); mock_connack_code = 5;
    assert(gateway_network_open());
    assert(!gateway_mqtt_open(&will) && !gateway_mqtt_yield());
    PASS("connect_refused_connack_stays_offline");

    mock_reset(); mock_read_limit = 1;
    assert(gateway_network_open() && gateway_mqtt_open(&will));
    PASS("connect_partial_connack");

    mock_reset(); mock_drop_connack = 1;
    assert(gateway_network_open());
    uint32_t start = g_uptime_ms;
    assert(!gateway_mqtt_open(&will));
    assert(g_uptime_ms - start >= 5000 && g_uptime_ms - start < 5100);
    PASS("connect_missing_connack_bounded_timeout");

    mock_connect(); g_uptime_ms += 16000;
    assert(gateway_mqtt_yield() && mock_ping_count == 1);
    assert(gateway_mqtt_yield());
    g_uptime_ms += 6000;
    assert(gateway_mqtt_yield());
    PASS("keepalive_pingreq_and_pingresp");

    mock_connect(); mock_drop_ping = 1; g_uptime_ms += 16000;
    assert(gateway_mqtt_yield()); g_uptime_ms += 5001;
    assert(!gateway_mqtt_yield());
    PASS("keepalive_missing_pingresp_disconnects");

    mock_reset(); mock_fail_at = "AT+CIPSSLCCONF=2,0,0";
    assert(!gateway_network_open() && !mock_tls_started);
    PASS("tls_ca_failure_no_plaintext_fallback");

    mock_reset(); mock_fail_at = "AT+CIPSSLCSNI=\"mqtt.example.invalid\"";
    assert(!gateway_network_open() && !mock_tls_started);
    PASS("tls_sni_failure_stops_connection");

    mock_connect();
    unsigned char half[] = {0x40, 2}; mock_queue(half, sizeof(half));
    assert(gateway_mqtt_yield()); g_uptime_ms += 5001;
    assert(!gateway_mqtt_yield());
    PASS("idle_partial_packet_has_total_timeout");

    mock_connect(); MpFrame state = mock_frame(MP_GATEWAY_STATUS, 0, false);
    assert(gateway_mqtt_publish(&state));
    assert((mock_packet[0] & 7U) == 3U);
    PASS("gateway_status_qos1_retained");
    return 0;
}
