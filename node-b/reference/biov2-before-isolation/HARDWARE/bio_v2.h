#ifndef BIO_V2_H
#define BIO_V2_H
#include <stdint.h>

/* 纯C流式算法接口；250 SPS、CH2 ECG / CH1阻抗原始码，不依赖旧算法或CMSIS FIR。 */
#define BIO_V2_SAMPLE_HZ 250u
#define BIO_V2_GAP_MS 100u
#define BIO_V2_WARMUP 1u
#define BIO_V2_NO_CYCLES 2u
#define BIO_V2_UNSTABLE 4u
#define BIO_V2_EXPIRED 8u
#define BIO_V2_DISCONTINUITY 16u
#define BIO_V2_CLIPPED 32u
#define BIO_V2_MAINS 64u
#define BIO_V2_BROADBAND_NOISE 128u

/* 固定宽度公开诊断区，所有位置由新ELF和offsetof绑定；valid仅表示工程判据通过。 */
typedef struct {
    uint32_t tag, abi_version, samples, last_sequence, last_sample_ms, segment;
    uint32_t discontinuities, clipped_samples;
    int32_t ecg_raw, resp_raw, ecg_filtered, resp_filtered;
    uint32_t hr, rpm, hr_valid, rpm_valid, hr_reason, rpm_reason;
    uint32_t hr_candidates, hr_accepted, resp_candidates, resp_accepted;
    uint32_t hr_last_cycle_ms, resp_last_cycle_ms, hr_fresh_intervals, resp_fresh_intervals;
    float ecg_rms_codes, resp_rms_codes, ecg_mains_fraction, resp_mains_fraction;
} BioV2Diag;
extern BioV2Diag g_bio_v2;
void BioV2_Init(uint32_t now_ms);
void BioV2_Process(int32_t ecg_raw, int32_t resp_raw, uint32_t sample_ms,
                   uint32_t sequence, uint8_t source_flags);
void BioV2_Tick(uint32_t now_ms);
uint8_t BioV2_GetHeart(uint16_t *rate, uint32_t now_ms);
uint8_t BioV2_GetResp(uint16_t *rate, uint32_t now_ms);
int32_t BioV2_EcgWave(void);
int32_t BioV2_RespWave(void);
#endif
