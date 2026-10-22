#include "tts_queue.h"
#include <string.h>

void tts_init(TtsQueue *q, TtsIo io)
{
    memset(q, 0, sizeof(*q)); q->io = io; q->state = TTS_DISABLED;
}

bool tts_enable(TtsQueue *q, bool power, bool protocol)
{
    if (q->stopping || q->state == TTS_SENDING || q->state == TTS_ACCEPTED || q->state == TTS_PLAYING ||
        q->state == TTS_ERROR || q->state == TTS_TIMEOUT || !q->io.write_byte || !q->io.tx_idle || !q->io.abort_tx) return false;
    q->power_good = power; q->protocol_confirmed = protocol;
    if (!power || !protocol) return false;
    q->enabled = true; q->state = TTS_IDLE;
    return true;
}

static bool available(TtsQueue *q)
{
    return q->enabled && q->power_good && q->protocol_confirmed && !q->stopping &&
        (q->state == TTS_IDLE || q->state == TTS_DONE);
}

static void start(TtsQueue *q, size_t n, uint32_t now)
{
    q->length = n; q->position = 0; q->at = now; q->tx_done = false; q->state = TTS_SENDING;
}

bool tts_submit(TtsQueue *q, const uint8_t *s, size_t n, uint32_t id, uint32_t now)
{
    if (!available(q) || !id || (q->submitted && (id <= q->last_id || (uint32_t)(now - q->last_submit) < 5000))) return false;
    size_t length = tts_text_frame(q->frame, sizeof(q->frame), s, n);
    if (!length) return false;
    q->admin_command = false;
    q->submitted = true; q->last_id = id; q->last_submit = now; start(q, length, now);
    return true;
}

bool tts_bench_volume(TtsQueue *q, unsigned volume, uint32_t now)
{
    if (!available(q)) return false;
    size_t n = tts_bench_volume_frame(q->frame, volume);
    if (!n) return false;
    q->admin_command = true; start(q, n, now); return true;
}

static void stop(TtsQueue *q, TtsState result, uint32_t now)
{
    q->enabled = false;
    if (q->io.abort_tx) q->io.abort_tx(q->io.context);
    /* 取消丢弃剩余文本，只尝试一次STOP，不重发旧文本；半帧中断不能承诺立即静音。 */
    memset(q->frame, 0, sizeof(q->frame));
    q->length = tts_control_frame(q->frame, 2); q->position = 0; q->at = now;
    q->stopping = true; q->stop_sent = q->stop_ack = q->stop_idle = q->stop_failed = false;
    q->state = result;
}

void tts_cancel(TtsQueue *q, uint32_t now) { if (!q->stopping) stop(q, TTS_DISABLED, now); }
void tts_power_lost(TtsQueue *q, uint32_t now)
{
    q->power_good = false; q->errors++; stop(q, TTS_ERROR, now);
}

void tts_poll(TtsQueue *q, uint32_t now)
{
    if (q->stopping) {
        if ((uint32_t)(now - q->at) >= 1500 || !q->io.write_byte || !q->io.tx_idle) {
            if (q->io.abort_tx) q->io.abort_tx(q->io.context);
            q->stopping = false; q->stop_failed = true; q->errors++; return;
        }
        if (q->position < q->length) {
            int rc = q->io.write_byte(q->io.context, q->frame[q->position]);
            if (rc > 0) q->position++;
            else if (rc < 0) { q->stopping = false; q->stop_failed = true; q->errors++; }
        } else if (q->io.tx_idle(q->io.context)) q->stop_sent = true;
        if (q->stop_sent && q->stop_ack && q->stop_idle) q->stopping = false;
        return;
    }
    if (q->state == TTS_SENDING) {
        if ((uint32_t)(now - q->at) >= 500) { q->errors++; stop(q, TTS_TIMEOUT, now); return; }
        if (q->position < q->length) {
            int rc = q->io.write_byte(q->io.context, q->frame[q->position]);
            if (rc > 0) q->position++;
            else if (rc < 0) { q->errors++; stop(q, TTS_ERROR, now); }
        } else if (q->io.tx_idle(q->io.context) && !q->tx_done) {
            q->tx_done = true; q->tx_done_count++;
        }
        /* ACK可在最后一个字节发完后到达，TX完成不转成接收/发声成功。 */
    } else if (q->state == TTS_ACCEPTED || q->state == TTS_PLAYING) {
        if ((uint32_t)(now - q->at) >= 20000) { q->errors++; stop(q, TTS_TIMEOUT, now); }
    }
}

void tts_receive(TtsQueue *q, uint8_t status, uint32_t now)
{
    if (q->stopping) {
        if (q->stop_sent && status == 0x41) q->stop_ack = true;
        if (q->stop_sent && q->stop_ack && status == 0x4f) q->stop_idle = true;
        return;
    }
    bool active = q->state == TTS_SENDING || q->state == TTS_ACCEPTED || q->state == TTS_PLAYING;
    if (!active) return; /* 空闲/禁用期间的迟到通知绝不启动或完成新任务。 */
    if (status == 0x41 && q->state == TTS_SENDING && q->tx_done) {
        q->ack_count++; q->state = TTS_ACCEPTED; q->at = now;
        /* 参数命令的41只确认设置接收，不等待一个手册未保证的语音结束通知。 */
        if (q->admin_command) q->state = TTS_DONE;
    } else if (status == 0x4e && (q->state == TTS_ACCEPTED || q->state == TTS_PLAYING)) q->state = TTS_PLAYING;
    else if (status == 0x4f && (q->state == TTS_ACCEPTED || q->state == TTS_PLAYING)) {
        q->state = TTS_DONE; q->done_count++; memset(q->frame, 0, sizeof(q->frame));
    } else { q->errors++; stop(q, TTS_ERROR, now); }
}
