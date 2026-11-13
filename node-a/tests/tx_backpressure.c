/* 真实A应用/协议栈，CAN发送边界短时忙；必须保留已排队点与UNO积压点。 */
#include "stm32f4xx.h"
#include "CANopen.h"
#include "canopen_app.h"
#include "app_bp.h"
#include "uno.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>
volatile uint32_t uwTick;
uint32_t host_primask;
uint8_t g_paused;
volatile uint8_t g_last_pr_ok=1;
measurement_t g_meas;
static uint32_t queued[128];
static unsigned head,tail;
bp_last_t bp_last_get(void){bp_last_t bp={0};return bp;}
bp_state_t bp_state_get(void){return ST_IDLE;}
uint16_t UNO_WaveTakeCAN(int32_t *value,uint32_t *tick,uint16_t maximum){
    if(!maximum || head==tail)return 0;
    *tick=queued[tail++%128];*value=(int32_t)(*tick)*100;return 1;
}
uint16_t UNO_WavePendingCAN(void){return head-tail;}
void UNO_WaveClearCAN(void){tail=head;}
extern void b4_host_now(uint32_t);
extern void b4_host_wire(FILE *);
extern void b4_host_block(int);
extern void b4_host_receive(uint32_t,uint8_t,const uint8_t *);
int main(void){
    FILE *wire=tmpfile();assert(wire);b4_host_wire(wire);
    g_meas.spo2=98;g_meas.pulse_rate=60;g_meas.probe_state=1;g_meas.result_valid=1;
    uwTick=1000;b4_host_now(uwTick);assert(canopen_app_init()==0);
    uint64_t relative=1800000000000ULL-441763200000ULL;
    uint32_t ms=relative%86400000u;uint16_t days=relative/86400000u;uint8_t time[6];
    memcpy(time,&ms,4);memcpy(time+4,&days,2);b4_host_receive(0x100,6,time);
    for(uwTick=1000;uwTick<=1640;uwTick++){
        b4_host_now(uwTick);g_meas.result_time_ms=uwTick;
        if(uwTick%8==0){assert(head-tail<128);queued[head++%128]=uwTick;}
        if(uwTick==1100)b4_host_block(1);
        if(uwTick==1180)b4_host_block(0);
        canopen_app_process();
    }
    rewind(wire);unsigned arrival,id,length,points=0,last_tick=0;
    while(fscanf(wire,"%u %u %u",&arrival,&id,&length)==3){
        uint8_t data[8]={0};unsigned byte;
        for(unsigned i=0;i<length;i++){assert(fscanf(wire,"%u",&byte)==1);data[i]=byte;}
        if(id==0x181){
            uint32_t tick;memcpy(&tick,data+4,4);
            if(points)assert(tick-last_tick==20);
            last_tick=tick;points++;
        }
    }
    assert(points>=30 && last_tick>=1620 && !UNO_WavePendingCAN());
    fclose(wire);puts("A_TX_BACKPRESSURE_REAL_STACK_POINT_CONSERVATION_PASS");return 0;
}
