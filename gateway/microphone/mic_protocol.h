#ifndef MIC_PROTOCOL_H
#define MIC_PROTOCOL_H
#include <stdint.h>
#include <stddef.h>
int mic_config_packet_valid(const uint8_t *p,size_t n);
int mic_config_byte(uint8_t packet[249],unsigned *position,uint8_t byte);
void mic_chunk_packet(uint8_t out[544],uint32_t session,unsigned seq,uint32_t whole_crc,const uint8_t data[512]);
void mic_chunk_packet_length(uint8_t out[544],uint32_t session,unsigned seq,uint32_t whole_crc,const uint8_t *data,unsigned bytes);
int mic_reply_packet_valid(const uint8_t *p,size_t n,uint32_t session,uint32_t whole_crc);
#ifdef MP_FIVE_APPLIANCE
#define MIC_FACT_REPLY_HEADER 82u
#define MIC_FACT_REPLY_MAX (MIC_FACT_REPLY_HEADER+120u)
typedef struct {
    uint64_t timestamp,expires;
    uint32_t seq,epoch,boot;
    uint8_t node,stream,status,synthetic;
    const uint8_t *text;unsigned length;
} MicFactReply;
int mic_fact_reply_valid(const uint8_t *p,size_t n,uint32_t session,uint32_t crc,uint64_t now,MicFactReply *out);
#endif
#endif
