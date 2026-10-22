#include "cloud_voice.h"
#include "tts_uart_port.h"
#include "gateway_transport.h"
#include "stm32f4xx_gpio.h"
#include <string.h>
CloudVoiceMetrics cloud_voice_metrics;
TtsQueue cloud_voice_queue;
static VoiceGuard guard;
static bool initialized, entered, raw_previous=true, stable=true, released;
static uint32_t changed, settled;
void cloud_voice_init(void) {
    tts_uart_init();tts_init(&cloud_voice_queue,tts_uart_io());
    GPIO_InitTypeDef gpio;GPIO_StructInit(&gpio);gpio.GPIO_Pin=GPIO_Pin_0;
    gpio.GPIO_Mode=GPIO_Mode_IN;gpio.GPIO_PuPd=GPIO_PuPd_DOWN;GPIO_Init(GPIOA,&gpio);
    initialized=true;
}
void cloud_voice_session(bool ready) {
    voice_session(&guard,gateway_epoch_milliseconds(),ready);
    if(initialized && cloud_voice_metrics.stage>0 && cloud_voice_metrics.stage<=4)
        tts_cancel(&cloud_voice_queue,g_uptime_ms);
    /* 网络重连不重新开启语音；每次开机最多一条低音量短句。 */
    if(cloud_voice_metrics.stage)cloud_voice_metrics.stage=90;
}
void cloud_voice_receive(const char *topic,size_t tn,unsigned qos,bool retain,const uint8_t *p,size_t n) {
    VoiceMessage m;cloud_voice_metrics.received++;
    VoiceResult r=voice_check(&guard,topic,tn,qos,retain,p,n,gateway_epoch_milliseconds(),g_uptime_ms,&m);
    if(r==VOICE_OK) {
        /* 8欧1W试验限制：仅一次、v1、最多60B；不能把此限制宣称为功率合规。 */
        if(cloud_voice_metrics.stage!=3 || m.length>60 || !tts_submit(&cloud_voice_queue,m.text,m.length,1,g_uptime_ms))r=VOICE_BUSY;
        else {
            memcpy(cloud_voice_metrics.turn,m.turn,16);memcpy(cloud_voice_metrics.digest,m.digest,16);
            voice_commit(&guard,&m,g_uptime_ms);cloud_voice_metrics.accepted++;cloud_voice_metrics.accepted_tick=g_uptime_ms;cloud_voice_metrics.stage=4;
        }
    }
    if(r!=VOICE_OK)cloud_voice_metrics.rejected[r]++;
}
void cloud_voice_poll(void) {
    /* platform_poll在AT等待和诊断输出中频繁调用；只推进单字节，严禁调用网络。 */
    if(!initialized || entered)return;
    entered=true;uint32_t now=g_uptime_ms;
    if(cloud_voice_metrics.poll_calls && cloud_voice_metrics.stage>0 && cloud_voice_metrics.stage<5) {
        uint32_t gap=now-cloud_voice_metrics.last_poll_tick;
        if(gap>cloud_voice_metrics.max_poll_gap_ms)cloud_voice_metrics.max_poll_gap_ms=gap;
    }
    cloud_voice_metrics.last_poll_tick=now;cloud_voice_metrics.poll_calls++;
    tts_poll(&cloud_voice_queue,now);
    for(unsigned i=0;i<4;i++) {int c=tts_uart_receive();if(c<0)break;
        cloud_voice_metrics.uart_rx++;cloud_voice_metrics.last_status=(uint32_t)c;
        /* 只记录短句对应的接收状态时刻；音量ACK不能冒充语音ACK/DONE。 */
        if(cloud_voice_metrics.stage==4 && c==0x41)cloud_voice_metrics.ack_tick=now;
        if(cloud_voice_metrics.stage==4 && c==0x4f)cloud_voice_metrics.done_tick=now;
        tts_receive(&cloud_voice_queue,(uint8_t)c,now);}
    cloud_voice_metrics.uart_errors=tts_uart_errors();cloud_voice_metrics.uart_overflow=tts_uart_overflow();
    if((cloud_voice_metrics.uart_errors || cloud_voice_metrics.uart_overflow) && cloud_voice_metrics.stage<90) {
        guard.armed=false;tts_power_lost(&cloud_voice_queue,now);cloud_voice_metrics.stage=90;
    }
    bool raw=GPIO_ReadInputDataBit(GPIOA,GPIO_Pin_0)!=0;
    if(raw!=raw_previous){raw_previous=raw;changed=now;}
    if(raw!=stable && (uint32_t)(now-changed)>=30u) {
        stable=raw;if(!stable)released=true;
        else if(released && now>=2000u) {
            released=false;
            if(cloud_voice_metrics.stage==0 && guard.session && tts_enable(&cloud_voice_queue,true,true) && tts_bench_volume(&cloud_voice_queue,1,now))
                cloud_voice_metrics.stage=1;
            else if(cloud_voice_metrics.stage>0 && cloud_voice_metrics.stage<5) {
                guard.armed=false;tts_cancel(&cloud_voice_queue,now);cloud_voice_metrics.stage=90;
            }
        }
    }
    if(cloud_voice_metrics.stage==1 && cloud_voice_queue.state==TTS_DONE){settled=now;cloud_voice_metrics.stage=2;}
    if(cloud_voice_metrics.stage==2 && (uint32_t)(now-settled)>=100u) {
        voice_arm(&guard,gateway_epoch_milliseconds());cloud_voice_metrics.armed_tick=now;cloud_voice_metrics.stage=3;
    }
    if(cloud_voice_metrics.stage==3 && (uint32_t)(now-cloud_voice_metrics.armed_tick)>=60000u) {
        guard.armed=false;cloud_voice_queue.enabled=false;cloud_voice_metrics.stage=90;
    }
    if(cloud_voice_metrics.stage==4 && cloud_voice_queue.state==TTS_DONE) {
        cloud_voice_queue.enabled=false;cloud_voice_metrics.stage=5;
    }
    if(cloud_voice_queue.state==TTS_ERROR || cloud_voice_queue.state==TTS_TIMEOUT) {
        guard.armed=false;cloud_voice_metrics.stage=90;
    }
    entered=false;
}
