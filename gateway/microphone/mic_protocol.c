#include "mic_protocol.h"
#include "mic_format.h"
#include <string.h>
static uint32_t load32(const uint8_t *p) {return (uint32_t)p[0]|((uint32_t)p[1]<<8)|((uint32_t)p[2]<<16)|((uint32_t)p[3]<<24);}
static void store16(uint8_t *p,unsigned n) {p[0]=(uint8_t)n;p[1]=(uint8_t)(n>>8);}
static void store32(uint8_t *p,uint32_t n) {store16(p,n);store16(p+2,n>>16);}
static int token(const char *p,size_t capacity) {
    size_t n=0;
    for(;n<capacity && p[n];++n)
        if(!((p[n]>='a'&&p[n]<='z') || (p[n]>='A'&&p[n]<='Z') ||
             (p[n]>='0'&&p[n]<='9') || p[n]=='-' || p[n]=='_'))return 0;
    return n>0 && n<capacity;
}
int mic_config_byte(uint8_t packet[249],unsigned *position,uint8_t byte) {
    if(*position) {
        packet[(*position)++-1]=byte;
        if(*position==250){*position=0;return 2;}
        return 1;
    }
    if(byte=='C'){*position=1;return 1;}
    return 0;
}
int mic_config_packet_valid(const uint8_t *p,size_t n) {
    if(n!=249 || memcmp(p,"MCF3",4) || load32(p+245)!=mic_crc32(p,245) || load32(p+241)<1700000000u ||
       !token((const char *)p+4,33) || !token((const char *)p+37,65) || !token((const char *)p+102,41))return 0;
    const unsigned offsets[2]={143,176},capacities[2]={33,65};
    for(unsigned field=0;field<2;field++) {
        unsigned length=0;const uint8_t *value=p+offsets[field];
        for(;length<capacities[field] && value[length];length++)
            if(value[length]<0x20 || value[length]==0x7f || value[length]=='"' || value[length]=='\\')return 0;
        if(length<(field?8u:1u) || length==capacities[field])return 0;
    }
    return 1;
}
void mic_chunk_packet(uint8_t p[544],uint32_t session,unsigned seq,uint32_t crc,const uint8_t data[512]) {
    memcpy(p,"MC01",4);store32(p+4,session);store16(p+8,seq);store16(p+10,125);
    store32(p+12,16000);store32(p+16,64000);store32(p+20,crc);memcpy(p+32,data,512);
    store32(p+24,mic_crc32(data,512));store16(p+28,512);
    p[30]=(uint8_t)((seq==0?1:0)|(seq==124?2:0));p[31]=1;
}
int mic_reply_packet_valid(const uint8_t *p,size_t n,uint32_t session,uint32_t crc) {
    if(n<=16 || n>76 || memcmp(p,"MR01",4) || load32(p+4)!=session || load32(p+8)!=crc ||
       (unsigned)p[12]+16u!=n || p[13] || p[14] || p[15])return 0;
    for(size_t i=16;i<n;i++)if(p[i]<0x20 || p[i]==0x7f || p[i]=='[' || p[i]==']')return 0;
    return 1;
}
