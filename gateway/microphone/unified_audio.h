#ifndef MP_UNIFIED_AUDIO_H
#define MP_UNIFIED_AUDIO_H
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
enum { UA_DISABLED, UA_IDLE, UA_RECORDING, UA_HASHING, UA_UPLOADING, UA_WAITING,
       UA_PLAYING, UA_STOPPING, UA_FAILED };
extern unsigned final_can_mask;
void unified_audio_init(void);
void unified_audio_local_poll(void);
void unified_audio_step(bool telemetry_idle);
void unified_audio_network(bool connected);
void unified_audio_command(int byte, bool export_allowed);
void unified_audio_reply(const uint8_t *, size_t);
void unified_audio_stop(void);
bool unified_audio_quiet(void);
void unified_audio_report(void);
int gateway_audio_configure(const uint8_t *, size_t);
int gateway_audio_subscribe(void);
int gateway_audio_ready(void);
int gateway_audio_begin(const uint8_t packet[544]);
int gateway_audio_result(void);
#endif
