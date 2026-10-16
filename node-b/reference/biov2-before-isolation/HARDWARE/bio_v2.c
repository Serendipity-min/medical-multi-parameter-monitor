/* 独立实现：有界IIR、RMS峰宽判据、完整呼吸起伏、连续新鲜间隔资格。
 * 工程试验算法，不用“处于范围内”代替参考输入准确度或患者安全认证。
 */
#include "bio_v2.h"
#include <math.h>
#include <string.h>

typedef struct { float b0,b1,b2,a1,a2,z1,z2; } Section;
typedef struct {
    uint32_t anchor, last_good, minimum, maximum, timeout, intervals[5];
    uint32_t count, index, candidate_rate, reason;
    uint8_t anchored;
} Periods;
typedef struct {
    Section notch1, notch2, hp, lp;
    float dc, raw_power, line_power, clean_power, band_power, previous, previous2;
    float peak, trough, gate;
    uint32_t peak_ms, trough_ms, above_ms;
    uint8_t seeded, in_peak, armed_trough;
    Periods periods;
} Channel;
BioV2Diag g_bio_v2;
static Channel heart, breathing;
static uint32_t segment_start, previous_ms, previous_sequence;
static uint8_t have_sample;

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
    p->count=0;p->index=0;p->candidate_rate=0;p->anchored=0;p->last_good=0;
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
}
static void new_segment(uint32_t now)
{
    configure(&heart,0);configure(&breathing,1);segment_start=now;
    g_bio_v2.segment++;have_sample=0;
    g_bio_v2.hr=g_bio_v2.rpm=g_bio_v2.hr_valid=g_bio_v2.rpm_valid=0;
    g_bio_v2.hr_reason=g_bio_v2.rpm_reason=BIO_V2_WARMUP;
}
void BioV2_Init(uint32_t now_ms)
{
    memset(&g_bio_v2,0,sizeof(g_bio_v2));
    g_bio_v2.tag=0x324f4942u;g_bio_v2.abi_version=2;
    new_segment(now_ms);
}
static void expire(Periods *p,uint32_t now)
{
    if ((p->count!=0 && (uint32_t)(now-p->last_good)>p->timeout) ||
        (p->anchored && (uint32_t)(now-p->anchor)>p->maximum))
        forget_periods(p,BIO_V2_EXPIRED);
}
static uint8_t accept_cycle(Periods *p,uint32_t at)
{
    uint32_t elapsed, sorted[5],i,j,swap,median,largest;
    /* 候选时刻与最后合法周期分开。非法候选不能更新合法周期的有效期。 */
    expire(p,at);
    if (!p->anchored) { p->anchor=at;p->anchored=1;p->reason=BIO_V2_NO_CYCLES;return 0; }
    elapsed=(uint32_t)(at-p->anchor);
    if (elapsed<p->minimum) return 0;
    if (elapsed>p->maximum) {
        forget_periods(p,BIO_V2_EXPIRED);p->anchor=at;p->anchored=1;return 0;
    }
    p->anchor=at;p->last_good=at;
    p->intervals[p->index]=elapsed;p->index=(p->index+1u)%5u;
    if (p->count<5u) p->count++;
    p->candidate_rate=0;p->reason=BIO_V2_NO_CYCLES;
    if (p->count<3u) return 1;
    for (i=0;i<p->count;i++) sorted[i]=p->intervals[i];
    for (i=0;i<p->count;i++) for(j=i+1;j<p->count;j++)
        if(sorted[j]<sorted[i]) {swap=sorted[i];sorted[i]=sorted[j];sorted[j]=swap;}
    median=sorted[p->count/2u];largest=0;
    for(i=0;i<p->count;i++) {
        uint32_t difference=sorted[i]>median ? sorted[i]-median : median-sorted[i];
        if(difference>largest)largest=difference;
    }
    /* 最近窗口每个间隔都需在中位周期的20%内；不是只看数值是否在量程内。 */
    if(largest*100u>median*20u) {p->reason=BIO_V2_UNSTABLE;return 1;}
    p->candidate_rate=(60000u+median/2u)/median;p->reason=0;return 1;
}
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
               (uint32_t)(now-segment_start)>=5000u)
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
       (uint32_t)(now-breathing.trough_ms)>=300u && (uint32_t)(now-segment_start)>=10000u) {
        breathing.armed_trough=0;g_bio_v2.resp_candidates++;
        if(accept_cycle(&breathing.periods,now))g_bio_v2.resp_accepted++;
    }
    breathing.previous2=breathing.previous;breathing.previous=y;
}
static void publish(Channel *c,uint8_t resp,uint32_t now)
{
    uint32_t reason=c->periods.reason,rate=c->periods.candidate_rate;
    float fraction=c->raw_power>1.0f ? c->line_power/c->raw_power : 0.0f;
    if(fraction>1.0f)fraction=1.0f;
    if((uint32_t)(now-segment_start)<(resp ? 10000u : 5000u))reason|=BIO_V2_WARMUP;
    /* 原始干扰很强时保留滤波波形，但不通过制造量程内数字宣告可信。 */
    if(fraction>.95f && c->raw_power>10000.0f)reason|=BIO_V2_MAINS;
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
    if(flags || (have_sample && ((uint32_t)(now-previous_ms)>BIO_V2_GAP_MS ||
                                sequence!=(uint32_t)(previous_sequence+1u)))) {
        g_bio_v2.discontinuities++;new_segment(now);
    }
    if(ecg>=8304721 || ecg<=-8304721 || resp>=8304721 || resp<=-8304721) {
        g_bio_v2.clipped_samples++;new_segment(now);
        g_bio_v2.hr_reason=g_bio_v2.rpm_reason=BIO_V2_CLIPPED;
        return;
    }
    if(!have_sample)segment_start=now;
    h=filter_channel(&heart,ecg,0);r=filter_channel(&breathing,resp,1);
    /* 先判本次周期的输入资格，再建立周期历史，避免干扰结束后复活噪声历史。
       呼吸低通会把白噪声变成慢起伏，必须有足够低频能量占比才能候选判周期。 */
    if(heart.raw_power>10000.0f && heart.line_power>heart.raw_power*.95f) {
        forget_periods(&heart.periods,BIO_V2_MAINS);heart.in_peak=0;
    } else heartbeat(h,now);
    if(breathing.raw_power>10000.0f && breathing.line_power>breathing.raw_power*.95f) {
        forget_periods(&breathing.periods,BIO_V2_MAINS);breathing.armed_trough=0;
        breathing.previous2=breathing.previous;breathing.previous=r;
    } else if(breathing.clean_power>1.0f && breathing.band_power<breathing.clean_power*.05f) {
        forget_periods(&breathing.periods,BIO_V2_BROADBAND_NOISE);breathing.armed_trough=0;
        breathing.previous2=breathing.previous;breathing.previous=r;
    } else respiration(r,now);
    previous_ms=now;previous_sequence=sequence;have_sample=1;
    expire(&heart.periods,now);expire(&breathing.periods,now);
    publish(&heart,0,now);publish(&breathing,1,now);
    g_bio_v2.ecg_raw=ecg;g_bio_v2.resp_raw=resp;
    /* UI尺度只作兼容换算；计算和原始证据均保留ADC码，不输出未经校准的mV/欧姆。 */
    g_bio_v2.ecg_filtered=(int32_t)(h*.11920928955f);
    g_bio_v2.resp_filtered=(int32_t)(r*.11920928955f);
    g_bio_v2.last_sequence=sequence;g_bio_v2.last_sample_ms=now;g_bio_v2.samples++;
}
void BioV2_Tick(uint32_t now)
{
    if(!have_sample || (uint32_t)(now-previous_ms)>BIO_V2_GAP_MS) {
        forget_periods(&heart.periods,BIO_V2_DISCONTINUITY);
        forget_periods(&breathing.periods,BIO_V2_DISCONTINUITY);
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
