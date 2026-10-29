/* 厂家V3二进制响应为A4 03 07 07、7个寄存器、累加校验；不发配置/保存指令。 */
#include "gy641.h"
#include <string.h>
void gy641_init(Gy641 *s) { memset(s,0,sizeof(*s)); }
int gy641_feed(Gy641 *s, uint8_t byte, uint32_t now) {
    static const uint8_t header[4]={0xa4,0x03,0x07,0x07};
    if (s->used<4u && byte!=header[s->used]) {
        if (s->used) s->header_errors++;
        s->used=byte==header[0]?1u:0u;
        if (s->used) s->frame[0]=byte;
        return 0;
    }
    s->frame[s->used++]=byte;
    if (s->used<GY641_FRAME_BYTES) return 0;
    s->used=0;
    uint8_t sum=0;
    for (unsigned i=0;i<GY641_FRAME_BYTES-1u;i++) sum=(uint8_t)(sum+s->frame[i]);
    if (sum!=s->frame[11]) { s->checksum_errors++; return 0; }
    s->emissivity=s->frame[4];
    s->object_centi=(uint16_t)((uint16_t)s->frame[5]<<8|s->frame[6]);
    s->ambient_centi=(uint16_t)((uint16_t)s->frame[7]<<8|s->frame[8]);
    s->body_centi=(uint16_t)((uint16_t)s->frame[9]<<8|s->frame[10]);
    memcpy(s->last_frame,s->frame,GY641_FRAME_BYTES);
    s->last_ms=now;s->present=1;s->frames++;
    return 1;
}
int gy641_object(const Gy641 *s, uint32_t now, uint16_t *centi) {
    /* 本轮只开放0..100℃非人体物表工程域；不解释负温编码或签发补偿体温。 */
    if (!s->present || (uint32_t)(now-s->last_ms)>2500u ||
        !s->emissivity || s->emissivity>100u || s->object_centi>10000u) return 0;
    *centi=s->object_centi;return 1;
}
