/* 编译真实network_main入口，替换设备/网络边界，核验武装、B-only及有限停止顺序。 */
#include "b5_policy.h"
#include "../dual_can/b4_bxcan.h"
#include "gateway_transport.h"
#include "esp_io_metrics.h"
#include <assert.h>
#include <setjmp.h>
#include <stdio.h>
#include <string.h>
static jmp_buf finished;
static void (*poller)(void);
static const char script[]="B5START\nxxxxxxxxxB5START\nB5START\n";
static unsigned pos,configs,opens,closes,nmts,stops,notice_count,ticks,polls,callbacks;
static uint32_t arm_tick,notice_tick;
static int overflow_case,inflight_case,wrap_case,open_fail_case;
static int retry_then_pass_case,retry_exhaust_case;
volatile uint32_t g_uptime_ms;
volatile B4HwDiag b4_hw_diag[2];
int b5_firmware_main(void);
void platform_init(void) {}
void platform_set_poll(void (*fn)(void)){poller=fn;}
void platform_poll(void){g_uptime_ms++;
#ifdef MP_B5_EGRESS_FINAL
    b5_hard_tick();
#endif
    polls++;if(poller)for(unsigned i=0;i<16;i++){callbacks++;poller();if(b5_network_stopped())break;}}
int console_char(void){if(pos>=sizeof(script)-1)return -1;return script[pos++];}
void console(const char *s){
    if(!strcmp(s,"B5 STOPPED NO_AUTOREARM\r\n")){notice_count++;notice_tick=g_uptime_ms;}
    if(strstr(s,"stop=1")){assert(notice_count==1);assert(strstr(s,"mqtt_fail=0"));}
}
int platform_console_busy(void){return 0;}
uint32_t platform_uart_errors_total(void){return 0;}
void platform_io_snapshot(EspIoMetrics *out){memset(out,0,sizeof(*out));}
void delay_ms(uint32_t ms){g_uptime_ms+=ms;platform_poll();}
int gateway_config_valid(void){configs++;return configs>1;}
int gateway_network_open(void){assert(pos==sizeof(script)-1 && configs==2);opens++;return !open_fail_case && !retry_exhaust_case && (!retry_then_pass_case || opens>2);}
int gateway_mqtt_open(const MpFrame *f){assert(f->synthetic && !f->valid && f->stream==MP_GATEWAY_STATUS);return 1;}
int gateway_mqtt_publish(const MpFrame *f){assert(f->synthetic);while(!b5_network_stopped())platform_poll();return 0;}
int gateway_mqtt_yield(void){if(overflow_case && g_uptime_ms>30000)b4_hw_diag[1].overflow=1;return 1;}
void gateway_network_close(void){
#ifndef MP_B5_EGRESS_FINAL
    assert(notice_count==1);
#else
    assert(b5_business_remaining()>=2000 || b5_network_stopped());
#endif
    closes++;g_uptime_ms+=2000;}
#ifdef MP_B5_EGRESS_FINAL
int platform_at_unsynced(void){return 0;}
int gateway_network_retryable(void){return retry_then_pass_case || retry_exhaust_case;}
int gateway_mqtt_begin(const MpFrame *f){(void)f;return GW_COMPLETE;}
int gateway_mqtt_progress(void){if(overflow_case && g_uptime_ms>30000)b4_hw_diag[1].overflow=1;return GW_COMPLETE;}
int gateway_mqtt_pending(void){return 0;}
void gateway_mqtt_metrics(GatewayMqttMetrics *out){memset(out,0,sizeof(*out));}
bool mp_router_take_egress(MpRouter *r,MpFrame *f,uint32_t now,uint64_t utc,bool pending){
    (void)utc;(void)pending;return mp_router_take(r,f,now);}
#endif
uint64_t gateway_epoch_milliseconds(void){return 1800000000000ULL+g_uptime_ms;}
int b4_gateway_init(B4Gateway *g){memset(g,0,sizeof(*g));return 0;}
int b4_hw_init(void){return 0;}
void b4_gateway_tick(B4Gateway *g,uint32_t tick){g->now=tick;ticks++;}
void b4_hw_poll(B4Gateway *g){(void)g;}
void b4_gateway_link(B4Gateway *g,unsigned bus,bool up){(void)g;assert(bus==0 && !up);}
void b4_gateway_sync_ms(B4Gateway *g,uint64_t utc,uint32_t now){(void)g;(void)utc;(void)now;}
int b4_gateway_nmt(B4Gateway *g,unsigned node,CO_NMT_command_t cmd){(void)g;assert(node==2 && cmd==CO_NMT_ENTER_OPERATIONAL);nmts++;arm_tick=g_uptime_ms;return 0;}
void b4_hw_stop(void){stops++;}
void b4_hw_idle(void){if(b5_network_stopped())longjmp(finished,1);else assert(!opens && !nmts);}
void mp_router_online(MpRouter *r,bool online){r->online=online;}
void mp_router_put(MpRouter *r,const MpFrame *f){(void)r;assert(f->synthetic);}
bool mp_router_take(MpRouter *r,MpFrame *f,uint32_t now){(void)r;(void)now;if(inflight_case){memset(f,0,sizeof(*f));f->synthetic=true;f->timestamp=gateway_epoch_milliseconds();return true;}return false;}
void mp_router_ack(MpRouter *r,const MpFrame *f,bool ok){(void)r;(void)f;(void)ok;assert(!b5_network_stopped());}
int main(int argc,char **argv){
    overflow_case=argc>1 && !strcmp(argv[1],"overflow");inflight_case=argc>1 && !strcmp(argv[1],"inflight");wrap_case=argc>1 && !strcmp(argv[1],"wrap");
    open_fail_case=argc>1 && !strcmp(argv[1],"openfail");
    retry_then_pass_case=argc>1 && !strcmp(argv[1],"retry-pass");retry_exhaust_case=argc>1 && !strcmp(argv[1],"retry-exhaust");
    if(wrap_case)g_uptime_ms=0xffff0000u;
    if(!setjmp(finished))b5_firmware_main();
    assert(opens==((retry_then_pass_case||retry_exhaust_case)?3u:1u) && closes==1 && nmts==1 && stops==1);
    assert(notice_count==1 && ticks<=polls && ticks*8<callbacks);
    assert(ticks<=(polls+B5_SERVICE_MS-1)/B5_SERVICE_MS);
    assert(overflow_case||open_fail_case||retry_exhaust_case?(uint32_t)(notice_tick-arm_tick)<B5_WINDOW_MS:(uint32_t)(notice_tick-arm_tick)==B5_WINDOW_MS);
    printf("ENTRY_PASS %s stop_offset_ms=%lu poll_calls=%u CAN_ticks=%u cleanup_after_notice=1\n",overflow_case?"OVERFLOW":inflight_case?"INFLIGHT":wrap_case?"WRAP":"420S",(unsigned long)(notice_tick-arm_tick),callbacks,ticks);
    return 0;
}
