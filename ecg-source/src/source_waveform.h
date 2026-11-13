#ifndef MPM_SOURCE_WAVEFORM_H
#define MPM_SOURCE_WAVEFORM_H
#include <stdint.h>
#define SRC_SAMPLE_HZ 1000u
#define SRC_BIAS_CODE 2048u
#define SRC_MIN_CODE 1024u
#define SRC_MAX_CODE 3328u
#define SRC_MAX_TABLE 2000u
typedef enum { SRC_OFF=0, SRC_BIAS=1, SRC_SINE_1HZ=2, SRC_ECG_60=3, SRC_ECG_90=4 } SrcMode;
typedef struct {
    const uint16_t *codes;
    uint32_t length, beats_per_table, nominal_bpm;
} SrcTable;
const SrcTable *Src_GetTable(uint32_t mode);
uint8_t Src_CopyRotated(const uint16_t *codes,uint32_t length,uint32_t *out);
uint8_t Src_TimerPlan(uint32_t timer_hz,uint32_t *psc,uint32_t *arr);
#endif
