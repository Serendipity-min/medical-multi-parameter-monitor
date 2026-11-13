#include "tts_queue.h"
#include <stdio.h>
#include <string.h>

#define REQUIRE(x) do { if (!(x)) { printf("STOP_QUERY_FAIL line=%d\n", __LINE__); return 3; } } while (0)
typedef struct { uint8_t bytes[32]; unsigned n, writes; int busy, blocked, failed; } Port;
static int put(void *ctx, uint8_t c) {
    Port *p = ctx; p->writes++;
    if (p->failed) return -1;
    if (p->blocked) return 0;
    p->bytes[p->n++] = c; return 1;
}
static bool idle(void *ctx) { return !((Port *)ctx)->busy; }
static void abort_tx(void *ctx) { (void)ctx; }
static void begin(TtsQueue *q, Port *p, uint32_t now) {
    memset(p, 0, sizeof(*p)); tts_init(q, (TtsIo){p, put, idle, abort_tx});
    tts_enable(q, true, true); tts_cancel(q, now);
}
static int drain(TtsQueue *q, Port *p, uint32_t now) {
    for (unsigned i = 0; i < 12; ++i) {
        unsigned before = p->writes; tts_poll(q, now);
        if (p->writes - before > 1) return 0;
    }
    return 1;
}
int main(void) {
    TtsQueue q; Port p;
    const uint8_t expected[] = {0xfd, 0, 1, 2, 0xfd, 0, 1, 0x21};
    begin(&q, &p, 10); REQUIRE(drain(&q, &p, 11)); REQUIRE(p.n == 4 && q.stop_sent);
    tts_receive(&q, 0x4f, 12); REQUIRE(!q.stop_idle);
    tts_receive(&q, 0x41, 13); REQUIRE(q.stop_ack);
    tts_receive(&q, 0x4f, 13); REQUIRE(!q.stop_idle);
    REQUIRE(drain(&q, &p, 14)); REQUIRE(p.n == sizeof expected && !memcmp(p.bytes, expected, sizeof expected));
    tts_receive(&q, 0x4e, 15); REQUIRE(!q.stop_idle && q.stopping);
    tts_receive(&q, 0x41, 16); tts_receive(&q, 0x4f, 17); tts_poll(&q, 18);
    REQUIRE(q.stop_ack && q.stop_idle && !q.stopping && !q.stop_failed);
    REQUIRE(!tts_submit(&q, (const uint8_t *)"test", 4, 1, 100));

    begin(&q, &p, 0); REQUIRE(drain(&q, &p, 1));
    REQUIRE(drain(&q, &p, 1000)); REQUIRE(p.n == 4);
    tts_poll(&q, 1500); REQUIRE(q.stop_failed && !q.stopping && !q.stop_ack);

    begin(&q, &p, 0); REQUIRE(drain(&q, &p, 1)); tts_receive(&q, 0x41, 2);
    p.busy = 1; REQUIRE(drain(&q, &p, 3)); REQUIRE(p.n == 8);
    tts_receive(&q, 0x4f, 4); REQUIRE(!q.stop_idle);
    p.busy = 0; tts_poll(&q, 5); tts_receive(&q, 0x4f, 6); tts_poll(&q, 7);
    REQUIRE(q.stop_idle && !q.stop_failed && !q.stopping);

    begin(&q, &p, 0); REQUIRE(drain(&q, &p, 1)); tts_receive(&q, 0x41, 2);
    p.blocked = 1; REQUIRE(drain(&q, &p, 3)); REQUIRE(p.n == 4);
    tts_receive(&q, 0x4f, 4); REQUIRE(!q.stop_idle);
    tts_poll(&q, 1500); REQUIRE(q.stop_failed && !q.stopping);

    begin(&q, &p, 0); REQUIRE(drain(&q, &p, 1)); tts_receive(&q, 0x41, 2);
    REQUIRE(drain(&q, &p, 3)); tts_receive(&q, 0x4e, 4); tts_poll(&q, 1500);
    REQUIRE(q.stop_failed && !q.stop_idle && p.n == 8);
    REQUIRE(!tts_enable(&q, true, true));

    begin(&q, &p, 0); REQUIRE(drain(&q, &p, 1)); tts_receive(&q, 0x41, 2);
    p.failed = 1; tts_poll(&q, 3); REQUIRE(q.stop_failed && !q.stopping);

    begin(&q, &p, UINT32_MAX - 10); REQUIRE(drain(&q, &p, UINT32_MAX - 9));
    tts_receive(&q, 0x41, UINT32_MAX - 8); REQUIRE(drain(&q, &p, 5));
    tts_poll(&q, 1489); REQUIRE(q.stop_failed && !q.stop_idle);

    begin(&q, &p, 0); p.busy = 1; REQUIRE(drain(&q, &p, 1));
    tts_receive(&q, 0x41, 2); REQUIRE(!q.stop_ack && p.n == 4);
    puts("STOP_QUERY_HOST_PASS cases=8 hardware=NOT_RUN");
    return 0;
}
