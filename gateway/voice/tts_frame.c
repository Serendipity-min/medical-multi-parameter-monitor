#include "tts_frame.h"
#include <string.h>

static int allowed(uint32_t c)
{
    /* 拒绝控制字、方向/零宽标记和模块内嵌标签，避免看似普通文本改变播放参数。 */
    return c >= 32 && !(c >= 127 && c <= 159) && c != '[' && c != ']' &&
        !(c >= 0x200b && c <= 0x200f) && !(c >= 0x2028 && c <= 0x202e) &&
        !(c >= 0x2060 && c <= 0x206f) && c != 0xfeff &&
        !(c >= 0xfdd0 && c <= 0xfdef) && (c & 0xffffu) < 0xfffeu;
}

static int valid_utf8(const uint8_t *s, size_t n)
{
    for (size_t i = 0; i < n;) {
        uint32_t c = s[i++], minimum = 0;
        unsigned extra = 0;
        if (c >= 0xc2 && c <= 0xdf) { c &= 31; extra = 1; minimum = 0x80; }
        else if (c >= 0xe0 && c <= 0xef) { c &= 15; extra = 2; minimum = 0x800; }
        else if (c >= 0xf0 && c <= 0xf4) { c &= 7; extra = 3; minimum = 0x10000; }
        else if (c >= 0x80) return 0;
        if (n - i < extra) return 0;
        while (extra--) {
            if ((s[i] & 0xc0) != 0x80) return 0;
            c = (c << 6) | (s[i++] & 63);
        }
        if (c < minimum || c > 0x10ffff || (c >= 0xd800 && c <= 0xdfff) || !allowed(c)) return 0;
    }
    return 1;
}

size_t tts_text_frame(uint8_t *out, size_t capacity, const uint8_t *text, size_t n)
{
    if (!out || !text || !n || n > TTS_TEXT_MAX || capacity < n + 5 || !valid_utf8(text, n)) return 0;
    /* 先校验后写入；拒绝时不产生半帧，也不截断多字节字符。 */
    out[0] = 0xfd; out[1] = (uint8_t)((n + 2) >> 8); out[2] = (uint8_t)(n + 2);
    out[3] = 1; out[4] = 4; memcpy(out + 5, text, n);
    return n + 5;
}

size_t tts_control_frame(uint8_t out[4], uint8_t command)
{
    if (!out || (command != 2 && command != 3 && command != 4 && command != 0x21)) return 0;
    /* 使用V0.21表格的一字节命令长度；查询版本差异仍需实际模块抓包确认。 */
    out[0] = 0xfd; out[1] = 0; out[2] = 1; out[3] = command;
    return 4;
}

size_t tts_bench_volume_frame(uint8_t out[9], unsigned volume)
{
    if (!out || volume > 1) return 0;
    const uint8_t frame[9] = {0xfd, 0, 6, 1, 1, '[', 'v', (uint8_t)('0' + volume), ']'};
    memcpy(out, frame, sizeof(frame));
    return sizeof(frame);
}
