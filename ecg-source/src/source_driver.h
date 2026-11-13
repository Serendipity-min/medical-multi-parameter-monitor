#ifndef MPM_SOURCE_DRIVER_H
#define MPM_SOURCE_DRIVER_H
#include "source_waveform.h"
#define SRC_FAULT_CLOCK 1u
#define SRC_FAULT_MODE 2u
#define SRC_FAULT_TABLE 4u
#define SRC_FAULT_DMA 8u
#define SRC_FAULT_UNDERRUN 16u
#define SRC_FAULT_DMA_STOP 32u
#define SRC_FAULT_EXCEPTION 64u
#define SRC_STATE_OFF 0u
#define SRC_STATE_STATIC 1u
#define SRC_STATE_STREAM 2u
#define SRC_STATE_FAULT_STATIC 3u
#define SRC_STATE_FAULT_HIGHZ 4u
typedef struct {
    uint32_t tag,version,mode,state,faults,mode_changes;
    uint32_t core_hz,timer_hz,psc,arr,table_length,completed_tables;
    uint32_t completed_dma_samples,bias_code,first_code,last_dma_flags,last_dac_flags;
    uint32_t dma_reset_count;
} SrcDiagnostic;
extern volatile SrcDiagnostic g_source_diag;
extern volatile uint32_t g_source_requested_mode;
extern uint32_t g_source_dma_buffer[SRC_MAX_TABLE];
void Src_Init(void);
uint8_t Src_ApplyMode(uint32_t mode);
void Src_Fault(uint32_t reason);
void DMA1_Stream5_IRQHandler(void);
void TIM6_DAC_IRQHandler(void);
#endif
