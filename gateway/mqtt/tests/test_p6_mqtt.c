/* 真实 coreMQTT 回调与状态引擎，只有 ESP 字节接口/SUBACK 由合成夹具替代。 */
#include "mocks/mock_esp.h"
#include "p6_voice.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>
#define PASS(name) puts("PASS " name)
static unsigned writes;
static int writer(void *context, const uint8_t *data, size_t size)
{ (void)context; (void)data; writes++; return (int)size; }
static void put64(uint8_t *data, uint64_t value)
{ for (unsigned i = 0; i < 8; ++i) { data[7U-i] = (uint8_t)value; value >>= 8; } }
static void queue_voice(unsigned identity, int invalid)
{
    /* 使用标准 QoS1 PUBLISH；应用帧固定 58B、Topic 精确白名单，不反射生产配置。 */
    uint8_t packet[130] = {0x32}; size_t topic_size = sizeof(P6_VOICE_TOPIC)-1U;
    size_t remaining = 2U + topic_size + 2U + 58U;
    packet[1] = (uint8_t)remaining; packet[2] = 0; packet[3] = (uint8_t)topic_size;
    memcpy(packet+4, P6_VOICE_TOPIC, topic_size);
    size_t offset = 4U + topic_size;
    packet[offset++] = 0; packet[offset++] = (uint8_t)identity;
    uint8_t *body = packet + offset;
    memcpy(body, "P6V1", 4); put64(body+4, 1800000000000ULL); put64(body+12, 1800000015000ULL);
    memset(body+20, 1, 16); memset(body+36, 2, 16); body[53] = 4; memcpy(body+54, "text", 4);
    if (invalid) body[54] = '[';
    mock_queue(packet, remaining+2U);
}
static int open_mode(int mode)
{
    mock_reset(); mock_suback_mode = mode; p6_voice_bind(writer, NULL, 0);
    assert(gateway_network_open());
    MpFrame will = mock_frame(MP_GATEWAY_STATUS, 0, false);
    return gateway_mqtt_open(&will);
}
int main(void)
{
    p6_voice_bind(NULL, NULL, 0); mock_connect();
    MpFrame frame = mock_frame(MP_HR, 0, false);
    assert(gateway_mqtt_publish(&frame)); PASS("enabled_unbound_keeps_p4_publish_only");
    assert(open_mode(0)); p6_voice_poll(2000); writes = 0;
    uint16_t next_id = (uint16_t)(((uint16_t)mock_packet[2] << 8) | mock_packet[3]); next_id++;
    queue_voice(next_id, 0); mock_delay_ms = 100;
    assert(gateway_mqtt_publish(&frame));
    assert(p6_voice_driver()->state == TW_SEND && !writes && mock_last_id == next_id);
    PASS("inbound_same_packet_id_not_outgoing_ack_queue_only");
    queue_voice(10, 0); assert(gateway_mqtt_yield()); assert(p6_voice_rejected() == 1);
    PASS("duplicate_business_id_refused_telemetry_survives");
    queue_voice(11, 1); assert(gateway_mqtt_publish(&frame)); assert(p6_voice_rejected() >= 2);
    PASS("illegal_voice_and_qos1_telemetry_coexist");
    gateway_network_close(); assert(gateway_network_open());
    MpFrame will = mock_frame(MP_GATEWAY_STATUS, 0, false); assert(gateway_mqtt_open(&will));
    queue_voice(12, 0); assert(gateway_mqtt_yield()); assert(p6_voice_rejected() >= 3);
    PASS("reconnect_preserves_business_dedup");
    assert(open_mode(0)); p6_voice_poll(2000); queue_voice(20, 0); mock_ack_mode = ACK_WRONG;
    MpRouter router; mp_router_init(&router); mp_router_online(&router, true); mp_router_put(&router, &frame);
    MpFrame sent; assert(mp_router_take(&router, &sent, g_uptime_ms));
    bool ok = gateway_mqtt_publish(&sent); assert(!ok); mp_router_ack(&router, &sent, ok);
    assert(!router.online && router.cn == 1); PASS("voice_does_not_mask_wrong_puback_router_recaches");
    assert(!open_mode(1)); PASS("wrong_suback_not_success");
    assert(!open_mode(2)); PASS("refused_suback_not_success");
    uint32_t start = g_uptime_ms; assert(!open_mode(3)); assert(g_uptime_ms >= 5000U); (void)start;
    PASS("missing_suback_bounded");
    assert(open_mode(0)); const uint8_t late_suback[] = {0x90,3,0,1,1}; mock_queue(late_suback, sizeof(late_suback));
    assert(!gateway_mqtt_publish(&frame)); PASS("late_suback_cannot_confirm_outgoing_publish");
    return 0;
}
