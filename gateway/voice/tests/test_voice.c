#include "tts_queue.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>

static unsigned checks;
#define CHECK(x) do { assert(x); checks++; } while (0)
typedef struct { uint8_t sent[1024]; size_t n; int blocked, failed, busy; unsigned writes, aborted; } Port;
static int put(void *ctx, uint8_t c) {
    Port *p = ctx; p->writes++;
    if (p->failed) return -1;
    if (p->blocked) return 0;
    assert(p->n < sizeof(p->sent)); p->sent[p->n++] = c; return 1;
}
static bool idle(void *ctx) { return !((Port *)ctx)->busy; }
static void abort_tx(void *ctx) { ((Port *)ctx)->aborted++; }
static void ready(TtsQueue *q, Port *p) {
    memset(p, 0, sizeof(*p)); tts_init(q, (TtsIo){p, put, idle, abort_tx});
    CHECK(q->state == TTS_DISABLED); CHECK(tts_enable(q, true, true));
}
static void drain(TtsQueue *q, uint32_t now) {
    /* 外部模拟调度，不按真实线路睡眠；每步写入上限由测试独立断言。 */
    Port *p = q->io.context;
    for (unsigned i = 0; i < TTS_FRAME_MAX + 2; i++) {
        unsigned before = p->writes; tts_poll(q, now); CHECK(p->writes - before <= 1);
    }
}
int main(void)
{
    uint8_t out[300], text[300]; memset(text, 'a', sizeof(text));
    const uint8_t hello[] = {0xe4,0xbd,0xa0,0xe5,0xa5,0xbd};
    const uint8_t expected[] = {0xfd,0,8,1,4,0xe4,0xbd,0xa0,0xe5,0xa5,0xbd};
    CHECK(tts_text_frame(out, sizeof(out), hello, sizeof(hello)) == sizeof(expected));
    CHECK(!memcmp(out, expected, sizeof(expected)));
    CHECK(!tts_text_frame(NULL, sizeof(out), text, 1));
    CHECK(!tts_text_frame(out, sizeof(out), NULL, 1));
    CHECK(!tts_text_frame(out, sizeof(out), text, 0));
    CHECK(tts_text_frame(out, 6, text, 1) == 6);
    CHECK(!tts_text_frame(out, 5, text, 1));
    CHECK(tts_text_frame(out, sizeof(out), text, 240) == 245 && out[1] == 0 && out[2] == 242);
    /* 254/255/256/4K超限全部拒绝，绝不让低字节截断后写出伪造长度。 */
    const size_t too_long[] = {241, 254, 255, 256, 4096, (size_t)-1};
    for (size_t i = 0; i < sizeof(too_long)/sizeof(*too_long); i++) CHECK(!tts_text_frame(out, sizeof(out), text, too_long[i]));
    CHECK(!tts_text_frame(out, sizeof(out), hello, 5));
    const uint8_t invalid[][4] = {{0xc0,0xaf},{0xed,0xa0,0x80},{0xf4,0x90,0x80,0x80},
        {0x80},{0xe2,0x28,0xa1},{0xe2,0x80,0xae},{0xef,0xbb,0xbf},{0xc2,0x85}};
    const size_t sizes[] = {2,3,4,1,3,3,3,2};
    for (size_t i = 0; i < sizeof(sizes)/sizeof(*sizes); i++) {
        memset(out, 0xa5, sizeof(out)); CHECK(!tts_text_frame(out, sizeof(out), invalid[i], sizes[i]));
        CHECK(out[0] == 0xa5); /* 拒绝路径不产生任何部分输出。 */
    }
    const uint8_t controls[] = {0, '\n', '\r', 0x1b, 0x7f, '[', ']'};
    for (size_t i = 0; i < sizeof(controls); i++) CHECK(!tts_text_frame(out, sizeof(out), controls + i, 1));
    const uint8_t valid4[] = {0xf0,0x9f,0x98,0x80};
    CHECK(tts_text_frame(out, sizeof(out), valid4, 4) == 9);
    const uint8_t cmds[] = {2,3,4,0x21};
    for (size_t i = 0; i < sizeof(cmds); i++) CHECK(tts_control_frame(out, cmds[i]) == 4 && out[2] == 1 && out[3] == cmds[i]);
    CHECK(!tts_control_frame(out, 0)); CHECK(!tts_control_frame(NULL, 2));
    CHECK(tts_bench_volume_frame(out, 1) == 9 && out[7] == '1');
    CHECK(!tts_bench_volume_frame(out, 2));

    TtsQueue q; Port p; ready(&q, &p);
    tts_init(&q, (TtsIo){&p, put, idle, abort_tx});
    CHECK(!tts_submit(&q, hello, 6, 1, 0));
    CHECK(!tts_enable(&q, false, true)); CHECK(!tts_enable(&q, true, false));
    CHECK(tts_enable(&q, true, true)); CHECK(tts_submit(&q, hello, 6, 1, 0));
    CHECK(!tts_submit(&q, hello, 6, 2, 6000));
    p.busy = 1; drain(&q, 10); CHECK(q.state == TTS_SENDING && !q.tx_done);
    p.busy = 0; tts_poll(&q, 11);
    CHECK(q.tx_done && q.state == TTS_SENDING && !q.ack_count && !q.done_count);
    CHECK(p.n == sizeof(expected) && !memcmp(p.sent, expected, p.n));
    tts_receive(&q, 0x41, 12); CHECK(q.state == TTS_ACCEPTED && q.ack_count == 1);
    tts_receive(&q, 0x4e, 13); CHECK(q.state == TTS_PLAYING);
    tts_receive(&q, 0x4f, 14); CHECK(q.state == TTS_DONE && q.done_count == 1);
    CHECK(!tts_submit(&q, hello, 6, 1, 6000)); CHECK(!tts_submit(&q, hello, 6, 2, 4999));
    CHECK(tts_submit(&q, hello, 6, 2, 5000));
    tts_cancel(&q, 5001); CHECK(q.state == TTS_DISABLED && !q.enabled && q.stopping && p.aborted);
    drain(&q, 5002); CHECK(q.stop_sent && !q.stop_idle && !q.stop_ack);
    tts_receive(&q, 0x4f, 5003); CHECK(!q.stop_idle);
    tts_receive(&q, 0x41, 5004); tts_receive(&q, 0x4f, 5005); tts_poll(&q, 5006);
    CHECK(!q.stopping && q.stop_idle && !q.stop_failed);
    CHECK(!tts_submit(&q, hello, 6, 3, 10000));
    CHECK(tts_enable(&q, true, true));
    CHECK(!tts_submit(&q, hello, 6, 2, 10000)); /* 关/开不清除防重放身份。 */

    ready(&q, &p); CHECK(tts_submit(&q, hello, 6, 1, 0));
    tts_receive(&q, 0x41, 1); CHECK(q.state == TTS_ERROR); /* 未发送的ACK不能认领。 */
    const uint8_t faults[] = {0x45,0x46,0x4a,0x00,0x4f};
    for (size_t i = 0; i < sizeof(faults); i++) {
        ready(&q, &p); CHECK(tts_submit(&q, hello, 6, 1, 0)); drain(&q, 1);
        tts_receive(&q, faults[i], 2); CHECK(q.state == TTS_ERROR && q.stopping && !q.done_count);
    }
    ready(&q, &p); CHECK(tts_submit(&q, hello, 6, 1, 0)); drain(&q, 1);
    tts_poll(&q, 500); CHECK(q.state == TTS_TIMEOUT && !q.ack_count);
    tts_poll(&q, 2000); CHECK(q.stop_failed && !q.stopping);
    CHECK(!tts_enable(&q, true, true));
    ready(&q, &p); p.blocked = 1; CHECK(tts_submit(&q, hello, 6, 1, 0));
    for (uint32_t tick = 0; tick < 500; tick++) {
        unsigned before = p.writes; tts_poll(&q, tick); CHECK(p.writes - before == 1);
    }
    CHECK(!p.n); tts_poll(&q, 500); CHECK(q.state == TTS_TIMEOUT);
    ready(&q, &p); p.failed = 1; CHECK(tts_submit(&q, hello, 6, 1, 0)); tts_poll(&q, 1);
    CHECK(q.state == TTS_ERROR);
    ready(&q, &p); CHECK(tts_submit(&q, hello, 6, 1, 0)); drain(&q, 1); tts_receive(&q, 0x41, 2);
    tts_poll(&q, 20002); CHECK(q.state == TTS_TIMEOUT && !q.done_count);
    ready(&q, &p); CHECK(tts_bench_volume(&q, 1, 0)); drain(&q, 1); tts_receive(&q, 0x41, 2);
    CHECK(q.state == TTS_DONE && !q.done_count); /* 设置命令没有声学成功计数。 */
    ready(&q, &p); CHECK(tts_submit(&q, hello, 6, 1, 0)); tts_power_lost(&q, 1);
    CHECK(q.state == TTS_ERROR && !q.enabled && !q.power_good);
    ready(&q, &p); uint32_t start = UINT32_MAX - 100;
    CHECK(tts_submit(&q, hello, 6, 1, start)); tts_poll(&q, start + 500);
    CHECK(q.state == TTS_TIMEOUT); /* 无符号差值覆盖SysTick回绕。 */
    ready(&q, &p); tts_receive(&q, 0x4f, 0); CHECK(!q.done_count && q.state == TTS_IDLE);

    /* 合成CAN/ESP调度负载：一次TTS调用最多一字节，绝不等待线路/播放完成。
       这是Host算法边界，不宣称实板中断时延、栈水位或MQTT连续窗口通过。 */
    ready(&q, &p); CHECK(tts_submit(&q, text, 240, 1, 0));
    unsigned can = 0, esp = 0;
    for (unsigned i = 0; i < 1000; i++) { can++; esp++; tts_poll(&q, i / 4); }
    CHECK(can == 1000 && esp == 1000 && q.tx_done && p.n == 245);
    printf("VOICE_HOST_PASS checks=%u sizeof_queue=%zu hardware=NOT_RUN\n", checks, sizeof(q));
    return 0;
}
