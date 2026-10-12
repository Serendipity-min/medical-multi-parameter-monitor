/* TW-TTS 官方 V0.21：FD + 长度(text+2) + 01 + 04(UTF-8) + 文本，无 XOR 尾校验。
 * 不绑定引脚；9600 8N1/供电/实物版本必须在新的硬件窗口核对。 */
#include "p6_voice.h"
#include <string.h>

static TwTts voice;
static uint64_t last_issued;
static uint8_t seen[8][16];
static unsigned seen_count, seen_next;
static uint32_t rejected;
static uint32_t expiry_tick;

/* 拒绝非最短编码、代理项、超出 Unicode 的码点、控制/方向字符与模块控制标签。 */
int p6_utf8_valid(const uint8_t *data, size_t size)
{
    if (!data || !size || size > P6_TEXT_MAX) return 0;
    for (size_t index = 0; index < size;)
    {
        uint32_t cp = data[index++], minimum = 0;
        unsigned continuation = 0;
        if (cp < 0x80U) { }
        else if (cp >= 0xc2U && cp <= 0xdfU) { cp &= 31U; continuation = 1; minimum = 0x80U; }
        else if (cp >= 0xe0U && cp <= 0xefU) { cp &= 15U; continuation = 2; minimum = 0x800U; }
        else if (cp >= 0xf0U && cp <= 0xf4U) { cp &= 7U; continuation = 3; minimum = 0x10000U; }
        else return 0;
        if (continuation > size - index) return 0;
        for (unsigned count = 0; count < continuation; ++count)
        {
            uint8_t byte = data[index++];
            if ((byte & 0xc0U) != 0x80U) return 0;
            cp = (cp << 6) | (byte & 63U);
        }
        if (cp < minimum || cp > 0xffffU || (cp >= 0xd800U && cp <= 0xdfffU)
            || cp < 32U || (cp >= 0x7fU && cp <= 0x9fU) || cp == '[' || cp == ']'
            || (cp >= 0x200bU && cp <= 0x200fU) || (cp >= 0x2028U && cp <= 0x202eU)
            || (cp >= 0x2060U && cp <= 0x206fU) || cp == 0xfeffU || cp >= 0xfffeU)
            return 0;
    }
    return 1;
}

void tw_tts_init(TwTts *tts, P6Writer writer, void *context, uint32_t now)
{
    memset(tts, 0, sizeof(*tts));
    tts->writer = writer; tts->context = context; tts->since = now;
    tts->state = writer ? TW_BOOT : TW_OFF;
}

int tw_tts_queue(TwTts *tts, const uint8_t *text, size_t size, uint32_t now)
{
    if (tts->state != TW_IDLE || !tts->writer || !p6_utf8_valid(text, size)) return 0;
    tts->frame[0] = 0xfdU; tts->frame[1] = (uint8_t)((size + 2U) >> 8);
    tts->frame[2] = (uint8_t)(size + 2U); tts->frame[3] = 1; tts->frame[4] = 4;
    memcpy(tts->frame + 5, text, size);
    tts->size = size + 5U; tts->offset = 0; tts->since = now; tts->state = TW_SEND;
    return 1;
}

/* 单次最多写 32B，不等待 UART/播放；所有时间差使用无符号减法兼容 SysTick 回绕。 */
void tw_tts_poll(TwTts *tts, uint32_t now)
{
    uint32_t elapsed = now - tts->since;
    if (tts->state == TW_BOOT && elapsed >= 2000U) tts->state = TW_IDLE;
    else if ((tts->state == TW_SEND && elapsed >= 1000U)
             || (tts->state == TW_ACCEPT && elapsed >= 2000U)
             || (tts->state == TW_PLAY && elapsed >= 30000U))
    { tts->state = TW_FAULT; tts->errors++; }
    else if (tts->state == TW_SEND)
    {
        size_t budget = tts->size - tts->offset;
        if (budget > 32U) budget = 32U;
        int sent = tts->writer(tts->context, tts->frame + tts->offset, budget);
        if (sent < 0 || (size_t)sent > budget) { tts->state = TW_FAULT; tts->errors++; }
        else
        {
            tts->offset += (size_t)sent;
            if (tts->offset == tts->size) { tts->state = TW_ACCEPT; tts->since = now; }
        }
    }
}

void tw_tts_feedback(TwTts *tts, uint8_t status, uint32_t now)
{
    tts->last_status = status;
    if (tts->state == TW_OFF || tts->state == TW_FAULT) return;
    if (status == 0x41U && tts->state == TW_ACCEPT)
    { tts->accepted++; tts->state = TW_PLAY; tts->since = now; }
    else if (status == 0x4fU && tts->state == TW_PLAY)
    { tts->completed++; tts->state = TW_IDLE; }
    else if (status != 0x41U && status != 0x4fU && status != 0x4eU)
    { tts->errors++; tts->state = TW_FAULT; }
    /* 提前/重复 41/4F 或单独 busy 不构成完成，不能确认云端或 Router。 */
}

void p6_voice_bind(P6Writer writer, void *context, uint32_t now)
{
    /* 仅冷启动/显式脱机配置调用；MQTT 重连不得清空去重高水位。 */
    tw_tts_init(&voice, writer, context, now);
    last_issued = 0; seen_count = seen_next = 0; rejected = 0;
    memset(seen, 0, sizeof(seen));
}
int p6_voice_bound(void) { return voice.writer != NULL; }
const TwTts *p6_voice_driver(void) { return &voice; }
uint32_t p6_voice_rejected(void) { return rejected; }
void p6_voice_poll(uint32_t now)
{
    /* 消息在槽内尚未发首字节时也要检查寿命，不能把临近过期文本延后启动。 */
    if (voice.state == TW_SEND && !voice.offset && (int32_t)(now - expiry_tick) >= 0)
    { voice.state = TW_FAULT; voice.errors++; }
    else tw_tts_poll(&voice, now);
}
void p6_voice_feedback(uint8_t status, uint32_t now) { tw_tts_feedback(&voice, status, now); }

static uint64_t read64(const uint8_t *bytes)
{
    uint64_t value = 0;
    for (unsigned index = 0; index < 8; ++index) value = (value << 8) | bytes[index];
    return value;
}

int p6_voice_receive(const char *topic, size_t topic_size, const uint8_t *payload,
                     size_t payload_size, int qos, int retain, uint64_t now_ms, uint32_t tick)
{
    if (!p6_voice_bound() || !topic || topic_size != sizeof(P6_VOICE_TOPIC) - 1U
        || memcmp(topic, P6_VOICE_TOPIC, topic_size) || qos != 1 || retain || !payload
        || payload_size <= P6_HEADER_SIZE || payload_size > P6_HEADER_SIZE + P6_TEXT_MAX
        || memcmp(payload, "P6V1", 4)) goto reject;
    uint64_t issued = read64(payload + 4), expires = read64(payload + 12);
    size_t text_size = ((size_t)payload[52] << 8) | payload[53];
    /* 秒级 SNTP 对毫秒帧容许最多一秒前偏；寿命/顺序/频率独立核验。 */
    if (now_ms < 1700000000000ULL || issued > now_ms + 1000U || expires <= now_ms
        || expires <= issued || expires - issued > 15000U || issued <= last_issued
        || (last_issued && issued - last_issued < 5000U)
        || text_size != payload_size - P6_HEADER_SIZE) goto reject;
    for (unsigned index = 0; index < seen_count; ++index)
        if (!memcmp(seen[index], payload + 20, 16)) goto reject;
    if (!tw_tts_queue(&voice, payload + P6_HEADER_SIZE, text_size, tick)) goto reject;
    memcpy(seen[seen_next], payload + 20, 16);
    seen_next = (seen_next + 1U) % 8U;
    if (seen_count < 8U) seen_count++;
    last_issued = issued;
    expiry_tick = tick + (uint32_t)(expires - now_ms);
    return 1;
reject:
    rejected++;
    return 0;
}
