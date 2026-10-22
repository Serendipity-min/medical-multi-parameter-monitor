#ifndef MPM_P6V1_H
#define MPM_P6V1_H
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#define VOICE_TOPIC "mpm/v1/GW-C-001/voice/reply"
#define VOICE_HEADER 54u
#define VOICE_WIRE_MAX 294u
typedef enum { VOICE_OK, VOICE_OFF, VOICE_AUTHORITY, VOICE_SIZE, VOICE_TEXT,
    VOICE_TIME, VOICE_REPLAY, VOICE_RATE, VOICE_BUSY } VoiceResult;
typedef struct {
    uint64_t floor, high_time, last_issued;
    uint32_t last_tick;
    uint8_t ids[8][16], cursor, count;
    bool session, armed, submitted;
} VoiceGuard;
typedef struct { uint64_t issued, expires; const uint8_t *turn, *digest, *text; size_t length; } VoiceMessage;
/* 回调中的视图只在回调返回前有效；调用者须先复制文本，成功入槽才commit。 */
void voice_session(VoiceGuard *, uint64_t now, bool ready);
void voice_arm(VoiceGuard *, uint64_t now);
VoiceResult voice_check(VoiceGuard *, const char *, size_t, unsigned qos, bool retain,
    const uint8_t *, size_t, uint64_t now, uint32_t tick, VoiceMessage *);
void voice_commit(VoiceGuard *, const VoiceMessage *, uint32_t tick);
#endif
