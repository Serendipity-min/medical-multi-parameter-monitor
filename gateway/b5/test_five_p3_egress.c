/* P3 Host：运行真实 Router、coreMQTT、AT 状态机和音频推进器。 */
#include "../mqtt/src/gateway_transport.c"
#include "../mqtt/src/platform.c"
static int measured_ticket(uint16_t id);
#define gateway_mqtt_ticket_result measured_ticket
#include "egress.h"
#undef gateway_mqtt_ticket_result
#include "../microphone/mic_api.h"
#include "../microphone/mic_format.h"
#include "../voice/tts_uart_port.h"
#include <assert.h>
#include <inttypes.h>

enum { WINDOW_MS=110000, QUEUE_ACKS=8, SEQUENCES=300 };
const GatewayConfig gateway_test_config={GATEWAY_CONFIG_MAGIC,1700000000u,
    "synthetic-wifi","synthetic-password","mqtt.example.invalid","b5-gateway","synthetic-password","b5-c-isolated"};
volatile uint32_t g_uptime_ms;
TestUsart platform_usart[2]={{.SR=USART_SR_TXE},{.SR=USART_SR_TXE}};
static MpRouter router;
static uint64_t simulated_us;
static unsigned wire_us=87,byte_cpu_us;
static uint32_t origin, produced, stop_at, record_at, first_audio, last_audio;
static uint32_t telemetry_ack_at[GATEWAY_TELEMETRY_SLOTS], reclaim_max, prompt_ms=4, terminal_ms=22, rx_ms=9, peer_ack_ms=55;
static unsigned mic_state, samples_wanted, audio_blocks, medical_published, recording_started;
static unsigned outgoing_length, outgoing_count, command_count, reply_count, reply_offset;
static uint32_t reply_at;
static uint8_t wire_packet[2048], reply_bytes[512];
static char command_bytes[64];
static int16_t pcm[MIC_SAMPLES];
static unsigned serial_payload_bytes, query_empty_us_count, rx_queries_with_queue;
static uint64_t stage_us[7], empty_query_us, rx_cycle_start, rx_queue_us;
static unsigned seq[6][MP_STREAMS], delivered[6][MP_STREAMS];
static uint32_t expected_hash[6][MP_STREAMS][SEQUENCES], replay_hash[6][MP_STREAMS][SEQUENCES];
static uint32_t most_recent_seq[6][MP_STREAMS], max_gap_ms[6][MP_STREAMS], recent_at[6][MP_STREAMS];
static unsigned identity_errors, late, replay_count, duplicates;
typedef struct {uint8_t data[5];unsigned count;uint32_t at;} PeerReply;
static PeerReply peer[QUEUE_ACKS];
static unsigned peer_head, peer_count;

int b5_network_stopped(void){return 0;}
uint32_t b5_business_remaining(void){return 420000u;}
int mic_initialize(void){return 1;}
void mic_record_begin(void){mic_state=1;record_at=g_uptime_ms;}
unsigned mic_record_state(void){return mic_state;}
void mic_record_poll(void){
    if(mic_state==1 && g_uptime_ms-record_at>=samples_wanted/16u)mic_state=2;
}
void mic_record_cancel(void){mic_state=3;}
void mic_record_finish(void){mic_state=2;}
const int16_t *mic_record_pcm(unsigned *count){*count=mic_state==2?samples_wanted:0;return pcm;}
void mic_record_export(void){}
void mic_diagnostics(MicDiag *out){memset(out,0,sizeof *out);}
bool unified_audio_fact_current(unsigned node,unsigned stream,uint32_t seq_no,uint32_t epoch_no,uint32_t boot){
    (void)node;(void)stream;(void)seq_no;(void)epoch_no;(void)boot;return false;
}
void tts_uart_init(void){}
static unsigned tts_queued;
static bool tts_tx_completed;
static int tts_write(void *ctx,uint8_t byte){(void)ctx;(void)byte;tts_queued++;return 1;}
static bool tts_idle(void *ctx){(void)ctx;tts_tx_completed=true;return true;}
static void tts_abort(void *ctx){(void)ctx;}
TtsIo tts_uart_io(void){return (TtsIo){NULL,tts_write,tts_idle,tts_abort};}
int tts_uart_receive(void){if(tts_queued==9 && tts_tx_completed){tts_queued=0;return 0x41;}return -1;}
uint32_t tts_uart_errors(void){return 0;}
uint32_t tts_uart_overflow(void){return 0;}

static void advance(unsigned elapsed){
    unsigned stage=0;
    if(rx_state)stage=rx_state<=2?5:6;
    else if(io_metrics.at_phase==ESP_AT_COMMAND)stage=1;
    else if(io_metrics.at_phase==ESP_AT_WAIT_PROMPT)stage=2;
    else if(io_metrics.at_phase==ESP_AT_DATA)stage=3;
    else if(io_metrics.at_phase==ESP_AT_WAIT_SEND_OK)stage=4;
    stage_us[stage]+=elapsed;
    if(rx_state && router.ln)rx_queue_us+=elapsed;
    simulated_us+=elapsed;
    g_uptime_ms=(uint32_t)(simulated_us/1000);
}

static void uart_reply(const void *data,unsigned count,unsigned delay){
    assert(reply_offset==reply_count && count<=sizeof(reply_bytes));
    memcpy(reply_bytes,data,count);
    reply_offset=0;reply_count=count;reply_at=g_uptime_ms+delay;
}
static void terminal(const char *line,unsigned delay){uart_reply(line,(unsigned)strlen(line),delay);}
static void peer_reply(const uint8_t *data,unsigned count,unsigned delay){
    assert(peer_count<QUEUE_ACKS && count<=5);
    PeerReply *p=&peer[(peer_head+peer_count++)%QUEUE_ACKS];
    memcpy(p->data,data,count);p->count=count;p->at=g_uptime_ms+delay;
}

static unsigned stream_id(const char *topic){
    const char *tail=strrchr(topic,'/');assert(tail);tail++;
    if(!strcmp(tail,"status"))return strstr(topic,"/NODE-")?MP_NODE_STATUS:MP_GATEWAY_STATUS;
    for(unsigned i=0;i<MP_STREAMS;i++)if(!strcmp(tail,mp_stream_name((MpStream)i)))return i;
    assert(0);return 0;
}
static void observe_publish(unsigned pos,unsigned topic_length){
    char topic[120];assert(topic_length<sizeof(topic));
    memcpy(topic,wire_packet+pos,topic_length);topic[topic_length]=0;
    pos+=topic_length;
    if(wire_packet[0]&2u)pos+=2;
    unsigned length=outgoing_count-pos;
    if(!strcmp(topic,"mpm/mic/v1/in")){
        const uint8_t *block=wire_packet+pos;
        assert(length==544 && !memcmp(block,"MC01",4));
        assert((unsigned)(block[8]+256u*block[9])==audio_blocks);
        unsigned bytes=samples_wanted*2u-audio_blocks*512u;if(bytes>512)bytes=512;
        assert(!memcmp(block+32,(const uint8_t *)pcm+audio_blocks*512u,bytes));
        if(!audio_blocks)first_audio=g_uptime_ms;
        audio_blocks++;last_audio=g_uptime_ms;return;
    }
    if(!origin)return;
    char body[2048];assert(length<sizeof body);memcpy(body,wire_packet+pos,length);body[length]=0;
    const char *node_mark=strstr(topic,"/NODE-");
    unsigned node=node_mark?(unsigned)(node_mark[6]-'A'+1):3, stream=stream_id(topic);
    const char *sequence=strstr(body,"\"seq\":");
    const char *timestamp=strstr(body,"\"timestamp\":");
    assert(sequence && timestamp && node<=5);
    unsigned id=(unsigned)strtoul(sequence+6,NULL,10);assert(id && id<SEQUENCES);
    bool replay=strstr(topic,"/replay/")!=NULL;
    uint32_t hash=mic_crc32(body,length);
    if(hash!=(replay?replay_hash:expected_hash)[node][stream][id])identity_errors++;
    if(replay){replay_count++;return;}
    if(id<=most_recent_seq[node][stream])duplicates++;
    most_recent_seq[node][stream]=id;
    if(recent_at[node][stream] && g_uptime_ms-recent_at[node][stream]>max_gap_ms[node][stream])
        max_gap_ms[node][stream]=g_uptime_ms-recent_at[node][stream];
    recent_at[node][stream]=g_uptime_ms;
    uint64_t stamp=strtoull(timestamp+12,NULL,10);
    if(gateway_epoch_milliseconds()-stamp>=(stream==MP_NIBP?90000u:5000u))late++;
    medical_published++;delivered[node][stream]++;
}
static void mqtt_packet(void){
    unsigned type=wire_packet[0]>>4;
    if(type==1){peer_reply((const uint8_t[]){0x20,2,0,0},4,0);return;}
    if(type==12){peer_reply((const uint8_t[]){0xd0,0},2,0);return;}
    unsigned pos=1;
    while(wire_packet[pos++]&128u){}
    if(type==8){peer_reply((const uint8_t[]){0x90,3,wire_packet[pos],wire_packet[pos+1],1},5,0);return;}
    if(type!=3)return;
    unsigned topic_length=256u*wire_packet[pos]+wire_packet[pos+1];pos+=2;
    observe_publish(pos,topic_length);
    if(wire_packet[0]&2u){
        pos+=topic_length;
        peer_reply((const uint8_t[]){0x40,2,wire_packet[pos],wire_packet[pos+1]},4,peer_ack_ms);
    }
}
void platform_test_tx(unsigned char byte){
    advance(wire_us+byte_cpu_us);
    if(outgoing_length){
        assert(outgoing_count<sizeof wire_packet);
        wire_packet[outgoing_count++]=byte;
        if(outgoing_count==outgoing_length){
            serial_payload_bytes+=outgoing_length;outgoing_length=0;
            mqtt_packet();terminal("\r\nSEND OK\r\n",terminal_ms);
        }
        return;
    }
    assert(command_count<sizeof(command_bytes)-1);
    command_bytes[command_count++]=(char)byte;
    if(command_count<2 || command_bytes[command_count-2]!='\r' || byte!='\n')return;
    command_bytes[command_count]=0;command_count=0;
    if(sscanf(command_bytes,"AT+CIPSEND=%u",&outgoing_length)==1){
        outgoing_count=0;terminal(">",prompt_ms);return;
    }
    unsigned ready_bytes=0;
    for(unsigned i=0;i<peer_count;i++){
        const PeerReply *p=&peer[(peer_head+i)%QUEUE_ACKS];
        if(p->at>g_uptime_ms)break;
        ready_bytes+=p->count;
    }
    if(!strncmp(command_bytes,"AT+CIPRECVLEN?",14)){
        char line[96];int count=snprintf(line,sizeof line,"\r\n+CIPRECVLEN:%u,0,0,0,0\r\n\r\nOK\r\n",ready_bytes);
        if(origin && router.ln)rx_queries_with_queue++;
        uart_reply(line,(unsigned)count,rx_ms);
    }else if(!strncmp(command_bytes,"AT+CIPRECVDATA=",15)){
        unsigned char line[128];
        unsigned n=(unsigned)snprintf((char *)line,sizeof line,"\r\n+CIPRECVDATA:%u,",ready_bytes);
        while(ready_bytes){
            PeerReply *p=&peer[peer_head];memcpy(line+n,p->data,p->count);n+=p->count;
            ready_bytes-=p->count;peer_head=(peer_head+1)%QUEUE_ACKS;peer_count--;
        }
        memcpy(line+n,"\r\nOK\r\n",6);uart_reply(line,n+6,rx_ms);
    }else terminal("\r\nOK\r\n",rx_ms);
}

static void put(unsigned node,unsigned stream,unsigned rate,unsigned count,int value){
    MpFrame f={0};f.node=node;f.stream=stream;f.rate=rate;f.count=count;
    f.synthetic=true;f.valid=true;f.timestamp=1800000000000ULL+produced;
    f.epoch=1712345678;f.boot=1;f.seq=++seq[node][stream];assert(f.seq<SEQUENCES);
    for(unsigned i=0;i<count;i++){
        f.values[i]=value;
        if(rate)f.values[i]=(value+(int)i)*((stream!=MP_PPG && i%2)?-1:1);
    }
    if(stream==MP_NIBP)f.values[1]=760;
    char body[2048];
    int length=mp_json(&f,body,sizeof body);assert(length>0);
    expected_hash[node][stream][f.seq]=mic_crc32(body,(unsigned)length);
    f.replay=true;length=mp_json(&f,body,sizeof body);assert(length>0);
    replay_hash[node][stream][f.seq]=mic_crc32(body,(unsigned)length);
    f.replay=false;mp_router_put(&router,&f);
}
static void tick(void){
    advance(25);
    if(reply_offset<reply_count && g_uptime_ms>=reply_at){
        USART3->DR=reply_bytes[reply_offset++];USART3->SR|=USART_SR_RXNE;
        USART3_IRQHandler();USART3->SR&=~USART_SR_RXNE;advance(wire_us+byte_cpu_us);
    }
    if(origin){
        while(produced<g_uptime_ms-origin && produced<WINDOW_MS){
            produced++;
            if(produced%400==0)put(2,MP_ECG,250,100,1103);
            if(produced%1000==0){
                put(2,MP_RESP,50,50,10000);put(1,MP_PPG,50,50,1230000);
                put(1,MP_SPO2,0,1,9750);put(1,MP_PR,0,1,7200);
                put(2,MP_HR,0,1,6000);put(2,MP_RR,0,1,1800);put(4,MP_TEMP,0,1,2450);
            }
            if(produced%5000==0){
                put(3,MP_GATEWAY_STATUS,0,1,1);
                put(1,MP_NODE_STATUS,0,1,1);put(2,MP_NODE_STATUS,0,1,1);
                put(4,MP_NODE_STATUS,0,1,1);put(5,MP_NODE_STATUS,0,1,1);
            }
            if(produced==2000)put(5,MP_NIBP,0,2,1180);
        }
        unified_audio_local_poll();
    }
    if(rx_state==1 && !rx_tx)rx_cycle_start=simulated_us;
    if(io_metrics.rx_empty!=query_empty_us_count){
        query_empty_us_count=io_metrics.rx_empty;
        if(origin)empty_query_us+=simulated_us-rx_cycle_start;
    }
}

static void record_mqtt_event(MQTTContext_t *ctx,MQTTPacketInfo_t *packet,MQTTDeserializedInfo_t *data){
    if(packet->type==MQTT_PACKET_TYPE_PUBACK)
        for(unsigned i=0;i<GATEWAY_TELEMETRY_SLOTS;i++)
            if(telemetry[i].id==data->packetIdentifier)telemetry_ack_at[i]=g_uptime_ms;
    mqtt_event(ctx,packet,data);
}

static int measured_ticket(uint16_t id){
    unsigned slot=0;
    while(slot<GATEWAY_TELEMETRY_SLOTS && telemetry[slot].id!=id)slot++;
    int result=gateway_mqtt_ticket_result(id);
    if(result==GW_COMPLETE){
        assert(slot<GATEWAY_TELEMETRY_SLOTS && telemetry_ack_at[slot]);
        uint32_t delay=g_uptime_ms-telemetry_ack_at[slot];
        if(delay>reclaim_max)reclaim_max=delay;
        telemetry_ack_at[slot]=0;
    }
    return result;
}

static void latency(const char *name,const B5Latency *m){
    printf("lat %s n=%lu p50_upper=%lu p95_upper=%lu max=%lu\n",name,(unsigned long)m->count,
        (unsigned long)b5_latency_percentile(m,50),(unsigned long)b5_latency_percentile(m,95),(unsigned long)m->max);
}
int main(int argc,char **argv){
    unsigned blocks=argc>1?(unsigned)atoi(argv[1]):0;
    assert(blocks==0 || blocks==64 || blocks==125);
    if(argc>2){terminal_ms=(unsigned)atoi(argv[2]);assert(terminal_ms<500);}
    if(argc>3)esp_uart_baud=(unsigned)atoi(argv[3]);
    assert(esp_uart_baud==115200u || esp_uart_baud==230400u);
    if(argc>4)byte_cpu_us=(unsigned)atoi(argv[4]);
    assert(byte_cpu_us<=120u);
    wire_us=(10000000u+esp_uart_baud/2u)/esp_uart_baud;
    samples_wanted=blocks==64?16160:32000;
    for(unsigned i=0;i<MIC_SAMPLES;i++)pcm[i]=(int16_t)(i*13u+7u);
    platform_set_poll(tick);mqtt_adapter_reset(&network);esp_mqtt_reset();
    epoch=1800000000;epoch_tick=g_uptime_ms;
    MpFrame will={0};will.node=3;will.stream=MP_GATEWAY_STATUS;will.synthetic=true;will.timestamp=gateway_epoch_milliseconds();
    assert(gateway_mqtt_open(&will));
    client.appCallback=record_mqtt_event;
    assert(gateway_audio_subscribe()==GW_PENDING);
    while(!gateway_audio_ready())assert(gateway_mqtt_progress()!=GW_FAILED);
    mp_router_init(&router);mp_router_online(&router,true);
    unified_audio_init();unified_audio_network(true);
    B5Publisher publisher={0};
    origin=g_uptime_ms;epoch_tick=origin;
    memset(stage_us,0,sizeof stage_us);serial_payload_bytes=0;
    uint32_t first_queries=io_metrics.rx_queries, first_empty=io_metrics.rx_empty, first_reads=io_metrics.rx_reads;
    while(g_uptime_ms-origin<WINDOW_MS){
        platform_poll();
        if(blocks && !recording_started && produced>=10000){unified_audio_command('R',false);recording_started=1;assert(mic_state==1);}
        if(!b5_egress_step(&router,&publisher,true)){
            printf("FAILED tick=%u phase=%lu q0=%lu q1=%lu audio=%u\n",(unsigned)(g_uptime_ms-origin),
                (unsigned long)io_metrics.at_phase,(unsigned long)publisher.q0,(unsigned long)publisher.q1,audio_blocks);
            return 3;
        }
        unified_audio_step(!publisher.deferred && !router.ln);
    }
    stop_at=g_uptime_ms;
    printf("case blocks=%u terminal_ms=%u baud=%u cpu_us=%u wire_us=%u elapsed_ms=%u offered_wave=%u delivered_wave=%u\n",
        blocks,terminal_ms,(unsigned)esp_uart_baud,byte_cpu_us,wire_us,
        (unsigned)(stop_at-origin),seq[2][MP_ECG]+seq[2][MP_RESP]+seq[1][MP_PPG],
        delivered[2][MP_ECG]+delivered[2][MP_RESP]+delivered[1][MP_PPG]);
    printf("flow q0=%lu q1=%lu published=%u replay=%u audio=%u audio_span_ms=%u audio_first_ms=%u audio_acked=%u queue_live=%u queue_history=%u inflight=%u high=%lu overflow=%lu replaced=%lu dropped=%lu expired=%lu late=%u identity_errors=%u duplicates=%u\n",
        (unsigned long)publisher.q0,(unsigned long)publisher.q1,medical_published,replay_count,audio_blocks,
        audio_blocks?(unsigned)(last_audio-first_audio):0,audio_blocks?(unsigned)(first_audio-origin):0,
        audio_blocks-(gateway_audio_pending()?1u:0u),router.ln,router.cn,(unsigned)publisher.pending,
        (unsigned long)router.high_water,(unsigned long)router.live_overflow,(unsigned long)router.live_replaced,
        (unsigned long)router.dropped,(unsigned long)router.expired,late,identity_errors,duplicates);
    printf("owner idle_us=%" PRIu64 " command_us=%" PRIu64 " prompt_us=%" PRIu64 " data_us=%" PRIu64
        " send_ok_us=%" PRIu64 " rx_len_us=%" PRIu64 " rx_data_us=%" PRIu64 " rx_with_queue_us=%" PRIu64
        " empty_us=%" PRIu64 " queries=%lu empty=%lu reads=%lu queries_with_queue=%u tx_payload_bytes=%u reclaim_max_ms=%u\n",
        stage_us[0],stage_us[1],stage_us[2],stage_us[3],stage_us[4],stage_us[5],stage_us[6],
        rx_queue_us,empty_query_us,(unsigned long)(io_metrics.rx_queries-first_queries),
        (unsigned long)(io_metrics.rx_empty-first_empty),(unsigned long)(io_metrics.rx_reads-first_reads),
        rx_queries_with_queue,serial_payload_bytes,reclaim_max);
    for(unsigned node=1;node<=5;node++)for(unsigned stream=0;stream<MP_STREAMS;stream++){
        if(seq[node][stream])printf("stream node=%u stream=%u offered=%u delivered=%u max_gap_ms=%u\n",node,stream,
             seq[node][stream],delivered[node][stream],max_gap_ms[node][stream]);
    }
    latency("json",&mqtt_metrics.json);latency("send",&mqtt_metrics.send);latency("puback",&mqtt_metrics.ack);
    latency("residence",&router.residence);latency("source_age",&router.source_age);
    return identity_errors || duplicates || publisher.failed || platform_at_unsynced()?3:0;
}
