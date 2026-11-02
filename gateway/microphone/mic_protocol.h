#ifndef MIC_PROTOCOL_H
#define MIC_PROTOCOL_H
#include <stdint.h>
#include <stddef.h>
int mic_config_packet_valid(const uint8_t *p,size_t n);
int mic_config_byte(uint8_t packet[249],unsigned *position,uint8_t byte);
void mic_chunk_packet(uint8_t out[544],uint32_t session,unsigned seq,uint32_t whole_crc,const uint8_t data[512]);
int mic_reply_packet_valid(const uint8_t *p,size_t n,uint32_t session,uint32_t whole_crc);
#endif
