/* 脱机 TW-TTS/业务帧测试：生产实现，固定合成输入，不绑定 STM32 外设。 */
#include "p6_voice.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>
#define PASS(name) puts("PASS " name)
static uint8_t sent[300];
static size_t used, max_chunk;
static int write_mode;
static int writer(void *context, const uint8_t *data, size_t size)
{
    (void)context;
    if (size > max_chunk) max_chunk = size;
    if (write_mode == 1) return 0;
    if (write_mode == 2) return (int)size + 1;
    size_t count = size > 2U ? 2U : size;
    memcpy(sent + used, data, count); used += count;
    return (int)count;
}
static void put64(uint8_t *data, uint64_t value)
{
    for (unsigned index = 0; index < 8; ++index) { data[7U - index] = (uint8_t)value; value >>= 8; }
}
static size_t frame(uint8_t *data, uint64_t now)
{
    const char *text = "模拟心率72 bpm。";
    memset(data, 0, 300); memcpy(data, "P6V1", 4); put64(data + 4, now); put64(data + 12, now + 15000U);
    memset(data + 20, 1, 16); memset(data + 36, 2, 16);
    data[53] = (uint8_t)strlen(text); memcpy(data + 54, text, strlen(text));
    return 54U + strlen(text);
}
static int receive(uint8_t *data, size_t size, uint64_t now)
{
    return p6_voice_receive(P6_VOICE_TOPIC, sizeof(P6_VOICE_TOPIC) - 1U, data, size, 1, 0, now, 2000);
}
static void bind_ready(void)
{
    used = max_chunk = 0; write_mode = 0;
    p6_voice_bind(writer, NULL, 0); p6_voice_poll(2000);
}
int main(void)
{
    TwTts tts;
    tw_tts_init(&tts, NULL, NULL, 0);
    assert(tts.state == TW_OFF && !tw_tts_queue(&tts, (const uint8_t *)"text", 4, 0));
    PASS("unbound_off_preserves_p4");
    tw_tts_init(&tts, writer, NULL, UINT32_MAX - 1000U);
    tw_tts_poll(&tts, 998U); assert(tts.state == TW_BOOT);
    tw_tts_poll(&tts, 999U); assert(tts.state == TW_IDLE);
    PASS("boot_delay_and_tick_wrap");
    const uint8_t text[] = {0xe4, 0xbd, 0xa0, 0xe5, 0xa5, 0xbd};
    const uint8_t expected[] = {0xfd, 0, 8, 1, 4, 0xe4, 0xbd, 0xa0, 0xe5, 0xa5, 0xbd};
    assert(tw_tts_queue(&tts, text, sizeof(text), 1000));
    assert(!tw_tts_queue(&tts, text, sizeof(text), 1000));
    for (unsigned i = 0; i < 8; ++i) tw_tts_poll(&tts, 1000 + i);
    assert(tts.state == TW_ACCEPT && used == sizeof(expected) && !memcmp(sent, expected, used) && max_chunk <= 32U);
    PASS("official_utf8_frame_no_xor_partial_nonblocking");
    tw_tts_feedback(&tts, 0x4f, 1008); assert(!tts.completed && tts.state == TW_ACCEPT);
    tw_tts_feedback(&tts, 0x41, 1009); assert(tts.accepted == 1 && !tts.completed && tts.state == TW_PLAY);
    tw_tts_feedback(&tts, 0x41, 1010); assert(tts.accepted == 1);
    tw_tts_feedback(&tts, 0x4e, 1011); assert(!tts.completed);
    tw_tts_feedback(&tts, 0x4f, 1012); assert(tts.completed == 1 && tts.state == TW_IDLE);
    tw_tts_feedback(&tts, 0x4f, 1013); assert(tts.completed == 1);
    PASS("41_acceptance_and_4f_completion_separate_ordered");
    tw_tts_feedback(&tts, 0x45, 1014); assert(tts.errors == 1 && tts.state == TW_FAULT);
    PASS("module_error_latches_no_auto_replay");
    tw_tts_init(&tts, writer, NULL, 0); tw_tts_poll(&tts, 2000); write_mode = 1;
    assert(tw_tts_queue(&tts, text, sizeof(text), UINT32_MAX - 100));
    tw_tts_poll(&tts, 899); assert(tts.state == TW_FAULT);
    PASS("zero_writer_bounded_timeout_wrap");
    write_mode = 2; tw_tts_init(&tts, writer, NULL, 0); tw_tts_poll(&tts, 2000);
    assert(tw_tts_queue(&tts, text, sizeof(text), 2000)); tw_tts_poll(&tts, 2000); assert(tts.state == TW_FAULT);
    PASS("writer_cannot_exceed_budget");
    write_mode = 0; used = 0; tw_tts_init(&tts, writer, NULL, 0); tw_tts_poll(&tts, 2000);
    assert(tw_tts_queue(&tts, text, sizeof(text), 2000));
    for (unsigned i = 0; i < 8; ++i) tw_tts_poll(&tts, 2000+i);
    tw_tts_poll(&tts, 4007); assert(tts.state == TW_FAULT && !tts.completed);
    PASS("accept_feedback_missing_timeout");
    used = 0; tw_tts_init(&tts, writer, NULL, 0); tw_tts_poll(&tts, 2000);
    assert(tw_tts_queue(&tts, text, sizeof(text), 2000));
    for (unsigned i = 0; i < 8; ++i) tw_tts_poll(&tts, 2000+i);
    tw_tts_feedback(&tts, 0x41, 2008); tw_tts_poll(&tts, 32008);
    assert(tts.state == TW_FAULT && tts.accepted == 1 && !tts.completed);
    PASS("play_feedback_missing_timeout_no_completion");
    const uint8_t overlong[] = {0xc0, 0xaf}, surrogate[] = {0xed, 0xa0, 0x80}, bidi[] = {0xe2, 0x80, 0xae};
    assert(!p6_utf8_valid(overlong, sizeof(overlong)) && !p6_utf8_valid(surrogate, sizeof(surrogate))
           && !p6_utf8_valid(bidi, sizeof(bidi)) && !p6_utf8_valid((const uint8_t *)"[v9]", 4)
           && !p6_utf8_valid(text, 5));
    PASS("unicode_overlong_surrogate_bidi_tags_boundary_rejected");
    uint8_t data[300]; uint64_t now = 1800000000000ULL; size_t size = frame(data, now);
    bind_ready(); assert(receive(data, size, now) && p6_voice_driver()->state == TW_SEND && !used);
    assert(!receive(data, size, now)); PASS("voice_queue_only_duplicate_rejected");
    bind_ready(); assert(!receive(data, size, now + 15000U)); PASS("expired_rejected");
    bind_ready(); assert(!receive(data, size, now - 1001U)); PASS("future_rejected");
    bind_ready(); put64(data + 12, now + 15001U); assert(!receive(data, size, now)); PASS("ttl_limit_rejected");
    size = frame(data, now); bind_ready(); data[53]++; assert(!receive(data, size, now)); PASS("length_mismatch_rejected");
    size = frame(data, now); bind_ready(); assert(!receive(data, 295, now)); PASS("size_above_294_rejected");
    bind_ready(); assert(!p6_voice_receive("mpm/v1/GW-DEV-001/voice/reply", 29, data, size, 1, 0, now, 2000));
    assert(!p6_voice_receive(P6_VOICE_TOPIC, sizeof(P6_VOICE_TOPIC) - 1U, data, size, 0, 0, now, 2000));
    assert(!p6_voice_receive(P6_VOICE_TOPIC, sizeof(P6_VOICE_TOPIC) - 1U, data, size, 1, 1, now, 2000));
    PASS("topic_device_qos_retain_whitelist");
    bind_ready(); assert(receive(data, size, now));
    for (unsigned i = 0; i < 100; ++i) p6_voice_poll(2000 + i);
    p6_voice_feedback(0x41, 2100); p6_voice_feedback(0x4f, 2101);
    put64(data + 4, now + 4999U); put64(data + 12, now + 19999U); data[20] = 3;
    assert(!receive(data, size, now + 4999U)); PASS("device_frequency_limit");
    put64(data + 4, now - 1U); put64(data + 12, now + 14999U);
    assert(!receive(data, size, now)); PASS("out_of_order_high_watermark");
    put64(data + 4, now + 5000U); put64(data + 12, now + 20000U);
    assert(receive(data, size, now + 5000U)); PASS("next_valid_after_completion");
    bind_ready(); size = frame(data, now); assert(receive(data, size, now + 14999U));
    p6_voice_poll(2001); assert(p6_voice_driver()->state == TW_FAULT && !used);
    PASS("queued_expiry_before_first_uart_byte");
    return 0;
}
