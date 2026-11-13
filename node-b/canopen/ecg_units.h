#ifndef B4_ECG_UNITS_H
#define B4_ECG_UNITS_H
#include <stdint.h>
/* 绑定冻结的CH2SET=0x40（GAIN[2:0]=100→4），不是ADS复位默认gain6。
 * BIO显示量先按h*10^6/2^23截断；TI数据格式LSB=Vref/(2^23-1)，还需补偿两者分母差。
 * 名义差分电压再除PGA gain得到µV，网关/1000输出mV。
 * 参考2.42V未经绝对校准；这里只修复通信单位，绝不改变ADC寄存器或BIO阈值。 */
#define B4_ECG_CH2SET 0x40u
#define B4_ECG_GAIN 4u
#define B4_ECG_VREF_UV 2420000u
static inline int32_t b4_ecg_display_to_uv(int32_t display) {
    /* (121/200)*(8388608/8388607)约分为126877696/209715175。
     * int32×分子最大约2.73e17，int64安全；C99除法向零截断。
     * 整数显示量到整数µV的量化误差严格小于1µV，不包括上游UI量化/滤波或参考误差。 */
    return (int32_t)((int64_t)display * 126877696 / 209715175);
}
#endif
