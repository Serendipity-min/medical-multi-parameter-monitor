#ifndef MP_H3_SNTP_SAMPLE_H
#define MP_H3_SNTP_SAMPLE_H
#include <stdint.h>
#include <stddef.h>
#include <string.h>

static inline uint32_t sntp_u32(const unsigned char *p) {
    return ((uint32_t)p[0]<<24)|((uint32_t)p[1]<<16)|((uint32_t)p[2]<<8)|p[3];
}
static inline void sntp_put32(unsigned char *p,uint32_t v) {
    p[0]=(unsigned char)(v>>24);p[1]=(unsigned char)(v>>16);p[2]=(unsigned char)(v>>8);p[3]=(unsigned char)v;
}
/* 目标从模块当前SNTP配置读取；仅接收一个有界DNS名，不在源码内固化真实连接地址。 */
static inline int sntp_first_server(const char *reply,char server[65]) {
    const char *p=strstr(reply,"+CIPSNTPCFG:");
    if(!p || !(p=strchr(p,'"')))return 0;
    p++;size_t length=0;
    while(p[length] && p[length]!='"') {
        char c=p[length];
        if(length>=64 || !((c>='a' && c<='z') || (c>='A' && c<='Z') ||
             (c>='0' && c<='9') || c=='.' || c=='-'))return 0;
        server[length]=c;length++;
    }
    if(!length || p[length]!='"')return 0;
    server[length]=0;return 1;
}
/* 真实SNTP回复必须匹配本次请求的8字节originate；闰秒未同步/KoD/旧包均不授时。
 * 收到时刻按服务器发送时间加网络半程估计；RTT大于1秒则拒绝，不放宽监护TTL。 */
static inline int sntp_sample(const unsigned char *packet,size_t length,
                              const unsigned char request[48],uint32_t rtt_ms,
                              uint32_t minimum_epoch,uint64_t *received_ms) {
    if(length!=48 || rtt_ms>1000 || (packet[0]>>6)==3 ||
       (packet[0]&7)!=4 || ((packet[0]>>3)&7)<3 || ((packet[0]>>3)&7)>4 ||
       packet[1]<1 || packet[1]>15 || memcmp(packet+24,request+40,8))return 0;
    uint32_t seconds=sntp_u32(packet+40),recv_seconds=sntp_u32(packet+32);
    if(seconds<2208988800u || recv_seconds<2208988800u)return 0;
    uint64_t tx=((uint64_t)seconds-2208988800u)*1000u+
        (((uint64_t)sntp_u32(packet+44)*1000u)>>32);
    uint64_t rx=((uint64_t)recv_seconds-2208988800u)*1000u+
        (((uint64_t)sntp_u32(packet+36)*1000u)>>32);
    if(tx<rx || tx-rx>rtt_ms || tx/1000u<minimum_epoch)return 0;
    *received_ms=tx+(rtt_ms-(uint32_t)(tx-rx))/2u;return 1;
}
#endif
