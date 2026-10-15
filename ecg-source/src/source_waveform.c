#include "source_waveform.h"
extern const uint16_t src_sine[1000],src_ecg60[1000],src_ecg90[2000];
static const SrcTable tables[]={
    {0,0,0,0}, {0,0,0,0}, {src_sine,1000,0,0},
    {src_ecg60,1000,1,60}, {src_ecg90,2000,3,90}
};
const SrcTable *Src_GetTable(uint32_t mode)
{
    return mode<=SRC_ECG_90 ? &tables[mode] : 0;
}
uint8_t Src_CopyRotated(const uint16_t *codes,uint32_t length,uint32_t *out)
{
    uint32_t i;
    if(!codes || !out || length==0 || length>SRC_MAX_TABLE)return 0;
    /* 先完整校验再写DMA缓冲，错误输入不能留下半张可运行表，也不通过削顶掩盖错误。 */
    for(i=0;i<length;i++)if(codes[i]<SRC_MIN_CODE || codes[i]>SRC_MAX_CODE)return 0;
    /* DHR预装第0点；第1次TRGO输出它后DMA必须装第1点，避免启动重复/周期错位。 */
    for(i=0;i<length;i++)out[i]=codes[(i+1u)%length];
    return 1;
}
uint8_t Src_TimerPlan(uint32_t timer_hz,uint32_t *psc,uint32_t *arr)
{
    if(!psc || !arr || timer_hz<1000000u || timer_hz>84000000u || timer_hz%1000000u)return 0;
    /* 定时器先分到1MHz，再1000计数触发一次；只有整除条件成立才宣布名义1kSPS。 */
    *psc=timer_hz/1000000u-1u;*arr=1000000u/SRC_SAMPLE_HZ-1u;
    return 1;
}
