/* Host 只调用真实探针入口和停止锁存；不打开设备或网络。 */
#define main field01_firmware_main
#include "../b5/network_main.c"
#undef main
#include <assert.h>

volatile uint32_t g_uptime_ms;
volatile B4HwDiag b4_hw_diag[2];
static const unsigned char *command;
static size_t remaining;
static bool config_valid,op;
#ifndef MP_AUDIO_DISABLED
static bool subscribed;
static MicDiag microphone;
#endif
static unsigned pre_calls,pre_advance;
#ifdef MP_TRANSPORT_PROFILE
static unsigned profile_resets;
void platform_cpu_reset_service_max(void){profile_resets++;}
#endif
static bool pre_restore_ok,pre_manual_stop;

int console_char(void) {
    if(!remaining)return -1;
    remaining--;return *command++;
}
void console(const char *line){(void)line;}
uint32_t platform_uart_errors_total(void){return 0;}
int platform_at_synchronized(void){return 1;}
void platform_io_snapshot(EspIoMetrics *out){memset(out,0,sizeof *out);}
int gateway_config_valid(void){return config_valid;}
#ifndef MP_AUDIO_DISABLED
int gateway_audio_ready(void){return subscribed;}
#endif
#ifdef MP_ESP_UART_230400
int gateway_uart_negotiating(void){return 0;}
#endif
bool b4_gateway_online(B4Gateway *g,unsigned node){(void)g;(void)node;return op;}
#ifndef MP_AUDIO_DISABLED
void mic_diagnostics(MicDiag *out){*out=microphone;}
#endif
void b4_hw_idle(void){}
void b4_hw_stop(void){assert(0);}
#ifndef MP_AUDIO_DISABLED
void unified_audio_stop(void){assert(0);}
#endif
void mp_router_online(MpRouter *r,bool online){(void)r;(void)online;assert(0);}
int platform_console_busy(void){return 0;}
void platform_poll(void){service();}

static void input(const char *line,size_t size) {
    command=(const unsigned char *)line;remaining=size;
    while(remaining)local_control();
}
#define INPUT(s) input(s,sizeof(s)-1)
int gateway_preflight(uint32_t target,uint32_t deadline) {
    assert(target==pre_target && deadline==pre_deadline && pre_state==PRE_RUNNING);
    pre_calls++;
    b4_hw_diag[0].overflow=1;
    g_uptime_ms+=pre_advance;
    b5_hard_tick();
    platform_poll();
    assert(!network_fault && !stop_due && !armed && !field01_t0 && !runtime_ready);
    INPUT("FIELD01 START\nFIELD01 KEY\nFIELD01 PRE 500\n");
    assert(pre_state==PRE_RUNNING && !armed);
#ifndef MP_AUDIO_DISABLED
    assert(!field_key_approved);
#endif
    if(pre_manual_stop){
        static const unsigned char stop_input[]="FIELD01 STOP\n";
        command=stop_input;remaining=sizeof stop_input-1;
        platform_poll();
        assert(stop_due && stop_reason==FIELD01_MANUAL);
    }
    b4_hw_diag[0].overflow=0;
    return pre_restore_ok;
}

static void reset_pre(void) {
    pre_state=PRE_UNUSED;stop_due=stopped=armed=false;field01_t0=0;
#ifndef MP_AUDIO_DISABLED
    field_key_approved=false;
#endif
    g_uptime_ms=1000;
    pre_advance=0;pre_restore_ok=true;pre_manual_stop=false;
}

int main(void) {
    config_valid=true;
    reset_pre();
    INPUT("FIELD01 PRE 460\nFIELD01 PRE 500x\nFIELD01 PRE\0\n");
    assert(pre_state==PRE_UNUSED);
    INPUT("FIELD01 PRE 230\r\n");
    assert(pre_state==PRE_QUEUED && pre_target==230400);
    field01_disarmed_step();
    assert(pre_state==PRE_CLEAN && pre_calls==1 && !stop_due);
    INPUT("FIELD01 PRE 500\nFIELD01 START\n");
    assert(pre_calls==1 && armed && uart_error_baseline==0 && !field01_t0);
    reset_pre();
    pre_restore_ok=false;
    INPUT("FIELD01 PRE 500\n");
    assert(pre_target==500000);
    field01_disarmed_step();
    INPUT("FIELD01 START\nFIELD01 PRE\n");
    assert(pre_state==PRE_DIRTY && pre_calls==2 && !armed && !stop_due);
    reset_pre();
    pre_advance=60000;
    INPUT("FIELD01 PRE\n");
    field01_disarmed_step();
    INPUT("FIELD01 START\n");
    assert(!armed && !b5_business_remaining());
    b5_hard_tick();
    assert(stop_due && stop_reason==FIELD01_TIMER);
    reset_pre();
    pre_manual_stop=true;
    INPUT("FIELD01 PRE\n");
    field01_disarmed_step();
    assert(stop_due && stop_reason==FIELD01_MANUAL && !armed);
    reset_pre();
    INPUT("FIELD01 PRE\n");
    g_uptime_ms=210000;b5_hard_tick();
    assert(stop_due && stop_reason==FIELD01_TIMER);
    reset_pre();
    config_valid=false;
    INPUT("FIELD01 START\n");
    assert(!armed);
    config_valid=true;
    INPUT("FIELD01 START and more\n");
    INPUT("FIELD01 START\0x\n");
    INPUT("R\n");
    assert(!armed);
    g_uptime_ms=44999;
    b5_hard_tick();
    assert(!stop_due && b5_business_remaining()==1);
    g_uptime_ms=45000;
    b5_hard_tick();
    INPUT("FIELD01 START\n");
    assert(stop_due && !armed && stop_tick==45000 && stop_reason==FIELD01_TIMER);

    stop_due=false;g_uptime_ms=8000;
    INPUT("FIELD01 START\r\n");
    assert(armed && !stop_due);
    INPUT("FIELD01 KEY\n");
#ifndef MP_AUDIO_DISABLED
    assert(!field_key_approved);
    subscribed=true;
#endif
    gateway.utc_valid=true;op=true;
    field01_begin();
    assert(!field01_t0);
    for(unsigned bus=0;bus<2;bus++)for(unsigned slot=0;slot<2;slot++)
        gateway.segments[bus].remote[slot].seen[4]=true;
    field01_begin();
    assert(field01_t0==8000 && b5_business_remaining()==150000);
    INPUT("FIELD01 KEY\n");
#ifndef MP_AUDIO_DISABLED
    assert(field_key_approved);
#endif
    g_uptime_ms=8001;
    INPUT("FIELD01 START\n");
    field01_begin();
    assert(field01_t0==8000 && b5_business_remaining()==149999);
#ifdef MP_TRANSPORT_PROFILE
    assert(profile_resets==1);
#endif
    g_uptime_ms=12999;
    field01_poll();
    assert(!stop_due);
    g_uptime_ms=13000;
    field01_poll();
    assert(stop_due && stop_reason==FIELD01_SOURCE);

    stop_due=false;g_uptime_ms=13001;
    for(unsigned i=0;i<3;i++)gateway.router.enqueued[field_waves[i]]++;
#ifndef MP_AUDIO_DISABLED
    microphone.overruns=1;
    field01_poll();
    assert(stop_due && stop_reason==FIELD01_DMA);
    microphone.overruns=0;stop_due=false;
#endif
    for(unsigned i=1;i<=3;i++){
        g_uptime_ms+=100;
        b4_hw_diag[1].esr=i<<16;
        field01_poll();
    }
    assert(stop_due && stop_reason==FIELD01_CAN);
    stop_due=false;
    INPUT("FIELD01 STOP\n");
    assert(stop_due && stop_reason==FIELD01_MANUAL);
    g_uptime_ms=158000;
    b5_hard_tick();
    assert(stop_reason==FIELD01_MANUAL);
    stop_due=false;
    b5_hard_tick();
    assert(stop_due && stop_reason==FIELD01_TIMER && stop_tick==158000);
    assert(field01_remaining(209999,80000)==1 && !field01_remaining(210000,80000));
    assert((FIELD01_PCM_SAMPLES*2u+511u)/512u==FIELD01_AUDIO_CHUNKS);
    assert((FIELD01_MIN_SAMPLES*2u+511u)/512u==FIELD01_AUDIO_CHUNKS);
    puts("FIELD01_HOST_PASS PRE isolation, one-shot, dirty lock, deadlines, STOP, legacy START and T0");
}
