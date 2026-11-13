#ifndef MP_MIC_API_H
#define MP_MIC_API_H
#include <stdint.h>
int mic_initialize(void);
void mic_record_begin(void);
void mic_record_poll(void);
void mic_record_cancel(void);
#ifdef MP_FIVE_APPLIANCE
void mic_record_finish(void);
#endif
unsigned mic_record_state(void);
const int16_t *mic_record_pcm(unsigned *count);
void mic_record_export(void);
typedef struct { uint32_t frames, blocks, dma_errors, overruns, decode_cycles_max; } MicDiag;
void mic_diagnostics(MicDiag *);
#endif
