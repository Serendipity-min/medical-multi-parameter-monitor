#include "tts_broadcast.h"
#include "tts_uart_port.h"
#include "b5_policy.h"
#include <string.h>

enum { HEADER = 19, MAX_TEXT = 200, CAPACITY = 3, TTL_MS = 15000 };

typedef struct {
    uint64_t issued_ms;
    uint8_t text[MAX_TEXT];
    uint8_t length;
} Message;

static TtsQueue player;
static Message queued[CAPACITY];
static unsigned head, count;
static uint64_t last_issued;

static uint64_t read_be(const uint8_t *p, unsigned bytes)
{
    uint64_t value = 0;
    while (bytes--) value = (value << 8) | *p++;
    return value;
}

static bool expired(uint64_t now, uint64_t issued)
{
    return now >= issued && now - issued >= TTL_MS;
}

void tts_broadcast_init(TtsIo io)
{
    head = count = 0;
    last_issued = 0;
    tts_init(&player, io);
    /* 电源与状态回码由硬件阶段核验，固件没有独立电源感测。 */
    (void)tts_enable(&player, true, true);
}

bool tts_broadcast_offer(const uint8_t *frame, size_t length, uint64_t utc_ms)
{
    if (!utc_ms || !player.enabled || count == CAPACITY || length <= HEADER ||
        length > HEADER + MAX_TEXT || memcmp(frame, "MPB1", 4) || frame[4] != 1u ||
        read_be(frame + 13, 4) != TTL_MS || read_be(frame + 17, 2) != length - HEADER) return false;
    uint64_t issued = read_be(frame + 5, 8);
    if (issued <= last_issued || expired(utc_ms, issued) ||
        (issued > utc_ms && issued - utc_ms >= TTL_MS)) return false;

    Message *message = &queued[(head + count) % CAPACITY];
    message->issued_ms = issued;
    message->length = (uint8_t)(length - HEADER);
    memcpy(message->text, frame + HEADER, message->length);
    last_issued = issued;
    count++;
    return true;
}

void tts_broadcast_poll(uint32_t now)
{
    tts_poll(&player, now);
    for (unsigned i = 0; i < 4; i++) {
        int status = tts_uart_receive();
        if (status < 0) break;
        tts_receive(&player, (uint8_t)status, now);
    }
    if (!count || !tts_ready(&player, now)) return;
    Message *message = &queued[head];
    uint64_t utc_ms = b5_data_utc();
    if (utc_ms && !expired(utc_ms, message->issued_ms)) {
        (void)tts_submit(&player, message->text, message->length, player.last_id + 1u, now);
    }
    head = (head + 1u) % CAPACITY;
    count--;
}

void tts_broadcast_stop(uint32_t now)
{
    count = 0;
    if (player.state == TTS_SENDING || player.state == TTS_ACCEPTED || player.state == TTS_PLAYING)
        tts_cancel(&player, now);
}
