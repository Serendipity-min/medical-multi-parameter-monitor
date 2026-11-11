/* 调用生产重连入口，硬件与事务接口用替身。 */
#include <stdint.h>
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
static uint32_t uart_total;
static unsigned retries,acquisitions;
static bool config_ok=true;
void console(const char *s){(void)s;}
int platform_console_busy(void){return 0;}
void platform_io_snapshot(EspIoMetrics *out){memset(out,0,sizeof *out);}
uint32_t platform_uart_errors_total(void){return uart_total;}
int platform_at_synchronized(void){return 1;}
int platform_passthrough_soft_reset_safe(void){return 0;}
int gateway_config_valid(void){return config_ok;}
int gateway_link_retry(PassLinkDrops *drops,unsigned *reentries){
    (void)reentries;retries++;g_uptime_ms+=pass_link_drop(drops);return 1;
}
int gateway_passthrough_acquire(uint32_t *delay){
    acquisitions++;g_uptime_ms+=pass_acquire_backoff(delay);return 1;
}
void b4_hw_stop(void){}
void mp_router_online(MpRouter *r,bool online){r->online=online;}
int console_char(void){return -1;}

int main(void){
    PassRecovery recovery={0};uint32_t delay=2000;
    for(unsigned i=0;i<20;i++)assert(pass_reconnect(&recovery,NULL) && !stopped);
    for(unsigned i=0;i<20;i++)assert(pass_reconnect(&recovery,&delay) && !stopped);
    assert(retries==20 && acquisitions==20);
    uart_total=1025;assert(!pass_reconnect(&recovery,NULL) && stopped && retries==20);
    stopped=stop_reported=false;uart_total=0;
    config_ok=false;assert(!pass_reconnect(&recovery,NULL) && stopped);
    config_ok=true;stopped=stop_reported=false;stop_due=true;
    assert(!pass_reconnect(&recovery,NULL) && stopped && retries==20);
    puts("PASS_AW_PRODUCTION_RECONNECT_NETWORK_RETRIES_LOCAL_UART_CONFIG_STOP_LATCH");
    return 0;
}
