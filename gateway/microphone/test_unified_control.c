/* 调用真实C主入口的控制/服务方法；硬件和音频端口为替身。 */
#define main unified_firmware_main
#include "../b5/network_main.c"
#undef main
#include <stdlib.h>
static unsigned checks,can_ticks,can_stops,audio_polls,audio_commands,audio_stops,configs;
static int sync_bad;static uint8_t input[1024];static unsigned head,tail;
uint32_t b4_replayed[2];
int b4_hw_set_replay(bool enabled){(void)enabled;return !final_can_mask;}
volatile B4HwDiag b4_hw_diag[2];volatile uint32_t g_uptime_ms;
#define CHECK(x) do{if(!(x)){fprintf(stderr,"FAIL line=%d\n",__LINE__);exit(3);}checks++;}while(0)
int console_char(void){return tail<head?input[tail++]:-1;}
void console(const char *s){(void)s;}
int gateway_config_valid(void){return 1;}
int gateway_audio_configure(const uint8_t *p,size_t n){(void)p;CHECK(n==249);configs++;return 1;}
void unified_audio_command(int c,bool export_allowed){(void)c;(void)export_allowed;audio_commands++;}
void unified_audio_stop(void){audio_stops++;}
void unified_audio_local_poll(void){audio_polls++;}
void unified_audio_network(bool connected){CHECK(!connected);}
void b4_hw_idle(void){}
void b4_hw_stop(void){can_stops++;}
void b4_hw_poll(B4Gateway *g){(void)g;}
void b4_gateway_tick(B4Gateway *g,uint32_t tick){(void)g;(void)tick;can_ticks++;}
void b4_gateway_sync_ms(B4Gateway *g,uint64_t utc,uint32_t now){(void)g;(void)utc;(void)now;}
uint64_t gateway_epoch_milliseconds(void){return 1800000000000ULL+g_uptime_ms;}
void mp_router_online(MpRouter *r,bool online){r->online=online;}
void mp_router_put(MpRouter *r,const MpFrame *f){(void)r;(void)f;}
int platform_console_busy(void){return 0;}
int platform_at_unsynced(void){return sync_bad;}
uint32_t platform_uart_errors_total(void){return 0;}
void platform_io_snapshot(EspIoMetrics *out){memset(out,0,sizeof *out);}
static void feed(const void *p,unsigned n) {
    CHECK(n<=sizeof input);memcpy(input,p,n);head=n;tail=0;
    while(tail<head)local_control();
}
static void textline(const char *s){feed(s,(unsigned)strlen(s));}
int main(void) {
    textline("UNISTART C\n");CHECK(armed && !final_can_mask && !run_limit_ms);
    g_uptime_ms=1000000;armed_at=0;b5_hard_tick();CHECK(!stop_due && b5_business_remaining()>420000);
    armed=false;textline("UNISTART BC\n");CHECK(armed && final_can_mask==2);
    armed=false;textline("UNISTART ABC\n");CHECK(armed && final_can_mask==3);
    armed=false;textline("B5START\n");CHECK(armed && run_limit_ms==420000);
    g_uptime_ms=420000;b5_hard_tick();CHECK(stop_due && !can_stops);stop_due=false;
    armed=false;textline("XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXUNISTART ABC\n");CHECK(!armed);
    uint8_t frame[250];frame[0]='F';memset(frame+1,'X',249);feed(frame,250);
    CHECK(configs==1 && !armed && !can_stops && !audio_commands);
    textline("UNISTART BC\n");feed(frame,250);CHECK(configs==1 && !can_stops && !audio_commands);
    textline("RS");CHECK(audio_commands==2);
    g_uptime_ms=100;armed_at=0;service_seen=false;network_open=mqtt_connected=true;sync_bad=1;
    service();CHECK(network_fault && can_ticks==1 && !can_stops && audio_polls>0);
    CHECK(b5_network_stopped());sync_bad=0;network_fault=false;
    textline("X");CHECK(stopped && can_stops==1 && audio_stops==1);
    unsigned before=audio_commands;textline("R");CHECK(audio_commands==before);
    printf("HOST_UNIFIED_CONTROL_PASS checks=%u CAN_CONTINUES_ON_NETWORK_FAULT hardware=NOT_RUN\n",checks);
    return 0;
}
