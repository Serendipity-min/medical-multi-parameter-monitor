#include "unified_audio.h"
#include "mic_api.h"
#include "mic_format.h"
#include "mic_protocol.h"
#include "tts_uart_port.h"
#include "gateway_transport.h"
#include <stdio.h>

static TtsQueue speaker;
static unsigned state,chunk,hash_bytes,block_pending,online,report_due;
static uint32_t session,checksum,hash_state,began,failures,turns,acked_chunks,last_audio_at;
static uint8_t packet[544];

static void phase(unsigned next) {state=next;report_due=1;}
void unified_audio_init(void) {
    tts_uart_init();tts_init(&speaker,tts_uart_io());
    if(!mic_initialize()){phase(UA_DISABLED);return;}
    if(!tts_enable(&speaker,true,true) || !tts_bench_volume(&speaker,1,g_uptime_ms))phase(UA_DISABLED);
    else phase(UA_IDLE);
}
void unified_audio_stop(void) {
    if(mic_record_state()==1)mic_record_cancel();
    if(!speaker.stopping && !speaker.stop_failed)tts_cancel(&speaker,g_uptime_ms);
    block_pending=0;phase(UA_STOPPING);
}
static void failed(void) {failures++;unified_audio_stop();}
void unified_audio_network(bool connected) {
    online=connected;
    if(!connected && state>=UA_RECORDING && state<=UA_PLAYING)failed();
    report_due=1;
}
void unified_audio_local_poll(void) {
    tts_poll(&speaker,g_uptime_ms);
    for(unsigned i=0;i<4;i++) {
        int byte=tts_uart_receive();if(byte<0)break;
        tts_receive(&speaker,(uint8_t)byte,g_uptime_ms);
    }
    mic_record_poll();
    if(speaker.stop_failed){if(state!=UA_FAILED)phase(UA_FAILED);return;}
    if(state!=UA_FAILED && state!=UA_STOPPING && (speaker.state==TTS_ERROR || speaker.state==TTS_TIMEOUT ||
       tts_uart_errors() || tts_uart_overflow())){failed();return;}
    if(state==UA_RECORDING) {
        if(mic_record_state()==3){failed();return;}
        if(mic_record_state()==2){hash_bytes=0;hash_state=0xffffffffu;phase(UA_HASHING);}
    }
    if(state==UA_PLAYING && speaker.state==TTS_DONE)phase(UA_IDLE);
    if(state>=UA_RECORDING && state<=UA_PLAYING && (uint32_t)(g_uptime_ms-began)>=UA_TURN_BUDGET_MS)failed();
    if(state==UA_STOPPING && !speaker.stopping && speaker.stop_idle)
        phase(speaker.state==TTS_DISABLED?UA_IDLE:UA_FAILED);
}
void unified_audio_reply(const uint8_t *p,size_t n) {
    if(state!=UA_WAITING || !mic_reply_packet_valid(p,n,session,checksum) ||
       (uint32_t)(g_uptime_ms-began)>=UA_TURN_BUDGET_MS)return;
    if(tts_submit(&speaker,p+16,n-16,session,g_uptime_ms))phase(UA_PLAYING);
}
void unified_audio_step(bool telemetry_idle) {
    unsigned count=0;const int16_t *pcm=mic_record_pcm(&count);
    if(state==UA_HASHING) {
        if(count!=MIC_SAMPLES){failed();return;}
        unsigned bytes=64000u-hash_bytes;if(bytes>128)bytes=128;
        hash_state=mic_crc32_update(hash_state,(const uint8_t *)pcm+hash_bytes,bytes);hash_bytes+=bytes;
        if(hash_bytes==64000u){checksum=hash_state^0xffffffffu;chunk=block_pending=0;phase(UA_UPLOADING);}
        return;
    }
    if(state!=UA_UPLOADING)return;
    if(block_pending) {
        int result=gateway_audio_result();
        if(result==GW_FAILED){failed();return;}
        if(result!=GW_COMPLETE)return;
        block_pending=0;++chunk;++acked_chunks;report_due=1;
        if(chunk==125){phase(UA_WAITING);return;}
    }
    /* 每次至多一块，主循环限制竞争发送间隔；始终复用同一个QoS1所有者。 */
    if(!telemetry_idle || !online || !gateway_audio_ready())return;
    mic_chunk_packet(packet,session,chunk,checksum,(const uint8_t *)pcm+chunk*512u);
    int result=gateway_audio_begin(packet);
    if(result==GW_PENDING){block_pending=1;last_audio_at=g_uptime_ms;}
    else if(result==GW_FAILED)failed();
}
void unified_audio_command(int c,bool export_allowed) {
    if(c=='S'){unified_audio_stop();return;}
    if(c=='Q' || c=='I'){report_due=1;return;}
    if(c=='D') {
        if(export_allowed && mic_record_state()==2)mic_record_export();
        else console("UNI EXPORT_REJECTED_ACTIVE_MONITORING\r\n");
        return;
    }
    if(c!='R')return;
    if(state!=UA_IDLE || !online || !gateway_audio_ready() ||
       speaker.stopping || speaker.stop_failed ||
       (!speaker.enabled && !tts_enable(&speaker,true,true)) ||
       (speaker.state!=TTS_IDLE && speaker.state!=TTS_DONE)) {
        console("UNI RECORD_NOT_READY\r\n");return;
    }
    uint32_t now=(uint32_t)(gateway_epoch_milliseconds()/1000u);
    session=now>session?now:session+1u;began=g_uptime_ms;turns++;
    checksum=chunk=block_pending=0;console("UNI RECORDING\r\n");mic_record_begin();phase(UA_RECORDING);
}
bool unified_audio_quiet(void) {return state!=UA_RECORDING;}
bool unified_audio_send_due(void) {
    return state==UA_UPLOADING && !block_pending && (uint32_t)(g_uptime_ms-last_audio_at)>=250u;
}
void unified_audio_report(void) {
    if(!report_due || !unified_audio_quiet())return;
    report_due=0;MicDiag d;mic_diagnostics(&d);char line[512];
    snprintf(line,sizeof line,"UNI AUDIO phase=%u session=%lu crc=%lu chunk=%u online=%u subscribed=%u frames=%lu dma=%lu overrun=%lu decode=%lu turns=%lu acked=%lu failures=%lu tts_ack=%lu tts_done=%lu stop_ack=%u stop_query=%u stop_idle=%u stop_failed=%u tts_uart=%lu tts_overflow=%lu\r\n",
        state,(unsigned long)session,(unsigned long)checksum,chunk,online,(unsigned)gateway_audio_ready(),
        (unsigned long)d.frames,(unsigned long)d.dma_errors,(unsigned long)d.overruns,(unsigned long)d.decode_cycles_max,
        (unsigned long)turns,(unsigned long)acked_chunks,(unsigned long)failures,
        (unsigned long)speaker.ack_count,(unsigned long)speaker.done_count,
        speaker.stop_ack,speaker.stop_query_sent,speaker.stop_idle,speaker.stop_failed,
        (unsigned long)tts_uart_errors(),(unsigned long)tts_uart_overflow());
    console(line);
}
