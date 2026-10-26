/* 编译真实network_main入口，替换设备/网络边界，核验武装、B-only及有限停止顺序。 */
#include "b5_policy.h"
#include "../dual_can/b4_bxcan.h"
#include "gateway_transport.h"
#include <assert.h>
#include <setjmp.h>
#include <stdio.h>
#include <string.h>
static jmp_buf finished;
static void (*poller)(void);
static const char script[]="B5START\nxxxxxxxxxB5START\nB5START\n";
static unsigned pos,configs,opens,closes,nmts,stops;
static int overflow_case;
volatile uint32_t g_uptime_ms;
volatile B4HwDiag b4_hw_diag[2];
int b5_firmware_main(void);
void platform_init(void) {}
void platform_set_poll(void (*fn)(void)){poller=fn;}
void platform_poll(void){g_uptime_ms+=1000;if(poller)poller();}
int console_char(void){if(pos>=sizeof(script)-1)return -1;return script[pos++];}
void console(const char *s){(void)s;}
int platform_console_busy(void){return 0;}
uint32_t platform_uart_errors_total(void){return 0;}
void delay_ms(uint32_t ms){g_uptime_ms+=ms;platform_poll();}
int gateway_config_valid(void){configs++;return configs>1;}
int gateway_network_open(void){assert(pos==sizeof(script)-1 && configs==2);opens++;return 1;}
int gateway_mqtt_open(const MpFrame *f){assert(f->synthetic && !f->valid && f->stream==MP_GATEWAY_STATUS);return 1;}
int gateway_mqtt_publish(const MpFrame *f){assert(f->synthetic);return 1;}
int gateway_mqtt_yield(void){if(overflow_case && g_uptime_ms>30000)b4_hw_diag[1].overflow=1;return 1;}
void gateway_network_close(void){closes++;}
uint64_t gateway_epoch_milliseconds(void){return 1800000000000ULL+g_uptime_ms;}
int b4_gateway_init(B4Gateway *g){memset(g,0,sizeof(*g));return 0;}
int b4_hw_init(void){return 0;}
void b4_gateway_tick(B4Gateway *g,uint32_t tick){g->now=tick;}
void b4_hw_poll(B4Gateway *g){(void)g;}
void b4_gateway_link(B4Gateway *g,unsigned bus,bool up){(void)g;assert(bus==0 && !up);}
void b4_gateway_sync_ms(B4Gateway *g,uint64_t utc,uint32_t now){(void)g;(void)utc;(void)now;}
int b4_gateway_nmt(B4Gateway *g,unsigned node,CO_NMT_command_t cmd){(void)g;assert(node==2 && cmd==CO_NMT_ENTER_OPERATIONAL);nmts++;return 0;}
void b4_hw_stop(void){stops++;}
void b4_hw_idle(void){if(b5_network_stopped())longjmp(finished,1);else assert(!opens && !nmts);}
void mp_router_online(MpRouter *r,bool online){r->online=online;}
void mp_router_put(MpRouter *r,const MpFrame *f){(void)r;assert(f->synthetic);}
bool mp_router_take(MpRouter *r,MpFrame *f,uint32_t now){(void)r;(void)f;(void)now;return false;}
void mp_router_ack(MpRouter *r,const MpFrame *f,bool ok){(void)r;(void)f;(void)ok;}
int main(int argc,char **argv){
    (void)argv;overflow_case=argc>1;
    if(!setjmp(finished))b5_firmware_main();
    assert(opens==1 && closes==1 && nmts==1 && stops==1);
    assert(overflow_case?g_uptime_ms<100000:g_uptime_ms>=B5_WINDOW_MS);
    printf("ENTRY_PASS %s no_auto_network bad_config_and_overlong_line_refused B_only stop_once no_rearm\n",overflow_case?"OVERFLOW":"420S");
    return 0;
}
