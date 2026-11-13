#include "mic_protocol.h"
#include "mic_format.h"
#include <string.h>
#ifdef MP_FIVE_APPLIANCE
#include "../data_model/roles.h"
#endif
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
    mic_chunk_packet_length(p,session,seq,crc,data,64000u);
}
void mic_chunk_packet_length(uint8_t p[544],uint32_t session,unsigned seq,uint32_t crc,const uint8_t *data,unsigned bytes) {
    unsigned total=(bytes+511u)/512u,length=bytes-seq*512u;if(length>512u)length=512u;
    memset(p,0,544);memcpy(p,"MC01",4);store32(p+4,session);store16(p+8,seq);store16(p+10,total);
    store32(p+12,16000);store32(p+16,bytes);store32(p+20,crc);memcpy(p+32,data,length);
    store32(p+24,mic_crc32(data,length));store16(p+28,length);
    p[30]=(uint8_t)((seq==0?1:0)|(seq+1==total?2:0));p[31]=1;
}
int mic_reply_packet_valid(const uint8_t *p,size_t n,uint32_t session,uint32_t crc) {
    if(n<=16 || n>76 || memcmp(p,"MR01",4) || load32(p+4)!=session || load32(p+8)!=crc ||
       (unsigned)p[12]+16u!=n || p[13] || p[14] || p[15])return 0;
    for(size_t i=16;i<n;i++)if(p[i]<0x20 || p[i]==0x7f || p[i]=='[' || p[i]==']')return 0;
    return 1;
}
#ifdef MP_FIVE_APPLIANCE
static uint64_t load64(const uint8_t *p){return load32(p)|((uint64_t)load32(p+4)<<32);}
int mic_fact_reply_valid(const uint8_t *p,size_t n,uint32_t session,uint32_t crc,uint64_t now,MicFactReply *out) {
    static const char gateway[12]="GW-B5-001";
    if(n<=MIC_FACT_REPLY_HEADER || n>MIC_FACT_REPLY_MAX || memcmp(p,"MR02",4) ||
       load32(p+4)!=session || load32(p+8)!=crc || memcmp(p+52,gateway,12) ||
       (unsigned)p[80]+((unsigned)p[81]<<8)+MIC_FACT_REPLY_HEADER!=n || p[50]>MIC_REPLY_NO_FACT || p[51]>1)return 0;
    uint64_t issued=load64(p+12),expires=load64(p+20),stamp=load64(p+28);
    if(!now || issued>now+1000u || now>=expires || expires<=issued || expires-issued>15000u)return 0;
    unsigned nonzero=0;for(unsigned i=64;i<80;i++)nonzero|=p[i];if(!nonzero)return 0;
    unsigned stream=p[49],node=p[48];
    bool scalar=stream==MP_HR || stream==MP_RR || stream==MP_SPO2 || stream==MP_PR || stream==MP_TEMP || stream==MP_NIBP;
    if(p[50]>=MIC_REPLY_ADVICE) {
        if(stamp || load32(p+36) || load32(p+40) || load32(p+44) || node || stream || p[51] ||
           n!=MIC_FACT_REPLY_HEADER+1 || p[MIC_FACT_REPLY_HEADER]!='!')return 0;
    } else if(!scalar || node!=mp_role_node((MpStream)stream))return 0;
    if(!p[50]) {
        uint64_t ttl=stream==MP_NIBP?90000u:5000u;
        if(!stamp || stamp>now+1000u || (now>stamp && now-stamp>=ttl) ||
           expires>stamp+ttl || !load32(p+36) || !load32(p+40) || !load32(p+44))return 0;
    }
    for(size_t i=MIC_FACT_REPLY_HEADER;i<n;i++)if(p[i]<0x20 || p[i]==0x7f || p[i]=='[' || p[i]==']')return 0;
    *out=(MicFactReply){stamp,expires,load32(p+36),load32(p+40),load32(p+44),p[48],p[49],p[50],p[51],p+MIC_FACT_REPLY_HEADER,(unsigned)(n-MIC_FACT_REPLY_HEADER)};
    return 1;
}
#endif
