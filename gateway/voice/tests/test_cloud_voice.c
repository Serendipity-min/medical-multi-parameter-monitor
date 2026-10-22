/* 真实coreMQTT+P6V1+单槽状态机；UART边界有意标为Host假设备，不能冒充可闻。 */
#include "cloud_voice.h"
#include "tts_uart_port.h"
#include "stm32f4xx_gpio.h"
#include "mock_esp.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>
extern int mock_suback_mode,mock_subscribe_count,mock_in_pubacks;
static int key,rx=-1,phase;
static uint8_t tx[1024];static size_t tx_n,frame_start;static uint32_t finish;
void GPIO_StructInit(GPIO_InitTypeDef *p){memset(p,0,sizeof(*p));}
void GPIO_Init(void *p,GPIO_InitTypeDef *g){(void)p;(void)g;}
int GPIO_ReadInputDataBit(void *p,unsigned n){(void)p;(void)n;return key;}
void tts_uart_init(void){}
static int write_byte(void *p,uint8_t c){(void)p;assert(tx_n<sizeof(tx));tx[tx_n++]=c;return 1;}
static bool idle(void *p){(void)p;
    if(tx_n-frame_start>=3 && tx_n-frame_start==3u+((size_t)tx[frame_start+1]<<8)+tx[frame_start+2]) {
        finish=g_uptime_ms;phase=1;frame_start=tx_n;
    }return true;
}
static void abort_tx(void *p){(void)p;frame_start=tx_n;}
TtsIo tts_uart_io(void){return (TtsIo){NULL,write_byte,idle,abort_tx};}
uint32_t tts_uart_errors(void){return 0;}
uint32_t tts_uart_overflow(void){return 0;}
int tts_uart_receive(void){if(rx>=0){int x=rx;rx=-1;return x;}
    if(phase==1 && g_uptime_ms>finish){phase=2;return 0x41;}
    if(phase==2 && g_uptime_ms-finish>15){phase=3;return 0x4e;}
    if(phase==3 && g_uptime_ms-finish>30){phase=0;return 0x4f;}return -1;
}
static void advance(unsigned n){while(n--)platform_poll();}
static void be64(uint8_t *p,uint64_t v){for(unsigned i=0;i<8;i++){p[7-i]=(uint8_t)v;v>>=8;}}
static size_t payload(uint8_t *p,uint64_t issued,uint8_t id,const uint8_t *text,size_t n){
    memcpy(p,"P6V1",4);be64(p+4,issued);be64(p+12,issued+15000);memset(p+20,id,16);memset(p+36,0x5a,16);
    p[52]=(uint8_t)(n>>8);p[53]=(uint8_t)n;memcpy(p+54,text,n);return n+54;
}
static void packet(const uint8_t *p,size_t n,unsigned qos,bool retain,const char *topic){
    uint8_t b[512];size_t tn=strlen(topic),len=2+tn+(qos?2:0)+n,i=0;
    b[i++]=0x30|(qos<<1)|(retain?1:0);size_t remain=len;
    do{b[i]=(uint8_t)(remain%128);remain/=128;if(remain)b[i]|=128;i++;}while(remain);
    b[i++]=(uint8_t)(tn>>8);b[i++]=(uint8_t)tn;memcpy(b+i,topic,tn);i+=tn;
    if(qos){b[i++]=0;b[i++]=23;}memcpy(b+i,p,n);mock_queue(b,i+n);
}
#define PASS(s) puts("PASS " s)
int main(void){
    uint8_t p[VOICE_WIRE_MAX];const uint8_t phrase[]="请适当休息。";
    for(int mode=1;mode<=4;mode++){
        mock_suback_mode=mode;mock_connect();assert(gateway_mqtt_yield());
        assert(gateway_mqtt_publish(&(MpFrame){.stream=MP_GATEWAY_STATUS,.node=3,.timestamp=1800000000000ULL}));
    }PASS("denied_wrong_id_downgraded_missing_suback_monitoring_survives");
    mock_suback_mode=0;cloud_voice_init();mock_connect();assert(mock_subscribe_count==5);
    size_t n=payload(p,gateway_epoch_milliseconds(),1,phrase,sizeof(phrase)-1);
    packet(p,n,1,false,VOICE_TOPIC);assert(gateway_mqtt_yield());assert(!cloud_voice_metrics.accepted);
    assert(mock_in_pubacks==1);PASS("default_off_still_official_inbound_puback");
    advance(40);key=1;advance(40);key=0;advance(200);assert(cloud_voice_metrics.stage==3);
    advance(1100);n=payload(p,gateway_epoch_milliseconds(),2,phrase,sizeof(phrase)-1);
    packet(p,n,1,true,VOICE_TOPIC);assert(gateway_mqtt_yield());
    packet(p,n,0,false,VOICE_TOPIC);assert(gateway_mqtt_yield());
    packet(p,n,1,false,"mpm/v1/GW-C-001/control");assert(gateway_mqtt_yield());
    assert(!cloud_voice_metrics.accepted);PASS("retained_wrong_qos_wrong_topic_rejected_without_network_reset");
    /* 下行在等待本次上行PUBACK期间到达；一字节短读覆盖真实库的部分包装配。 */
    mock_read_limit=1;packet(p,n,1,false,VOICE_TOPIC);
    MpFrame f=mock_frame(MP_SPO2,0,false);assert(gateway_mqtt_publish(&f));
    assert(cloud_voice_metrics.accepted==1 && mock_last_id);advance(200);
    assert(cloud_voice_queue.ack_count==2 && cloud_voice_queue.done_count==1 && cloud_voice_metrics.stage==5);
    assert(tx_n==9+sizeof(phrase)-1+5);PASS("mixed_outbound_ack_inbound_qos1_partial_reads_real_decoder_fake_uart_done");
    packet(p,n,1,false,VOICE_TOPIC);assert(gateway_mqtt_yield());assert(cloud_voice_metrics.accepted==1);
    gateway_network_close();assert(gateway_network_open());assert(gateway_mqtt_open(&f));
    packet(p,n,1,false,VOICE_TOPIC);assert(gateway_mqtt_yield());assert(cloud_voice_metrics.accepted==1);
    PASS("duplicate_reconnect_never_rearms_or_replays");
    mock_ack_mode=ACK_NONE;uint32_t start=g_uptime_ms;assert(!gateway_mqtt_publish(&f));
    assert(g_uptime_ms-start>=5000u && g_uptime_ms-start<5100u);PASS("outbound_5000ms_timeout_unchanged_with_voice");
    printf("HOST_C_RECEIVED accepted=%lu inbound_puback=%d uart_done=%lu audible=NOT_TESTED\n",(unsigned long)cloud_voice_metrics.accepted,mock_in_pubacks,(unsigned long)cloud_voice_queue.done_count);
}
