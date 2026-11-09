/* 复用真实coreMQTT/adapter/模型及既有ESP字节替身；无设备或网络连接。 */
#include "../mqtt/tests/mocks/mock_esp.h"
#include "unified_audio.h"
#include "mic_format.h"
#include "mic_protocol.h"
#include "../mqtt/src/gateway_transport.c"
#include <stdlib.h>

static unsigned checks;
extern void (*mock_poll_callback)(void);
#define CHECK(x) do { if(!(x)){fprintf(stderr,"FAIL line=%d\n",__LINE__);exit(3);}++checks; } while(0)
#ifdef MP_AUDIO_DISABLED
int main(void){
    mock_connect();mock_delay_ms=200;
    MpFrame scalar=mock_frame(MP_TEMP,0,false),wave=mock_frame(MP_ECG,250,false);
    for(unsigned i=0;i<GATEWAY_TELEMETRY_SLOTS;i++){
        scalar.seq++;
        CHECK(gateway_mqtt_begin(&scalar)==GW_PENDING);
        CHECK(gateway_mqtt_ticket()!=0);
    }
    CHECK(gateway_mqtt_slots_full() && gateway_mqtt_begin(&scalar)==GW_DEFERRED);
    CHECK(gateway_mqtt_begin(&wave)==GW_COMPLETE);
    CHECK(!unified_audio_send_due());
    /* 无订阅时收到未知下行业务，必须终止 MQTT 会话。 */
    const uint8_t unsolicited[]={0x30,4,0,1,'x','!'};
    mock_queue(unsolicited,sizeof unsolicited);
    unsigned loops=0;
    while(network.connected && loops++<100)gateway_mqtt_progress();
    CHECK(!network.connected && session_error);
    printf("UNIFIED_NO_AUDIO_EGRESS_PASS checks=%u\n",checks);
    return 0;
}
#else
static unsigned replies,polls;
void unified_audio_reply(const uint8_t *p,size_t n){CHECK(n==19 && !memcmp(p,"MR01",4));replies++;}
static void poll(void){polls++;}
static void connect_subscribe(unsigned grant,unsigned fragment,int wrong) {
    config=&gateway_test_config;mock_connect();mock_read_limit=(int)fragment;
    CHECK(gateway_audio_subscribe()==GW_PENDING);CHECK(mock_packet[0]==0x82);
    uint16_t id=(uint16_t)(((unsigned)mock_packet[2]<<8)|mock_packet[3]);
    id+=(unsigned)wrong;uint8_t p[]={0x90,3,(uint8_t)(id>>8),(uint8_t)id,(uint8_t)grant};mock_queue(p,5);
    for(unsigned i=0;i<50 && !gateway_audio_ready() && network.connected;i++)gateway_mqtt_progress();
    CHECK(gateway_audio_ready()==(grant==1 && !wrong));
}
static void inbound(int retain,int wrong_topic) {
    uint8_t p[39]={0x32,37,0,14};p[0]|=(uint8_t)retain;memcpy(p+4,AUDIO_OUTPUT,14);
    if(wrong_topic)p[4]='x';
    p[18]=0;p[19]=55;memcpy(p+20,"MR01",4);
    mock_queue(p,sizeof p);for(unsigned i=0;i<100;i++)CHECK(gateway_mqtt_progress()!=GW_FAILED);
}
int main(void) {
    for(unsigned fragment=1;fragment<=5;fragment++)connect_subscribe(1,fragment,0);
    connect_subscribe(0,5,0);connect_subscribe(0x80,5,0);connect_subscribe(1,5,1);
    connect_subscribe(1,1,0);mock_delay_ms=150;
    uint8_t data[512]={0},packet[544];mic_chunk_packet(packet,1800000000u,0,7,data);
    CHECK(gateway_audio_begin(packet)==GW_PENDING);uint16_t id=mock_last_id;
    MpFrame scalar=mock_frame(MP_TEMP,0,false),wave=mock_frame(MP_ECG,250,false);
    CHECK(gateway_mqtt_begin(&scalar)==GW_PENDING);uint16_t scalar_id=mock_last_id;CHECK(scalar_id!=id);
    CHECK(gateway_audio_begin(packet)==GW_DEFERRED);
    CHECK(gateway_mqtt_begin(&wave)==GW_COMPLETE && mock_last_id==scalar_id);
    unsigned loops=0;while((gateway_audio_result()==GW_PENDING || gateway_mqtt_pending()) && loops++<1000){
        CHECK(gateway_mqtt_progress()!=GW_FAILED);if(scalar_id && gateway_mqtt_ticket_result(scalar_id)==GW_COMPLETE)scalar_id=0;
    }
    CHECK(gateway_audio_result()==GW_COMPLETE && !gateway_mqtt_pending());CHECK(mqtt_metrics.q1_acked==1);
    CHECK(gateway_mqtt_begin(&scalar)==GW_PENDING);scalar_id=mock_last_id;
    CHECK(gateway_audio_begin(packet)==GW_PENDING && mock_last_id!=scalar_id);
    loops=0;while((gateway_audio_result()==GW_PENDING || gateway_mqtt_pending()) && loops++<1000){
        CHECK(gateway_mqtt_progress()!=GW_FAILED);if(scalar_id && gateway_mqtt_ticket_result(scalar_id)==GW_COMPLETE)scalar_id=0;
    }
    CHECK(mqtt_metrics.q1_acked==2 && gateway_audio_result()==GW_COMPLETE);
    /* 反向ACK只能完成对应业务，不能把音频ACK误交给Router。 */
    mock_ack_mode=ACK_NONE;CHECK(gateway_mqtt_begin(&scalar)==GW_PENDING);scalar_id=mock_last_id;
    CHECK(gateway_audio_begin(packet)==GW_PENDING);id=mock_last_id;
    uint8_t ack[]={0x40,2,(uint8_t)(id>>8),(uint8_t)id};mock_queue(ack,4);
    for(unsigned i=0;i<20 && gateway_audio_result()==GW_PENDING;i++)CHECK(gateway_mqtt_progress()!=GW_FAILED);
    CHECK(gateway_audio_result()==GW_COMPLETE && gateway_mqtt_pending() && mqtt_metrics.q1_acked==2);
    ack[2]=(uint8_t)(scalar_id>>8);ack[3]=(uint8_t)scalar_id;mock_queue(ack,4);
    for(unsigned i=0;i<20 && gateway_mqtt_pending();i++){
        CHECK(gateway_mqtt_progress()!=GW_FAILED);if(scalar_id && gateway_mqtt_ticket_result(scalar_id)==GW_COMPLETE)scalar_id=0;
    }
    CHECK(!gateway_mqtt_pending() && mqtt_metrics.q1_acked==3);mock_ack_mode=ACK_MATCH;
    /* 三个遥测槽加一个音频槽满载，反序ACK与槽复用均保持精确归属。 */
    mock_ack_mode=ACK_NONE;CHECK(gateway_mqtt_begin(&scalar)==GW_PENDING);uint16_t first=gateway_mqtt_ticket();
    scalar.seq++;CHECK(gateway_mqtt_begin(&scalar)==GW_PENDING);uint16_t second=gateway_mqtt_ticket();
    CHECK(first!=second && !gateway_mqtt_slots_full());scalar.seq++;
    CHECK(gateway_mqtt_begin(&scalar)==GW_PENDING);uint16_t third=gateway_mqtt_ticket();
    CHECK(third!=first && third!=second && gateway_mqtt_slots_full());CHECK(gateway_audio_begin(packet)==GW_PENDING);id=mock_last_id;
    CHECK(id!=first && id!=second && gateway_mqtt_begin(&scalar)==GW_DEFERRED && gateway_audio_begin(packet)==GW_DEFERRED);
    ack[2]=(uint8_t)(second>>8);ack[3]=(uint8_t)second;mock_queue(ack,4);
    for(unsigned i=0;i<20 && telemetry[1].result==GW_PENDING;i++)CHECK(gateway_mqtt_progress()!=GW_FAILED);
    CHECK(gateway_mqtt_ticket_result(first)==GW_PENDING && gateway_mqtt_ticket_result(second)==GW_COMPLETE);
    CHECK(!gateway_mqtt_slots_full() && gateway_audio_result()==GW_PENDING);
    ack[2]=(uint8_t)(id>>8);ack[3]=(uint8_t)id;mock_queue(ack,4);
    for(unsigned i=0;i<20 && gateway_audio_result()==GW_PENDING;i++)CHECK(gateway_mqtt_progress()!=GW_FAILED);
    CHECK(gateway_audio_result()==GW_COMPLETE && gateway_mqtt_ticket_result(first)==GW_PENDING);
    ack[2]=(uint8_t)(first>>8);ack[3]=(uint8_t)first;mock_queue(ack,4);
    for(unsigned i=0;i<20 && telemetry[0].result==GW_PENDING;i++)CHECK(gateway_mqtt_progress()!=GW_FAILED);
    CHECK(gateway_mqtt_ticket_result(first)==GW_COMPLETE && gateway_mqtt_pending());
    ack[2]=(uint8_t)(third>>8);ack[3]=(uint8_t)third;mock_queue(ack,4);
    for(unsigned i=0;i<20 && telemetry[2].result==GW_PENDING;i++)CHECK(gateway_mqtt_progress()!=GW_FAILED);
    CHECK(gateway_mqtt_ticket_result(third)==GW_COMPLETE && !gateway_mqtt_pending());mock_ack_mode=ACK_MATCH;
    /* 任一槽缺ACK都遵守原5秒期限，其余ACK不代替缺失者。 */
    for(unsigned missing=0;missing<4;missing++){
        connect_subscribe(1,2,0);mock_ack_mode=ACK_NONE;unsigned before=mqtt_metrics.q1_acked;
        uint16_t tickets[4];
        for(unsigned i=0;i<3;i++){scalar.seq++;CHECK(gateway_mqtt_begin(&scalar)==GW_PENDING);tickets[i]=gateway_mqtt_ticket();}
        CHECK(gateway_audio_begin(packet)==GW_PENDING);tickets[3]=mock_last_id;
        for(unsigned i=0;i<4;i++)if(i!=missing){ack[2]=(uint8_t)(tickets[i]>>8);ack[3]=(uint8_t)tickets[i];mock_queue(ack,4);}
        for(unsigned i=0;i<20;i++)CHECK(gateway_mqtt_progress()!=GW_FAILED);
        for(unsigned i=0;i<3;i++)CHECK(gateway_mqtt_ticket_result(tickets[i])==(i==missing?GW_PENDING:GW_COMPLETE));
        CHECK(gateway_audio_result()==(missing==3?GW_PENDING:GW_COMPLETE));
        mock_poll_callback=poll;polls=0;uint32_t at=g_uptime_ms;int failed=0;
        for(unsigned i=0;i<6000;i++)if(gateway_mqtt_progress()==GW_FAILED){failed=1;break;}
        CHECK(failed && polls && g_uptime_ms-at<5100 && !gateway_audio_pending() && !gateway_mqtt_pending());
        CHECK(mqtt_metrics.q1_acked-before==(missing==3?3u:2u));mock_poll_callback=NULL;
    }
    connect_subscribe(1,1,0);
    inbound(0,0);CHECK(replies==1);inbound(1,0);inbound(0,1);CHECK(replies==1);
    CHECK(gateway_mqtt_begin(&wave)==GW_COMPLETE);
    const unsigned modes[]={ACK_WRONG,ACK_NONE,ACK_HALF,ACK_OLD};
    for(unsigned n=0;n<4;n++) {
        connect_subscribe(1,2,0);mock_ack_mode=(int)modes[n];mock_old_id=65000;
        uint32_t prior_acks=mqtt_metrics.q1_acked;
        mock_poll_callback=poll;polls=0;CHECK(gateway_audio_begin(packet)==GW_PENDING);
        uint32_t began=g_uptime_ms;loops=0;
        while(gateway_audio_result()==GW_PENDING && loops++<6000)gateway_mqtt_progress();
        CHECK(gateway_audio_result()==GW_FAILED && polls>0 && g_uptime_ms-began<5100);
        CHECK(mqtt_metrics.q1_acked==prior_acks);mock_poll_callback=NULL;
    }
    config=&gateway_test_config;mock_connect();mqtt_failed();uint8_t cfg[249]={0};
    memcpy(cfg,"MCF3",4);memcpy(cfg+4,"b5-gateway",11);memcpy(cfg+37,"synthetic-password",19);
    memcpy(cfg+102,"b5-c-isolated",14);memcpy(cfg+143,"synthetic-wifi",15);
    memcpy(cfg+176,"synthetic-password",19);uint32_t epoch=1800000000u;memcpy(cfg+241,&epoch,4);
    uint32_t crc=mic_crc32(cfg,245);memcpy(cfg+245,&crc,4);CHECK(gateway_audio_configure(cfg,249));
    GatewayConfig prior=*config;cfg[4]='x';crc=mic_crc32(cfg,245);memcpy(cfg+245,&crc,4);
    CHECK(!gateway_audio_configure(cfg,249) && !memcmp(config,&prior,sizeof prior));
    printf("HOST_UNIFIED_SINGLE_MQTT_OWNER_PASS checks=%u callback_poll=%u hardware=NOT_RUN\n",checks,polls);
    return 0;
}
#endif
