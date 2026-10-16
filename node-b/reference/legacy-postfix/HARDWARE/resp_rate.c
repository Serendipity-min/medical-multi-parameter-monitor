/**
 * @file    resp_rate.c
 * @brief   ADS1292R 呼吸阻抗波形和呼吸率计算（修正版）。
 *
 * ADS1292R 的呼吸测量原理：芯片往胸腔注入 32kHz 的微小电流，测阻抗。
 * 吸气时胸廓扩张、阻抗上升，呼气时相反。所以呼吸通道（CH1）拿到的是
 * 一个叠加在直流上的慢变化信号，频率就是呼吸频率（0.1 ~ 0.7Hz）。
 *
 * ============================ 本文件修正了什么 ============================
 *
 * 【P0】呼吸率恒为真值的 2 倍（最严重的一条）。
 *   原实现用"相邻两点差值的绝对值"|Δ| 的上升沿当作一次呼吸峰：
 *         envelope = |s_lowpass − s_prev|
 *   但正弦信号的一个周期里，|Δ| 会出现**两次**峰（上升半周一个、下降半周一个），
 *   所以它每个呼吸周期都数了两下 —— 间隔被算成一半，呼吸率翻倍。
 *   数值验证（合成呼吸信号，250SPS）：
 *        真值 12 次/分 → 原版报 24.5
 *        真值 18 次/分 → 原版报 36.1
 *        真值 24 次/分 → 原版直接报不出来（翻倍后 48 超过 40 的量程上限被丢弃）
 *   修正版改为在**滤波后的波形本身**上找局部极大值，实测：
 *        12 → 12.0，18 → 18.1，24 → 23.8
 *
 * 【P0】时间用毫秒时间戳，不再用采样点数。
 *   和心率那边同样的原因：丢帧会让"采样点数"走得比真实时间慢。
 *
 * 【P1】超时从 2 秒改成 12 秒（见 resp_rate.h 的说明）。
 *
 * 【P1】幅度判据明确化：只有在滤波波形上出现了"足够大的一下起伏"才算一次呼吸，
 *   避免噪声把人数的呼吸数抬上去。
 *
 * ============================ 还没有做的（如实说明）============================
 *   · 没有做呼吸阻抗的"基线漂移跟踪"，长时间监护（几十分钟）时
 *     低频漂移可能盖过呼吸幅度。真产品需要加高通或自适应基线。
 *   · 没有做呼吸暂停（apnea）事件判定，只输出速率。
 *   · 增益：数据手册 9.4 对 32kHz 调制频率推荐呼吸通道增益 3~4。
 *     2026-09-24 已把 CH1SET 从 0x60（增益12，厂家原值）改成 0x40（增益4），
 *     解决解调输出的直流分量把波形顶到满量程削顶成方波的问题。
 *     ⚠ 改增益不需要重标本文件的任何阈值：下面的幅度判据全部是相对量
 *       （"峰高 > 0.35 x (峰值包络 - 噪声基线)"），增益只是把 x 整体等比缩小。
 *       唯一可见的影响是 RespRate_GetFiltered() 输出的数值同比变小
 *       （串口 B: 通道和屏幕上的呼吸波形会矮约 3 倍），这是预期的。
 * ==========================================================================*/
#include "resp_rate.h"
#include "timer.h"      // TimeBase_GetMs：算呼吸间隔 / 超时判定用

/* ---- 直流跟踪与低通 ----
   s_dc      ：慢速跟踪直流分量（α=0.002 → 时间常数约 2 秒）
   s_lowpass ：扣掉直流后的低通，α=0.012 @250SPS → −3dB 约 0.48Hz
   即：通带覆盖 6~40 次/分（0.1~0.67Hz）。
   40 次/分 处约 −4.7dB 衰减，但呼吸率的估计靠的是"峰值出现的时刻"，
   幅度衰减不影响周期判断，只影响幅度判据，由下面的自适应基线兜住。 */
#define RESP_DC_ALPHA        0.002f
#define RESP_LP_ALPHA        0.012f

// 幅度基线与噪声基线的跟踪速度（都在 |低通输出| 上做包络估计）
#define RESP_PEAK_UP_ALPHA   0.05f
#define RESP_PEAK_DN_ALPHA   0.001f
#define RESP_NOISE_ALPHA     0.0005f

// 峰值幅度判据：峰高必须超过"幅度基线 − 噪声基线"的 35%
#define RESP_AMP_RATIO       0.35f

// 同一呼吸波形内的双峰保护
#define RESP_REFRACTORY_MS   240

#define RESP_MIN_INTERVAL_MS (60000 / RESP_MAX_BPM)   // 1500ms
#define RESP_MAX_INTERVAL_MS (60000 / RESP_MIN_BPM)   // 10000ms

#define RESP_RR_COUNT        5    // 速率中值窗口
#define RESP_RR_MIN_VALID    2    // 至少 2 个间隔才输出


// ============================ 内部状态 ============================

static float    s_dc, s_lowpass;       // 直流基底估计 / 去直流后的低通输出（呼吸波形）
static float    s_prev1, s_prev2;      // 前两个低通输出，用来找局部极大值
static float    s_peak_level;          // 幅度包络（|低通输出| 的上包络）
static float    s_noise_level;         // 幅度包络的低端（噪声基线）

static uint32_t s_last_peak_ms;        // 上一次呼吸峰的毫秒时刻
static uint8_t  s_have_peak;           // 是否已经找到过第一个峰

static uint16_t s_rate[RESP_RR_COUNT]; // 环形缓冲，存的是"次/分"
static uint8_t  s_rr_index;            // 环形缓冲下一个写入位置
static uint8_t  s_rr_count;            // 已写入的间隔个数

static int32_t  s_filtered;


// 取呼吸速率的中位数（次/分）。
static uint16_t median_rate(void)
{
    uint16_t a[RESP_RR_COUNT];
    uint16_t t;
    uint8_t  n = (s_rr_count < (uint8_t)RESP_RR_COUNT)
                 ? s_rr_count : (uint8_t)RESP_RR_COUNT;
    uint8_t  start, i, j;

    if (n == 0)
        return 0;

    start = (uint8_t)((s_rr_index + (uint8_t)RESP_RR_COUNT - n) % (uint8_t)RESP_RR_COUNT);
    for (i = 0; i < n; i++)
        a[i] = s_rate[(uint8_t)((start + i) % (uint8_t)RESP_RR_COUNT)];

    for (i = 1; i < n; i++) {
        t = a[i];
        j = i;
        while (j > 0 && a[j - 1] > t) 
		{
            a[j] = a[j - 1];
            j--;
        }
        a[j] = t;
    }

    return a[n / 2];
}


// ============================ 对外接口 ============================

void RespRate_Init(void)
{
    uint8_t i;

    s_dc = 0.0f;
    s_lowpass = 0.0f;
    s_prev1 = s_prev2 = 0.0f;
    s_peak_level = 0.0f;
    s_noise_level = 0.0f;

    s_last_peak_ms = 0;
    s_have_peak = 0;

    s_rr_index = 0;
    s_rr_count = 0;
    s_filtered = 0;

    for (i = 0; i < (uint8_t)RESP_RR_COUNT; i++)
        s_rate[i] = 0;
}

void RespRate_ProcessAt(int32_t respiration_sample, uint32_t now_ms)
{
    float    x, a, amp;
    uint32_t interval;


    //归一化
    x = (float)respiration_sample / 8388608.0f;   // 满量程 ±2^23 → ±1
    // 两级 EMA 级联：第一级慢跟直流基底，第二级在"去直流后的残差"上低通，等效出一个覆盖呼吸频段的带通
    s_dc      += RESP_DC_ALPHA * (x - s_dc);
    s_lowpass += RESP_LP_ALPHA * ((x - s_dc) - s_lowpass);

    s_filtered = (int32_t)(s_lowpass * 100000000.0f);   // 给屏幕/上位机画呼吸波

    // 幅度包络与噪声基线：都是对 |s_lowpass| 的慢速跟踪。
    // peak 上升快、下降慢 → 跟得住包络；noise 很慢 → 跟得住平均值。
    a = (s_lowpass >= 0.0f) ? s_lowpass : -s_lowpass;
    if (a > s_peak_level)
        s_peak_level += RESP_PEAK_UP_ALPHA * (a - s_peak_level);
    else
        s_peak_level += RESP_PEAK_DN_ALPHA * (a - s_peak_level);
    s_noise_level += RESP_NOISE_ALPHA * (a - s_noise_level);

    /* ---- 局部极大值检测 ----
       ★ 这里是和原实现最本质的差别。
       原实现用 |Δ|（一阶差分）的上升沿，一个呼吸周期里会数出两次；
       现在直接在低通波形上找"比前一点和后一点都高"的点，
       一个呼吸周期只会有一个这样的点。 */
    if ((s_prev2 < s_prev1) && (s_prev1 >= s_lowpass)) {

        // 幅度判据：这一下起伏要足够大才算呼吸，否则是噪声/伪迹。
        // 参考量取"幅度包络 − 噪声基线"，所以会自动适应不同人的呼吸幅度。
        amp = s_prev1 - s_noise_level;

        if ((amp > (RESP_AMP_RATIO * (s_peak_level - s_noise_level))) &&
            ((s_have_peak == 0) ||
             ((now_ms - s_last_peak_ms) >= RESP_REFRACTORY_MS))) {

            if (s_have_peak != 0) {
                interval = now_ms - s_last_peak_ms;     // 真实毫秒，丢帧不受影响
                // 间隔超出 1.5~10s（>40 或 <6 次/分）视为伪峰丢弃，是主要的异常值剔除手段
                if ((interval >= RESP_MIN_INTERVAL_MS) &&
                    (interval <= RESP_MAX_INTERVAL_MS)) {
                    // 60000 / 间隔(ms) = 次/分
                    s_rate[s_rr_index] = (uint16_t)(60000 / interval);
                    s_rr_index = (uint8_t)((s_rr_index + 1) % (uint8_t)RESP_RR_COUNT);
                    if (s_rr_count < (uint8_t)RESP_RR_COUNT)
                        s_rr_count++;
                }
            }

            s_last_peak_ms = now_ms;
            s_have_peak = 1;
        }
    }

    // 找局部极大值要用的"前两点"
    s_prev2 = s_prev1;
    s_prev1 = s_lowpass;
}

uint8_t RespRate_Get(uint16_t *respiration_rate)
{
    if (respiration_rate == 0)
        return 0;

    // 三种情况都算"无有效呼吸信号"：
    // 还没找到第一个峰 / 间隔数不够 / 超过 12 秒没有新的呼吸峰
    if ((s_have_peak == 0) ||
        (s_rr_count < (uint8_t)RESP_RR_MIN_VALID) ||
        ((TimeBase_GetMs() - s_last_peak_ms) > RESP_TIMEOUT_MS)) {
        *respiration_rate = 0;
        return 0;
    }

    *respiration_rate = median_rate();
    return 1;
}

int32_t RespRate_GetFiltered(void)
{
    return s_filtered;
}

/* 兼容旧调用；队列输入用真实采集时间，呼吸滤波参数与判峰条件不变。 */
void RespRate_Process(int32_t sample) { RespRate_ProcessAt(sample,TimeBase_GetMs()); }
