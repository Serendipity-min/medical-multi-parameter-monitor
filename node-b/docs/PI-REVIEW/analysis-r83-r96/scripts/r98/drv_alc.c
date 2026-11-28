/* R103 夹具：主线 bio_v2.c（BIO_V2_ALC=1）的工频抵消 + C2 峰检/判据，喂录制的检测带 y，与 R99 的 Python ALC 逐点对照。仅离线分析用。 */
#define BIO_V2_ALC 1
#include BIO_SRC
void A_Init(uint32_t t0) { memset(&g_bio_v2,0,sizeof(g_bio_v2)); configure(&heart,0); heart.valid_start_ms=t0-5000u; }
/* Python 原型在时间缺口 >20 ms 时清零权重；板上由 new_segment() 整体重置，这里只为逐点对照 */
void A_Reset(void) { heart.line_a=heart.line_b=heart.line_var=0.0f; heart.line_seeded=0; }
float A_Line(float y,uint32_t now) { line_ms=now; return cancel_line(&heart,y); }
uint32_t A_Feed(float y,uint32_t now)
{
    float e=A_Line(y,now);
    heart.band_power+=.004f*(e*e-heart.band_power);
    heartbeat(e,now); expire(&heart.periods,now); publish(&heart,0,now);
    return g_bio_v2.hr_valid ? g_bio_v2.hr : 0u;
}
