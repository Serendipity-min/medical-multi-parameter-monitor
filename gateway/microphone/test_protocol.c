#include "mic_protocol.h"
#include "mic_format.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>
static void u32(uint8_t *p,uint32_t n){for(unsigned i=0;i<4;i++)p[i]=(uint8_t)(n>>(8*i));}
int main(int argc,char **argv) {
    uint8_t config[147]={0};memcpy(config,"MCFG",4);strcpy((char *)config+4,"mock-user");
    strcpy((char *)config+37,"INVALID_TEST_ONLY");strcpy((char *)config+102,"mock-client");
    u32(config+143,mic_crc32(config,143));assert(mic_config_packet_valid(config,sizeof config));
    for(unsigned n=0;n<147;n++)assert(!mic_config_packet_valid(config,n));
    config[7]='\n';u32(config+143,mic_crc32(config,143));assert(!mic_config_packet_valid(config,147));
    config[7]='k';u32(config+143,mic_crc32(config,143));config[146]^=1;assert(!mic_config_packet_valid(config,147));
    uint8_t reply[21]={0};memcpy(reply,"MR01",4);u32(reply+4,7);u32(reply+8,8);reply[12]=5;memcpy(reply+16,"hello",5);
    assert(mic_reply_packet_valid(reply,21,7,8));assert(!mic_reply_packet_valid(reply,20,7,8));
    assert(!mic_reply_packet_valid(reply,21,9,8));assert(!mic_reply_packet_valid(reply,21,7,9));
    reply[16]='[';assert(!mic_reply_packet_valid(reply,21,7,8));reply[16]=0;assert(!mic_reply_packet_valid(reply,21,7,8));
    uint8_t data[512],packet[544];for(unsigned i=0;i<512;i++)data[i]=(uint8_t)i;
    mic_chunk_packet(packet,7,0,8,data);assert(!memcmp(packet,"MC01",4) && packet[30]==1 && packet[31]==1);
    if(argc>1){FILE *f=fopen(argv[1],"wb");assert(f);assert(fwrite(packet,1,sizeof packet,f)==sizeof packet);assert(!fclose(f));}
    mic_chunk_packet(packet,7,124,8,data);assert(packet[30]==2);
    puts("HOST_MIC_PROTOCOL_PASS: credentials framing, reply binding, unsafe text, actual C chunk vector; no devices");
    return 0;
}
