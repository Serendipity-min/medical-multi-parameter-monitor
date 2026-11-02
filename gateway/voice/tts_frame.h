#ifndef MPM_TTS_FRAME_H
#define MPM_TTS_FRAME_H
#include <stddef.h>
#include <stdint.h>

#define TTS_TEXT_MAX 240u
#define TTS_FRAME_MAX (TTS_TEXT_MAX + 5u)
/* 只接受明确长度的UTF-8，不把串口数据当成以NUL结尾的字符串。 */
size_t tts_text_frame(uint8_t *out, size_t capacity, const uint8_t *text, size_t length);
size_t tts_control_frame(uint8_t out[4], uint8_t command);
/* 音量是本地管理操作，与外来文本分离；台架仅允许0/1，不能证明输出功率。 */
size_t tts_bench_volume_frame(uint8_t out[9], unsigned volume);
#endif
