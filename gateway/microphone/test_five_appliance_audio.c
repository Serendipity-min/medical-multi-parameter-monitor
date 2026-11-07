/* 复用旧真实音频/TTS夹具的端口替身；测试新增KEY1与短块，而非复制状态机。 */
#define main legacy_audio_main
#include "test_unified_audio.c"
#undef main

static unsigned finishes;
static bool fact_current=true;
void mic_record_finish(void){finishes++;record_state=2;}
bool unified_audio_fact_current(unsigned node,unsigned stream,uint32_t seq,uint32_t epoch,uint32_t boot){
    return fact_current && node==4 && stream==8 && seq==1 && epoch==123 && boot==1;
}
static void key(bool down){unified_audio_key(down);for(unsigned i=0;i<30;i++)tick();unified_audio_key(down);}
static void put32(uint8_t *p,uint32_t x){memcpy(p,&x,4);}
static void put64(uint8_t *p,uint64_t x){memcpy(p,&x,8);}
static unsigned reply(uint8_t *p,unsigned status){
    memset(p,0,MIC_FACT_REPLY_MAX);memcpy(p,"MR02",4);put32(p+4,accepted_session);put32(p+8,accepted_crc);
    uint64_t now=gateway_epoch_milliseconds();put64(p+12,now);put64(p+20,now+1000);put64(p+28,now-100);
    put32(p+36,1);put32(p+40,123);put32(p+44,1);p[48]=4;p[49]=8;p[50]=(uint8_t)status;p[51]=1;
    memcpy(p+52,"GW-B5-001",9);memset(p+64,7,16);
    static const char text[]="MOCK object temperature 24.5 C";
    p[80]=sizeof text-1;memcpy(p+82,text,sizeof text-1);return 82+sizeof text-1;
}
static void full_record(void){
    prepare();submissions=0;unified_audio_command('R',false);CHECK(record_state==1);
    sample_count=MIC_SAMPLES;record_state=2;tick();
    for(unsigned i=0;i<500;i++){unified_audio_step(false);tick();}
    for(unsigned i=0;i<125;i++){
        for(unsigned j=0;j<250;j++)tick();
        unified_audio_step(true);CHECK(result==GW_PENDING && last_packet[10]==125);
        memcpy(&accepted_session,last_packet+4,4);memcpy(&accepted_crc,last_packet+20,4);
        result=GW_COMPLETE;unified_audio_step(false);
    }
    CHECK(submissions==125 && accepted_crc==mic_crc32(samples,64000));
}
int main(int argc,char **argv){
    for(unsigned i=0;i<MIC_SAMPLES;i++)samples[i]=(int16_t)(i*13u+7u);
    prepare();record_state=sample_count=0;
    unified_audio_network(false);key(true);CHECK(record_state==0);key(false);unified_audio_network(true);
    unified_audio_key(true);for(unsigned i=0;i<10;i++)tick();unified_audio_key(false);for(unsigned i=0;i<40;i++)tick();unified_audio_key(false);
    CHECK(record_state==0);key(true);CHECK(record_state==1);
    for(unsigned i=0;i<80;i++){tick();unified_audio_key(true);}CHECK(record_state==1 && finishes==0);
    sample_count=8000;key(false);key(true);CHECK(!finishes && record_state==1);
    key(false);sample_count=16160;key(true);CHECK(finishes==1 && record_state==2);tick();
    for(unsigned i=0;i<400;i++){unified_audio_step(false);tick();}
    FILE *wire=argc>1?fopen(argv[1],"wb"):NULL;
    for(unsigned i=0;i<64;i++){
        for(unsigned j=0;j<250;j++)tick();
        unified_audio_step(true);CHECK(result==GW_PENDING);
        unsigned length=last_packet[28]|((unsigned)last_packet[29]<<8);CHECK(length==(i==63?64:512));
        CHECK(!memcmp(last_packet+32,(uint8_t *)samples+512*i,length));
        for(unsigned j=length;j<512;j++)CHECK(last_packet[32+j]==0);
        CHECK(last_packet[10]==64 && last_packet[11]==0);
        memcpy(&accepted_session,last_packet+4,4);memcpy(&accepted_crc,last_packet+20,4);
        if(wire)CHECK(fwrite(last_packet,544,1,wire)==1);
        result=GW_COMPLETE;unified_audio_step(false);
    }
    if(wire)fclose(wire);
    CHECK(submissions==64 && accepted_crc==mic_crc32(samples,32320));
    uint8_t packet[MIC_FACT_REPLY_MAX];unsigned length=reply(packet,0),before=nbytes;
    packet[4]^=1;unified_audio_reply(packet,length);CHECK(nbytes==before);packet[4]^=1;
    unified_audio_reply(packet,length);drain();CHECK(nbytes>before);ack_due=1;tick();idle_due=1;tick();tick();
    CHECK(unified_audio_send_due()==false);
    full_record();length=reply(packet,2);before=nbytes;
    unified_audio_reply(packet,length);drain();
    static const char unavailable[]="当前读数不可用";
    CHECK(nbytes==before+5+sizeof unavailable-1 && !memcmp(tx+before+5,unavailable,sizeof unavailable-1));
    ack_due=1;tick();idle_due=1;tick();tick();
    full_record();length=reply(packet,0);before=nbytes;fact_current=false;
    unified_audio_reply(packet,length);drain();CHECK(nbytes==before);fact_current=true;
    unified_audio_reply(packet,length);drain();ack_due=1;tick();g_uptime_ms+=1000;tick();drain();
    ack_due=1;tick();drain();idle_due=1;tick();tick();
    CHECK(!memcmp(tx+nbytes-8,(uint8_t[]){0xfd,0,1,2,0xfd,0,1,0x21},8));
    prepare();unified_audio_command('R',false);unified_audio_command('S',false);CHECK(record_state==3);
    printf("HOST_FIVE_KEY_AUDIO_PASS checks=%u short_samples=16160 short_chunks=64 full_samples=32000 full_chunks=125 refusal_fixed=1 expired_STOP_QUERY_IDLE=1 hardware=NOT_RUN\n",checks);
    return 0;
}
