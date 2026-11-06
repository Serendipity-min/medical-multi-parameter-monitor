/* 真实Router/coreMQTT/音频状态机同窗；只替换ESP、DMA、TTS物理端口。 */
#include "../mqtt/tests/mocks/mock_esp.h"
#include "../b5/egress.h"
#include "unified_audio.c"
#include <stdlib.h>
#include <string.h>

extern void (*mock_poll_callback)(void);
extern void (*mock_published)(const unsigned char *,size_t);
extern unsigned mock_send_base_ms,mock_emulate_uart,mock_model_poll_divisor;
static MpRouter r;
static unsigned checks,abc,payload_stress,produced,record_at,record_state,reply_sent,started;
static unsigned delivered[3][MP_STREAMS],last_seq[3][MP_STREAMS],gaps,scalar_skips,stale,audio_blocks;
static uint32_t origin,seqs[3][MP_STREAMS],audio_session,audio_crc,first_audio_at,last_audio_at,voice_done_at;
static uint32_t last_seen_at[3][MP_STREAMS],max_gap[3][MP_STREAMS];
static uint64_t last_source_timestamp[3][MP_STREAMS];
static unsigned ppg_segments,ppg_samples;
static unsigned hash_slice_ms,scalar_source_age_ms,latest_stale_ticks,max_latest_age_ms;
static uint64_t epoch_origin;
static int16_t source[MIC_SAMPLES];
static uint8_t received[64000];
#define CHECK(x) do{if(!(x)){fprintf(stderr,"FAIL line=%d t=%lu blocks=%u live=%u\n",__LINE__,(unsigned long)(g_uptime_ms-origin),audio_blocks,r.ln);exit(3);}checks++;}while(0)

int b5_network_stopped(void){return 0;}
int mic_initialize(void){return 1;}
void mic_record_begin(void){record_state=1;record_at=g_uptime_ms;}
unsigned mic_record_state(void){return record_state;}
void mic_record_poll(void){if(record_state==1 && g_uptime_ms-record_at>=2000)record_state=2;}
void mic_record_cancel(void){record_state=3;}
void mic_record_finish(void){if(record_state==1)record_state=2;}
const int16_t *mic_record_pcm(unsigned *n){*n=record_state==2?MIC_SAMPLES:0;return source;}
void mic_record_export(void){}
void mic_diagnostics(MicDiag *d){*d=(MicDiag){record_state==2?MIC_SAMPLES:0,200,0,0,0};}
static int tx(void *p,uint8_t b){(void)p;(void)b;return 1;}
static bool idle(void *p){(void)p;return true;}
static void abort_tx(void *p){(void)p;}
void tts_uart_init(void){}
TtsIo tts_uart_io(void){return (TtsIo){NULL,tx,idle,abort_tx};}
uint32_t tts_uart_errors(void){return 0;}
uint32_t tts_uart_overflow(void){return 0;}
int tts_uart_receive(void){
    if(speaker.stopping){
        if(speaker.stop_sent && !speaker.stop_ack)return 0x41;
        if(speaker.stop_query_sent && !speaker.stop_idle)return 0x4f;
    }else{
        if(speaker.state==TTS_SENDING && speaker.tx_done)return 0x41;
        if(speaker.state==TTS_ACCEPTED)return 0x4f;
    }
    return -1;
}
static void put(unsigned node,unsigned stream,unsigned rate,unsigned count,unsigned tick){
    MpFrame f=mock_frame((MpStream)stream,(uint16_t)rate,false);f.node=(uint8_t)node;
    f.seq=++seqs[node][stream];f.count=(uint16_t)count;f.timestamp=epoch_origin+tick;
    if(stream==MP_HR || stream==MP_RR || stream==MP_TEMP || stream==MP_SPO2 || stream==MP_PR)f.timestamp-=scalar_source_age_ms;
    for(unsigned i=0;i<count;i++)f.values[i]=rate?(payload_stress?(i%2?5000000:-5000000):(int32_t)(100+i%10)):(stream==MP_HR?6000:stream==MP_TEMP?2560:stream==MP_SPO2?9700:7200);
    if(stream==MP_NIBP){f.values[0]=1200;f.values[1]=800;}
    mp_router_put(&r,&f);
}
static void poll(void){
    while(produced<g_uptime_ms-origin){
        produced++;
        if(produced%400==0)put(2,MP_ECG,250,100,produced);
        if(produced%1000==0){
            put(2,MP_RESP,50,50,produced);put(2,MP_HR,0,1,produced);
            put(2,MP_RR,0,1,produced);put(2,MP_TEMP,0,1,produced);
            if(abc){put(1,MP_SPO2,0,1,produced);put(1,MP_PR,0,1,produced);if(ppg_segments){put(1,MP_PPG,50,25,produced-500);put(1,MP_PPG,50,25,produced);}else put(1,MP_PPG,50,50,produced);}
        }
        if(produced%5000==0){put(2,MP_NODE_STATUS,0,1,produced);put(0,MP_GATEWAY_STATUS,0,1,produced);if(abc)put(1,MP_NODE_STATUS,0,1,produced);}
        if(abc && produced==60000)put(1,MP_NIBP,0,2,produced);
        if(produced>=45000 && produced<345000){
            uint64_t last=last_source_timestamp[2][MP_TEMP],now=epoch_origin+produced;
            if(last && now>last){unsigned age=(unsigned)(now-last);if(age>max_latest_age_ms)max_latest_age_ms=age;if(age>5000)latest_stale_ticks++;}
        }
    }
    unified_audio_local_poll();
}
static size_t header(const uint8_t *p){size_t at=1;while(p[at++]&128u){}return at;}
static void published(const uint8_t *p,size_t n){
    size_t at=header(p),length=((size_t)p[at]<<8)|p[at+1];const uint8_t *topic=p+at+2;
    size_t body_at=at+2+length+((p[0]&6u)==2u?2:0);CHECK(body_at<=n);
    const uint8_t *body=p+body_at;size_t size=n-body_at;
    if(length==13 && !memcmp(topic,"mpm/mic/v1/in",13)){
        CHECK(size==544 && audio_blocks<125);unsigned order=body[8]|((unsigned)body[9]<<8);
        CHECK(order==audio_blocks && !memcmp(body,"MC01",4));
        memcpy(&audio_session,body+4,4);memcpy(&audio_crc,body+20,4);
        if(!audio_blocks)first_audio_at=g_uptime_ms;
        memcpy(received+audio_blocks*512,body+32,512);audio_blocks++;last_audio_at=g_uptime_ms;
        return;
    }
    char text[2048];CHECK(size<sizeof text);memcpy(text,body,size);text[size]=0;
    const char *t=strstr(text,"\"timestamp\":");CHECK(t);uint64_t timestamp=strtoull(t+12,NULL,10);
    const char *s=strstr(text,"\"seq\":");CHECK(s);unsigned sequence=(unsigned)strtoul(s+6,NULL,10);
    unsigned elapsed=(unsigned)(timestamp-epoch_origin);
    for(unsigned node=0;node<3;node++)for(unsigned stream=0;stream<MP_STREAMS;stream++){
        if((node==0)!=(stream==MP_GATEWAY_STATUS))continue;
        MpFrame f=mock_frame((MpStream)stream,0,false);f.node=(uint8_t)node;char expected[120];
        if(!mp_topic(&f,expected,sizeof expected) || strlen(expected)!=length || memcmp(topic,expected,length))continue;
        if(stream==MP_NODE_STATUS || stream==MP_GATEWAY_STATUS)return;
        last_source_timestamp[node][stream]=timestamp;
        if(elapsed<45000 || elapsed>=345000)return;
        if(stream==MP_ECG || stream==MP_RESP || stream==MP_PPG){
            const char *samples=strstr(text,"\"samples\":[");CHECK(samples);samples+=11;
            unsigned count=stream==MP_ECG?100:stream==MP_PPG && ppg_segments?25:50;
            if(stream==MP_PPG)ppg_samples+=count;
            int scale=stream==MP_ECG?1000:1000000;
            for(unsigned i=0;i<count;i++){
                char *end;double actual=strtod(samples,&end)*scale;
                int expected=payload_stress?(i%2?5000000:-5000000):(int)(100+i%10);
                CHECK(end!=samples && actual-expected<0.01 && actual-expected>-0.01);
                CHECK(*end==(i+1==count?']':','));samples=end+1;
            }
        }
        if(stream==MP_NIBP)CHECK(strstr(text,"\"value\":[120.0,80.0]"));
        if(last_seq[node][stream] && sequence!=last_seq[node][stream]+1){
            if(stream==MP_ECG || stream==MP_RESP || stream==MP_PPG)gaps++;
            else scalar_skips+=sequence-last_seq[node][stream]-1;
        }
        if(last_seen_at[node][stream]){uint32_t gap=g_uptime_ms-last_seen_at[node][stream];if(gap>max_gap[node][stream])max_gap[node][stream]=gap;}
        last_seen_at[node][stream]=g_uptime_ms;
        last_seq[node][stream]=sequence;delivered[node][stream]++;
        if(gateway_epoch_milliseconds()-timestamp>5000)stale++;
        return;
    }
}
int main(int argc,char **argv){
    abc=argc>1;payload_stress=argc>2 && !strcmp(argv[2],"large-payload-300ms-ACK");
    for(unsigned i=0;i<MIC_SAMPLES;i++)source[i]=(int16_t)(i*13u+7u);
    mock_connect();CHECK(gateway_audio_subscribe()==GW_PENDING);
    uint16_t id=(uint16_t)(((unsigned)mock_packet[2]<<8)|mock_packet[3]);uint8_t sub[]={0x90,3,(uint8_t)(id>>8),(uint8_t)id,1};mock_queue(sub,5);
    while(!gateway_audio_ready())CHECK(gateway_mqtt_progress()!=GW_FAILED);
    mp_router_init(&r);mp_router_online(&r,true);unified_audio_init();unified_audio_network(true);
    origin=g_uptime_ms;epoch_origin=gateway_epoch_milliseconds();mock_poll_callback=poll;mock_published=published;
    mock_delay_ms=payload_stress?300:200;mock_send_base_ms=payload_stress?25:15;mock_emulate_uart=1;mock_model_poll_divisor=10;
    if(argc>3)mock_send_base_ms=(unsigned)strtoul(argv[3],NULL,10);
    if(argc>4)mock_delay_ms=(int)strtoul(argv[4],NULL,10);
    if(argc>5)hash_slice_ms=(unsigned)strtoul(argv[5],NULL,10);
    if(argc>6)scalar_source_age_ms=(unsigned)strtoul(argv[6],NULL,10);
    ppg_segments=argc>7;
    B5Publisher publisher={0};unsigned result=0;
    while(g_uptime_ms-origin<360000){
        platform_poll();
        if(!started && produced>=45000){unified_audio_command('R',false);CHECK(record_state==1);started=1;}
        CHECK(b5_egress_step(&r,&publisher,true));
        unsigned hashing=state==UA_HASHING;
        unified_audio_step(false);
        if(hashing && hash_slice_ms){g_uptime_ms+=hash_slice_ms;platform_poll();}
        if(audio_blocks==125 && !reply_sent && g_uptime_ms-last_audio_at>=36500){
            uint8_t message[39]={0x32,37,0,14};memcpy(message+4,"mpm/mic/v1/out",14);message[18]=0x6a;message[19]=0x51;
            memcpy(message+20,"MR01",4);memcpy(message+24,&audio_session,4);memcpy(message+28,&audio_crc,4);message[32]=3;memcpy(message+36,"OK!",3);
            mock_queue(message,sizeof message);reply_sent=1;
        }
        if(speaker.done_count && !voice_done_at)voice_done_at=g_uptime_ms-origin-45000;
        if(failures)fprintf(stderr,"FAIL_DETAIL phase=%u sent=%u acked=%u sends=%u publishes=%u ECG=%u RESP=%u PPG=%u overflow=%lu expired=%lu medical_ms=%lu\n",state,sent_chunks,chunk,mock_send_calls,mock_publish_count,delivered[2][MP_ECG],delivered[2][MP_RESP],delivered[1][MP_PPG],(unsigned long)r.live_overflow,(unsigned long)r.expired,(unsigned long)timing.blocked_ms[0]);
        CHECK(!failures && !speaker.stop_failed);
        result=publisher.failed;
    }
    fprintf(stderr,"COUNTS ECG=%u RESP=%u PPG=%u HR=%u TEMP=%u stale=%u gaps=%u voice=%lu upload=%lu blocks=%u dropped=%lu expired=%lu live_overflow=%lu replaced=%lu\n",delivered[2][MP_ECG],delivered[2][MP_RESP],delivered[1][MP_PPG],delivered[2][MP_HR],delivered[2][MP_TEMP],stale,gaps,(unsigned long)voice_done_at,(unsigned long)(timing.uploaded-timing.first),audio_blocks,(unsigned long)r.dropped,(unsigned long)r.expired,(unsigned long)r.live_overflow,(unsigned long)r.live_replaced);
    CHECK(!result && !r.dropped && !r.expired && !stale && !gaps);
    if(hash_slice_ms || scalar_source_age_ms){
        fprintf(stderr,"CONTINUOUS_FRESHNESS stale_ticks=%u max_latest_age_ms=%u hash_slice_ms=%u scalar_source_age_ms=%u\n",latest_stale_ticks,max_latest_age_ms,hash_slice_ms,scalar_source_age_ms);
        CHECK(!latest_stale_ticks);
    }
    CHECK(delivered[2][MP_ECG]==750 && delivered[2][MP_RESP]==300);
    CHECK(delivered[2][MP_HR]==300 && delivered[2][MP_TEMP]==300);
    if(payload_stress)fprintf(stderr,"A_STRESS SPO2=%u PR=%u PPG=%u max_gap_SPO2=%lu PR=%lu scalar_coalesced=%u\n",delivered[1][MP_SPO2],delivered[1][MP_PR],delivered[1][MP_PPG],(unsigned long)max_gap[1][MP_SPO2],(unsigned long)max_gap[1][MP_PR],scalar_skips);
    if(abc)CHECK(delivered[1][MP_SPO2]==300 && delivered[1][MP_PR]==300 && max_gap[1][MP_SPO2]<=5000 && max_gap[1][MP_PR]<=5000 && delivered[1][MP_PPG]==(ppg_segments?600u:300u) && ppg_samples==15000 && delivered[1][MP_NIBP]==1);
    CHECK(!scalar_skips);
    CHECK(audio_blocks==125 && reply_sent && voice_done_at && voice_done_at<UA_TURN_BUDGET_MS);
    /* 新增短段压力仍按原240秒协议期限；180秒性能目标另记，不改生产超时。 */
    if(ppg_segments)fprintf(stderr,"PPG_SEGMENT_PERFORMANCE target180_met=%u assembly240_met=%u\n",last_audio_at-origin-45000<180000u,last_audio_at-origin-45000<240000u);
    CHECK(last_audio_at-origin-45000<(ppg_segments?240000u:180000u));
    CHECK(!memcmp(source,received,sizeof received) && audio_crc==mic_crc32(source,sizeof source));
    unified_audio_stop();for(unsigned i=0;i<500;i++)platform_poll();
    CHECK(speaker.stop_ack && speaker.stop_query_sent && speaker.stop_idle && !speaker.stop_failed);
    printf("HOST_WIRE base_ms=%u ack_ms=%d sends=%u publishes=%u enqueue_to_all_ack_ms=%lu broker_span_ms=%lu NIBP=%u wave_values_exact=1\n",mock_send_base_ms,mock_delay_ms,mock_send_calls,mock_publish_count,(unsigned long)(timing.uploaded-timing.first),(unsigned long)(last_audio_at-first_audio_at),delivered[1][MP_NIBP]);
    printf("HOST_REAL_COREMQTT_%s_CONTENTION_PASS ECG=%u RESP=%u HR=%u TEMP=%u SPO2=%u PR=%u audio=%u voice_ms=%lu high=%lu scalar_coalesced=%u checks=%u hardware=NOT_RUN\n",
        abc?"ABC":"BC",delivered[2][MP_ECG]*100,delivered[2][MP_RESP]*50,delivered[2][MP_HR],delivered[2][MP_TEMP],
        delivered[1][MP_SPO2],delivered[1][MP_PR],audio_blocks,(unsigned long)voice_done_at,(unsigned long)r.high_water,scalar_skips,checks);
    return 0;
}
