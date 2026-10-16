#ifndef __RESP_RATE_H
#define __RESP_RATE_H

#include <stdint.h>

// 呼吸率算法的输入采样率，必须与 ADS1292 CONFIG1 的 DR[2:0] 一致。
// 注意：呼吸通道的"低通"系数是按这个采样率算的，改采样率要一起改。
#define RESP_SAMPLE_RATE_HZ       250

// 呼吸率量程：6 ~ 40 次/分
#define RESP_MIN_BPM              6
#define RESP_MAX_BPM              40

// 判定有效的超时。
// 原实现写的是 2 秒 —— 但这和 6 次/分（间隔 10 秒）自相矛盾，
// 2 秒超时会把手动减慢的呼吸一直判成"无信号"。
// （它当时"能用"是因为另一个 bug 让测出的呼吸率翻倍、间隔减半，
//   两个错误互相抵消了。翻倍问题已修正，所以这里必须放到 12 秒。）
#define RESP_TIMEOUT_MS           12000

void     RespRate_Init(void);
void     RespRate_Process(int32_t respiration_sample);
uint8_t  RespRate_Get(uint16_t *respiration_rate);
int32_t  RespRate_GetFiltered(void);

/* 采集时戳接口，避免排队消费改变呼吸间隔。 */
void RespRate_ProcessAt(int32_t sample,uint32_t sample_ms);
#endif
