/* Host 只调用真实探针入口和停止锁存；不打开设备或网络。 */
#define main field01_firmware_main
#include "../b5/network_main.c"
#undef main
#include <assert.h>

volatile uint32_t g_uptime_ms;
volatile B4HwDiag b4_hw_diag[2];
static const unsigned char *command;
static size_t remaining;
static bool config_valid,subscribed,op;
static MicDiag microphone;

int console_char(void) {
    if(!remaining)return -1;
    remaining--;return *command++;
}
void console(const char *line){(void)line;}
uint32_t platform_uart_errors_total(void){return 0;}
int platform_at_synchronized(void){return 1;}
void platform_io_snapshot(EspIoMetrics *out){memset(out,0,sizeof *out);}
int gateway_config_valid(void){return config_valid;}
int gateway_audio_ready(void){return subscribed;}
bool b4_gateway_online(B4Gateway *g,unsigned node){(void)g;(void)node;return op;}
void mic_diagnostics(MicDiag *out){*out=microphone;}

static void input(const char *line,size_t size) {
    command=(const unsigned char *)line;remaining=size;
    while(remaining)local_control();
}
#define INPUT(s) input(s,sizeof(s)-1)
int main(void) {
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
    assert(!field_key_approved);
    gateway.utc_valid=true;subscribed=true;op=true;
    field01_begin();
    assert(!field01_t0);
    for(unsigned bus=0;bus<2;bus++)for(unsigned slot=0;slot<2;slot++)
        gateway.segments[bus].remote[slot].seen[4]=true;
    field01_begin();
    assert(field01_t0==8000 && b5_business_remaining()==150000);
    INPUT("FIELD01 KEY\n");
    assert(field_key_approved);
    g_uptime_ms=8001;
    INPUT("FIELD01 START\n");
    field01_begin();
    assert(field01_t0==8000 && b5_business_remaining()==149999);
    g_uptime_ms=12999;
    field01_poll();
    assert(!stop_due);
    g_uptime_ms=13000;
    field01_poll();
    assert(stop_due && stop_reason==FIELD01_SOURCE);

    stop_due=false;g_uptime_ms=13001;
    for(unsigned i=0;i<3;i++)gateway.router.enqueued[field_waves[i]]++;
    microphone.overruns=1;
    field01_poll();
    assert(stop_due && stop_reason==FIELD01_DMA);
    microphone.overruns=0;stop_due=false;
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
    puts("FIELD01_HOST_PASS exact commands, readiness, hard cutoff, STOP, source, DMA, CAN, MC01 length");
}
