#ifndef __PAN_TOMPKINS_H
#define __PAN_TOMPKINS_H

#include "stm32f4xx.h"

/* ============================================================================
 * 采样率：必须与 ADS1292 CONFIG1 的 DR[2:0] 完全一致。
 *   DR=001 → 250 SPS（本工程默认）
 *   改这一个宏，下面所有"毫秒 → 采样点"的换算会自动跟着变；
 *   但 CONFIG1 的寄存器值、板子上的晶振分频不会自动变，
 *   所以换采样率时两边都要改。
 * ==========================================================================*/
#define PT_SAMPLE_RATE_HZ       250

// 一个采样点的毫秒数（250 SPS → 4ms），仅用于把"当前点"的时刻回推一格。
#define PT_SAMPLE_PERIOD_MS     (1000 / PT_SAMPLE_RATE_HZ)

/* 信号丢失判定：连续这么多毫秒没有检测到 R 波，就认为心率无效。
 * 调用方拿到 GetBPM 返回 0 时，界面应该显示 "---" 而不是上一次的数字。
 * 4 秒的依据：成人最慢心率按 30 BPM 算，RR = 2s；留一倍余量。 */
#define PT_SIGNAL_HOLD_MS       4000

// 超过 100ms 没有新采样点，定采样率的滤波器历史就失效了
#define PT_INPUT_GAP_MS         100

// 输入异常后清除心率/RR/滤波历史并重新进入学习期
void PanTompkins_Invalidate(void);

// ----------------------------------------------------------------------------

// 初始化（清状态、记录开机时刻）。必须在 TimeBase_Init() 之后调用。
void PanTompkins_Init(void);

// 输入一个心电原始采样点（ADS1292 的 24 位补码扩展成 int32），每帧调一次。
void PanTompkins_Process(int32_t ecg_sample);

// 取最近的心率。返回 1 表示有效（此时 *bpm 是心率）；
// 返回 0 表示无效（无信号/脱落/还在学习期），调用方应显示 "---"。
uint8_t PanTompkins_GetBPM(uint16_t *bpm);

// 返回带通后（供上位机/屏幕画波形）的信号，已定点化成 int32。
int32_t PanTompkins_GetFiltered(void);

/* 队列输入以采集时戳计算RR和学习期，不采用UI处理时间。 */
void PanTompkins_InitAt(uint32_t sample_ms);
void PanTompkins_ProcessAt(int32_t sample,uint32_t sample_ms);
void PanTompkins_InvalidateAt(uint32_t sample_ms);
#endif
