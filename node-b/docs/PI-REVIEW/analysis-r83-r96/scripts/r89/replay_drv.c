/* 离线重放夹具：把录到的滤波 ECG（内部量纲 y）直接喂入 heartbeat()，跳过滤波；仅 PI 离线分析用。 */
#include BIO_SRC
void Replay_Init(uint32_t t0)
{
    memset(&g_bio_v2,0,sizeof(g_bio_v2));
    configure(&heart,0);heart.valid_start_ms=t0-5000u;
}
uint32_t Replay_Feed(float y,uint32_t now)
{
    heart.band_power+=.004f*(y*y-heart.band_power);
    heartbeat(y,now);expire(&heart.periods,now);publish(&heart,0,now);
    return g_bio_v2.hr_valid ? g_bio_v2.hr : 0u;
}
