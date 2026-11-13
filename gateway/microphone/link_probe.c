/* 仅离线保留完整音频API以核算Flash/RAM；原B5 main不调用此表，不是现场入口。 */
#include "mic_api.h"
#include "tts_uart_port.h"
const struct {
    int (*initialize)(void);
    void (*begin)(void), (*poll)(void), (*cancel)(void), (*export_pcm)(void);
    unsigned (*state)(void);
    const int16_t *(*pcm)(unsigned *);
    void (*tts_init)(TtsQueue *, TtsIo);
    bool (*tts_enable)(TtsQueue *, bool, bool);
    bool (*tts_submit)(TtsQueue *, const uint8_t *, size_t, uint32_t, uint32_t);
    bool (*tts_volume)(TtsQueue *, unsigned, uint32_t);
    void (*tts_poll)(TtsQueue *, uint32_t), (*tts_cancel)(TtsQueue *, uint32_t);
    void (*tts_power_lost)(TtsQueue *, uint32_t);
    void (*tts_receive)(TtsQueue *, uint8_t, uint32_t);
    void (*uart_init)(void);
    TtsIo (*uart_io)(void);
    int (*uart_receive)(void);
    uint32_t (*uart_errors)(void), (*uart_overflow)(void);
} audio_link_probe __attribute__((used, section(".audio_link_probe"))) = {
    mic_initialize, mic_record_begin, mic_record_poll, mic_record_cancel, mic_record_export,
    mic_record_state, mic_record_pcm, tts_init, tts_enable, tts_submit, tts_bench_volume,
    tts_poll, tts_cancel, tts_power_lost, tts_receive, tts_uart_init, tts_uart_io,
    tts_uart_receive, tts_uart_errors, tts_uart_overflow
};
