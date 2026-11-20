/* C3 研究夹具：复用 C2 的 heartbeat()/accept_cycle()，只喂检测带 y 或外部给定的心搏时刻。仅离线分析用。 */
#include "bio_v2_c2.c"
void D_Init(uint32_t t0) { memset(&g_bio_v2,0,sizeof(g_bio_v2)); configure(&heart,0); heart.valid_start_ms=t0-5000u; }
/* C2 原峰检 + C2 判据 */
uint32_t D_Feed(float y,uint32_t now)
{
    heart.band_power+=.004f*(y*y-heart.band_power);
    heartbeat(y,now); expire(&heart.periods,now); publish(&heart,0,now);
    return g_bio_v2.hr_valid ? g_bio_v2.hr : 0u;
}
/* 外部检测器给出心搏时刻 at，用 C2 判据 */
void D_Beat(uint32_t at) { accept_cycle(&heart.periods,at); }
uint32_t D_Tick(uint32_t now) { expire(&heart.periods,now); publish(&heart,0,now); return g_bio_v2.hr_valid ? g_bio_v2.hr : 0u; }
