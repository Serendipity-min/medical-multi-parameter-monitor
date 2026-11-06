#include "unified_audio.h"
#include "mic_api.h"
#include "mic_format.h"
#include "mic_protocol.h"
#include "tts_uart_port.h"
#include "gateway_transport.h"
#include <stdio.h>
#include <string.h>

static TtsQueue speaker;
static unsigned state,chunk,hash_bytes,block_pending,online,report_due;
static uint32_t session,checksum,hash_state,began,failures,turns,acked_chunks;
static uint8_t packet[544];
static unsigned pcm_bytes,total_chunks,sent_chunks;
static struct {uint16_t ticket;uint32_t sent_at;} pending_audio[GATEWAY_AUDIO_SLOTS];
static bool key_raw,key_stable;
static uint32_t key_changed_at;
static struct {
    uint32_t recorded,hashed,first,uploaded,reply,tts_ack,done,blocked_ms[4],hash_slices,hash_cycles_max;
    B5Latency eligible,send,puback,prompt,send_ok;
} timing;
static uint32_t ready_at,gate_at,tts_ack_before;
static unsigned gate_mask;

void unified_audio_wait(unsigned mask) {
    if(state!=UA_UPLOADING || sent_chunks>=total_chunks)return;
    uint32_t elapsed=g_uptime_ms-gate_at;
    for(unsigned i=0;i<4;i++)if(gate_mask&(1u<<i))timing.blocked_ms[i]+=elapsed;
    gate_at=g_uptime_ms;gate_mask=mask;
}

static void phase(unsigned next) {state=next;report_due=1;}
static void local_notice(const char *text) {
    if(!speaker.enabled && !tts_enable(&speaker,true,true))return;
    if(tts_submit(&speaker,(const uint8_t *)text,strlen(text),++session,g_uptime_ms))phase(UA_LOCAL_NOTICE);
}
void unified_audio_init(void) {
    key_raw=key_stable=false;key_changed_at=g_uptime_ms;
    block_pending=sent_chunks=0;memset(pending_audio,0,sizeof pending_audio);
    tts_uart_init();tts_init(&speaker,tts_uart_io());
    if(!mic_initialize()){phase(UA_DISABLED);return;}
    if(!tts_enable(&speaker,true,true) || !tts_bench_volume(&speaker,1,g_uptime_ms))phase(UA_DISABLED);
    else phase(UA_IDLE);
}
void unified_audio_stop(void) {
    if(mic_record_state()==1)mic_record_cancel();
    if(!speaker.stopping && !speaker.stop_failed)tts_cancel(&speaker,g_uptime_ms);
    phase(UA_STOPPING);
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
        if(mic_record_state()==2){
            unsigned count;mic_record_pcm(&count);
            if(count<MIC_RATE || count>MIC_SAMPLES){failed();return;}
            pcm_bytes=count*2u;total_chunks=(pcm_bytes+511u)/512u;
            timing.recorded=g_uptime_ms;
            hash_bytes=0;hash_state=0xffffffffu;phase(UA_HASHING);
        }
    }
    if(state==UA_PLAYING && !timing.tts_ack && speaker.ack_count>tts_ack_before)timing.tts_ack=g_uptime_ms;
    if(state==UA_PLAYING && speaker.state==TTS_DONE){timing.done=g_uptime_ms;phase(UA_IDLE);}
    if(state==UA_LOCAL_NOTICE && speaker.state==TTS_DONE)phase(UA_IDLE);
    if(state>=UA_RECORDING && state<=UA_PLAYING && (uint32_t)(g_uptime_ms-began)>=UA_TURN_BUDGET_MS)failed();
    if(state==UA_STOPPING && !speaker.stopping && speaker.stop_idle)
        phase(speaker.state==TTS_DISABLED?UA_IDLE:UA_FAILED);
}
void unified_audio_reply(const uint8_t *p,size_t n) {
    if(state!=UA_WAITING || !mic_reply_packet_valid(p,n,session,checksum) ||
       (uint32_t)(g_uptime_ms-began)>=UA_TURN_BUDGET_MS)return;
    if(tts_submit(&speaker,p+16,n-16,session,g_uptime_ms)){
        timing.reply=g_uptime_ms;tts_ack_before=speaker.ack_count;phase(UA_PLAYING);
    }
}
bool unified_audio_step(bool telemetry_idle) {
    for(unsigned i=0;i<GATEWAY_AUDIO_SLOTS;i++)if(pending_audio[i].ticket){
        int result=gateway_audio_ticket_result(pending_audio[i].ticket);
        if(result==GW_PENDING)continue;
        unified_audio_wait(0);
        if(block_pending==GATEWAY_AUDIO_SLOTS)ready_at=g_uptime_ms;
        pending_audio[i].ticket=0;block_pending--;
        if(result==GW_FAILED){if(state==UA_UPLOADING)failed();continue;}
        b5_latency_add(&timing.puback,g_uptime_ms-pending_audio[i].sent_at);
        ++chunk;++acked_chunks;
    }
    if(state==UA_UPLOADING && chunk==total_chunks){timing.uploaded=g_uptime_ms;phase(UA_WAITING);return false;}
    unsigned count=0;const int16_t *pcm=mic_record_pcm(&count);
    if(state==UA_HASHING) {
        unsigned bytes=pcm_bytes-hash_bytes;if(bytes>1024)bytes=1024;
#ifdef __arm__
        uint32_t hash_at=*(volatile uint32_t *)0xe0001004;
        __asm__ volatile("" : "+r"(hash_state) : "r"(hash_at) : "memory");
#endif
        hash_state=mic_crc32_update(hash_state,(const uint8_t *)pcm+hash_bytes,bytes);hash_bytes+=bytes;
        timing.hash_slices++;
#ifdef __arm__
        __asm__ volatile("" : "+r"(hash_state) : : "memory");
        uint32_t cycles=*(volatile uint32_t *)0xe0001004-hash_at;
        if(cycles>timing.hash_cycles_max)timing.hash_cycles_max=cycles;
#endif
        if(hash_bytes==pcm_bytes){
            checksum=hash_state^0xffffffffu;chunk=sent_chunks=0;
            timing.hashed=ready_at=gate_at=g_uptime_ms;gate_mask=0;phase(UA_UPLOADING);
        }
        return false;
    }
    if(state!=UA_UPLOADING)return false;
    /* 每次至多一块，主循环限制竞争发送间隔；始终复用同一个QoS1所有者。 */
    if(!telemetry_idle || !online || !gateway_audio_ready() || !unified_audio_send_due())return false;
    mic_chunk_packet_sized(packet,session,sent_chunks,pcm_bytes,checksum,(const uint8_t *)pcm+sent_chunks*512u);
    uint32_t sending_at=g_uptime_ms;
    int result=gateway_audio_begin(packet);
    if(result==GW_PENDING){
        unified_audio_wait(0);b5_latency_add(&timing.eligible,sending_at-ready_at);
        b5_latency_add(&timing.send,g_uptime_ms-sending_at);
        /* 批量发送的AT耗时由B5 LAT/IO统计；这里仅计入队，不能套用上一批的AT时延。 */
        if(!sent_chunks)timing.first=sending_at;
        unsigned slot=0;while(pending_audio[slot].ticket)slot++;
        pending_audio[slot].ticket=gateway_audio_ticket();pending_audio[slot].sent_at=g_uptime_ms;
        block_pending++;sent_chunks++;ready_at=gate_at=g_uptime_ms;
        return true;
    }
    else if(result==GW_DEFERRED)unified_audio_wait(UA_BLOCK_AT);
    else if(result==GW_FAILED)failed();
    return false;
}
void unified_audio_key(bool pressed) {
    if(pressed!=key_raw){key_raw=pressed;key_changed_at=g_uptime_ms;return;}
    if(key_stable==key_raw || (uint32_t)(g_uptime_ms-key_changed_at)<30u)return;
    key_stable=key_raw;
    if(!key_stable)return;
    if(state==UA_IDLE){
        if(!online || !gateway_audio_ready()){
            local_notice("网络未连接");
            console("UNI OFFLINE_LOCAL_NOTICE\r\n");
        }else unified_audio_command('R',false);
        return;
    }
    if(state!=UA_RECORDING)return;
    mic_record_finish();
    if(mic_record_state()==3){failed();return;}
    unsigned count;mic_record_pcm(&count);
    if(count<MIC_RATE){console("UNI SHORT_RECORD_CANCELLED\r\n");phase(UA_IDLE);local_notice("录音太短");}
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
    if(state!=UA_IDLE || block_pending || !online || !gateway_audio_ready() ||
       speaker.stopping || speaker.stop_failed ||
       (!speaker.enabled && !tts_enable(&speaker,true,true)) ||
       (speaker.state!=TTS_IDLE && speaker.state!=TTS_DONE)) {
        console("UNI RECORD_NOT_READY\r\n");return;
    }
    uint32_t now=(uint32_t)(gateway_epoch_milliseconds()/1000u);
    session=now>session?now:session+1u;began=g_uptime_ms;turns++;
    memset(&timing,0,sizeof timing);
    checksum=chunk=sent_chunks=0;console("UNI RECORDING\r\n");mic_record_begin();phase(UA_RECORDING);
}
bool unified_audio_quiet(void) {return state!=UA_RECORDING;}
bool unified_audio_send_due(void) {
    return state==UA_UPLOADING && sent_chunks<total_chunks && block_pending<GATEWAY_AUDIO_SLOTS;
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
    if(!turns)return;
    console("UNI METRIC_SCHEMA batch=1 first=enqueue_start stage1=enqueue stage2=enqueue_to_puback stage3_4=unused at=B5_LAT_IO\r\n");
    snprintf(line,sizeof line,"UNI TIME session=%lu record_end=%lu hash_end=%lu first=%lu upload_end=%lu reply=%lu tts_ack=%lu done=%lu medical_ms=%lu yield_ms=%lu at_ms=%lu gap_or_window_ms=%lu hash_slices=%lu hash_cycles_max=%lu\r\n",
        (unsigned long)session,(unsigned long)(timing.recorded?timing.recorded-began:0),
        (unsigned long)(timing.hashed?timing.hashed-began:0),(unsigned long)(timing.first?timing.first-began:0),
        (unsigned long)(timing.uploaded?timing.uploaded-began:0),(unsigned long)(timing.reply?timing.reply-began:0),
        (unsigned long)(timing.tts_ack?timing.tts_ack-began:0),(unsigned long)(timing.done?timing.done-began:0),
        (unsigned long)timing.blocked_ms[0],(unsigned long)timing.blocked_ms[1],
        (unsigned long)timing.blocked_ms[2],(unsigned long)timing.blocked_ms[3],
        (unsigned long)timing.hash_slices,(unsigned long)timing.hash_cycles_max);console(line);
    const B5Latency *lat[]={&timing.eligible,&timing.send,&timing.puback,&timing.prompt,&timing.send_ok};
    for(unsigned i=0;i<5;i++){
        const B5Latency *s=lat[i];
        snprintf(line,sizeof line,"UNI LAT stage=%u n=%lu p50_upper=%lu p95_upper=%lu max=%lu\r\n",i,
            (unsigned long)s->count,(unsigned long)b5_latency_percentile(s,50),
            (unsigned long)b5_latency_percentile(s,95),(unsigned long)s->max);console(line);
    }
}
