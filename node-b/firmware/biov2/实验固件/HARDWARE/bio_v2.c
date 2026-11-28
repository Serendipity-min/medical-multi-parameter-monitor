/* 独立实现：有界IIR、RMS峰宽判据、完整呼吸起伏、连续新鲜间隔资格。
 * 工程试验算法，不用“处于范围内”代替参考输入准确度或患者安全认证。
 */
#include "bio_v2.h"
#include <math.h>
#include <string.h>

#ifndef BIO_V2_ALC
#define BIO_V2_ALC 0 /* 1=心搏检测前加 50 Hz 自适应工频抵消（R99 ALC）；0 时与 C2 逐条一致 */
#endif
#ifndef BIO_V2_RR_R1
#define BIO_V2_RR_R1 1 /* 1=RR 由 R102 R1 窗内谱峰给出；0 时用时域周期，与 C2 逐条一致 */
#endif
#if BIO_V2_RR_R1
static void r1_tables(void);
static void r1_reset(void);
#endif
typedef struct { float b0,b1,b2,a1,a2,z1,z2; } Section;
typedef struct {
    uint32_t anchor, last_good, minimum, maximum, timeout, intervals[5];
    uint32_t count, index, candidate_rate, reason, required, tolerance;
    uint8_t anchored, bridge, bridged;
} Periods;
typedef struct {
    Section notch1, notch2, hp, lp;
    float dc, raw_power, line_power, clean_power, band_power, previous, previous2;
    float peak, trough, gate;
    uint32_t peak_ms, trough_ms, above_ms;
    uint8_t seeded, in_peak, armed_trough, clipped;
    Periods periods;
    uint32_t valid_start_ms; /* 单通道恢复预热起点，不因另一路削顶而重置。 */
#if BIO_V2_ALC
    float line_a, line_b, line_var, wave; /* 工频抵消权重/误差方差；wave 为抵消前的检测带波形 */
    uint8_t line_seeded;
#endif
} Channel;
BioV2Diag g_bio_v2;
static Channel heart, breathing;
static uint32_t previous_ms, previous_sequence;
static uint8_t have_sample;
#ifndef HEART_REQUIRED
#define HEART_REQUIRED 5u
#endif
#ifndef HEART_TOLERANCE
#define HEART_TOLERANCE 30u /* 心搏窗口相对中位数的允许偏差，百分比 */
#endif
#ifndef MAINS_ABS_POWER
#define MAINS_ABS_POWER 9.6e11f /* 约100 mV峰值工频 */
#endif

static float absolute(float x) { return x<0.0f ? -x : x; }
static float greater(float a,float b) { return a>b ? a : b; }
static Section make_section(float b0,float b1,float b2,float a1,float a2)
{
    Section out;
    out.b0=b0;out.b1=b1;out.b2=b2;out.a1=a1;out.a2=a2;out.z1=0;out.z2=0;
    return out;
}
static float section_step(Section *s,float x)
{
    /* 转置直接II型，仅2个状态；每帧常数操作，不在ISR内执行。 */
    float y=s->b0*x+s->z1;
    s->z1=s->b1*x-s->a1*y+s->z2;
    s->z2=s->b2*x-s->a2*y;
    return y;
}
static void forget_periods(Periods *p,uint32_t reason)
{
    /* 失效清除资格和全部旧间隔；仅保留配置，不重置滤波制造新的阶跃。 */
    p->count=0;p->index=0;p->candidate_rate=0;p->anchored=0;p->bridged=0;p->last_good=0;
    memset(p->intervals,0,sizeof(p->intervals));p->reason=reason;
}
static void configure(Channel *c,uint8_t respiration)
{
    memset(c,0,sizeof(*c));
    /* 系数以250Hz、RBJ标准公式生成：50/100Hz Q=35；不移植旧滤波数组。 */
    c->notch1=make_section(.9865955975f,-.6097496124f,.9865955975f,-.6097496124f,.9731911951f);
    c->notch2=make_section(.9916729892f,1.604560602f,.9916729892f,1.604560602f,.9833459783f);
    c->hp=make_section(.9149691441f,-1.829938288f,.9149691441f,-1.822694925f,.8371816513f);
    c->lp=respiration ? make_section(.00009964476774f,.0001992895355f,.00009964476774f,-1.971567425f,.9719660038f)
                      : make_section(.06745527389f,.1349105478f,.06745527389f,-1.142980503f,.4128015981f);
    c->periods.minimum=respiration ? 1500u : 273u;
    c->periods.maximum=respiration ? 10000u : 2000u;
    c->periods.timeout=respiration ? 12000u : 4000u;
    c->periods.reason=BIO_V2_WARMUP;
    c->periods.required=respiration ? 3u : HEART_REQUIRED;
    c->periods.tolerance=respiration ? 20u : HEART_TOLERANCE;
    c->periods.bridge=!respiration;
}
static uint8_t accept_input(Channel *c,int32_t raw,uint8_t resp,uint32_t now)
{
    if(raw>=8304721 || raw<=-8304721) {
        /* 只重置故障通道，首次削顶清空滤波及全部周期资格；后续削顶不喂入滤波。
           clipped独立保留，getter/超时发布不能把削顶原因悄悄抹掉。 */
        if(!c->clipped)configure(c,resp);
        c->clipped=1;forget_periods(&c->periods,BIO_V2_CLIPPED);
        return 0;
    }
    if(c->clipped) {
        /* 恢复要从首个未削顶输入重新预热并积累新周期，不复活旧率值/极值历史。 */
        configure(c,resp);c->valid_start_ms=now;
    }
    return 1;
}
static void new_segment(uint32_t now)
{
    configure(&heart,0);configure(&breathing,1);
    heart.valid_start_ms=breathing.valid_start_ms=now;
    g_bio_v2.segment++;have_sample=0;
#if BIO_V2_RR_R1
    r1_reset();
#endif
    g_bio_v2.hr=g_bio_v2.rpm=g_bio_v2.hr_valid=g_bio_v2.rpm_valid=0;
    g_bio_v2.hr_reason=g_bio_v2.rpm_reason=BIO_V2_WARMUP;
}
void BioV2_Init(uint32_t now_ms)
{
    memset(&g_bio_v2,0,sizeof(g_bio_v2));
    g_bio_v2.tag=0x324f4942u;g_bio_v2.abi_version=2;
#if BIO_V2_RR_R1
    r1_tables();
#endif
    new_segment(now_ms);
}
static void expire(Periods *p,uint32_t now)
{
    /* 可桥接漏检时锚点最长等两个最大间隔，否则慢心率下漏检一拍会先被判过期。 */
    uint32_t limit=(p->bridge && !p->bridged && p->count>=3u) ? 2u*p->maximum : p->maximum;
    if ((p->count!=0 && (uint32_t)(now-p->last_good)>p->timeout) ||
        (p->anchored && (uint32_t)(now-p->anchor)>limit))
        forget_periods(p,BIO_V2_EXPIRED);
}
static uint32_t window_median(const Periods *p,uint32_t sorted[5])
{
    uint32_t i,j,swap;
    for (i=0;i<p->count;i++) sorted[i]=p->intervals[i];
    for (i=0;i<p->count;i++) for(j=i+1;j<p->count;j++)
        if(sorted[j]<sorted[i]) {swap=sorted[i];sorted[i]=sorted[j];sorted[j]=swap;}
    return sorted[p->count/2u];
}
static uint8_t accept_cycle(Periods *p,uint32_t at)
{
    uint32_t elapsed, sorted[5],i,median,largest,tolerance;
    /* 候选时刻与最后合法周期分开。非法候选不能更新合法周期的有效期。 */
    expire(p,at);
    if (!p->anchored) { p->anchor=at;p->anchored=1;p->reason=BIO_V2_NO_CYCLES;return 0; }
    elapsed=(uint32_t)(at-p->anchor);
    if (elapsed<p->minimum) return 0;
    /* 漏检一拍：间隔为窗口中位数1.75–2.25倍时只前移锚点，不入窗、不改率值；
       不连续桥接，真实减半时下一间隔照常入窗并判不稳定。 */
    if (p->bridge && !p->bridged && p->count>=3u) {
        median=window_median(p,sorted);
        if (elapsed*4u>=median*7u && elapsed*4u<=median*9u) {
            p->anchor=at;p->last_good=at;p->bridged=1;return 0;
        }
    }
    if (elapsed>p->maximum) {
        forget_periods(p,BIO_V2_EXPIRED);p->anchor=at;p->anchored=1;return 0;
    }
    p->anchor=at;p->last_good=at;p->bridged=0;
    /* 滞回：上一判定有效才用放宽容差维持，首次锁定仍按20%，噪声难以偶然成锁。 */
    tolerance=p->candidate_rate ? p->tolerance : 20u;
    p->intervals[p->index]=elapsed;p->index=(p->index+1u)%5u;
    if (p->count<5u) p->count++;
    p->candidate_rate=0;p->reason=BIO_V2_NO_CYCLES;
    if (p->count<p->required) return 1;
    median=window_median(p,sorted);largest=0;
    for(i=0;i<p->count;i++) {
        uint32_t difference=sorted[i]>median ? sorted[i]-median : median-sorted[i];
        if(difference>largest)largest=difference;
    }
    /* 最近窗口每个间隔都需在中位周期的容差内（首次锁定20%，已有效的心搏按HEART_TOLERANCE维持）；不是只看数值是否在量程内。 */
    if(largest*100u>median*tolerance) {p->reason=BIO_V2_UNSTABLE;return 1;}
    p->candidate_rate=(60000u+median/2u)/median;p->reason=0;return 1;
}
#if BIO_V2_ALC
static uint32_t line_ms; /* 当前样本时刻，供工频参考取相位 */
static float cancel_line(Channel *c,float y)
{
    /* 50 Hz 参考按毫秒时刻取相位（周期 20 ms 查表，sin 由 cos 错位 5 格）；μ=0.01，
       |e|>3σ 时冻结更新，免得 QRS 把权重拉偏。参考跟着实际采样时刻走，ADS 时钟偏差不影响相位。 */
    static const float k_cos[20]={1.0f,.951056516f,.809016994f,.587785252f,.309016994f,0.0f,-.309016994f,
        -.587785252f,-.809016994f,-.951056516f,-1.0f,-.951056516f,-.809016994f,-.587785252f,-.309016994f,
        0.0f,.309016994f,.587785252f,.809016994f,.951056516f};
    uint32_t i=line_ms%20u;
    float co=k_cos[i],si=k_cos[(i+15u)%20u];
    float e=y-(c->line_a*co+c->line_b*si);
    c->line_var=c->line_seeded ? c->line_var+.002f*(e*e-c->line_var) : e*e;
    c->line_seeded=1;
    if(e*e<=9.0f*c->line_var) {c->line_a+=.01f*e*co;c->line_b+=.01f*e*si;}
    return e;
}
#endif
static float filter_channel(Channel *c,int32_t raw,uint8_t respiration)
{
    float ac,notched,y,removed;
    if(!c->seeded) {c->dc=(float)raw;c->seeded=1;}
    /* 首点初始化直流估计；恒定大偏置不会从零初态产生虚假的呼吸峰。 */
    c->dc+=(respiration ? .0006664445f : .0124877435f)*((float)raw-c->dc);
    ac=(float)raw-c->dc;
    notched=section_step(&c->notch2,section_step(&c->notch1,ac));
    removed=ac-notched;
    c->raw_power+=.001f*(ac*ac-c->raw_power);
    c->line_power+=.001f*(removed*removed-c->line_power);
    c->clean_power+=.004f*(notched*notched-c->clean_power);
    y=respiration ? section_step(&c->lp,notched) : section_step(&c->lp,section_step(&c->hp,notched));
#if BIO_V2_ALC
    if(!respiration) {c->wave=y;y=cancel_line(c,y);} /* 带内功率与峰检都用抵消后的波形 */
#endif
    c->band_power+=.004f*(y*y-c->band_power);
    return y;
}
static void heartbeat(float y,uint32_t now)
{
    float a=absolute(y);
    float threshold=greater(30.0f,2.5f*sqrtf(greater(heart.band_power,0.0f)));
    if(!heart.in_peak && a>=threshold) {
        heart.in_peak=1;heart.above_ms=now;heart.peak=a;heart.peak_ms=now;heart.gate=threshold;
    } else if(heart.in_peak) {
        if(a>heart.peak) {heart.peak=a;heart.peak_ms=now;}
        if(a<heart.gate*.5f || (uint32_t)(now-heart.above_ms)>200u) {
            uint32_t width=(uint32_t)(now-heart.above_ms);
            heart.in_peak=0;
            g_bio_v2.hr_candidates++;
            /* 完整峰宽+幅度+不应期+新鲜周期窗口，不沿用旧积分/SPKI状态机。 */
            if(width>=12u && width<=160u && heart.peak>=heart.gate*1.05f &&
               (uint32_t)(now-heart.valid_start_ms)>=5000u)
                if(accept_cycle(&heart.periods,heart.peak_ms))g_bio_v2.hr_accepted++;
        }
    }
}
static void respiration(float y,uint32_t now)
{
    float gate=greater(20.0f,.6f*sqrtf(greater(breathing.band_power,0.0f)));
    if(breathing.previous2>breathing.previous && breathing.previous<=y) {
        if(!breathing.armed_trough || breathing.previous<breathing.trough) {
            breathing.trough=breathing.previous;breathing.trough_ms=now;breathing.armed_trough=1;
        }
    }
    if(breathing.previous2<breathing.previous && breathing.previous>=y && breathing.armed_trough &&
       breathing.previous-breathing.trough>2.0f*gate &&
       (uint32_t)(now-breathing.trough_ms)>=300u && (uint32_t)(now-breathing.valid_start_ms)>=10000u) {
        breathing.armed_trough=0;g_bio_v2.resp_candidates++;
        if(accept_cycle(&breathing.periods,now))g_bio_v2.resp_accepted++;
    }
    breathing.previous2=breathing.previous;breathing.previous=y;
}
#if BIO_V2_RR_R1
/* R102 候选 R1：50 Hz RESP（与 CAN 上传同一批点、同一量化）32 s 窗内谱峰，步长 2 s。
   参数逐项对应 resp_r1.py（R125 起下限 8→9.5 次/分）；时域周期仍运行，只保留诊断计数。
   谱计算按频点摊到后续采样帧（每帧一个频点，约 1 s 算完），主循环不再每 2 s 长时间停顿（R124 §3.1）。 */
#define R1_WINDOW_MS 32000u
#define R1_STEP_MS 2000u
#define R1_RING 1800u     /* 36 s × 50 Hz */
#define R1_GRID 320u      /* 32 s 重采样到 10 Hz */
#define R1_BIN_LO 41u     /* 4096 点补零谱的 0.1–0.7 Hz：k×10/4096 Hz，k=41..286 */
#define R1_BINS 246u
#define R1_PEAK_BINS 12   /* ±0.03 Hz */
#define R1_RPM_MIN 9.5f   /* R124 §3.3：9.5 次/分以下多为基线慢漂的低频泄漏；10 次/分（谱格 9.96）仍可输出 */
typedef struct {
    uint32_t ms[R1_RING], head, count, next_end;
    float v[R1_RING], hist[3];
    uint8_t hist_ok[3], hist_n, started, pending;
    uint32_t rate, reason, valid;
    uint32_t pend_end, bin, kp;   /* 待算窗的末端、下一个频点、当前最大频点 */
    float best, total;
} R1State;
static R1State r1;
static float r1_sorted[R1_RING], r1_grid[R1_GRID], r1_hann[R1_GRID], r1_coeff[R1_BINS], r1_power[R1_BINS];
#ifdef BIO_V2_HOST_TEST
static uint32_t *trace_end, trace_n, trace_cap;
static float *trace_est, *trace_val;
static uint8_t *trace_why;
#endif
static void r1_tables(void)
{
    uint32_t i;
    for(i=0;i<R1_GRID;i++)r1_hann[i]=.5f-.5f*cosf(6.283185307f*(float)i/(float)(R1_GRID-1u));
    for(i=0;i<R1_BINS;i++)r1_coeff[i]=2.0f*cosf(6.283185307f*(float)(R1_BIN_LO+i)/4096.0f);
}
static void r1_reset(void)
{
    r1.head=r1.count=0;r1.hist_n=0;r1.started=0;r1.pending=0;r1.valid=0;r1.rate=0;r1.reason=BIO_V2_WARMUP;
}
static float r1_select(float *a,int32_t n,int32_t k)
{
    /* Hoare 选择：返回第 k 小，a 被部分重排；a[k+1..] 均不小于返回值。 */
    int32_t lo=0,hi=n-1,i,j;
    float pivot,t;
    while(lo<hi) {
        pivot=a[(lo+hi)/2];i=lo;j=hi;
        while(i<=j) {
            while(a[i]<pivot)i++;
            while(a[j]>pivot)j--;
            if(i<=j) {t=a[i];a[i]=a[j];a[j]=t;i++;j--;}
        }
        if(k<=j)hi=j; else if(k>=i)lo=i; else break;
    }
    return a[k];
}
static float r1_percentile(int32_t n,float q)
{
    /* numpy 默认线性插值：位置 q×(n−1)。 */
    float pos=q*(float)(n-1),t,lo,hi;
    int32_t k=(int32_t)pos,i;
    lo=r1_select(r1_sorted,n,k);t=pos-(float)k;hi=lo;
    if(k+1<n) {hi=r1_sorted[k+1];for(i=k+2;i<n;i++)if(r1_sorted[i]<hi)hi=r1_sorted[i];}
    return t<.5f ? lo+(hi-lo)*t : hi-(hi-lo)*(1.0f-t);
}
static uint8_t r1_prepare(uint32_t end)
{
    /* 取窗、门槛和网格准备；返回 0=网格就绪待算谱，1 覆盖不足、2 缺口、3 瞬变、4 幅度，顺序同 resp_r1.window。 */
    uint32_t a=end-R1_WINDOW_MS,i,idx,first=0,prev=a,d,j,gap=0;
    int32_t n=0;
    float base=0,lo=0,hi=0,p5,p95,mean=0,slope=0;
    for(i=0;i<r1.count;i++) {
        idx=(r1.head+R1_RING-r1.count+i)%R1_RING;d=r1.ms[idx]-a;
        if((int32_t)d<0 || d>=R1_WINDOW_MS)continue;
        if(!n) {first=i;base=r1.v[idx];}
        if(r1.ms[idx]-prev>gap)gap=r1.ms[idx]-prev;
        prev=r1.ms[idx];r1_sorted[n]=r1.v[idx]-base; /* 去掉首值，大基线下保留 float 精度 */
        if(!n || r1_sorted[n]<lo)lo=r1_sorted[n];
        if(!n || r1_sorted[n]>hi)hi=r1_sorted[n];
        n++;
    }
    if(n<1440)return 1u;
    if(a+R1_WINDOW_MS-prev>gap)gap=a+R1_WINDOW_MS-prev;
    if(gap>1000u)return 2u;
    p5=r1_percentile(n,.05f);p95=r1_percentile(n,.95f);
    if(hi-lo>3.0f*(p95-p5))return 3u;
    if((p95-p5)*.5f<60.0f)return 4u;
    /* 线性插值到 10 Hz 网格（两端取端值），再去线性趋势、加 Hann 窗。 */
    for(i=first,j=0;j<R1_GRID;j++) {
        uint32_t g=a+100u*j,i0,i1;
        while(i+1u<r1.count) {
            i1=(r1.head+R1_RING-r1.count+i+1u)%R1_RING;
            if((int32_t)(r1.ms[i1]-g)>0 || (int32_t)(r1.ms[i1]-end)>=0)break;
            i++;
        }
        i0=(r1.head+R1_RING-r1.count+i)%R1_RING;i1=(i0+1u)%R1_RING;
        if((int32_t)(g-r1.ms[i0])<=0 || i+1u>=r1.count || (int32_t)(r1.ms[i1]-end)>=0)r1_grid[j]=r1.v[i0]-base;
        else r1_grid[j]=r1.v[i0]-base+(r1.v[i1]-r1.v[i0])*(float)(g-r1.ms[i0])/(float)(r1.ms[i1]-r1.ms[i0]);
        mean+=r1_grid[j];
    }
    mean/=(float)R1_GRID;
    for(j=0;j<R1_GRID;j++)slope+=((float)j-159.5f)*(r1_grid[j]-mean);
    slope/=(float)R1_GRID*((float)R1_GRID*(float)R1_GRID-1.0f)/12.0f;
    for(j=0;j<R1_GRID;j++)r1_grid[j]=(r1_grid[j]-mean-slope*((float)j-159.5f))*r1_hann[j];
    return 0u;
}
static void r1_decide(uint32_t end,uint8_t why,float e)
{
    /* 5 贴边、6 谱峰占比由 r1_finish 判定；三窗一致才输出，同 resp_r1.run。 */
    float lo,hi,mid=0;
    uint8_t i;
    (void)end; /* 只供主机重放记录 */
    for(i=0;i<2u;i++) {r1.hist[i]=r1.hist[i+1u];r1.hist_ok[i]=r1.hist_ok[i+1u];}
    r1.hist[2]=e;r1.hist_ok[2]=why==0u;
    if(r1.hist_n<3u)r1.hist_n++;
    r1.valid=0;r1.rate=0;
    if(r1.hist_n<3u)r1.reason=BIO_V2_WARMUP;
    else if(!r1.hist_ok[0] || !r1.hist_ok[1] || !r1.hist_ok[2])r1.reason=BIO_V2_NO_CYCLES;
    else {
        lo=hi=r1.hist[0];
        for(i=1;i<3u;i++) {if(r1.hist[i]<lo)lo=r1.hist[i];if(r1.hist[i]>hi)hi=r1.hist[i];}
        mid=r1.hist[0]+r1.hist[1]+r1.hist[2]-lo-hi;
        if(hi-lo>2.0f)r1.reason=BIO_V2_UNSTABLE;
        else {r1.valid=1;r1.rate=(uint32_t)(mid+.5f);r1.reason=0;}
    }
#ifdef BIO_V2_HOST_TEST
    if(trace_n<trace_cap) {
        trace_end[trace_n]=end;trace_est[trace_n]=why ? 0.0f : e;trace_why[trace_n]=why;
        trace_val[trace_n]=r1.valid ? mid : -1.0f;trace_n++;
    }
#endif
}
static void r1_finish(void)
{
    float e=(float)(R1_BIN_LO+r1.kp)*600.0f/4096.0f,peak=0;
    uint32_t k;
    uint8_t why=0;
    if(!(e>R1_RPM_MIN && e<39.0f))why=5u;
    else {
        for(k=r1.kp-R1_PEAK_BINS;k<=r1.kp+R1_PEAK_BINS;k++)peak+=r1_power[k];
        if(peak<.5f*r1.total)why=6u;
    }
    r1.pending=0;r1_decide(r1.pend_end,why,e);
}
static void r1_work(void)
{
    /* Goertzel 求一个频点的功率，等于补零 4096 点 rfft 的 |X|²；频点顺序与累加顺序同整窗一次算完。 */
    float c,s0,s1=0,s2=0;
    uint32_t j;
    if(!r1.pending)return;
    c=r1_coeff[r1.bin];
    for(j=0;j<R1_GRID;j++) {s0=r1_grid[j]+c*s1-s2;s2=s1;s1=s0;}
    r1_power[r1.bin]=s1*s1+s2*s2-c*s1*s2;r1.total+=r1_power[r1.bin];
    if(r1_power[r1.bin]>r1.best) {r1.best=r1_power[r1.bin];r1.kp=r1.bin;}
    if(++r1.bin==R1_BINS)r1_finish();
}
static void r1_feed(uint32_t ms,float v)
{
    uint8_t why;
    if(!r1.started) {r1.next_end=ms+R1_WINDOW_MS;r1.started=1;}
    while((int32_t)(ms-r1.next_end)>=0) {
        while(r1.pending)r1_work(); /* 只在输入跳过多个步长时出现：先补完上一窗，保持逐窗顺序 */
        why=r1_prepare(r1.next_end);
        if(why)r1_decide(r1.next_end,why,0.0f);
        else {r1.pending=1;r1.pend_end=r1.next_end;r1.bin=0;r1.kp=0;r1.best=-1.0f;r1.total=0;}
        r1.next_end+=R1_STEP_MS;
    }
    r1.ms[r1.head]=ms;r1.v[r1.head]=v;r1.head=(r1.head+1u)%R1_RING;
    if(r1.count<R1_RING)r1.count++;
}
#ifdef BIO_V2_HOST_TEST
/* 仅主机重放：直接喂 50 Hz RESP（r 单位），每点之间按板上节奏调用 5 次 r1_work（250 SPS）；
   first_end 非 0 时对齐首窗末端，逐窗结果写入数组。 */
uint32_t BioV2_R1Replay(const uint32_t *ms,const float *v,uint32_t n,uint32_t first_end,
                        uint32_t *end,float *est,uint8_t *why,float *val,uint32_t cap)
{
    uint32_t i;
    r1_tables();r1_reset();
    trace_end=end;trace_est=est;trace_why=why;trace_val=val;trace_cap=cap;trace_n=0;
    if(first_end) {r1.next_end=first_end;r1.started=1;}
    for(i=0;i<n;i++) {r1_feed(ms[i],v[i]);r1_work();r1_work();r1_work();r1_work();r1_work();}
    while(r1.pending)r1_work();
    trace_cap=0;return trace_n;
}
#endif
#endif
static void publish(Channel *c,uint8_t resp,uint32_t now)
{
    uint32_t reason=c->periods.reason,rate=c->periods.candidate_rate;
    float fraction=c->raw_power>1.0f ? c->line_power/c->raw_power : 0.0f;
#if BIO_V2_RR_R1
    if(resp) {reason=r1.reason;rate=r1.valid ? r1.rate : 0;}
#endif
    if(fraction>1.0f)fraction=1.0f;
    if(c->clipped)reason|=BIO_V2_CLIPPED;
    else if((uint32_t)(now-c->valid_start_ms)<(resp ? 10000u : 5000u))reason|=BIO_V2_WARMUP;
    /* 原始干扰很强时保留滤波波形，但不通过制造量程内数字宣告可信。 */
    if(c->line_power>MAINS_ABS_POWER)reason|=BIO_V2_MAINS;
    if(!rate)reason|=BIO_V2_NO_CYCLES;
    if(resp) {
        g_bio_v2.rpm_valid=reason==0;g_bio_v2.rpm=reason==0 ? rate : 0;g_bio_v2.rpm_reason=reason;
        g_bio_v2.resp_last_cycle_ms=c->periods.last_good;g_bio_v2.resp_fresh_intervals=c->periods.count;
        g_bio_v2.resp_rms_codes=sqrtf(greater(c->band_power,0));g_bio_v2.resp_mains_fraction=fraction;
    } else {
        g_bio_v2.hr_valid=reason==0;g_bio_v2.hr=reason==0 ? rate : 0;g_bio_v2.hr_reason=reason;
        g_bio_v2.hr_last_cycle_ms=c->periods.last_good;g_bio_v2.hr_fresh_intervals=c->periods.count;
        g_bio_v2.ecg_rms_codes=sqrtf(greater(c->band_power,0));g_bio_v2.ecg_mains_fraction=fraction;
    }
}
void BioV2_Process(int32_t ecg,int32_t resp,uint32_t now,uint32_t sequence,uint8_t flags)
{
    float h,r;
    uint8_t good_h,good_r;
#if BIO_V2_ALC
    line_ms=now;
#endif
    if(flags || (have_sample && ((uint32_t)(now-previous_ms)>BIO_V2_GAP_MS ||
                                sequence!=(uint32_t)(previous_sequence+1u)))) {
        g_bio_v2.discontinuities++;new_segment(now);
    }
    if(!have_sample)heart.valid_start_ms=breathing.valid_start_ms=now;
    good_h=accept_input(&heart,ecg,0,now);good_r=accept_input(&breathing,resp,1,now);
    if(!good_h || !good_r)g_bio_v2.clipped_samples++; /* 一帧两路削顶仍只计一次。 */
    h=good_h ? filter_channel(&heart,ecg,0) : 0.0f;
    r=good_r ? filter_channel(&breathing,resp,1) : 0.0f;
    /* 先判本次周期的输入资格，再建立周期历史，避免干扰结束后复活噪声历史。
       呼吸低通会把白噪声变成慢起伏，必须有足够低频能量占比才能候选判周期。 */
    if(good_h && heart.line_power>MAINS_ABS_POWER) {
        forget_periods(&heart.periods,BIO_V2_MAINS);heart.in_peak=0;
    } else if(good_h)heartbeat(h,now);
    if(good_r && breathing.line_power>MAINS_ABS_POWER) {
        forget_periods(&breathing.periods,BIO_V2_MAINS);breathing.armed_trough=0;
        breathing.previous2=breathing.previous;breathing.previous=r;
    } else if(good_r && breathing.clean_power>1.0f && breathing.band_power<breathing.clean_power*.05f) {
        forget_periods(&breathing.periods,BIO_V2_BROADBAND_NOISE);breathing.armed_trough=0;
        breathing.previous2=breathing.previous;breathing.previous=r;
    } else if(good_r)respiration(r,now);
    /* 削顶帧也保留源序号/时间和原始码；公共缺口/超时判断仍覆盖整个输入流。 */
    previous_ms=now;previous_sequence=sequence;have_sample=1;
    expire(&heart.periods,now);expire(&breathing.periods,now);
#if BIO_V2_RR_R1
    /* 与 CAN 上传相同：序号逢 5 取一点、按上传量化；削顶时窗口作废重来。 */
    if(!good_r)r1_reset();
    else {
        if(sequence%5u==0u)r1_feed(now,(float)(int32_t)(r*.11920928955f)/.11920928955f);
        r1_work();
    }
#endif
    publish(&heart,0,now);publish(&breathing,1,now);
    g_bio_v2.ecg_raw=ecg;g_bio_v2.resp_raw=resp;
    /* UI尺度只作兼容换算；计算和原始证据均保留ADC码，不输出未经校准的mV/欧姆。 */
#if BIO_V2_ALC
    /* 上传波形仍为抵消前的检测带，与 C2 录制口径一致，便于离线对照。 */
    g_bio_v2.ecg_filtered=(int32_t)((good_h ? heart.wave : 0.0f)*.11920928955f);
#else
    g_bio_v2.ecg_filtered=(int32_t)(h*.11920928955f);
#endif
    g_bio_v2.resp_filtered=(int32_t)(r*.11920928955f);
    g_bio_v2.last_sequence=sequence;g_bio_v2.last_sample_ms=now;g_bio_v2.samples++;
}
void BioV2_Tick(uint32_t now)
{
    if(!have_sample || (uint32_t)(now-previous_ms)>BIO_V2_GAP_MS) {
        forget_periods(&heart.periods,BIO_V2_DISCONTINUITY);
        forget_periods(&breathing.periods,BIO_V2_DISCONTINUITY);
#if BIO_V2_RR_R1
        r1.valid=0;r1.rate=0;r1.reason=BIO_V2_DISCONTINUITY;
#endif
    } else {expire(&heart.periods,now);expire(&breathing.periods,now);}
    publish(&heart,0,now);publish(&breathing,1,now);
}
uint8_t BioV2_GetHeart(uint16_t *rate,uint32_t now)
{
    if(!rate)return 0;
    BioV2_Tick(now);*rate=(uint16_t)g_bio_v2.hr;return (uint8_t)g_bio_v2.hr_valid;
}
uint8_t BioV2_GetResp(uint16_t *rate,uint32_t now)
{
    if(!rate)return 0;
    BioV2_Tick(now);*rate=(uint16_t)g_bio_v2.rpm;return (uint8_t)g_bio_v2.rpm_valid;
}
int32_t BioV2_EcgWave(void) {return g_bio_v2.ecg_filtered;}
int32_t BioV2_RespWave(void) {return g_bio_v2.resp_filtered;}
