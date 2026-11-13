/**
 * @file    hr_page.c
 * @brief   心率/呼吸屏业务层：ADS1292 数据 -> 实时显示 / 波形 / 报警 / 趋势 / 记录
 *
 * 节拍（HrPage_Task 里按传入的 10ms 时基分频）：
 *   每帧   : 抑制接触伪迹 -> 喂算法 + 心电/呼吸波形抽点推屏（仅主界面在前台时）
 *   1 s    : 心率/呼吸数字 + 状态字 + 报警判定 + 探头状态页(5)整页刷新
 *   10 s   : 信号质量（帧通过率 x 覆盖率）
 *   60 s   : 趋势历史曲线推点（1 点/分钟，进趋势页时 TrendSync 补齐）
 *   30 s   : ReadRTC 校时（报警记录时间戳用）
 *   500 ms : 回读屏上控件（报警声音开关 + 设置页 4 个限值框 + 暂停页提示文本）
 * 设置页 ± 按钮、暂停页确认/恢复按钮都是 button_type=2（自定义按键），
 * 帧里 Status 是保留字节，MCU 收不到按下/弹起；故一律以 lua 写出的文本为源，
 * MCU 定期回读：限值读设置页 4 个框，运行/暂停读暂停页提示文本。
 * 暂停中不判定不报警（s_run=0）。
 */
#include "hmi_driver.h"
#include "hr_page.h"
#include "ads1292.h"
#include "pan_tompkins.h"
#include "resp_rate.h"
#include "beep.h"
#include "timer.h"
#include <stdio.h>
#include <string.h>

// ---------------- 阈值规则（与屏内 main.lua 完全同一套） ----------------
#define HP_HR_STEP        5     // 心率步长 5 bpm
#define HP_HR_HI_LO       100   // 心率上限可调 100~250
#define HP_HR_HI_HI       250
#define HP_HR_LO_LO       30    // 心率下限可调 30~150
#define HP_HR_LO_HI       150
#define HP_HR_GAP         10    // 心率上下限最小间隔
#define HP_HR_DEF_HI      120
#define HP_HR_DEF_LO      50

#define HP_RR_STEP        1     // 呼吸步长 1 rpm
#define HP_RR_HI_LO       10    // 呼吸上限可调 10~60
#define HP_RR_HI_HI       60
#define HP_RR_LO_LO       4     // 呼吸下限可调 4~40
#define HP_RR_LO_HI       40
#define HP_RR_GAP         2
#define HP_RR_DEF_HI      30
#define HP_RR_DEF_LO      8

#define HP_OFFLINE_MS     5000  // 5 s 无新帧 = 模块离线（250Hz，余量巨大）

#define HP_HIST_N         1440  // 趋势历史 1440 点 = 24 小时（1 点/分钟）
#define HP_LOG_ROWS       4

#define HP_PERIOD_VALUE   1000
#define HP_PERIOD_QUAL    10000
#define HP_PERIOD_MIN     60000
#define HP_PERIOD_RTC     30000
#define HP_PERIOD_SCAN    500   // 回读屏上控件（声音开关 / 限值框 / 暂停页提示）

#define HP_ECG_DECIM      4     // 心电 250Hz -> 62.5Hz 上屏（曲线 1 点=1px）
#define HP_RESP_DECIM     8     // 呼吸 250Hz -> 31.25Hz 上屏

/* 接触电位跳变抑制：电极-皮肤跳变单步可达 1.4mV（≈9500 码），
   真 QRS 斜率只 ~0.2mV（≈1400 码），门限取 0.72mV（5000 码）不误伤 R 波。
   50Hz 不用单独陷波：PanTompkins 里的 129 抽头 FIR 带通止带已在 29Hz 以上。 */
#define HP_SPIKE_STEP     80000
#define HP_SPIKE_MAX      5
/* 5-point median rejects isolated 1-2 sample spikes at 250 SPS (8 ms delay).
 * 上面的门限是增益 2（CH2SET=0x20，≈6932 码/mV）下的码值，改增益必须同比缩放。 */
#define HP_MEDIAN_N       5
#define HP_ADC_CLIP       8304721 // 99% of signed 24-bit positive full scale

// 屏内按钮状态：0 = 松开（按下+弹起都会通知，只认弹起防双触发）
#define HP_BTN_RELEASE    0

// 板载蜂鸣器节拍
#define HP_BEEP_ON_MS     150
#define HP_BEEP_OFF_MS    100

// 上电默认报警声音: 0 关 1 开
#define HP_DEF_SOUND      0

// RGB565
#define HP_C_GREEN        20208
#define HP_C_RED          64398
#define HP_C_ORANGE       62689
#define HP_C_GREY         38167
#define HP_C_PGREEN       28371  // 探头条原始绿(104,217,159)

// 中文提示走 GBK 字节数组（屏固件按 GBK 渲染）
static const uint8_t STR_HR_OK[]  = {0xD0,0xC4,0xC2,0xCA,0xD5,0xFD,0xB3,0xA3,0};   // 心率正常
static const uint8_t STR_HR_HI[]  = {0xD0,0xC4,0xC2,0xCA,0xB9,0xFD,0xCB,0xD9,0};   // 心率过速
static const uint8_t STR_HR_LO[]  = {0xD0,0xC4,0xC2,0xCA,0xB9,0xFD,0xBB,0xBA,0};   // 心率过缓
static const uint8_t STR_RR_OK[]  = {0xBA,0xF4,0xCE,0xFC,0xD5,0xFD,0xB3,0xA3,0};   // 呼吸正常
static const uint8_t STR_RR_HI[]  = {0xBA,0xF4,0xCE,0xFC,0xB9,0xFD,0xCB,0xD9,0};   // 呼吸过速
static const uint8_t STR_RR_LO[]  = {0xBA,0xF4,0xCE,0xFC,0xB9,0xFD,0xBB,0xBA,0};   // 呼吸过缓
static const uint8_t STR_BAD[]    = {0xB2,0xE2,0xC1,0xBF,0xCE,0xDE,0xD0,0xA7,0};   // 测量无效
static const uint8_t STR_GOOD[]   = {0xB2,0xE2,0xC1,0xBF,0xD3,0xD0,0xD0,0xA7,0};   // 测量有效
static const uint8_t STR_LIM[]    = {0xB1,0xA8,0xBE,0xAF,0xCF,0xDE,0xD6,0xB5,0x20,0}; // "报警限值 "
static const uint8_t STR_CAP[]    = {0xD0,0xC4,0xB5,0xE7,0x2F,0xBA,0xF4,0xCE,0xFC,0xB2,0xC9,0xBC,0xAF,0xD6,0xD0,0}; // 心电/呼吸采集中
static const uint8_t STR_RUN[]    = {0xBC,0xE0,0xBB,0xA4,0xD4,0xCB,0xD0,0xD0,0xD6,0xD0,0}; // 监护运行中
static const uint8_t STR_PAUSE[]  = {0xBC,0xE0,0xBB,0xA4,0xD2,0xD1,0xD4,0xDD,0xCD,0xA3,0}; // 监护已暂停
// 暂停页提示文本里的状态关键词"已暂停"（= STR_PAUSE 尾部 6 字节）
#define STR_TAG_PAUSED  (STR_PAUSE + 4)
static const uint8_t STR_URG[]    = {0xBD,0xF4,0xBC,0xB1,0};                        // 紧急
static const uint8_t STR_GEN[]    = {0xD2,0xBB,0xB0,0xE3,0};                        // 一般
static const uint8_t STR_ACT[]    = {0xB1,0xA8,0xBE,0xAF,0xD6,0xD0,0};              // 报警中
static const uint8_t STR_END[]    = {0xD2,0xD1,0xBD,0xE2,0xB3,0xFD,0};              // 已解除
static const uint8_t STR_NONE[]   = {0xD4,0xDD,0xCE,0xDE,0xB1,0xA8,0xBE,0xAF,0xBC,0xC7,0xC2,0xBC,0}; // 暂无报警记录
static const uint8_t STR_CNT[]    = {0xB1,0xA8,0xBE,0xAF,0xCA,0xC2,0xBC,0xFE,0x20,0}; // "报警事件 "
static const uint8_t STR_TIAO[]   = {0x20,0xCC,0xF5,0};                             // " 条"
static const uint8_t STR_PROBE_ON[]  = {0xCC,0xBD,0xCD,0xB7,0xD2,0xD1,0xBD,0xD3,0xC8,0xEB,0};  // 探头已接入
static const uint8_t STR_PROBE_OFF[] = {0xCC,0xBD,0xCD,0xB7,0xCE,0xB4,0xBD,0xD3,0xC8,0xEB,0};  // 探头未接入
static const uint8_t STR_Q_GOOD[] = {0xD0,0xC5,0xBA,0xC5,0xC1,0xBC,0xBA,0xC3,0};   // 信号良好
static const uint8_t STR_Q_WEAK[] = {0xD0,0xC5,0xBA,0xC5,0xC6,0xAB,0xC8,0xF5,0};   // 信号偏弱
static const uint8_t STR_ADV_OK[] = {0xD0,0xC5,0xBA,0xC5,0xD3,0xEB,0xCA,0xFD,0xBE,0xDD,0xC1,0xB4,0xC2,0xB7,0xD5,0xFD,0xB3,0xA3,0x2C,0x20,0xBC,0xE0,0xBB,0xA4,0xBD,0xF8,0xD0,0xD0,0xD6,0xD0,0xA1,0xA3,0};
static const uint8_t STR_ADV_WEAK[] = {0xD0,0xC5,0xBA,0xC5,0xBD,0xCF,0xC8,0xF5,0x2C,0x20,0xC7,0xEB,0xBC,0xEC,0xB2,0xE9,0xB5,0xE7,0xBC,0xAB,0xC5,0xC6,0xB4,0xF7,0xB4,0xF7,0xA1,0xA3,0};
static const uint8_t STR_ADV_OFF[]  = {0xB5,0xBC,0xC1,0xAA,0xCE,0xB4,0xC1,0xAC,0xBD,0xD3,0x2C,0x20,0xC7,0xEB,0xBC,0xEC,0xB2,0xE9,0xD0,0xD8,0xB5,0xBC,0xC1,0xAA,0xBD,0xD3,0xCF,0xDF,0xA1,0xA3,0};
static const uint8_t STR_LIVE[]  = {0xCA,0xB5,0xCA,0xB1,0xBC,0xE0,0xBB,0xA4,0xD6,0xD0,0};          // 实时监护中
static const uint8_t STR_WAIT[]  = {0xB5,0xC8,0xB4,0xFD,0xCE,0xC8,0xB6,0xA8,0xD0,0xC5,0xBA,0xC5,0}; // 等待稳定信号

// ---------------- 内部状态 ----------------
static uint8_t  s_run = 1;
static uint8_t  s_cur = HP_SCR_HOME;
static uint8_t  s_sound = HP_DEF_SOUND;

static uint16_t s_hr_hi = HP_HR_DEF_HI;
static uint16_t s_hr_lo = HP_HR_DEF_LO;
static uint16_t s_rr_hi = HP_RR_DEF_HI;
static uint16_t s_rr_lo = HP_RR_DEF_LO;

static uint8_t  s_st_hr;            // 0 正常 1 过速 2 过缓 3 无效
static uint8_t  s_st_rr;
static uint8_t  s_row_hr = 0xFF;    // 该报警源在记录页的行号，0xFF = 无
static uint8_t  s_row_rr = 0xFF;

static uint32_t s_frame_ms;         // 最近读到帧的时刻
static uint32_t s_t_scan;           // 屏控件回读节拍

static uint32_t s_ecg_cnt, s_resp_cnt;  // 上屏抽点分频计数（250Hz 原始帧计数）
static int32_t  s_ecg_peak = 1000;      // 心电波形自动增益跟踪峰值（ADC 码）
static int32_t  s_rr_peak  = 4096;      // 呼吸波形自动增益跟踪峰值（ADC 码）

static int32_t  s_sp_p;             // 伪迹抑制器：上一个可信值
static uint8_t  s_sp_init;
static int32_t  g_ecgMedian[HP_MEDIAN_N];
static uint8_t  g_medianIndex, g_medianReady;
static uint32_t g_ecgLastMs;
static uint32_t g_ecgLastSequence;
static uint8_t  g_ecgHaveFrame;
static uint8_t  s_sp_n;             // 剩余抑制点数

static uint16_t s_bpm, s_rpm;       // 最近一次取到的心率/呼吸率
static uint8_t  s_bpm_valid, s_rpm_valid;

static int16_t  s_hh[HP_HIST_N];    // 心率历史 bpm
static uint16_t s_hh_cnt;
static uint32_t s_hh_gen, s_hh_push;
static int16_t  s_rrh[HP_HIST_N];   // 呼吸历史 rpm
static uint16_t s_rrh_cnt;
static uint32_t s_rrh_gen, s_rrh_push;

static uint32_t s_frm_last, s_miss_last;
static uint8_t  s_quality;
static uint8_t  s_probe;
static char     s_valtm[9];         // 最近有效测量时刻 hh:mm:ss

static uint32_t s_now_ms;
static uint32_t s_btn_ms;
static uint16_t s_btn_key;

static uint32_t s_t_value, s_t_qual, s_t_min, s_t_rtc;
static uint32_t s_rtc_abs, s_rtc_ms;
static uint8_t  s_rtc_ok;

// 报警记录：环形 4 行
static uint16_t s_log_total;
static uint8_t  s_log_row;
static const uint8_t *s_log_evt[HP_LOG_ROWS];
static const uint8_t *s_log_lvl[HP_LOG_ROWS];
static uint8_t  s_log_act[HP_LOG_ROWS];   // 1=报警中 0=已解除
static char     s_log_time[HP_LOG_ROWS][9];

// ---------------- 小工具 ----------------
static void TxtGB(uint16_t scr, uint16_t ctl, const uint8_t *gb)
{
    SetTextValue((uint16)scr, (uint16)ctl, (uchar *)gb);
}

// 公历 <-> 天数(1970 起)：报警时间戳用（与体温工程同实现）
static uint32_t CivilDays(uint16_t y, uint8_t m, uint8_t d)
{
    int32_t yy = (int32_t)y;
    int32_t era;
    uint32_t yoe, doy, doe;

    if (m <= 2) { yy -= 1; }
    era = (yy >= 0) ? (yy / 400) : ((yy - 399) / 400);
    yoe = (uint32_t)(yy - era * 400);
    doy = (uint32_t)(153 * (m + ((m > 2) ? -3 : 9)) + 2) / 5 + d - 1;
    doe = yoe * 365 + yoe / 4 - yoe / 100 + doy;
    return (uint32_t)era * 146097 + doe - 719468;
}

static uint32_t SecOfDay(uint32_t now_ms)
{
    uint32_t t;

    if (s_rtc_ok == 0) { return 0xFFFFFFFF; }
    // 以最近一次 RTC 读数为锚点，用 MCU 毫秒外推当前当天秒数
    t = s_rtc_abs + (now_ms - s_rtc_ms) / 1000;
    return t % 86400;
}

static void TimeStr(char *buf, uint32_t now_ms)
{
    uint32_t sec = SecOfDay(now_ms);

    if (sec == 0xFFFFFFFF) { strcpy(buf, "--:--:--"); return; }
    sprintf(buf, "%02u:%02u:%02u",
            (unsigned)(sec / 3600), (unsigned)((sec / 60) % 60),
            (unsigned)(sec % 60));
}

// ---------------- 波形上屏（自动增益：峰值归一化到 0~255） ----------------
static uint8_t WaveScale(int32_t v, int32_t *peak)
{
    int32_t a = (v >= 0) ? v : -v;
    int32_t y;

    if (a > *peak)      { *peak = a; }
    else                { *peak -= (*peak >> 8) + 1; if (*peak < 200) { *peak = 200; } }
    // 以峰值满量程映射到中线 128 上下 ±110 级（屏波形通道按 0~255 纵坐标绘制）
    y = 128 + (v * 110) / *peak;
    if (y < 0)   { y = 0; }
    if (y > 255) { y = 255; }
    return (uint8_t)y;
}

// ---------------- 报警记录 ----------------
static void LogWrite(uint8_t row, const char *tstr, const uint8_t *evt,
                     const uint8_t *lvl, const uint8_t *st)
{
    uint16_t base = (uint16_t)(HP_LOG_ROW0 + row * 4);

    SetTextValue(HP_SCR_LOG, base, (uchar *)tstr);
    TxtGB(HP_SCR_LOG, (uint16_t)(base + 1), evt);
    TxtGB(HP_SCR_LOG, (uint16_t)(base + 2), lvl);
    TxtGB(HP_SCR_LOG, (uint16_t)(base + 3), st);
}

static void LogRefresh(void)
{
    char buf[20];
    uint8_t i;
    uint16_t shown;

    shown = (s_log_total > HP_LOG_ROWS) ? HP_LOG_ROWS : s_log_total;
    for (i = 0; i < shown; i++)
    {
        LogWrite(i, s_log_time[i], s_log_evt[i], s_log_lvl[i],
                 (s_log_act[i] != 0) ? STR_ACT : STR_END);
    }
    sprintf(buf, "%s%u%s", (const char *)STR_CNT, (unsigned)s_log_total,
            (const char *)STR_TIAO);
    SetTextValue(HP_SCR_LOG, HP_TXT_EVT_CNT, (uchar *)buf);
    TxtGB(HP_SCR_LOG, HP_TXT_EMPTY, (s_log_total == 0) ? STR_NONE : (const uint8_t *)"");
}

// 单一报警源状态翻转：进报警写一行记录，退出把该行标已解除
static void AlarmOne(uint8_t st_new, uint8_t st_old, const uint8_t *evt_hi,
                     const uint8_t *evt_lo, uint32_t now_ms, uint8_t *myrow)
{
    char tbuf[12];
    uint8_t row;

    if (st_new == st_old) { return; }

    if ((st_new == 1) || (st_new == 2))
    {
        TimeStr(tbuf, now_ms);
        row = s_log_row;
        strcpy(s_log_time[row], tbuf);
        s_log_evt[row] = (st_new == 1) ? evt_hi : evt_lo;
        s_log_lvl[row] = (st_new == 1) ? STR_URG : STR_GEN;
        s_log_act[row] = 1;
        s_log_row = (uint8_t)((s_log_row + 1) % HP_LOG_ROWS);
        s_log_total++;
        *myrow = row;
        LogWrite(row, tbuf, s_log_evt[row], s_log_lvl[row], STR_ACT);
        LogRefresh();
    }
    else if ((st_old == 1) || (st_old == 2))
    {
        if (*myrow < HP_LOG_ROWS)
        {
            s_log_act[*myrow] = 0;
            TxtGB(HP_SCR_LOG, (uint16_t)(HP_LOG_ROW0 + *myrow * 4 + 3), STR_END);
            *myrow = 0xFF;
        }
    }
}

// ---------------- 每帧：喂算法 + 波形 ----------------

// Reset acquisition history after discontinuity, clipping or initial startup.
// 2026-10-07 HU JIAXUAN: never join old and new electrode segments.
static void ecg_reset_at(uint32_t sample_ms)
{
    s_sp_init = 0;
    s_sp_n = 0;
    g_medianReady = 0;
    g_medianIndex = 0;
    PanTompkins_InvalidateAt(sample_ms);
}

/* 初始化等无帧调用仍以当前时刻为基准。 */
static void ecg_reset(void) { ecg_reset_at(TimeBase_GetMs()); }

// Median of the latest five ADC samples; seed with the first actual sample.
// 2026-10-07 HU JIAXUAN: migrate useful impulse rejection without debug output.
static int32_t ecg_median(int32_t value)
{
    int32_t sorted[HP_MEDIAN_N], item;
    uint8_t i, j;
    if (g_medianReady == 0) {
        for (i = 0; i < HP_MEDIAN_N; i++) { g_ecgMedian[i] = value; }
        g_medianReady = 1;
    }
    g_ecgMedian[g_medianIndex] = value;
    g_medianIndex = (uint8_t)((g_medianIndex + 1) % HP_MEDIAN_N);
    for (i = 0; i < HP_MEDIAN_N; i++) { sorted[i] = g_ecgMedian[i]; }
    for (i = 1; i < HP_MEDIAN_N; i++) {
        item = sorted[i];
        for (j = i; j > 0 && sorted[j - 1] > item; j--) {
            sorted[j] = sorted[j - 1];
        }
        sorted[j] = item;
    }
    return sorted[HP_MEDIAN_N / 2];
}

/* 接触伪迹抑制（保持-释放）。
   超门限判为伪迹，最多抑制 HP_SPIKE_MAX 点；释放时**无条件**按 1/8 步长追随输入，
   收敛快于门限就退出。不能只在"脱离门限"时才追随 —— 那样输入跳到新电平并停住时
   会被永久冻结（V0933A 死锁，实测 A 列钉死不动）。 */
static int32_t EcgDespike(int32_t v)
{
    int32_t d;

    if (s_sp_init == 0) { s_sp_init = 1; s_sp_p = v; return v; }

    d = v - s_sp_p;
    if (d < 0) { d = -d; }
    if (d > HP_SPIKE_STEP) {
        if (s_sp_n < HP_SPIKE_MAX) { s_sp_n++; }
    }

    if (s_sp_n > 0) {
        s_sp_p += (v - s_sp_p) / 8;
        if (d <= HP_SPIKE_STEP) { s_sp_n--; }
    } else {
        s_sp_p = v;
    }
    return s_sp_p;
}

static void FrameFeed(uint32_t now_ms)
{
    uint8_t f[9];
    int32_t resp_code, ecg_code;
    uint32_t sampleMs, sequence;

    // 一次任务循环把驱动接收缓冲里攒的帧全部取完；每帧 9 字节
    while (ADS1292_ReadFrame(f) != 0)
    {
        s_frame_ms = now_ms;
        resp_code = ADS1292_S24ToS32(&f[3]);     // CH1 = 呼吸
        ecg_code  = ADS1292_S24ToS32(&f[6]);     // CH2 = 心电
        sampleMs = ADS1292_GetLastFrameMs();
        sequence = ADS1292_GetLastFrameSequence();
        /* 真实采样顺序与时戳：发现溢出/断段时不拼接旧滤波历史。 */
        if (g_ecgHaveFrame != 0 &&
            ((sampleMs - g_ecgLastMs) > PT_INPUT_GAP_MS ||
             sequence != (uint32_t)(g_ecgLastSequence + 1u) || ADS1292_GetLastFrameFlags()!=0)) {
            ecg_reset_at(sampleMs); RespRate_Init();
        }
        RespRate_ProcessAt(resp_code,sampleMs);
        g_ecgLastSequence = sequence;
        g_ecgHaveFrame = 1;
        g_ecgLastMs = sampleMs;
		
        if (ecg_code >= HP_ADC_CLIP || ecg_code <= -HP_ADC_CLIP) {
            ecg_reset_at(sampleMs);
        } else {
            // 中值滤波 -> 伪迹抑制 -> Pan-Tompkins 心率算法
            PanTompkins_ProcessAt(EcgDespike(ecg_median(ecg_code)),sampleMs);
        }

        /* 导联脱落不做硬件判定（本模块 LOFF 激励电流已关，STATUS 位不可信），
           脱落由算法超时体现：心率 4s、呼吸 12s 无有效值即显示 --- */

        s_ecg_cnt++;
        if (((s_ecg_cnt % HP_ECG_DECIM) == 0) && (s_run != 0) &&
            (s_cur == HP_SCR_HOME))
        {
            uint8_t pt = WaveScale(PanTompkins_GetFiltered(), &s_ecg_peak);

            // 向波形控件通道 0 追加 1 点，屏内曲线自动左滚，1 点 = 1 像素
            GraphChannelDataAdd(HP_SCR_HOME, HP_GRAP_ECG, 0, &pt, 1);
        }
        s_resp_cnt++;
        if (((s_resp_cnt % HP_RESP_DECIM) == 0) && (s_run != 0) &&
            (s_cur == HP_SCR_HOME))
        {
            uint8_t pt = WaveScale(RespRate_GetFiltered(), &s_rr_peak);

            GraphChannelDataAdd(HP_SCR_HOME, HP_GRAP_RESP, 0, &pt, 1);
        }
    }
}

// ---------------- 限值显示 ----------------
static void WriteLimits(void)
{
    char buf[32];

    strcpy(buf, (const char *)STR_LIM);
    sprintf(buf + strlen(buf), "%u-%u bpm", (unsigned)s_hr_lo, (unsigned)s_hr_hi);
    SetTextValue(HP_SCR_HOME, HP_TXT_HR_LIM, (uchar *)buf);

    strcpy(buf, (const char *)STR_LIM);
    sprintf(buf + strlen(buf), "%u-%u rpm", (unsigned)s_rr_lo, (unsigned)s_rr_hi);
    SetTextValue(HP_SCR_HOME, HP_TXT_RR_LIM, (uchar *)buf);
}

// 设置页 4 个阈值框回显
static void WriteSetupTexts(void)
{
    char buf[8];

    sprintf(buf, "%u", (unsigned)s_hr_hi);
    SetTextValue(HP_SCR_SET, HP_TXT_HI_HR, (uchar *)buf);
    sprintf(buf, "%u", (unsigned)s_hr_lo);
    SetTextValue(HP_SCR_SET, HP_TXT_LO_HR, (uchar *)buf);
    sprintf(buf, "%u", (unsigned)s_rr_hi);
    SetTextValue(HP_SCR_SET, HP_TXT_HI_RR, (uchar *)buf);
    sprintf(buf, "%u", (unsigned)s_rr_lo);
    SetTextValue(HP_SCR_SET, HP_TXT_LO_RR, (uchar *)buf);
}

// ---------------- 探头/导联接入状态 ----------------
static void WriteProbe(void)
{
    uint16_t color = (s_probe != 0) ? HP_C_PGREEN : HP_C_RED;
    const uint8_t *txt = (s_probe != 0) ? STR_PROBE_ON : STR_PROBE_OFF;

    TxtGB(s_cur, HP_TXT_PROBE, txt);
    SetControlForeColor(s_cur, HP_TXT_PROBE, color);
    if (s_cur == HP_SCR_PROBE)
    {
        TxtGB(s_cur, HP_TXT5_PROBE, txt);
        SetControlForeColor(s_cur, HP_TXT5_PROBE, color);
    }
}

// 探头接入 = 5s 内有帧，且至少一路测量有效（脱落由算法超时体现）
static void ProbeRefresh(uint32_t now_ms)
{
    uint8_t conn = (uint8_t)(((now_ms - s_frame_ms) < HP_OFFLINE_MS) &&
                             ((s_bpm_valid != 0) || (s_rpm_valid != 0)));

    if (conn != s_probe)
    {
        s_probe = conn;
        WriteProbe();
    }
}

// ---------------- 每秒一次：数值 + 状态字 + 报警 ----------------
static void StateTxt(uint16_t ctl, uint8_t st)
{
    const uint8_t *txt;
    uint16_t color;

    if (st == 3)      { txt = STR_BAD;   color = HP_C_GREY; }
    else if (st == 1) { txt = (ctl == HP_TXT_HR_ST) ? STR_HR_HI : STR_RR_HI;
                        color = HP_C_RED; }
    else if (st == 2) { txt = (ctl == HP_TXT_HR_ST) ? STR_HR_LO : STR_RR_LO;
                        color = HP_C_ORANGE; }
    else              { txt = (ctl == HP_TXT_HR_ST) ? STR_HR_OK : STR_RR_OK;
                        color = HP_C_GREEN; }
    TxtGB(HP_SCR_HOME, ctl, txt);
    SetControlForeColor(HP_SCR_HOME, ctl, color);
}

static void ValueRefresh(uint32_t now_ms)
{
    char buf[8];
    uint8_t st_hr, st_rr;

    s_bpm_valid = PanTompkins_GetBPM(&s_bpm);
    s_rpm_valid = RespRate_Get(&s_rpm);

    // 状态码：0 正常 1 超限(过速) 2 欠限(过缓) 3 无效/暂停
    if (s_run == 0)                     { st_hr = 3; st_rr = 3; }
    else if (s_bpm_valid == 0)          { st_hr = 3; }
    else if (s_bpm > s_hr_hi)           { st_hr = 1; }
    else if (s_bpm < s_hr_lo)           { st_hr = 2; }
    else                                { st_hr = 0; }
    if (s_run == 0)                     { st_rr = 3; }
    else if (s_rpm_valid == 0)          { st_rr = 3; }
    else if (s_rpm > s_rr_hi)           { st_rr = 1; }
    else if (s_rpm < s_rr_lo)           { st_rr = 2; }
    else                                { st_rr = 0; }

    if ((s_cur == HP_SCR_HOME) && (s_run != 0))
    {
        if (st_hr == 3) { strcpy(buf, "---"); }
        else            { sprintf(buf, "%u", (unsigned)s_bpm); }
        SetTextValue(HP_SCR_HOME, HP_TXT_HR, (uchar *)buf);
        StateTxt(HP_TXT_HR_ST, st_hr);

        if (st_rr == 3) { strcpy(buf, "---"); }
        else            { sprintf(buf, "%u", (unsigned)s_rpm); }
        SetTextValue(HP_SCR_HOME, HP_TXT_RESP, (uchar *)buf);
        StateTxt(HP_TXT_RR_ST, st_rr);

        TxtGB(HP_SCR_HOME, HP_TXT_VALID,
              ((st_hr != 3) || (st_rr != 3)) ? STR_GOOD : STR_BAD);
        TxtGB(HP_SCR_HOME, HP_TXT_CAP, STR_CAP);
    }
    TxtGB(HP_SCR_HOME, HP_TXT_RUN, (s_run != 0) ? STR_RUN : (const uint8_t *)"");
    TxtGB(HP_SCR_HOME, HP_TXT_STOP, (s_run != 0) ? (const uint8_t *)"" : STR_PAUSE);

    // 最近一次有效测量时刻（探头状态页显示）
    if ((s_bpm_valid != 0) || (s_rpm_valid != 0)) { TimeStr(s_valtm, now_ms); }

    AlarmOne(st_hr, s_st_hr, STR_HR_HI, STR_HR_LO, now_ms, &s_row_hr);
    AlarmOne(st_rr, s_st_rr, STR_RR_HI, STR_RR_LO, now_ms, &s_row_rr);
    s_st_hr = st_hr;
    s_st_rr = st_rr;

    ProbeRefresh(now_ms);
}

// ---------------- 趋势 ----------------
static void TrendSyncOne(uint16_t ctl, const int16_t *h, uint16_t cnt,
                         uint32_t gen, uint32_t *push)
{
    float f;
    uint32_t i;
    int32_t k;
    uint32_t base;

    if (*push > gen) { *push = gen; }
    // 漏推超过一屏时只补最近 HP_HIST_N 点（屏重启/复位后自愈）
    if ((gen - *push) > HP_HIST_N) { *push = gen - HP_HIST_N; }
    base = gen - cnt;
    // gen=历史点累计生成序号，push=已推到屏的序号，区间内逐点补推
    for (i = *push; i < gen; i++)
    {
        k = (int32_t)(i - base);
        if (k >= 0)
        {
            f = (float)h[k];
            HistoryGraph_SetValueFloat(HP_SCR_TREND, ctl, &f, 1);
        }
    }
    *push = gen;
}

static void MinuteTick(void)
{
    uint16_t bpm, rpm;
    float f;

    if (s_run == 0) { return; }
    if (PanTompkins_GetBPM(&bpm) != 0)
    {
        if (s_hh_cnt < HP_HIST_N) { s_hh[s_hh_cnt++] = (int16_t)bpm; }
        else
        {
            // 24h 存满后整体前移 1 点，尾部放新值（线性滑动缓冲，非环形）
            memmove(&s_hh[0], &s_hh[1], (HP_HIST_N - 1) * sizeof(int16_t));
            s_hh[HP_HIST_N - 1] = (int16_t)bpm;
        }
        s_hh_gen++;
        if (s_cur == HP_SCR_TREND)
        {
            f = (float)bpm;
            HistoryGraph_SetValueFloat(HP_SCR_TREND, HP_HIS_HR, &f, 1);
            s_hh_push = s_hh_gen;
        }
    }
    if (RespRate_Get(&rpm) != 0)
    {
        if (s_rrh_cnt < HP_HIST_N) { s_rrh[s_rrh_cnt++] = (int16_t)rpm; }
        else
        {
            memmove(&s_rrh[0], &s_rrh[1], (HP_HIST_N - 1) * sizeof(int16_t));
            s_rrh[HP_HIST_N - 1] = (int16_t)rpm;
        }
        s_rrh_gen++;
        if (s_cur == HP_SCR_TREND)
        {
            f = (float)rpm;
            HistoryGraph_SetValueFloat(HP_SCR_TREND, HP_HIS_RR, &f, 1);
            s_rrh_push = s_rrh_gen;
        }
    }
    if (s_cur == HP_SCR_TREND)
    {
        char buf[8];

        if (PanTompkins_GetBPM(&bpm) == 0) { strcpy(buf, "---"); }
        else                               { sprintf(buf, "%u", (unsigned)bpm); }
        SetTextValue(HP_SCR_TREND, HP_TXT_T_HR, (uchar *)buf);
        if (RespRate_Get(&rpm) == 0)       { strcpy(buf, "---"); }
        else                               { sprintf(buf, "%u", (unsigned)rpm); }
        SetTextValue(HP_SCR_TREND, HP_TXT_T_RR, (uchar *)buf);
    }
}

// ---------------- 信号质量 ----------------
static void QualityTick(void)
{
    uint32_t frm, miss, d_f, d_m, tot, good, cov, inst;

    frm = ADS1292_GetFrameCount();
    miss = ADS1292_GetMissCount();
    d_f = frm - s_frm_last;
    d_m = miss - s_miss_last;
    s_frm_last = frm;
    s_miss_last = miss;
    tot = d_f + d_m;
    good = (tot != 0) ? (d_f * 100) / tot : 0;
    cov = (tot > 2500) ? 2500 : tot;      // 10 s 名义 2500 帧
    // 帧通过率 good% × 时间覆盖率，再按 2:3 新旧加权平滑
    inst = (good * cov) / 2500;
    s_quality = (uint8_t)((s_quality * 2 + inst * 3) / 5);
}

static void QualityRefresh(void)
{
    char buf[8];

    sprintf(buf, "%u", (unsigned)s_quality);
    SetTextValue(HP_SCR_HOME, HP_TXT_QUAL, (uchar *)buf);
    if (s_cur == HP_SCR_PROBE)
    {
        SetTextValue(HP_SCR_PROBE, HP_TXT5_QUAL, (uchar *)buf);
        SetProgressValue(HP_SCR_PROBE, HP_BAR5_QUAL, s_quality);
    }
}

// ---------------- 探头状态页(5) 每秒刷新 ----------------
static void ProbePageRefresh(uint32_t now_ms)
{
    char buf[40];
    const uint8_t *name, *adv;
    uint16_t color;
    uint8_t any_valid = (uint8_t)(((s_run != 0) &&
                                   ((s_bpm_valid != 0) || (s_rpm_valid != 0))) ? 1 : 0);

    TimeStr(buf, now_ms);
    SetTextValue(HP_SCR_PROBE, HP_TXT5_UPD, (uchar *)buf);
    SetTextValue(HP_SCR_PROBE, HP_TXT5_VALTM, (uchar *)s_valtm);

    if (s_probe == 0)
    {
        name = STR_PROBE_OFF; adv = STR_ADV_OFF;  color = HP_C_RED;
    }
    else if ((s_quality < 60) || (any_valid == 0))
    {
        name = STR_Q_WEAK;    adv = STR_ADV_WEAK; color = HP_C_ORANGE;
    }
    else
    {
        name = STR_Q_GOOD;    adv = STR_ADV_OK;   color = HP_C_PGREEN;
    }
    TxtGB(HP_SCR_PROBE, HP_TXT5_PROBE, name);
    SetControlForeColor(HP_SCR_PROBE, HP_TXT5_PROBE, color);
    TxtGB(HP_SCR_PROBE, HP_TXT5_NAME, name);
    TxtGB(HP_SCR_PROBE, HP_TXT5_ADVICE, adv);
    TxtGB(HP_SCR_PROBE, HP_TXT5_FOOT, (s_run != 0) ? STR_LIVE : STR_WAIT);

    if (s_bpm_valid == 0) { strcpy(buf, "---"); }
    else                  { sprintf(buf, "%u", (unsigned)s_bpm); }
    SetTextValue(HP_SCR_PROBE, HP_TXT5_HR, (uchar *)buf);
    if (s_rpm_valid == 0) { strcpy(buf, "---"); }
    else                  { sprintf(buf, "%u", (unsigned)s_rpm); }
    SetTextValue(HP_SCR_PROBE, HP_TXT5_RR, (uchar *)buf);
}

// ---------------- 板载蜂鸣器节拍（急促连响） ----------------
static void BeepTick(uint32_t now_ms)
{
    static uint32_t t0;
    static uint8_t  on;
    uint8_t active;

    active = (uint8_t)((s_run != 0) && (s_sound != 0) &&
                       ((s_st_hr == 1) || (s_st_hr == 2) ||
                        (s_st_rr == 1) || (s_st_rr == 2)));
    if (active == 0)
    {
        if (on != 0) { on = 0; BEEP_Off(); }
        return;
    }
    if (on == 0)
    {
        if ((now_ms - t0) >= HP_BEEP_OFF_MS) { t0 = now_ms; BEEP_On(); on = 1; }
    }
    else
    {
        if ((now_ms - t0) >= HP_BEEP_ON_MS) { t0 = now_ms; BEEP_Off(); on = 0; }
    }
}

// ---------------- 趋势页档位(30min/2h/8h)与横轴刻度 ----------------
/* 档位按钮 bt=1 开关型, 只在状态变化时发一帧(state=选中1/取消0)。
   历史曲线 1 点/分钟(sample_cycle=60), SetTimeLength 参数就是一屏点数:
   30 点铺满 558px(每点 18.6px), 480 点(每点 1.16px) */
static uint8_t s_range = 2;             // 当前档位 1/2/3, 上电默认 2h
static const uint16_t RANGE_MIN[4] = {0, 30, 120, 480};
static const uint16_t RANGE_LBL[4][3] =
{
    {0, 0, 0}, {30, 20, 10}, {120, 80, 40}, {480, 320, 160}
};

// 横轴刻度文本: "-N分"(分=B7D6) / "现在"(CFD6 D4DA)。
// 上下两排: U 排在心率曲线下(id19..22), T 排在呼吸曲线下(id15..18)
static void TrendLabel(uint16_t ctl, uint16_t min, uint8_t now)
{
    static const uint8_t GB_FEN[] = {0xB7, 0xD6, 0};
    static const uint8_t GB_NOW[] = {0xCF, 0xD6, 0xD4, 0xDA, 0};
    char buf[16];

    if (now != 0)
    {
        strcpy(buf, (const char *)GB_NOW);
    }
    else
    {
        sprintf(buf, "-%u%s", (unsigned)min, (const char *)GB_FEN);
    }
    SetTextValue(HP_SCR_TREND, ctl, (uchar *)buf);
}

static void TrendRangeSet(uint8_t r)
{
    uint8_t i;

    if ((r < 1) || (r > 3)) { return; }
    s_range = r;
    HistoryGraph_SetTimeLength(HP_SCR_TREND, HP_HIS_HR, RANGE_MIN[r]);
    HistoryGraph_SetTimeLength(HP_SCR_TREND, HP_HIS_RR, RANGE_MIN[r]);
    for (i = 0; i < 3; i++)
    {
        TrendLabel((uint16_t)(HP_TXT_U0 + i), RANGE_LBL[r][i], 0);
        TrendLabel((uint16_t)(HP_TXT_T0 + i), RANGE_LBL[r][i], 0);
    }
    TrendLabel((uint16_t)(HP_TXT_U0 + 3), 0, 1);
    TrendLabel((uint16_t)(HP_TXT_T0 + 3), 0, 1);
}

// ---------------- 屏控件回读 ----------------

// s 中是否含 GBK 串 pat（长度 n，不含结尾 0）
static uint8_t HasGBK(const uint8_t *s, const uint8_t *pat, uint8_t n)
{
    uint8_t i;

    while (*s != 0)
    {
        for (i = 0; i < n; i++)
        {
            if (s[i] != pat[i]) { break; }
        }
        if (i == n) { return 1; }
        s++;
    }
    return 0;
}

// 回读的文本 -> 无符号数；非数字即止，取不到数字返回 0xFFFF
static uint16_t TxtU16(const uint8_t *s)
{
    uint32_t v = 0;
    uint8_t  n = 0;

    while ((*s != 0) && ((*s < '0') || (*s > '9'))) { s++; }
    while ((n < 5) && (*s >= '0') && (*s <= '9'))
    {
        v = v * 10 + (uint32_t)(*s - '0');
        s++;
        n++;
    }
    return (uint16_t)((n == 0) ? 0xFFFF : v);
}

// 屏 -> MCU 文本通知（指令集 §2.22 回读回复）：暂停页提示 + 设置页 4 个限值框
void HrPage_OnText(uint16_t scr, uint16_t ctl, uint8_t *str)
{
    uint16_t v;
    uint8_t  chg = 0;

    // 暂停页(4)提示文本：含"已暂停"则该停判报警，否则照常；lua 是唯一写者
    if ((scr == HP_SCR_PAUSE) && (ctl == HP_TXT_PAUSE))
    {
        uint8_t run = (uint8_t)(HasGBK(str, STR_TAG_PAUSED, 6) ? 0 : 1);

        if (run != s_run)
        {
            s_run = run;
            TxtGB(HP_SCR_HOME, HP_TXT_RUN, (s_run != 0) ? STR_RUN : (const uint8_t *)"");
            TxtGB(HP_SCR_HOME, HP_TXT_STOP, (s_run != 0) ? (const uint8_t *)"" : STR_PAUSE);
        }
        return;
    }

    if (scr != HP_SCR_SET) { return; }

    v = TxtU16(str);
    if (v == 0xFFFF) { return; }        // 未取到数字：保持原值

    switch (ctl)
    {
    case HP_TXT_HI_HR:
        if (v < HP_HR_HI_LO) { v = HP_HR_HI_LO; }
        if (v > HP_HR_HI_HI) { v = HP_HR_HI_HI; }
        if (v != s_hr_hi) { s_hr_hi = v; chg = 1; }
        break;
    case HP_TXT_LO_HR:
        if (v < HP_HR_LO_LO) { v = HP_HR_LO_LO; }
        if (v > HP_HR_LO_HI) { v = HP_HR_LO_HI; }
        if (v != s_hr_lo) { s_hr_lo = v; chg = 1; }
        break;
    case HP_TXT_HI_RR:
        if (v < HP_RR_HI_LO) { v = HP_RR_HI_LO; }
        if (v > HP_RR_HI_HI) { v = HP_RR_HI_HI; }
        if (v != s_rr_hi) { s_rr_hi = v; chg = 1; }
        break;
    case HP_TXT_LO_RR:
        if (v < HP_RR_LO_LO) { v = HP_RR_LO_LO; }
        if (v > HP_RR_LO_HI) { v = HP_RR_LO_HI; }
        if (v != s_rr_lo) { s_rr_lo = v; chg = 1; }
        break;
    default:
        return;
    }

    if (chg != 0) { WriteLimits(); }    // 主界面限值行跟随
}

// 一次回读全部需要同步的屏控件（按钮 §2.19 / 文本 §2.22 回复走同一条通知链）
static void ScanControls(void)
{
    GetControlValue(HP_SCR_SET, HP_BTN_SOUND);
    GetControlValue(HP_SCR_SET, HP_TXT_HI_HR);
    GetControlValue(HP_SCR_SET, HP_TXT_LO_HR);
    GetControlValue(HP_SCR_SET, HP_TXT_HI_RR);
    GetControlValue(HP_SCR_SET, HP_TXT_LO_RR);
    GetControlValue(HP_SCR_PAUSE, HP_TXT_PAUSE);
}

// ---------------- 对外接口 ----------------
void HrPage_Init(void)
{
    s_hr_hi = HP_HR_DEF_HI;
    s_hr_lo = HP_HR_DEF_LO;
    s_rr_hi = HP_RR_DEF_HI;
    s_rr_lo = HP_RR_DEF_LO;
    s_run = 1;
    s_cur = HP_SCR_HOME;
    s_log_row = 0;
    s_log_total = 0;
    s_rtc_ok = 0;
    s_frame_ms = 0;
    s_sp_p = 0;
    g_ecgHaveFrame = 0;
    g_ecgLastMs = 0;
    ecg_reset();
    s_valtm[0] = '-';
    s_valtm[1] = 0;

    SetTextValue(HP_SCR_HOME, HP_TXT_HR, (uchar *)"---");
    SetTextValue(HP_SCR_HOME, HP_TXT_RESP, (uchar *)"---");
    StateTxt(HP_TXT_HR_ST, 0);
    StateTxt(HP_TXT_RR_ST, 0);
    WriteLimits();
    TxtGB(HP_SCR_HOME, HP_TXT_CAP, STR_CAP);
    LogRefresh();
    WriteSetupTexts();
    TrendRangeSet(s_range);             // 开机对齐趋势页档位与横轴刻度
    SetButtonValue(HP_SCR_SET, HP_BTN_SOUND, (uchar)HP_DEF_SOUND);   // 兜底: 开关图标与默认值对齐
    GraphChannelDataClear(HP_SCR_HOME, HP_GRAP_ECG, 0);
    GraphChannelDataClear(HP_SCR_HOME, HP_GRAP_RESP, 0);
    QualityRefresh();
    ReadRTC();
}

void HrPage_Task(uint32_t now_ms)
{
    s_now_ms = now_ms;

    FrameFeed(now_ms);

    if ((now_ms - s_t_value) >= HP_PERIOD_VALUE)
    {
        s_t_value = now_ms;
        ValueRefresh(now_ms);                    // 1s：瞬时心率/呼吸率 + 报警
        if (s_cur == HP_SCR_PROBE) { ProbePageRefresh(now_ms); }
    }
    if ((now_ms - s_t_qual) >= HP_PERIOD_QUAL)
    {
        s_t_qual = now_ms;
        QualityTick();                           // 10s：信号质量统计
        QualityRefresh();
    }
    if ((now_ms - s_t_min) >= HP_PERIOD_MIN)
    {
        s_t_min = now_ms;
        MinuteTick();                            // 60s：趋势历史推 1 点
    }
    if ((now_ms - s_t_rtc) >= HP_PERIOD_RTC)
    {
        s_t_rtc = now_ms;
        ReadRTC();                               // 30s：RTC 校时
    }
    BeepTick(now_ms);

    /* 定期回读屏上控件：声音开关(button_type=1) 屏只在状态改变时发一帧，
       限值框与暂停提示背后的按钮是 button_type=2（无状态字节），
       都靠回读才是可靠来源。 */
    if ((now_ms - s_t_scan) >= HP_PERIOD_SCAN)
    {
        s_t_scan = now_ms;
        ScanControls();
    }
}

void HrPage_NotifyScreen(uint16_t screen_id)
{
    s_cur = (uint8_t)screen_id;
    WriteProbe();
    switch (screen_id)
    {
    case HP_SCR_HOME:
        GraphChannelDataClear(HP_SCR_HOME, HP_GRAP_ECG, 0);
        GraphChannelDataClear(HP_SCR_HOME, HP_GRAP_RESP, 0);
        WriteLimits();
        QualityRefresh();
        break;
    case HP_SCR_TREND:
        TrendRangeSet(s_range);         // 进页重推档位与横轴刻度(屏重启也能自愈)
        TrendSyncOne(HP_HIS_HR, s_hh, s_hh_cnt, s_hh_gen, &s_hh_push);
        TrendSyncOne(HP_HIS_RR, s_rrh, s_rrh_cnt, s_rrh_gen, &s_rrh_push);
        break;
    case HP_SCR_LOG:
        LogRefresh();
        break;
    case HP_SCR_SET:                    // 进设置页立刻对齐声音开关与限值
        s_t_scan = s_now_ms;
        ScanControls();
        break;
    case HP_SCR_PAUSE:                  // 进暂停页立刻对齐运行/暂停态（lua 已刷新提示）
        s_t_scan = s_now_ms;
        ScanControls();
        break;
    case HP_SCR_PROBE:
        QualityRefresh();
        ProbePageRefresh(s_now_ms);
        break;
    default:
        break;
    }
    ReadRTC();
}

// 设置页 ±：与 lua 同一套"拒绝式钳制"（上/下限各自独立）
static void LimAdj(uint16_t *v, int8_t dir, uint16_t step,
                   int32_t lo, int32_t hi)
{
    int32_t x = *v;

    x += (dir > 0) ? step : -(int32_t)step;
    if (x < lo) { x = lo; }
    if (x > hi) { x = hi; }
    *v = (uint16_t)x;
}

void HrPage_OnButton(uint16_t scr, uint16_t ctl, uint8_t state)
{
    uint16_t key = (uint16_t)(((scr & 0xFF) << 8) | (ctl & 0xFF));
    int32_t lb;

    /* ---- 开关型按钮（屏内 button_type=1，操作风格"开关"）----
       屏只在"状态改变"时上传一帧，state 就是控件当前状态（1 按下/0 弹起），
       不能按"翻转"处理：用户点偶数次就会与屏显反相。这里一律直接同步。 */

    // 报警声音开关：state=1 开 / state=0 关
    if ((scr == HP_SCR_SET) && (ctl == HP_BTN_SOUND))
    {
        uint8_t want = (uint8_t)((state != 0) ? 1 : 0);

        if (want != s_sound)
        {
            s_sound = want;
            if (s_sound == 0) { BEEP_Off(); }    // 关声音立即停响，不等下个节拍
        }
        return;
    }

    // 趋势页量程：三个互斥开关按钮，被选中的那个给 state=1。
    // 不能放下面"只认弹起"早退之后——通知全被拦掉，三档横坐标永远不变
    if (scr == HP_SCR_TREND)
    {
        if (((ctl >= 1) && (ctl <= 3)) && (state != 0))
        {
            TrendRangeSet((uint8_t)ctl);
        }
        return;
    }

    // ---- 以下只认"弹起"：button_type=2 自定义按键帧里 Status 是保留字节，
    // 取到的是 Key_value，到不了这里；0.4s 判重防长按双触发
    if (state != HP_BTN_RELEASE) { return; }
    if ((s_btn_key == key) && ((s_now_ms - s_btn_ms) < 400)) { return; }
    s_btn_key = key;
    s_btn_ms = s_now_ms;

    if (scr == HP_SCR_SET)
    {
        switch (ctl)
        {
        case HP_BTN_HR_HI_DEC:
        case HP_BTN_HR_HI_INC:
            lb = s_hr_lo + HP_HR_GAP;
            if (lb < HP_HR_HI_LO) { lb = HP_HR_HI_LO; }
            LimAdj(&s_hr_hi, (ctl == HP_BTN_HR_HI_INC) ? 1 : -1,
                   HP_HR_STEP, lb, HP_HR_HI_HI);
            break;
        case HP_BTN_HR_LO_DEC:
        case HP_BTN_HR_LO_INC:
            lb = s_hr_hi - HP_HR_GAP;
            if (lb > HP_HR_LO_HI) { lb = HP_HR_LO_HI; }
            LimAdj(&s_hr_lo, (ctl == HP_BTN_HR_LO_INC) ? 1 : -1,
                   HP_HR_STEP, HP_HR_LO_LO, lb);
            break;
        case HP_BTN_RR_HI_DEC:
        case HP_BTN_RR_HI_INC:
            lb = s_rr_lo + HP_RR_GAP;
            if (lb < HP_RR_HI_LO) { lb = HP_RR_HI_LO; }
            LimAdj(&s_rr_hi, (ctl == HP_BTN_RR_HI_INC) ? 1 : -1,
                   HP_RR_STEP, lb, HP_RR_HI_HI);
            break;
        case HP_BTN_RR_LO_DEC:
        case HP_BTN_RR_LO_INC:
            lb = s_rr_hi - HP_RR_GAP;
            if (lb > HP_RR_LO_HI) { lb = HP_RR_LO_HI; }
            LimAdj(&s_rr_lo, (ctl == HP_BTN_RR_LO_INC) ? 1 : -1,
                   HP_RR_STEP, HP_RR_LO_LO, lb);
            break;
        default:
            break;
        }
        WriteSetupTexts();
        WriteLimits();
    }
    // 暂停/恢复不在这里做：暂停页"确认"与主界面"恢复"都是 button_type=2，
    // 帧里无状态字节；运行/暂停统一由回读暂停页提示文本同步（见 HrPage_OnText）
    else if ((scr == HP_SCR_CLEAR) && (ctl == 2))
    {
        uint8_t i;

        s_hh_cnt = 0; s_hh_gen = 0; s_hh_push = 0;
        s_rrh_cnt = 0; s_rrh_gen = 0; s_rrh_push = 0;
        s_log_total = 0; s_log_row = 0;
        for (i = 0; i < HP_LOG_ROWS; i++) { s_log_act[i] = 0; }
        s_row_hr = 0xFF;
        s_row_rr = 0xFF;
        LogRefresh();
    }
}

// 由 NotifyReadRTC() 调（BCD 先转十进制）
void HrPage_OnRtcTime(uint8_t year, uint8_t month, uint8_t day,
                      uint8_t hour, uint8_t min, uint8_t sec, uint32_t now_ms)
{
    // 屏回传 RTC 字段为 BCD：高 nibble×10 + 低 nibble
    uint8_t y  = (uint8_t)((year >> 4) * 10 + (year & 0x0F));
    uint8_t mo = (uint8_t)((month >> 4) * 10 + (month & 0x0F));
    uint8_t d  = (uint8_t)((day >> 4) * 10 + (day & 0x0F));
    uint8_t h  = (uint8_t)((hour >> 4) * 10 + (hour & 0x0F));
    uint8_t mi = (uint8_t)((min >> 4) * 10 + (min & 0x0F));
    uint8_t s  = (uint8_t)((sec >> 4) * 10 + (sec & 0x0F));

    // 折算成 1970 起的绝对秒并记录对应 MCU 时刻，供 SecOfDay 外推
    s_rtc_abs = CivilDays((uint16_t)(2000 + y), mo, d) * 86400 +
                (uint32_t)h * 3600 + (uint32_t)mi * 60 + s;
    s_rtc_ms = now_ms;
    s_rtc_ok = 1;
}

// ---------------- 对外快照（CANopen 用） ----------------
void HrPage_GetVitals(HrVitals_t *v)
{
    v->hr_valid = s_bpm_valid;
    v->rr_valid = s_rpm_valid;
    v->probe    = s_probe;
    v->running  = s_run;

    // 报警汇总：位0 心率异常，位1 呼吸异常 → 0/1/2/3
    v->alarm = (uint8_t)(((s_st_hr != 0) ? 1 : 0) | ((s_st_rr != 0) ? 2 : 0));

    v->quality  = s_quality;
    v->bpm      = (s_bpm_valid != 0) ? (int16_t)s_bpm : HP_VAL_INVALID;
    v->rpm      = (s_rpm_valid != 0) ? (int16_t)s_rpm : HP_VAL_INVALID;
    v->hr_hi    = (int16_t)s_hr_hi;
    v->hr_lo    = (int16_t)s_hr_lo;
    v->rr_hi    = (int16_t)s_rr_hi;
    v->rr_lo    = (int16_t)s_rr_lo;
}

// 写回限值：按屏同一套范围与最小间隔夹紧，再刷回设置页与主界面
uint8_t HrPage_SetLimits(int16_t hr_hi, int16_t hr_lo, int16_t rr_hi, int16_t rr_lo)
{
    uint16_t h, l;
    uint8_t  chg = 0;

    // 心率上限：100~250，且 ≥ 下限 + GAP
    h = (uint16_t)hr_hi;
    if (h < HP_HR_HI_LO) { h = HP_HR_HI_LO; }
    if (h > HP_HR_HI_HI) { h = HP_HR_HI_HI; }
    if (h != s_hr_hi) { s_hr_hi = h; chg = 1; }

    // 心率下限：30~150，且 ≤ 上限 - GAP
    l = (uint16_t)hr_lo;
    if (l < HP_HR_LO_LO) { l = HP_HR_LO_LO; }
    if (l > HP_HR_LO_HI) { l = HP_HR_LO_HI; }
    if (l != s_hr_lo) { s_hr_lo = l; chg = 1; }
    if ((s_hr_hi - s_hr_lo) < HP_HR_GAP)  // 夹紧后仍要保住最小间隔
    {
        s_hr_lo = (uint16_t)(s_hr_hi - HP_HR_GAP);
        if (s_hr_lo < HP_HR_LO_LO) { s_hr_lo = HP_HR_LO_LO; }
        chg = 1;
    }

    // 呼吸上限：10~60
    h = (uint16_t)rr_hi;
    if (h < HP_RR_HI_LO) { h = HP_RR_HI_LO; }
    if (h > HP_RR_HI_HI) { h = HP_RR_HI_HI; }
    if (h != s_rr_hi) { s_rr_hi = h; chg = 1; }

    // 呼吸下限：4~40
    l = (uint16_t)rr_lo;
    if (l < HP_RR_LO_LO) { l = HP_RR_LO_LO; }
    if (l > HP_RR_LO_HI) { l = HP_RR_LO_HI; }
    if (l != s_rr_lo) { s_rr_lo = l; chg = 1; }
    if ((s_rr_hi - s_rr_lo) < HP_RR_GAP)
    {
        s_rr_lo = (uint16_t)(s_rr_hi - HP_RR_GAP);
        if (s_rr_lo < HP_RR_LO_LO) { s_rr_lo = HP_RR_LO_LO; }
        chg = 1;
    }

    if (chg != 0)
    {
        WriteSetupTexts();
        WriteLimits();
    }
    return chg;
}
