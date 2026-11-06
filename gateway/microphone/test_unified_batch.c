/* 真实coreMQTT/adapter；核对缓冲、短写、失败及当前5+2+3额度的归属。 */
#include "../mqtt/tests/mocks/mock_esp.h"
#include "unified_audio.h"
#include "mic_protocol.h"
#include "../mqtt/src/gateway_transport.c"
#include <assert.h>
#include <stdio.h>

void unified_audio_reply(const uint8_t *p,size_t n){(void)p;(void)n;}
static void connect(void){
    config=&gateway_test_config;mock_connect();assert(gateway_audio_subscribe()==GW_PENDING);
    uint16_t id=(uint16_t)(((unsigned)mock_packet[2]<<8)|mock_packet[3]);
    uint8_t sub[]={0x90,3,(uint8_t)(id>>8),(uint8_t)id,1};mock_queue(sub,5);
    while(!gateway_audio_ready())assert(gateway_mqtt_progress()!=GW_FAILED);
}
static void flush(void){
    g_uptime_ms+=20;assert(gateway_mqtt_progress()!=GW_FAILED);assert(!network.queued);
}
static void ack(uint16_t id){uint8_t p[]={0x40,2,(uint8_t)(id>>8),(uint8_t)id};mock_queue(p,4);}
static void settle(void){for(unsigned i=0;i<100;i++)assert(gateway_mqtt_progress()!=GW_FAILED);}

int main(void){
    MpFrame scalar=mock_frame(MP_TEMP,0,false),wave=mock_frame(MP_ECG,250,false);
    uint8_t data[512]={0},packet[544];mic_chunk_packet(packet,1800000000u,0,7,data);
    for(unsigned short_write=0;short_write<2;short_write++){
        connect();mock_send_limit=short_write?17:0;mock_ack_mode=ACK_NONE;
        unsigned calls=mock_send_calls,publishes=mock_publish_count,q0=mqtt_metrics.q0_sent,q1=mqtt_metrics.q1_sent;
        assert(gateway_mqtt_begin(&wave)==GW_PENDING);uint16_t w=gateway_mqtt_ticket();
        assert(gateway_mqtt_begin(&scalar)==GW_PENDING);uint16_t s=gateway_mqtt_ticket();
        assert(gateway_audio_begin(packet)==GW_PENDING);uint16_t a=gateway_audio_ticket();
        assert(mock_send_calls==calls && mock_publish_count==publishes);
        assert(gateway_mqtt_ticket_result(w)==GW_PENDING && mqtt_metrics.q0_sent==q0 && mqtt_metrics.q1_sent==q1);
        flush();assert(mock_publish_count==publishes+3);
        assert(short_write || mock_send_calls==calls+1);
        assert(gateway_mqtt_ticket_result(w)==GW_COMPLETE && mqtt_metrics.q0_sent==q0+1 && mqtt_metrics.q1_sent==q1+1);
        assert(gateway_mqtt_ticket_result(s)==GW_PENDING && gateway_audio_ticket_result(a)==GW_PENDING);
        ack(a);ack(s);settle();assert(gateway_audio_ticket_result(a)==GW_COMPLETE && gateway_mqtt_ticket_result(s)==GW_COMPLETE);
    }
    enum { Q1=GATEWAY_TELEMETRY_SLOTS+GATEWAY_AUDIO_SLOTS };
    for(unsigned missing=0;missing<=Q1;missing++){
        connect();mock_ack_mode=ACK_NONE;uint16_t ids[Q1];
        for(unsigned i=0;i<GATEWAY_TELEMETRY_SLOTS;i++){
            int n=gateway_mqtt_begin(&scalar);if(n==GW_DEFERRED){flush();n=gateway_mqtt_begin(&scalar);}
            assert(n==GW_PENDING);ids[i]=gateway_mqtt_ticket();
        }
        assert(gateway_mqtt_slots_full());flush();
        for(unsigned i=0;i<GATEWAY_AUDIO_SLOTS;i++){
            int n=gateway_audio_begin(packet);if(n==GW_DEFERRED){flush();n=gateway_audio_begin(packet);}
            assert(n==GW_PENDING);ids[GATEWAY_TELEMETRY_SLOTS+i]=gateway_audio_ticket();
        }
        flush();assert(gateway_audio_begin(packet)==GW_DEFERRED && gateway_mqtt_begin(&scalar)==GW_DEFERRED);
        /* QoS1额度全满仍可提交波形；只有实际SEND成功后完成QoS0票据。 */
        assert(gateway_mqtt_begin(&wave)==GW_PENDING);uint16_t w=gateway_mqtt_ticket();
        assert(gateway_mqtt_ticket_result(w)==GW_PENDING);flush();assert(gateway_mqtt_ticket_result(w)==GW_COMPLETE);
        for(unsigned i=0;i<Q1;i++)for(unsigned k=0;k<i;k++)assert(ids[i]!=ids[k] && ids[i]!=w);
        for(unsigned i=Q1;i>0;i--)if(i-1!=missing)ack(ids[i-1]);
        if(missing==Q1){
            /* 同一已收缓冲中的ACK应一轮释放额度，不再逐轮被下一次发送/CRC隔开。 */
            assert(gateway_mqtt_progress()!=GW_FAILED);
            for(unsigned i=0;i<GATEWAY_TELEMETRY_SLOTS;i++)assert(telemetry[i].result==GW_COMPLETE);
            for(unsigned i=0;i<GATEWAY_AUDIO_SLOTS;i++)assert(audio[i].result==GW_COMPLETE);
        }
        settle();
        for(unsigned i=0;i<Q1;i++)assert((i<GATEWAY_TELEMETRY_SLOTS?gateway_mqtt_ticket_result(ids[i]):gateway_audio_ticket_result(ids[i]))==(i==missing?GW_PENDING:GW_COMPLETE));
        if(missing<Q1){
            uint32_t at=g_uptime_ms;unsigned failed=0;
            for(unsigned i=0;i<6000;i++)if(gateway_mqtt_progress()==GW_FAILED){failed=1;break;}
            assert(failed && g_uptime_ms-at<5000 && !gateway_mqtt_pending() && !gateway_audio_pending());
        }else assert(!gateway_mqtt_pending() && !gateway_audio_pending());
    }
    for(unsigned failure=0;failure<3;failure++){
        connect();unsigned q0=mqtt_metrics.q0_sent;
        assert(gateway_mqtt_begin(&wave)==GW_PENDING);uint16_t w=gateway_mqtt_ticket();
        if(failure==0)mock_send_error=1;
        if(failure==1)mock_send_zero=1;
        if(failure==2)mock_send_stall_ms=5001;
        g_uptime_ms+=20;assert(gateway_mqtt_progress()==GW_FAILED);
        assert(gateway_mqtt_ticket_result(w)==GW_FAILED && mqtt_metrics.q0_sent==q0 && !network.queued && !network.connected);
    }
    connect();mock_ack_mode=ACK_NONE;
    wave.count=100;for(unsigned i=0;i<100;i++)wave.values[i]=INT32_MIN;
    assert(gateway_mqtt_begin(&wave)==GW_PENDING);uint16_t w=gateway_mqtt_ticket();size_t bytes=network.queued;
    assert(gateway_mqtt_begin(&wave)==GW_DEFERRED && network.queued==bytes && network.flush_requested);
    assert(gateway_mqtt_progress()!=GW_FAILED && gateway_mqtt_ticket_result(w)==GW_COMPLETE);
    assert(gateway_mqtt_begin(&wave)==GW_PENDING);w=gateway_mqtt_ticket();flush();assert(gateway_mqtt_ticket_result(w)==GW_COMPLETE);
    connect();g_uptime_ms=UINT32_MAX-9u;
    assert(gateway_mqtt_begin(&scalar)==GW_PENDING);uint16_t s=gateway_mqtt_ticket();flush();settle();assert(gateway_mqtt_ticket_result(s)==GW_COMPLETE);
    puts("REAL_MQTT_BATCH_5_MEDICAL_2_WAVE_3_AUDIO_BUFFER_SHORT_WRITE_FAILURE_ACK_DEADLINE_WRAP_PASS hardware=NOT_RUN");
    return 0;
}
