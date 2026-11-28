/* R118 夹具：C2 的 accept_cycle()/expire()/publish() 原样复用，只把心搏峰检的门限换成可选口径。仅离线分析用。
 * mode 0：门限 = max(30, k × 检测带 RMS)，k=2.5 即 C2 原式（含 QRS 能量）；
 * mode 1：门限 = max(30, k × 噪声 RMS)，噪声功率只用 |y| < 3σ 的样本更新，QRS 不进入估计。 */
#include "bio_v2_c2.c"
static float mult, noise_power;
static int mode;
void V_Init(uint32_t t0,int m,float k)
{
    memset(&g_bio_v2,0,sizeof(g_bio_v2)); configure(&heart,0); heart.valid_start_ms=t0-5000u;
    mode=m; mult=k; noise_power=0.0f;
}
static void beat(float y,uint32_t now)
{
    float a=absolute(y),level;
    if(mode==0) level=heart.band_power;
    else {
        /* 首秒用全部样本播种，之后只收 3σ 以内的样本 */
        if(noise_power<=0.0f || y*y<9.0f*noise_power || (uint32_t)(now-heart.valid_start_ms)<6000u)
            noise_power+=.004f*(y*y-noise_power);
        level=noise_power;
    }
    float threshold=greater(30.0f,mult*sqrtf(greater(level,0.0f)));
    if(!heart.in_peak && a>=threshold) {
        heart.in_peak=1;heart.above_ms=now;heart.peak=a;heart.peak_ms=now;heart.gate=threshold;
    } else if(heart.in_peak) {
        if(a>heart.peak) {heart.peak=a;heart.peak_ms=now;}
        if(a<heart.gate*.5f || (uint32_t)(now-heart.above_ms)>200u) {
            uint32_t width=(uint32_t)(now-heart.above_ms);
            heart.in_peak=0;
            if(width>=12u && width<=160u && heart.peak>=heart.gate*1.05f &&
               (uint32_t)(now-heart.valid_start_ms)>=5000u)
                accept_cycle(&heart.periods,heart.peak_ms);
        }
    }
}
uint32_t V_Feed(float y,uint32_t now)
{
    heart.band_power+=.004f*(y*y-heart.band_power);
    beat(y,now); expire(&heart.periods,now); publish(&heart,0,now);
    return g_bio_v2.hr_valid ? g_bio_v2.hr : 0u;
}
/* 原样 C2，用于核对 mode 0、k=2.5 与 C2 逐点一致 */
uint32_t C2_Feed(float y,uint32_t now)
{
    heart.band_power+=.004f*(y*y-heart.band_power);
    heartbeat(y,now); expire(&heart.periods,now); publish(&heart,0,now);
    return g_bio_v2.hr_valid ? g_bio_v2.hr : 0u;
}
