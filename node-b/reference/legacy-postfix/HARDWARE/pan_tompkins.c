/**
 * @file    pan_tompkins.c
 * @brief   250 SPS 心电 QRS 检测 / 心率计算（Pan-Tompkins 经典结构 + 工程加固）。
 *
 *   ① 归一化            ADC 码 → 约 ±1 的无量纲值
 *   ② 带通              129 抽头 FIR，实测通带 ≈3.8~29.2Hz（见 ecg_filter.c）
 *   ③ 微分              y[n] = x[n] − x[n−1]，突出 QRS 的陡峭斜率
 *   ④ 平方              全波整流，同时把"斜率差"放大成"能量差"
 *   ⑤ 152ms 移动窗积分  得到一个平滑的能量包（标准 PT 用 150ms）
 *   ⑥ 局部极大值 + 自适应阈值   找到每一拍的峰值，按 SPKI/NPKI 更新阈值
 *   ⑦ 不应期 + T 波抑制 200ms 不应期；距上一拍 <360ms 且幅度不到一半的判为 T 波
 *   ⑧ search-back         长时间没新拍说明阈值偏高，用一半的阈值回搜补拍
 *   ⑨ RR 中值 → 心率      5 拍 RR 取中值，再限幅输出
 *
*/
#include "pan_tompkins.h"
#include "ecg_filter.h"
#include "timer.h"      // TimeBase_GetMs：算 RR 间隔用真实时间

// ============================ 参数 ============================

// 移动积分窗：38 点 @250SPS = 152ms（标准 Pan-Tompkins 用 150ms）
#define PT_INTEGRATION_SAMPLES   38

#define PT_REFRACTORY_MS         200   // 不应期：一次 QRS 之后 200ms 内不再判拍
#define PT_TWAVE_MS              360   // 距上一拍不足这么久 → 怀疑是 T 波
#define PT_TWAVE_RATIO           0.5f  // 且幅度不到上一拍的一半 → 判为 T 波

#define PT_MIN_RR_MS             273   // 上限心率 220 BPM
#define PT_MAX_RR_MS             2000  // 下限心率 30 BPM，更长的间隔丢弃
#define PT_RR_COUNT              5     // RR 中值窗口（拍数）。调大更稳但响应更慢
#define PT_RR_MIN_VALID          3     // 至少积累这么多 RR 才输出心率

#define PT_LEARN_MS              2000  // 上电学习期：先摸清噪声水平
#define PT_MIN_SIGNAL_RATIO      5.0f  // 学习结束时信号水平的兜底下限（×噪声）

/* 尚无首拍时，按最长有效RR取一个有界观察窗，替换过期的学习期高幅值。
   只更新信号估计，不降低8倍噪声闸门、不补造心拍，也不重置FIR历史。 */
#define PT_FIRST_ACQUIRE_MS      PT_MAX_RR_MS

// search-back：超过 1.66 × 中位 RR 还没新拍就回搜
#define PT_SEARCHBACK_NUM        166
#define PT_SEARCHBACK_DEN        100

/* 自适应系数。
   基底（噪声）估计用**非对称** EMA：下降快、上升极慢。
   为什么必须非对称：积分信号里 QRS 是稀疏的大尖峰，如果用对称 EMA，
   估计值会被 QRS 抬向"平均值"。实测数据（250SPS，1mV R 波）：
       积分信号的 峰值/中位数 = 140~183（真信号） vs 4.4（纯噪声）→ 判别力很强
       积分信号的 峰值/平均值 = 3.0~6.5（真信号） vs 3.9（纯噪声）→ 区分不出来
   所以"平均值"不能当基底用。非对称 EMA 收敛到的是信号的低分位（≈心拍之间的
   基底），对 QRS 尖峰不敏感，在任何采样率下都成立（与窗口长度无关）。
   下降速率决定跟踪基底掉落的快慢（约 50 个点，200ms）；
   上升速率决定 QRS 尖峰对基底的影响（约 2000 个点，8 秒）。 */
#ifndef PT_ALPHA_NOISE_UP
#define PT_ALPHA_NOISE_UP        0.0005f
#endif
#ifndef PT_ALPHA_NOISE_DN
#define PT_ALPHA_NOISE_DN        0.02f
#endif

// 信号水平更新。作用在"每次检出的心拍"上（≈1 次/秒），所以可以取大一些。
// 0.125 → 时间常数约 8 拍。
#define PT_ALPHA_SIGNAL          0.125f

/* 噪声底板闸门：阈值不得低于 基底 × 这个倍数。
   实测：真信号的 峰值/中位数 最低是 14（90BPM 且丢帧 40% 这种极端情况），
         纯噪声只有 4.4。取 8.0 落在中间，两边都有接近 2 倍的余量。
   改这个值之前请先看 README 里的"实测数据"一节。 */
#ifndef PT_SNR_GATE
#define PT_SNR_GATE              8.0f
#endif

// FIR 状态寄存器填满需要 129 个采样点（516ms）。这之后积分值才有意义，
// 所以学习期统计 learn_max 时跳过前 600ms，避免把爬升段的异常值当真信号。
#define PT_FIR_WARMUP_MS         600

/* 绝对底限，只是防"全零输入"时阈值退化成 0 的保险丝。
   标度参考：心电 1mV、增益6、VREF 2.42V → 归一化后 2.48e-3；
   积分峰值实测约 7e-8，噪声底板约 5e-10。1e-12 远低于两者。 */
#define PT_ABS_FLOOR             1.0e-12f

/* 心率显示限幅：向上每拍最多 +25%，向下每拍最多 −50%。
   向上收得紧（突然翻倍多半是误检），向下放得松（突然变慢更要紧、
   要尽快显示出来）。防的是"屏幕上的数字从 75 突然跳到 150"。 */
#define PT_BPM_UP_NUM            1
#define PT_BPM_UP_DEN            4
#define PT_BPM_DN_NUM            1
#define PT_BPM_DN_DEN            2


// ============================ 内部状态 ============================

static float    s_prev_band;                                        // 上一点带通输出（微分用）
static float    s_integral_buffer[PT_INTEGRATION_SAMPLES];          // 152ms 积分窗（环形）
static uint16_t s_integral_index;                                   // 积分窗下一个写入位置

static float    s_signal_level;    // SPKI：已检出心拍峰值的 EMA（信号能量水平）
static float    s_noise_level;     // NPKI：噪声底板的 EMA（心拍间基底能量）

static float    s_prev1, s_prev2;  // 前两个积分值，用于找局部极大值

static uint32_t s_t0_ms;           // 开机时刻（Init 时记录）
static uint8_t  s_learned;         // 学习期是否结束
static float    s_learn_max;       // 学习期内见过的最大的积分值
static uint32_t s_first_window_ms; // 首拍恢复使用采样时戳，排队消费和毫秒回绕不改变窗口
static float    s_first_window_peak;

static uint32_t s_last_beat_ms;    // 上一次心跳的时刻（毫秒，硬件时间戳）
static float    s_last_beat_peak;  // 上一次心跳的积分峰值（T 波判据要用）
static uint8_t  s_have_beat;       // 是否已经受理过至少一拍（首拍没有前一拍可比）

static uint32_t s_window_peak;     // 本拍以来积分最大值所在时刻
static float    s_window_peak_val; // 本拍以来积分最大值（search-back 用）
static uint8_t  s_searchback_done; // 本拍已经回搜过，避免反复补拍

static uint32_t s_rr_ms[PT_RR_COUNT];
static uint8_t  s_rr_index;        // 下一个要写入的位置
static uint8_t  s_rr_count;        // 已写入的个数（饱和到 PT_RR_COUNT）

static uint32_t g_lastSampleMs, g_lastRrMs; // 最近一次输入时刻 / 最近一次有效 RR 的时刻
static uint8_t g_haveSample;
static uint16_t s_bpm;
static uint8_t  s_bpm_valid;
static int32_t  s_filtered;


// ============================ 内部函数 ============================

// 把一次 RR 间隔压进环形缓冲。
static void push_rr(uint32_t rr_ms)
{
    s_rr_ms[s_rr_index] = rr_ms;
    s_rr_index = (uint8_t)((s_rr_index + 1) % (uint8_t)PT_RR_COUNT);
    if (s_rr_count < (uint8_t)PT_RR_COUNT)
        s_rr_count++;
}

/**
 * @brief  取 RR 间隔的中位数（毫秒）。
 * @note   用中值而不是平均：一次漏检/多发会让平均值明显偏移，
 *         中值只受"多数拍"影响，抗单次异常强得多。
 */
static uint32_t median_rr(void)
{
    uint32_t a[PT_RR_COUNT];
    uint32_t t;
    uint8_t  n = (s_rr_count < (uint8_t)PT_RR_COUNT)
                 ? s_rr_count : (uint8_t)PT_RR_COUNT;
    uint8_t  start, i, j;

    if (n == 0)
        return 0;

    // 从环形缓冲按时间先后顺序取出来：最老的从 (index − n) 开始
    start = (uint8_t)((s_rr_index + (uint8_t)PT_RR_COUNT - n) % (uint8_t)PT_RR_COUNT);
    for (i = 0; i < n; i++)
        a[i] = s_rr_ms[(uint8_t)((start + i) % (uint8_t)PT_RR_COUNT)];

    // 插入排序：n ≤ 5，简单粗暴最快
    for (i = 1; i < n; i++) {
        t = a[i];
        j = i;
        while (j > 0 && a[j - 1] > t) {
            a[j] = a[j - 1];
            j--;
        }
        a[j] = t;
    }

    return a[n / 2];
}

// 心率显示限幅，见文件头的参数说明。
static uint16_t limit_bpm(uint16_t raw)
{
    uint32_t up, dn;

    if (s_bpm == 0)                    // 第一次有效值，直接采用
        return raw;

    up = ((uint32_t)s_bpm * PT_BPM_UP_NUM) / PT_BPM_UP_DEN;
    if (up == 0) up = 1;
    if ((uint32_t)raw > ((uint32_t)s_bpm + up))
        return (uint16_t)((uint32_t)s_bpm + up);

    dn = ((uint32_t)s_bpm * PT_BPM_DN_NUM) / PT_BPM_DN_DEN;
    if (dn == 0) dn = 1;
    if (((uint32_t)raw + dn) < (uint32_t)s_bpm)
        return (uint16_t)((uint32_t)s_bpm - dn);

    return raw;
}


// ============================ 对外接口 ============================

void PanTompkins_InitAt(uint32_t sample_ms)
{
    uint16_t i;

    s_prev_band   = 0.0f;
    s_integral_index = 0;
    s_signal_level = 0.0f;
    s_noise_level  = 0.0f;
    s_prev1 = s_prev2 = 0.0f;

    g_lastSampleMs = 0;
    g_lastRrMs = 0;
    g_haveSample = 0;
    s_t0_ms    = sample_ms;      // 学习期从这个时刻开始
    s_learned  = 0;
    s_learn_max = 0.0f;
    s_first_window_ms = sample_ms;
    s_first_window_peak = 0.0f;

    s_last_beat_ms   = 0;
    s_last_beat_peak = 0.0f;
    s_have_beat      = 0;

    s_window_peak     = 0;
    s_window_peak_val = 0.0f;
    s_searchback_done = 0;

    s_rr_index = 0;
    s_rr_count = 0;
    s_bpm      = 0;
    s_bpm_valid = 0;
    s_filtered = 0;

    for (i = 0; i < PT_INTEGRATION_SAMPLES; i++)
        s_integral_buffer[i] = 0.0f;
    for (i = 0; i < (uint16_t)PT_RR_COUNT; i++)
        s_rr_ms[i] = 0;
}

void PanTompkins_ProcessAt(int32_t ecg_sample, uint32_t now_ms)
{
    float    input, derivative, squared, integrated;
    float    threshold, peak_val;
    uint32_t beat_ms, interval, rr_median;
    uint16_t k;
    uint8_t  accepted;

    // 2026-10-07 HU JIAXUAN：输入断流或历史 RR 已过期时，重新进入学习期；
    // 被拒的噪声拍绝不能让一个旧的心率数字一直挂着。
    if ((g_haveSample != 0 && (now_ms - g_lastSampleMs) > PT_INPUT_GAP_MS) ||  // 输入断流：距上一采样点超过 100ms，FIR 历史已失真
        (s_have_beat != 0 && (now_ms - s_last_beat_ms) > PT_SIGNAL_HOLD_MS) || // 4 秒没有检出新拍：电极脱落/人离开
        (s_bpm_valid != 0 && (now_ms - g_lastRrMs) > PT_SIGNAL_HOLD_MS)) {     // 或 RR 记录已超时

        PanTompkins_InvalidateAt(now_ms);
    }
    g_haveSample = 1;
    g_lastSampleMs = now_ms;

    //1.归一化
    input = (float)ecg_sample / ADS24_FULL_SCALE;

    //2.带通（3.8~29.2Hz）
    input = ECG_Filter_Process(input);

    //3。微分：突出 QRS 陡沿
    derivative = input - s_prev_band;
    s_prev_band = input;

    //4.平方：把斜率差放大
    squared = derivative * derivative;

    /* ---- ⑤ 152ms 移动窗积分 ----
       保留环形缓冲（滑动窗口），但每次重算整个窗口的和。
       原实现用"加新值减旧值"的滚动累加，浮点误差会缓慢累积；
       重算的代价只有每秒 9500 次加法（约 0.1% CPU），
       换来的是连续跑几天也不会漂移。 */
    s_integral_buffer[s_integral_index] = squared;
    s_integral_index++;
    if (s_integral_index >= (uint16_t)PT_INTEGRATION_SAMPLES)
        s_integral_index = 0;

    integrated = 0.0f;
    for (k = 0; k < (uint16_t)PT_INTEGRATION_SAMPLES; k++)
        integrated += s_integral_buffer[k];
    integrated /= (float)PT_INTEGRATION_SAMPLES;

    // 放大浮点值，给上位机/屏幕画波形用。注意带通有 256ms 群延迟
    s_filtered = (int32_t)(input * 1000000.0f);

    // ---- 学习期：只摸基底，不判拍 ----
    if (s_learned == 0) {
        // 用同一套非对称 EMA，这样学习期结束时就有一个正确的基底量级
        if (integrated < s_noise_level)
            s_noise_level += PT_ALPHA_NOISE_DN * (integrated - s_noise_level);
        else
            s_noise_level += PT_ALPHA_NOISE_UP * (integrated - s_noise_level);

        // 跳过 FIR 状态还没填满的爬升段（前 600ms），否则可能把
        // 滤波器的启动瞬态当成"最大信号"，导致初始阈值高到什么都检不到。
        if (((now_ms - s_t0_ms) >= PT_FIR_WARMUP_MS) &&
            (integrated > s_learn_max))
            s_learn_max = integrated;

        if ((now_ms - s_t0_ms) >= PT_LEARN_MS) {
            s_learned = 1;
            /* 学习期结束给信号水平一个初值。
               取"学习期内见过的最大的积分值"（正常情况就是 R 波），
               而不是 0 —— 原实现从 0 开始，第一个阈值只有噪声的 0.75 倍，
               会连续误检一大片，然后阈值被拉走，前十几秒的数字全是假的。 */
            s_signal_level = (s_learn_max > (s_noise_level * PT_MIN_SIGNAL_RATIO))
                             ? s_learn_max
                             : (s_noise_level * PT_MIN_SIGNAL_RATIO);
            s_first_window_ms = now_ms;
            s_first_window_peak = 0.0f;
        }

        s_prev2 = s_prev1;
        s_prev1 = integrated;
        return;
    }

    /* 学习期偶发大尖峰会使SPKI过高；没有首拍时原逻辑无法靠受理心拍更新它。
       每个完整窗口仅允许向当前窗口峰值/噪声下限下调一次，静默/噪声仍必须
       经过原阈值、局部峰与后续RR验证；不将窗口峰本身认定为心拍。 */
    if (s_have_beat == 0) {
        if (integrated > s_first_window_peak)
            s_first_window_peak = integrated;
        if ((uint32_t)(now_ms - s_first_window_ms) >= PT_FIRST_ACQUIRE_MS) {
            float level = s_first_window_peak;
            float floor = s_noise_level * PT_MIN_SIGNAL_RATIO;
            if (level < floor) level = floor;
            if (level < s_signal_level) s_signal_level = level;
            s_first_window_ms = now_ms;
            s_first_window_peak = 0.0f;
        }
    }

    /* ---- ⑥ 自适应阈值 ----
       THRESHOLD = NPKI + 0.25 × (SPKI − NPKI)，形式上与 Pan-Tompkins 原文一致。
       再叠加一道"噪声底板闸门"：没有真实信号时阈值不会被压到噪声里。 */
    threshold = s_noise_level + 0.25f * (s_signal_level - s_noise_level);
    if (threshold < (s_noise_level * PT_SNR_GATE))
        threshold = s_noise_level * PT_SNR_GATE;
    if (threshold < PT_ABS_FLOOR)
        threshold = PT_ABS_FLOOR;

    // 记录"本拍以来"积分最大值及其时刻（search-back 要用）
    if (integrated > s_window_peak_val) {
        s_window_peak_val = integrated;
        s_window_peak = now_ms;
    }

    /* 基底跟踪：非对称 EMA（下降快、上升极慢），收敛到信号的低分位。
       不要改成"和平均值的差 × 固定系数"—— 那种写法会把 QRS 也算进基底，
       基底被抬高 → 阈值跟着抬高 → 轻则数字偏低，重则完全检不出心跳。 */
    if (integrated < s_noise_level)
        s_noise_level += PT_ALPHA_NOISE_DN * (integrated - s_noise_level);
    else
        s_noise_level += PT_ALPHA_NOISE_UP * (integrated - s_noise_level);

    accepted = 0;
    peak_val = 0.0f;
    beat_ms  = now_ms;

    /* ---- ⑦ 用局部极大值判拍 ----
       s_prev1 同时大于前后两个点，说明它就是一个峰。
       这样做的好处是拿来更新阈值的是**真实峰值**，而不是"刚刚压线"的值。 */
    if ((s_prev2 < s_prev1) && (s_prev1 >= integrated)) {
        float    pv = s_prev1;
        uint32_t pm = now_ms - PT_SAMPLE_PERIOD_MS;   // 峰值在上一个采样点
        uint32_t since = pm - s_last_beat_ms;         // 候选峰距上一拍的间隔（ms）；无符号减法，时间戳回绕也正确

        if ((pv > threshold) &&
            ((s_have_beat == 0) || (since >= PT_REFRACTORY_MS))) {

            if ((s_have_beat != 0) &&
                (since < PT_TWAVE_MS) &&
                (pv < (PT_TWAVE_RATIO * s_last_beat_peak))) {
                /* 距上一拍不到 360ms 且幅度不到一半 → T 波，丢弃。
                   T 波比 R 波宽得多，经过"微分+平方"之后能量低一个数量级，
                   所以这个判据对正常心电几乎不会误伤，却能挡住高 T 波人群
                   最常见的"心率翻倍"问题。 */
            } else {
                accepted = 1;
                peak_val = pv;
                beat_ms  = pm;
            }
        }
    }

    /* ---- ⑧ search-back：漏检补救 ----
       超过 1.66 × 中位 RR 还没有新拍，说明阈值偏高把弱的 QRS 漏掉了。
       此时如果"本拍以来的最大积分值"超过阈值，就用它补一次心跳。
       补拍的时刻用**候选峰的时刻**而不是当前时刻：
       否则 RR 会被算长，心率会被算低。 */
    if ((accepted == 0) && (s_have_beat != 0) &&
        (s_rr_count >= 2) && (s_searchback_done == 0)) {

        rr_median = median_rr();
        if ((rr_median > 0) &&
            ((now_ms - s_last_beat_ms) >
             ((rr_median * PT_SEARCHBACK_NUM) / PT_SEARCHBACK_DEN)) &&
            (s_window_peak_val > threshold) &&
            (s_window_peak > s_last_beat_ms)) {

            accepted = 1;
            peak_val = s_window_peak_val;
            beat_ms  = s_window_peak;
            s_searchback_done = 1;
        }
    }

    // ---- 受理这一拍 ----
    if (accepted != 0) {
        if (s_have_beat != 0) {
            interval = beat_ms - s_last_beat_ms;   // 无符号差值，跨回绕也正确
            // 超出 273~2000ms 量程（>220 或 <30 BPM）的 RR 不入缓冲，避免一拍多发/漏检污染中值
            if ((interval >= PT_MIN_RR_MS) && (interval <= PT_MAX_RR_MS)) {
                push_rr(interval);
                g_lastRrMs = now_ms;
                if (s_rr_count >= (uint8_t)PT_RR_MIN_VALID) {
                    rr_median = median_rr();
                    if (rr_median > 0) {
                        // 60000 / RR(ms) = 次/分
                        s_bpm = limit_bpm((uint16_t)(60000 / rr_median));
                        s_bpm_valid = 1;
                    }
                }
            }
        }

        s_signal_level += (peak_val - s_signal_level) * PT_ALPHA_SIGNAL;
        s_last_beat_ms   = beat_ms;
        s_last_beat_peak = peak_val;
        s_have_beat      = 1;

        s_window_peak_val = 0.0f;      // 重新开始找"本拍以来的最大值"
        s_window_peak     = 0;
        s_searchback_done = 0;
    }

    // 局部极大值检测需要的前两点，在这里统一平移
    s_prev2 = s_prev1;
    s_prev1 = integrated;
}

uint8_t PanTompkins_GetBPM(uint16_t *bpm)
{
    uint32_t nowMs = TimeBase_GetMs();
    if (bpm == 0) { return 0; }
    *bpm = 0;
    // 即使 ADC 已停、Process 不再被调用，Getter 这里也要负责把过期数据作废
    if (s_bpm_valid != 0 &&
        ((nowMs - g_lastSampleMs) > PT_INPUT_GAP_MS ||
         (nowMs - g_lastRrMs) > PT_SIGNAL_HOLD_MS)) {
        PanTompkins_Invalidate();
    }
    if (s_bpm_valid == 0) { return 0; }
    *bpm = s_bpm;
    return 1;
}

int32_t PanTompkins_GetFiltered(void)
{
    return s_filtered;
}

// 清除全部历史 RR 和 FIR 状态，然后要求重新走学习期。
// 2026-10-07 HU JIAXUAN：保留原 Invalidate 的意图，过期的 RR 一律不保留。
void PanTompkins_InvalidateAt(uint32_t sample_ms)
{
    ECG_Filter_Init();
    PanTompkins_InitAt(sample_ms);
}

/* 兼容既有调用；队列消费者使用At接口，批量消费不会把多个采样压到同一时刻。 */
void PanTompkins_Init(void) { PanTompkins_InitAt(TimeBase_GetMs()); }
void PanTompkins_Process(int32_t sample) { PanTompkins_ProcessAt(sample,TimeBase_GetMs()); }
void PanTompkins_Invalidate(void) { PanTompkins_InvalidateAt(TimeBase_GetMs()); }
