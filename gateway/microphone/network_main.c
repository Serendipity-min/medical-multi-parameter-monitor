#include "mic_api.h"
#include "mic_format.h"
#include "mic_protocol.h"
#include "network_transport.h"
#include "gateway_platform.h"
#include "tts_uart_port.h"
#include <stdio.h>
#include <string.h>

static TtsQueue speaker;
static uint32_t session, checksum, began, ack_before, done_before;
static unsigned phase, chunk, online, ready, reply_received;
static unsigned stopping_reported;
static uint8_t packet[544], config_packet[249];
static unsigned config_count, offline_requested;
static uint32_t config_at;

static void report(const char *event) {
    char b[288];
    snprintf(b,sizeof b,"MIC_NET %s session=%lu crc=%lu chunk=%u phase=%u ack=%lu done=%lu uart_errors=%lu uart_overflow=%lu stop_sent=%u stop_ack=%u stop_idle=%u stop_failed=%u\r\n",
             event,(unsigned long)session,(unsigned long)checksum,chunk,phase,
             (unsigned long)(speaker.ack_count-ack_before),(unsigned long)(speaker.done_count-done_before),
             (unsigned long)tts_uart_errors(),(unsigned long)tts_uart_overflow(),
             speaker.stop_sent,speaker.stop_ack,speaker.stop_idle,speaker.stop_failed);console(b);
}
static void speaker_poll(void) {
    /* 沿用VOICE-002顺序：先确认物理TX完成，再消费可能已排队的ACK。 */
    tts_poll(&speaker,g_uptime_ms);
    for(unsigned i=0;i<4;i++){int c=tts_uart_receive();if(c<0)break;tts_receive(&speaker,(uint8_t)c,g_uptime_ms);}
}

void mic_network_reply(const uint8_t *p,size_t n) {
    if((phase!=2 && phase!=3) || reply_received || !mic_reply_packet_valid(p,n,session,checksum) ||
       g_uptime_ms-began>=120000u)return;
    if(tts_submit(&speaker,p+16,n-16,session,g_uptime_ms)){reply_received=1;report("REPLY_ACCEPTED");}
    else report("REPLY_REJECTED");
}

static void send_chunk(void) {
    unsigned count=0;const int16_t *samples=mic_record_pcm(&count);
    if(count!=MIC_SAMPLES){phase=5;report("INCOMPLETE_RECORD");return;}
    mic_chunk_packet(packet,session,chunk,checksum,(const uint8_t *)samples+chunk*512u);
    if(!mic_network_send(packet,sizeof packet)){phase=5;report("UPLOAD_FAILED");return;}
    ++chunk;
    if(chunk==125){phase=3;report("UPLOAD_PUBACK_COMPLETE_NOT_ASR_PROOF");}
    else if(chunk%16==0)report("UPLOAD_PROGRESS");
}

int main(void) {
    if(!mic_initialize())for(;;){}
    platform_init();tts_uart_init();tts_init(&speaker,tts_uart_io());platform_set_poll(speaker_poll);
    console("MIC_NETWORK_BENCH_READY C_ONLY CAN_PINS_UNTOUCHED NO_FLASH_WRITE\r\n");
    for(;;) {
        speaker_poll();mic_record_poll();
        if(offline_requested && !online && !speaker.stopping){offline_requested=0;console("MIC_CONTROL_READY\r\n");}
        if(online && !ready && speaker.state==TTS_DONE){ready=1;console("MIC_VOICE_READY\r\n");}
        if(phase==1 && mic_record_state()==2) {
            unsigned count;const int16_t *samples=mic_record_pcm(&count);
            checksum=mic_crc32(samples,count*2);phase=2;report("CAPTURE_COMPLETE");
        } else if(phase==1 && mic_record_state()==3){phase=5;report("CAPTURE_FAILED");}
        if(phase==2)send_chunk();
        else if(online && ready && phase!=1) {
            if(!mic_network_poll()){online=ready=0;phase=5;report("NETWORK_FAILED");}
        }
        if(phase==3 && reply_received && speaker.state==TTS_DONE){phase=4;report("PLAYBACK_DONE_REQUIRES_OWNER_HEARING");}
        if((phase==1 || phase==2 || phase==3) && g_uptime_ms-began>=120000u){phase=5;tts_cancel(&speaker,g_uptime_ms);report("TURN_TIMEOUT");}
        if(speaker.state==TTS_ERROR || speaker.state==TTS_TIMEOUT) {
            if(phase!=5){phase=5;report("TTS_FAILED");}
        }
        if(phase==5 && speaker.stop_sent && speaker.stop_ack && speaker.stop_idle && !speaker.stopping && !stopping_reported) {
            stopping_reported=1;report("STOP_ACK_IDLE_CONFIRMED");
        }
        if(config_count && g_uptime_ms-config_at>=5000){config_count=0;memset(config_packet,0,sizeof config_packet);console("MIC_CONFIG_TIMEOUT\r\n");}
        int c=console_char();if(c<0)continue;
        unsigned previous=config_count;int framed=mic_config_byte(config_packet,&config_count,(uint8_t)c);
        if(framed) {
            if(!previous)config_at=g_uptime_ms;
            if(framed==2) {
                int ok=!online && mic_network_configure(config_packet,sizeof config_packet);
                memset(config_packet,0,sizeof config_packet);console(ok?"MIC_CONFIG_OK\r\n":"MIC_CONFIG_REJECTED\r\n");
            }
        } else if(c=='N' && !online) {
            if(mic_network_connect() && tts_enable(&speaker,true,true) && tts_bench_volume(&speaker,1,g_uptime_ms)) {
                online=1;ready=phase=0;console("MIC_MQTT_READY_WAIT_TTS_VOLUME_ACK\r\n");
            } else {phase=5;report("CONNECT_FAILED");}
        } else if(c=='R' && online && ready && (phase==0 || phase==4)) {
            session=mic_network_epoch();began=g_uptime_ms;phase=1;chunk=reply_received=0;
            ack_before=speaker.ack_count;done_before=speaker.done_count;mic_record_begin();report("RECORDING");
        } else if(c=='U' && online && ready && phase==0 && session && mic_record_state()==2) {
            /* 只重传本板尚在RAM的同一份原始录音，不重新采集或伪造采集时间。 */
            began=g_uptime_ms;phase=2;chunk=reply_received=0;
            ack_before=speaker.ack_count;done_before=speaker.done_count;report("REUPLOAD_EXISTING_RECORD");
        } else if(c=='D' && (phase==0 || phase==4 || phase==5))mic_record_export();
        else if(c=='I')console("MIC_NETWORK_ID PA4_PC10_PC12 TLS_PCM16_TTS_LOW_VOLUME WIFI_RAM_V4_STATE_SAFE\r\n");
        else if(c=='S') {
            if(mic_record_state()==1)mic_record_cancel();
            tts_cancel(&speaker,g_uptime_ms);phase=5;stopping_reported=0;offline_requested=1;
            if(online)mic_network_close();
            online=ready=0;report("OWNER_STOP_STOP_ACK_NOT_ASSUMED");
        }
    }
}
