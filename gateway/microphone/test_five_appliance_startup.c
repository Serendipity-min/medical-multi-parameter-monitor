/* 调用真实启动入口；替换物理端口，验证无配置本地续跑及初始化期间的协作回调。 */
#define main five_appliance_firmware_main
#include "../b5/network_main.c"
#undef main
#include <setjmp.h>
#include <stdlib.h>

static jmp_buf returned;
static unsigned checks,valid_config,hardware_ready,audio_ready,links,nmt,can_ticks,polls,opens,missing,syncs;
static uint32_t sleeps[8];static unsigned sleep_count;
static uint32_t valid_flags=UINT32_MAX,temp_age;
static void (*callback)(void);
volatile uint32_t g_uptime_ms;volatile B4HwDiag b4_hw_diag[2];uint32_t b4_replayed[2];
#define CHECK(x) do{if(!(x)){fprintf(stderr,"FAIL line=%d\n",__LINE__);exit(3);}checks++;}while(0)
void platform_init(void){g_uptime_ms=0;}
void platform_set_poll(void (*f)(void)){callback=f;}
void platform_poll(void){
    g_uptime_ms+=5;if(callback)callback();polls++;
    if(!valid_config && hardware_ready && links==3 && polls>20){CHECK(!opens && !syncs && !gateway.utc_valid && can_ticks && missing);longjmp(returned,2);}
}
void console(const char *s){if(strstr(s,"CONFIG_MISSING"))missing++;}
int console_char(void){return -1;}
uint32_t platform_uart_errors_total(void){return 0;}
int platform_console_busy(void){return 0;}
int platform_at_unsynced(void){return 0;}
int platform_at_synchronized(void){return 1;}
void platform_io_snapshot(EspIoMetrics *out){memset(out,0,sizeof *out);}
void delay_ms(uint32_t n){
    CHECK(sleep_count<8);sleeps[sleep_count++]=n;
    unsigned before=can_ticks;
    for(uint32_t elapsed=0;elapsed<n;elapsed+=5)platform_poll();
    CHECK(can_ticks>before && !stopped);
}
int b4_gateway_init(B4Gateway *g){memset(g,0,sizeof *g);return 0;}
int b4_hw_init(void){CHECK(!armed);hardware_ready=1;platform_poll();return 0;}
void b4_hw_idle(void){}
void b4_hw_stop(void){CHECK(0);}
void b4_hw_poll(B4Gateway *g){(void)g;CHECK(hardware_ready && audio_ready);}
int b4_hw_set_replay(bool on){(void)on;return 0;}
void b4_gateway_tick(B4Gateway *g,uint32_t tick){(void)g;(void)tick;CHECK(hardware_ready);can_ticks++;}
void b4_gateway_link(B4Gateway *g,unsigned bus,bool on){(void)g;CHECK(hardware_ready && on);links|=1u<<bus;}
void b4_gateway_sync_ms(B4Gateway *g,uint64_t utc,uint32_t now){(void)now;CHECK(valid_config && utc && hardware_ready && links==3);g->utc_valid=true;syncs++;}
int b4_gateway_nmt(B4Gateway *g,unsigned node,CO_NMT_command_t command){(void)g;static const unsigned ids[]={1,2,4,5};CHECK(armed && nmt<4 && node==ids[nmt++] && command==CO_NMT_ENTER_OPERATIONAL);return 0;}
uint32_t mp_od_read(MpOD *od,uint16_t index,uint8_t sub){(void)od;return (index&255)==0x30 && sub==1?valid_flags:(index&255)==0x20 && sub==4?temp_age:0;}
void unified_audio_init(void){CHECK(!armed);audio_ready=1;platform_poll();CHECK(!can_ticks);}
void unified_audio_local_poll(void){}
void unified_audio_key(bool pressed){(void)pressed;}
bool b4_gateway_online(B4Gateway *g,unsigned node){(void)g;(void)node;return true;}
void unified_audio_command(int c,bool export_allowed){(void)c;(void)export_allowed;CHECK(0);}
void unified_audio_stop(void){}
void unified_audio_network(bool online){CHECK(!online);}
void unified_audio_report(void){}
bool unified_audio_quiet(void){return true;}
bool unified_audio_send_due(void){return false;}
void unified_audio_step(bool allowed){(void)allowed;CHECK(0);}
void unified_audio_wait(unsigned mask){(void)mask;}
int gateway_audio_pending(void){return 0;}
int gateway_audio_configure(const uint8_t *p,size_t n){(void)p;(void)n;return 0;}
int gateway_audio_subscribe(void){CHECK(mqtt_connected && retry_ms==2000 && syncs==1);longjmp(returned,1);}
int gateway_config_valid(void){return (int)valid_config;}
uint64_t gateway_epoch_milliseconds(void){return 1800000000000ULL+g_uptime_ms;}
int gateway_network_open(void){opens++;CHECK(armed && !run_limit_ms && final_can_mask==3 && hardware_ready && audio_ready && links==3 && nmt==4);return opens>=7;}
int gateway_network_retryable(void){return 0;}
void gateway_network_close(void){}
int gateway_mqtt_open(const MpFrame *f){CHECK(f->node==3 && f->stream==MP_GATEWAY_STATUS && network_open && syncs==1);return 1;}
void gateway_mqtt_metrics(GatewayMqttMetrics *out){memset(out,0,sizeof *out);}
int gateway_mqtt_progress(void){CHECK(0);return GW_FAILED;}
int gateway_mqtt_admit(void){CHECK(0);return GW_FAILED;}
int gateway_mqtt_begin(const MpFrame *f){(void)f;CHECK(0);return GW_FAILED;}
uint16_t gateway_mqtt_ticket(void){return 0;}
int gateway_mqtt_ticket_result(uint16_t id){(void)id;return GW_FAILED;}
int gateway_mqtt_slots_full(void){return 0;}

int main(void){
    for(volatile unsigned valid=0;valid<2;valid++){
        valid_config=valid;hardware_ready=audio_ready=links=nmt=can_ticks=polls=opens=missing=syncs=0;
        armed=stopped=service_seen=network_fault=network_open=mqtt_connected=runtime_ready=false;
        callback=NULL;int reason=setjmp(returned);
        if(!reason)five_appliance_firmware_main();
        CHECK(reason==(valid?1:2));
    }
    b4_hw_diag[0].busoff=b4_hw_diag[0].tx_failed=1;g_uptime_ms+=5;service();CHECK(!stopped && can_ticks);
    const uint32_t expected[]={2000,4000,8000,16000,30000,30000};CHECK(sleep_count==6 && opens==7 && !memcmp(sleeps,expected,sizeof expected));
    gateway.utc_valid=true;gateway.session=123;
    B4Remote *d=&gateway.segments[1].remote[1];d->observed_boot=1;d->generation=77;d->seq[MP_TEMP]=2;d->seen[4]=true;
    CHECK(unified_audio_fact_current(4,MP_TEMP,1,123,1));
    valid_flags=0;CHECK(!unified_audio_fact_current(4,MP_TEMP,1,123,1));valid_flags=UINT32_MAX;
    temp_age=2501;CHECK(!unified_audio_fact_current(4,MP_TEMP,1,123,1));temp_age=0;
    CHECK(!unified_audio_fact_current(4,MP_TEMP,1,1,77));
    d->observed_boot++;CHECK(!unified_audio_fact_current(4,MP_TEMP,1,123,1));
    B4Remote *e=&gateway.segments[0].remote[1];e->observed_boot=2;e->seq[MP_NIBP]=3;e->seen[1]=e->seen[4]=true;
    CHECK(unified_audio_fact_current(5,MP_NIBP,3,123,2));
    CHECK(!unified_audio_fact_current(5,MP_NIBP,2,123,2));
    gateway.utc_valid=false;CHECK(!unified_audio_fact_current(5,MP_NIBP,3,123,2));
    printf("HOST_FIVE_APPLIANCE_STARTUP_PASS checks=%u config_missing_local_only=1 init_callback_safe=1 backoff_max_ms=30000 hardware=NOT_RUN\n",checks);
    return 0;
}
