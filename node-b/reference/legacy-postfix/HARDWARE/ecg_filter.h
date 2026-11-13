#ifndef __ECG_FILTER_H
#define __ECG_FILTER_H

#ifndef ARM_MATH_CM4
#define ARM_MATH_CM4
#endif
#include "arm_math.h"

// 129 抽头（奇数）线性相位 FIR → 群延迟 (129-1)/2 = 64 个采样点。
// 250 SPS 下 = 256ms。做"R 波标记"时要注意这个滞后。
#define ECG_FIR_TAP_NUM 129

// 逐点处理（blockSize=1）。此时状态数组长度必须是 numTaps + blockSize - 1 = 129。
#define ECG_FIR_BLOCK_SIZE 1

// 滤波器输入归一化用的满量程。ADS1292 是 24 位，满量程 ±2^23。
// 注意：ecg_filter 本身不做归一化，归一化在 pan_tompkins.c 里做，
// 这里写下来是为了让两个模块的标度约定集中在一处。
#define ADS24_FULL_SCALE 8388608.0f

void ECG_Filter_Init(void);
float32_t ECG_Filter_Process(float32_t input);

#endif
