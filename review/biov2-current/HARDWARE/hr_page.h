#ifndef __HR_PAGE_H
#define __HR_PAGE_H

#include <stdint.h>

/* ============================================================================
 * 控件 ID（与 UI 工程 心率呼吸监护_UI_控件版_DC80480DN050 的 DefineID.h 一致）
 * 页面：0 主界面 1 趋势 2 报警记录 3 设置 4 暂停 5 报警与探头状态 6 清空 7 时间设置(lua)
 * ==========================================================================*/
#define HP_SCR_HOME    0
#define HP_SCR_TREND   1
#define HP_SCR_LOG     2
#define HP_SCR_SET     3
#define HP_SCR_PAUSE   4
#define HP_SCR_PROBE   5
#define HP_SCR_CLEAR   6

// ---- 主界面(0) ----
#define HP_TXT_HR      10   // 心率大数字
#define HP_TXT_RESP    11   // 呼吸率大数字
#define HP_TXT_VALID   12   // 测量有效/无效
#define HP_TXT_HR_LIM  13   // 心率报警限值行
#define HP_TXT_HR_ST   14   // 心率状态字
#define HP_TXT_RR_LIM  15   // 呼吸报警限值行
#define HP_TXT_RR_ST   16   // 呼吸状态字
#define HP_TXT_QUAL    17   // 信号质量
#define HP_GRAP_ECG    19   // 心电波形
#define HP_TXT_CAP     20   // 采集状态
#define HP_GRAP_RESP   22   // 呼吸波形
#define HP_TXT_RUN     23   // 监护运行中
#define HP_TXT_STOP    24   // 监护已暂停
#define HP_BTN_RESUME  27   // 恢复监护直达按钮

// ---- 暂停监护页(4) ----
#define HP_TXT_PAUSE   10   // 暂停确认提示文本（lua 写，MCU 回读判运行/暂停）

// ---- 趋势页(1) ----
#define HP_TXT_T_HR    10   // 最近心率
#define HP_TXT_T_RR    11   // 最近呼吸率
#define HP_HIS_HR      12   // 心率历史曲线
#define HP_HIS_RR      14   // 呼吸历史曲线
#define HP_TXT_T0      15   // 横轴刻度下排(呼吸曲线下) id15..18
#define HP_TXT_U0      19   // 横轴刻度上排(心率曲线下) id19..22

// ---- 报警记录页(2)：4 行 x [时间/事件/等级/状态] ----
#define HP_LOG_ROW0    20
#define HP_TXT_EVT_CNT 10
#define HP_TXT_EMPTY   11

// ---- 设置页(3)：lua 同一套 ±按钮 ----
#define HP_TXT_HI_HR     1
#define HP_BTN_HR_HI_DEC 2
#define HP_BTN_HR_HI_INC 3
#define HP_TXT_LO_HR     4
#define HP_BTN_HR_LO_DEC 5
#define HP_BTN_HR_LO_INC 6
#define HP_TXT_HI_RR     7
#define HP_BTN_RR_HI_DEC 8
#define HP_BTN_RR_HI_INC 9
#define HP_TXT_LO_RR    10
#define HP_BTN_RR_LO_DEC 11
#define HP_BTN_RR_LO_INC 12
#define HP_BTN_SOUND    16   // 报警声音开关

// ---- 公共状态条（每页都有） ----
#define HP_TXT_PROBE   91   // 探头已接入/未接入

// ---- 报警与探头状态页(5) ----
#define HP_TXT5_NAME   11   // 报警详情名
#define HP_TXT5_ADVICE 12   // 处理建议
#define HP_TXT5_PROBE  13
#define HP_TXT5_UPD    14
#define HP_TXT5_QUAL   15
#define HP_BAR5_QUAL   16
#define HP_TXT5_HR     17
#define HP_TXT5_RR     18
#define HP_TXT5_VALTM  19
#define HP_TXT5_FOOT   20

// ---- 对外数据快照（CANopen 上报 / 配置用，只读） ----
#define HP_VAL_INVALID      ((int16_t)0x7FFF)  // 心率/呼吸无效标记

typedef struct
{
    uint8_t  hr_valid;  // 心率有效
    uint8_t  rr_valid;  // 呼吸有效
    uint8_t  probe;  // 导联已接入(探头在线且至少一路有效)
    uint8_t  running;  // 监护中(未暂停)
    uint8_t  alarm;  // 0 正常 1 心率报警 2 呼吸报警 3 两路都异常
    uint8_t  quality;  // 信号质量 0~100
    int16_t  bpm;  // 心率 bpm，无效时 = HP_VAL_INVALID
    int16_t  rpm;  // 呼吸率 rpm，无效时 = HP_VAL_INVALID
    int16_t  hr_hi;  // 心率上限 bpm
    int16_t  hr_lo;  // 心率下限 bpm
    int16_t  rr_hi;  // 呼吸上限 rpm
    int16_t  rr_lo;  // 呼吸下限 rpm
} HrVitals_t;

void    HrPage_GetVitals(HrVitals_t *v);
// 写回限值：内部按屏规则夹紧(范围+最小间隔)；返回 1 = 已生效并刷屏
uint8_t HrPage_SetLimits(int16_t hr_hi, int16_t hr_lo, int16_t rr_hi, int16_t rr_lo);

void HrPage_Init(void);
void HrPage_Task(uint32_t now_ms);
void HrPage_NotifyScreen(uint16_t screen_id);
void HrPage_OnButton(uint16_t scr, uint16_t ctl, uint8_t state);
void HrPage_OnText(uint16_t scr, uint16_t ctl, uint8_t *str);
void HrPage_OnRtcTime(uint8_t year, uint8_t month, uint8_t day,
                      uint8_t hour, uint8_t min, uint8_t sec, uint32_t now_ms);

#endif
