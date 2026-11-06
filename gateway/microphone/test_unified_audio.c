/* 测真实音频状态机/TTS/CRC/分块；仅DMA和MQTT端口为受控替身。 */
#include "unified_audio.h"
#include "mic_api.h"
#include "mic_format.h"
#include "mic_protocol.h"
#include "tts_uart_port.h"
#include "gateway_transport.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static unsigned checks,record_state,sample_count,exported,sent,ready=1;
static unsigned nbytes,tx_done,submissions,steps;static int result=GW_DEFERRED;
static uint8_t tx[1024],last_packet[544];static int16_t samples[MIC_SAMPLES];
static unsigned ack_due,idle_due;static uint32_t accepted_session,accepted_crc;
volatile uint32_t g_uptime_ms;
#define CHECK(x) do{if(!(x)){fprintf(stderr,"FAIL line=%d\n",__LINE__);exit(3);}checks++;}while(0)
int mic_initialize(void){return 1;}
void mic_record_begin(void){record_state=1;sample_count=0;}
unsigned mic_record_state(void){return record_state;}
void mic_record_poll(void){}
void mic_record_finish(void){if(record_state==1)record_state=2;}
void mic_record_cancel(void){record_state=3;}
const int16_t *mic_record_pcm(unsigned *n){*n=sample_count;return samples;}
void mic_record_export(void){exported++;}
void mic_diagnostics(MicDiag *d){*d=(MicDiag){sample_count,250,0,0,100};}
static int put(void *p,uint8_t c){(void)p;CHECK(nbytes<sizeof tx);tx[nbytes++]=c;return 1;}
static bool idle(void *p){(void)p;tx_done=nbytes;return true;}
static void abort_tx(void *p){(void)p;}
void tts_uart_init(void){}
TtsIo tts_uart_io(void){return (TtsIo){NULL,put,idle,abort_tx};}
int tts_uart_receive(void){if(ack_due){ack_due=0;return 0x41;}if(idle_due){idle_due=0;return 0x4f;}return -1;}
uint32_t tts_uart_errors(void){return 0;}
uint32_t tts_uart_overflow(void){return 0;}
void console(const char *s){(void)s;}
void platform_last_send_timing(uint32_t *prompt,uint32_t *send_ok){*prompt=*send_ok=0;}
uint64_t gateway_epoch_milliseconds(void){return 1800000000000ULL+g_uptime_ms;}
int gateway_mqtt_pending(void){return result==GW_PENDING;}
int gateway_audio_ready(void){return (int)ready;}
int gateway_audio_begin(const uint8_t p[544]) {
    CHECK(!gateway_mqtt_pending());memcpy(last_packet,p,544);submissions++;result=GW_PENDING;return GW_PENDING;
}
uint16_t gateway_audio_ticket(void){return (uint16_t)submissions;}
int gateway_audio_ticket_result(uint16_t id){CHECK(id==submissions);return result;}
static void tick(void){g_uptime_ms++;unified_audio_local_poll();}
static void drain(void){for(unsigned i=0;i<250;i++)tick();}
static void prepare(void) {
    ready=1;result=GW_DEFERRED;nbytes=tx_done=0;ack_due=idle_due=0;
    unified_audio_init();drain();CHECK(nbytes==9);ack_due=1;tick();unified_audio_network(true);
}
int main(void) {
    for(unsigned i=0;i<MIC_SAMPLES;i++)samples[i]=(int16_t)(i*13u+7u);
    uint32_t whole=mic_crc32(samples,sizeof samples),part=0xffffffffu;
    for(unsigned i=0;i<sizeof samples;i+=128)part=mic_crc32_update(part,(uint8_t *)samples+i,128);
    CHECK((part^0xffffffffu)==whole && mic_crc32("123456789",9)==0xcbf43926u);
    prepare();result=GW_PENDING;unified_audio_command('R',false);CHECK(record_state==1);result=GW_DEFERRED;
    CHECK(!unified_audio_quiet());
    record_state=2;sample_count=MIC_SAMPLES;tick();
    CHECK(unified_audio_quiet());
    for(steps=0;steps<500;steps++){unified_audio_step(false);tick();CHECK(submissions==0);}
    unified_audio_step(false);CHECK(submissions==0);
    unsigned previous=nbytes;uint8_t early[19]={0};memcpy(early,"MR01",4);unified_audio_reply(early,19);CHECK(nbytes==previous);
    unified_audio_command('D',false);CHECK(!exported);
    CHECK(unified_audio_send_due());
    for(sent=0;sent<125;sent++) {
        unified_audio_step(true);CHECK(submissions==sent+1 && result==GW_PENDING);
        CHECK(unified_audio_send_due()==(sent<124));
        uint16_t seq;memcpy(&seq,last_packet+8,2);CHECK(seq==sent);
        CHECK(!memcmp(last_packet+32,(uint8_t *)samples+512*sent,512));
        memcpy(&accepted_session,last_packet+4,4);memcpy(&accepted_crc,last_packet+20,4);CHECK(accepted_crc==whole);
        if(!sent) {
            uint8_t premature[19]={0};memcpy(premature,"MR01",4);
            memcpy(premature+4,&accepted_session,4);memcpy(premature+8,&whole,4);
            premature[12]=3;memcpy(premature+16,"OK!",3);
            unified_audio_reply(premature,19);CHECK(nbytes==previous);
        }
        unsigned before=submissions;for(unsigned i=0;i<10;i++){unified_audio_step(false);tick();}CHECK(submissions==before);
        result=GW_COMPLETE;unified_audio_step(false);
        CHECK(unified_audio_send_due()==(sent<124));
        if(sent<124){for(unsigned i=0;i<240;i++)tick();CHECK(unified_audio_send_due());}
    }
    CHECK(submissions==125);
    uint8_t reply[19]={0};memcpy(reply,"MR01",4);memcpy(reply+4,&accepted_session,4);memcpy(reply+8,&whole,4);
    reply[12]=3;memcpy(reply+16,"OK!",3);
    reply[4]^=1;unified_audio_reply(reply,19);CHECK(nbytes==previous);reply[4]^=1;
    unified_audio_reply(reply,19);drain();CHECK(nbytes==previous+8 && !memcmp(tx+previous,(uint8_t[]){0xfd,0,5,1,4,'O','K','!'},8));
    ack_due=1;tick();unified_audio_network(false);drain();ack_due=1;tick();drain();idle_due=1;tick();tick();
    CHECK(!memcmp(tx+nbytes-8,(uint8_t[]){0xfd,0,1,2,0xfd,0,1,0x21},8));
    unified_audio_command('D',true);CHECK(exported==1);
    unsigned total=submissions;unified_audio_step(true);CHECK(submissions==total);
    prepare();unified_audio_command('R',false);CHECK(record_state==1);
    g_uptime_ms+=UA_TURN_BUDGET_MS-1u;unified_audio_local_poll();CHECK(record_state==1);
    g_uptime_ms++;unified_audio_local_poll();CHECK(record_state==3);
    /* 真实双CAN慢传需等待ASR；旧240秒整轮在有效回包前已经撤销会话。 */
    prepare();unified_audio_command('R',false);uint32_t turn_start=g_uptime_ms;
    record_state=2;sample_count=MIC_SAMPLES;tick();
    for(unsigned i=0;i<500;i++){unified_audio_step(false);tick();}
    for(unsigned i=0;i<125;i++){
        unified_audio_step(true);CHECK(result==GW_PENDING);
        memcpy(&accepted_session,last_packet+4,4);memcpy(&accepted_crc,last_packet+20,4);
        result=GW_COMPLETE;unified_audio_step(false);
    }
    g_uptime_ms=turn_start+270000u;unified_audio_local_poll();
    memcpy(reply+4,&accepted_session,4);memcpy(reply+8,&accepted_crc,4);
    previous=nbytes;unified_audio_reply(reply,sizeof reply);drain();CHECK(nbytes==previous+8);
    /* 同一真实状态机：消抖、极短取消、1.5秒提前结束及上传中按键不重入。 */
    prepare();record_state=0;unsigned key_before=submissions;
    unified_audio_key(true);g_uptime_ms+=29;unified_audio_key(true);CHECK(record_state==0);
    g_uptime_ms++;unified_audio_key(true);CHECK(record_state==1);
    unified_audio_key(false);g_uptime_ms+=30;unified_audio_key(false);
    sample_count=8000;unified_audio_key(true);g_uptime_ms+=30;unified_audio_key(true);
    CHECK(record_state==2 && submissions==key_before);
    drain();ack_due=idle_due=1;tick();
    unified_audio_key(false);g_uptime_ms+=30;unified_audio_key(false);
    unified_audio_key(true);g_uptime_ms+=30;unified_audio_key(true);CHECK(record_state==1);
    unified_audio_key(false);g_uptime_ms+=30;unified_audio_key(false);
    sample_count=24000;unified_audio_key(true);g_uptime_ms+=30;unified_audio_key(true);tick();
    for(unsigned i=0;i<375;i++){unified_audio_step(false);tick();}
    unified_audio_step(true);CHECK(submissions==key_before+1 && !memcmp(last_packet,"MC02",4));
    CHECK(last_packet[10]==94 && last_packet[11]==0);
    unified_audio_key(false);g_uptime_ms+=30;unified_audio_key(false);
    unified_audio_key(true);g_uptime_ms+=30;unified_audio_key(true);
    CHECK(record_state==2 && submissions==key_before+1);
    prepare();record_state=0;unified_audio_network(false);unsigned offline_before=submissions,voice_before=nbytes;
    unified_audio_key(true);g_uptime_ms+=30;unified_audio_key(true);drain();
    CHECK(record_state==0 && submissions==offline_before && nbytes>voice_before);
    ack_due=idle_due=1;tick();unified_audio_network(true);
    unified_audio_key(false);g_uptime_ms+=30;unified_audio_key(false);
    unified_audio_key(true);g_uptime_ms+=30;unified_audio_key(true);CHECK(record_state==1);
    printf("HOST_UNIFIED_AUDIO_PASS checks=%u chunks=%u hash_poll_calls=%u crc=%lu hardware=NOT_RUN\n",checks,submissions,steps,(unsigned long)whole);
    return 0;
}
