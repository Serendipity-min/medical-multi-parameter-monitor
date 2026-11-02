#include "mic_protocol.h"
#include "mic_format.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>
static void u32(uint8_t *p,uint32_t n){for(unsigned i=0;i<4;i++)p[i]=(uint8_t)(n>>(8*i));}
int main(int argc,char **argv) {
    uint8_t config[249]={0};memcpy(config,"MCF3",4);strcpy((char *)config+4,"mock-user");
    strcpy((char *)config+37,"INVALID_TEST_ONLY");strcpy((char *)config+102,"mock-client");
    strcpy((char *)config+143,"INVALID TEST AP");strcpy((char *)config+176,"INVALID_TEST_ONLY");
    u32(config+241,1790000000u);u32(config+245,mic_crc32(config,245));assert(mic_config_packet_valid(config,sizeof config));
    uint8_t received[249]={0};unsigned position=0;
    assert(mic_config_byte(received,&position,'C')==1);
    for(unsigned i=0;i<sizeof config;i++)assert(mic_config_byte(received,&position,config[i])==(i==sizeof config-1?2:1));
    assert(!position && !memcmp(received,config,sizeof config));
    assert(mic_config_byte(received,&position,'S')==0);
    assert(mic_config_byte(received,&position,'C')==1);
    for(unsigned i=0;i<sizeof config;i++)assert(mic_config_byte(received,&position,"SNRDC"[i%5])==(i==sizeof config-1?2:1));
    assert(!position);
    for(unsigned n=0;n<249;n++)assert(!mic_config_packet_valid(config,n));
    u32(config+241,1);u32(config+245,mic_crc32(config,245));assert(!mic_config_packet_valid(config,sizeof config));u32(config+241,1790000000u);
    config[7]='\n';u32(config+245,mic_crc32(config,245));assert(!mic_config_packet_valid(config,sizeof config));config[7]='k';
    for(unsigned i=0;i<4;i++) {
        config[143]=(uint8_t[]){'"','\\','\n',0}[i];u32(config+245,mic_crc32(config,245));
        assert(!mic_config_packet_valid(config,sizeof config));
    }
    memset(config+143,'x',33);u32(config+245,mic_crc32(config,245));assert(!mic_config_packet_valid(config,sizeof config));
    memset(config+143,0,33);strcpy((char *)config+143,"INVALID TEST AP");config[176]=0;
    u32(config+245,mic_crc32(config,245));assert(!mic_config_packet_valid(config,sizeof config));
    strcpy((char *)config+176,"INVALID_TEST_ONLY");u32(config+245,mic_crc32(config,245));config[248]^=1;assert(!mic_config_packet_valid(config,sizeof config));
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
