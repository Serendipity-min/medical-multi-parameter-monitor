#include "unified_audio.h"
#ifdef MP_FIVE_FIELD01
#include "../b5/field01_window.h"
#endif
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
#ifdef MP_FIVE_APPLIANCE
static bool key_raw,key_stable;
static uint32_t key_changed_at;
static unsigned audio_bytes,audio_chunks;
static uint64_t voice_deadline;
static MicFactReply voice_fact;
#endif

static void phase(unsigned next) {state=next;report_due=1;}
void unified_audio_init(void) {
#ifdef MP_FIVE_APPLIANCE
    key_raw=key_stable=false;key_changed_at=g_uptime_ms;
    voice_deadline=0;
#endif
    tts_uart_init();tts_init(&speaker,tts_uart_io());
    if(!mic_initialize()){phase(UA_DISABLED);return;}
    if(!tts_enable(&speaker,true,true) || !tts_bench_volume(&speaker,1,g_uptime_ms))phase(UA_DISABLED);
    else phase(UA_IDLE);
}
void unified_audio_stop(void) {
#ifdef MP_FIVE_APPLIANCE
    voice_deadline=0;
#endif
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
#ifdef MP_FIVE_APPLIANCE
    if(state==UA_PLAYING && voice_deadline &&
       (gateway_epoch_milliseconds()>=voice_deadline || (!voice_fact.status &&
        !unified_audio_fact_current(voice_fact.node,voice_fact.stream,voice_fact.seq,voice_fact.epoch,voice_fact.boot)))) {
        console("FIVE FACT_EXPIRED_OR_CHANGED_STOP\r\n");unified_audio_stop();return;
    }
#endif
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
#ifdef MP_FIVE_APPLIANCE
    if(state!=UA_WAITING || (uint32_t)(g_uptime_ms-began)>=UA_TURN_BUDGET_MS)return;
    MicFactReply reply;
    if(!mic_fact_reply_valid(p,n,session,checksum,gateway_epoch_milliseconds(),&reply) ||
       (!reply.status && !unified_audio_fact_current(reply.node,reply.stream,reply.seq,reply.epoch,reply.boot)))return;
    /* 失效/补传分支只播本地固定拒答，不能借状态位夹带旧数字。 */
    static const uint8_t unavailable[]="当前读数不可用";
    const uint8_t *text=reply.status?unavailable:reply.text;
    unsigned length=reply.status?sizeof unavailable-1:reply.length;
    if(reply.status==MIC_REPLY_ADVICE) {
        static const uint8_t advice[]="请核对设备和数据来源。有疑问可咨询医护人员。";
        text=advice;
        length=sizeof advice-1;
    } else if(reply.status==MIC_REPLY_CLARIFY) {
        static const uint8_t clarify[]="请一次询问一项读数。";
        text=clarify;
        length=sizeof clarify-1;
    }
    if(tts_submit(&speaker,text,length,session,g_uptime_ms)) {
        voice_fact=reply;voice_fact.text=NULL;voice_deadline=reply.expires;phase(UA_PLAYING);
    }
#else
    if(state!=UA_WAITING || !mic_reply_packet_valid(p,n,session,checksum) ||
       (uint32_t)(g_uptime_ms-began)>=UA_TURN_BUDGET_MS)return;
    if(tts_submit(&speaker,p+16,n-16,session,g_uptime_ms))phase(UA_PLAYING);
#endif
}
void unified_audio_step(bool telemetry_idle) {
    unsigned count=0;const int16_t *pcm=mic_record_pcm(&count);
    if(state==UA_HASHING) {
#ifdef MP_FIVE_APPLIANCE
        if(count<MIC_RATE || count>MIC_SAMPLES){failed();return;}
        audio_bytes=count*2u;audio_chunks=(audio_bytes+511u)/512u;
        unsigned bytes=audio_bytes-hash_bytes;
#else
        if(count!=MIC_SAMPLES){failed();return;}
        unsigned bytes=64000u-hash_bytes;
#endif
        if(bytes>128)bytes=128;
        hash_state=mic_crc32_update(hash_state,(const uint8_t *)pcm+hash_bytes,bytes);hash_bytes+=bytes;
        if(hash_bytes==count*2u){checksum=hash_state^0xffffffffu;chunk=block_pending=0;phase(UA_UPLOADING);}
        return;
    }
    if(state!=UA_UPLOADING)return;
    if(block_pending) {
        int result=gateway_audio_result();
        if(result==GW_FAILED){failed();return;}
        if(result!=GW_COMPLETE)return;
        block_pending=0;++chunk;++acked_chunks;report_due=1;
        if(chunk==
#ifdef MP_FIVE_APPLIANCE
           audio_chunks
#else
           125u
#endif
          ){phase(UA_WAITING);return;}
    }
    /* 每次至多一块，主循环限制竞争发送间隔；始终复用同一个QoS1所有者。 */
    if(!telemetry_idle || !online || !gateway_audio_ready())return;
#ifdef MP_FIVE_APPLIANCE
    mic_chunk_packet_length(packet,session,chunk,checksum,(const uint8_t *)pcm+chunk*512u,audio_bytes);
#else
    mic_chunk_packet(packet,session,chunk,checksum,(const uint8_t *)pcm+chunk*512u);
#endif
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
#ifdef MP_FIVE_APPLIANCE
void unified_audio_key(bool pressed) {
    if(pressed!=key_raw){key_raw=pressed;key_changed_at=g_uptime_ms;return;}
    if(key_stable==key_raw || (uint32_t)(g_uptime_ms-key_changed_at)<30u)return;
    key_stable=key_raw;if(!key_stable)return;
    if(state==UA_IDLE){
#ifdef MP_FIVE_FIELD01
        static bool requested;
        if(requested)return;
        requested=true;
#endif
        unified_audio_command('R',false);return;
    }
    if(state!=UA_RECORDING)return;
    unsigned count;mic_record_pcm(&count);
#ifdef MP_FIVE_FIELD01
    if(count<FIELD01_MIN_SAMPLES)return;
#else
    if(count<MIC_RATE){console("FIVE RECORD_TOO_SHORT_CONTINUE\r\n");return;}
#endif
    mic_record_finish();
}
#endif
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
