/* 调用生产入口和 CANopen 网关，硬件与网络接口用替身。 */
#include <stdint.h>
#include <setjmp.h>
static struct {uint32_t CSR;} test_rcc;
#define RCC (&test_rcc)
#define RCC_CSR_RMVF 1u
#define RCC_CSR_SFTRSTF 2u
#define RCC_CSR_PORRSTF 4u
#define RCC_CSR_BORRSTF 8u
#define __disable_irq() ((void)0)
#define __enable_irq() ((void)0)
static void NVIC_SystemReset(void){}
#define main firmware_main
#include "network_main.c"
#undef main
#include <assert.h>

volatile uint32_t g_uptime_ms;
volatile B4HwDiag b4_hw_diag[2];
uint32_t b4_replayed[2];
static jmp_buf first_open;
static void (*poller)(void);
static uint32_t uart_total;
static unsigned retries,acquisitions,stops,local_only_notices,opens;
static unsigned heartbeats[2],time_frames[2];
static bool config_ok=true;
static char last_uart_fault[160];
void console(const char *s){
    if(!strcmp(s,"FIVE AUTO CONFIG_MISSING LOCAL_ONLY\r\n"))local_only_notices++;
    if(!strncmp(s,"GW PASS_LOCAL_FAULT ",sizeof("GW PASS_LOCAL_FAULT ")-1))
        snprintf(last_uart_fault,sizeof last_uart_fault,"%s",s);
}
void platform_init(void){}
void platform_set_poll(void (*callback)(void)){poller=callback;}
void platform_poll(void){
    g_uptime_ms+=5u;
    assert(!stopped && !stops && !opens);
    if(g_uptime_ms==1000u){
        assert(heartbeats[0] && heartbeats[1]);
        assert(!time_frames[0] && !time_frames[1]);
        /* 冷启动没有可信 UTC。注入有效锚点验证本地轮询仍发送周期 TIME。 */
        b4_gateway_sync_ms(&gateway,1800000000000ULL,g_uptime_ms);
    }
    poller();
    if(g_uptime_ms==21000u)config_ok=true;
}
int platform_console_busy(void){return 0;}
void platform_io_snapshot(EspIoMetrics *out){memset(out,0,sizeof *out);}
void platform_cpu_snapshot(EspCpuMetrics *out){memset(out,0,sizeof *out);}
void platform_txcheck_report(uint32_t now){(void)now;}
uint32_t platform_uart_errors_total(void){return uart_total;}
void platform_uart_error_snapshot(EspUartErrors *out){*out=(EspUartErrors){uart_total,1,2,3,4};}
int platform_at_unsynced(void){return 0;}
int platform_at_synchronized(void){return 1;}
int platform_passthrough_soft_reset_safe(void){return 0;}
int platform_passthrough_startup(unsigned *escape_sent,uint32_t *baseline){
    (void)escape_sent;(void)baseline;assert(0);return 0;
}
int gateway_config_valid(void){return config_ok;}
int gateway_network_open(void){assert(config_ok);opens++;longjmp(first_open,1);}
void gateway_network_close(void){assert(0);}
uint64_t gateway_epoch_milliseconds(void){return 1800000000000ULL+g_uptime_ms;}
int gateway_mqtt_open(const MpFrame *f){(void)f;assert(0);return 0;}
int gateway_mqtt_admit(void){return GW_FAILED;}
int gateway_mqtt_begin(const MpFrame *f){(void)f;return GW_FAILED;}
int gateway_mqtt_progress(void){return GW_FAILED;}
int gateway_mqtt_slots_full(void){return 0;}
int gateway_mqtt_ticket_result(uint16_t id){(void)id;return GW_FAILED;}
uint16_t gateway_mqtt_ticket(void){return 0;}
void gateway_mqtt_metrics(GatewayMqttMetrics *out){memset(out,0,sizeof *out);}
void gateway_mqtt_production_diag(GatewayProductionDiag *out,uint32_t now){(void)now;memset(out,0,sizeof *out);}
bool gateway_link_wave_paused(void){return false;}
void gateway_link_diag(GatewayLinkDiag *out){memset(out,0,sizeof *out);}
int gateway_link_retry(PassLinkDrops *drops,unsigned *reentries){
    (void)reentries;retries++;g_uptime_ms+=pass_link_drop(drops);return 1;
}
int gateway_passthrough_acquire(uint32_t *delay){
    acquisitions++;g_uptime_ms+=pass_acquire_backoff(delay);return 1;
}
int b4_hw_init(void){return 0;}
void b4_hw_idle(void){}
void b4_hw_poll(B4Gateway *g){(void)g;}
void b4_hw_stop(void){stops++;}
int b4_bus_transmit(unsigned bus,const MpCanFrame *frame){
    if(frame->ident==0x703u)heartbeats[bus]++;
    if(frame->ident==0x100u){
        assert(frame->dlc==6);
        time_frames[bus]++;
    }
    return 1;
}
int console_char(void){return -1;}

int main(void){
    config_ok=false;
    if(!setjmp(first_open))firmware_main();
    assert(local_only_notices==1 && opens==1 && !stopped && !stops);
    assert(g_uptime_ms==21000u && heartbeats[0]>1 && heartbeats[1]>1);
    assert(time_frames[0]==3 && time_frames[1]==3);
    puts("PASS_AW_CONFIG_MISSING_LOCAL_ONLY_CAN_HEARTBEAT_TIME_NO_NETWORK_UNTIL_VALID");

    PassRecovery recovery={0};uint32_t delay=2000;
    for(unsigned i=0;i<20;i++)assert(pass_reconnect(&recovery,NULL) && !stopped);
    for(unsigned i=0;i<20;i++)assert(pass_reconnect(&recovery,&delay) && !stopped);
    assert(retries==20 && acquisitions==20);
    uart_error_baseline=222;uart_total=223;
    b5_uart_rebase_after_reset(222,223);
    assert(uart_error_baseline==223 && pass_reconnect(&recovery,&delay) && !stopped && acquisitions==21);
    uart_total=224;
    assert(!pass_reconnect(&recovery,NULL) && stopped && retries==20);
    assert(!strcmp(last_uart_fault,"GW PASS_LOCAL_FAULT baseline=223 total=224 ore=1 ne=2 fe=3 overflow=4\r\n"));
    stopped=stop_reported=false;
    uart_total=225;b5_uart_rebase_after_reset(224,225);
    assert(uart_error_baseline==223 && !pass_reconnect(&recovery,&delay) && stopped && acquisitions==21);
    puts("PASS_AX_REBASE_RESUMES_ACQUIRE_AND_STEADY_OR_PRE_RESET_ERRORS_STILL_STOP");
    stopped=stop_reported=false;uart_error_baseline=uart_total=0;
    stop_due=true;
    assert(!pass_reconnect(&recovery,NULL) && stopped && retries==20);
    puts("PASS_AW_PRODUCTION_RECONNECT_NETWORK_RETRIES_LOCAL_UART_STOP_LATCH");
    b4_gateway_close(&gateway);
    return 0;
}
