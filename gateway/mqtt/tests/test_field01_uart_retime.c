#define PLATFORM_HOST_TEST
#include "../src/platform.c"
#include <assert.h>

TestUsart platform_usart[2];
volatile uint32_t g_uptime_ms;
static uint32_t inject_at,stop_at;
uint32_t b5_business_remaining(void){return 10000;}
int b5_network_stopped(void){return stop_at && g_uptime_ms>=stop_at;}
void platform_test_tx(unsigned char byte){(void)byte;}

static void tick(void) {
    ++g_uptime_ms;
    if(g_uptime_ms==inject_at){
        USART3->DR='x';USART3->SR|=USART_SR_RXNE;
        USART3_IRQHandler();
        USART3->SR&=~USART_SR_RXNE;
    }
}

int main(void) {
    platform_set_poll(tick);
    USART3->BRR=0x45;USART3->CR1=USART_CR1_UE;USART3->SR=USART_SR_TXE|USART_SR_TC;
    assert(platform_preflight_retime(460800,100)==PRE_RETIME_BRR);
    errors=3;uart_hw_total=3;unsync();
    assert(platform_preflight_retime(230400,100)==PRE_RETIME_OK);
    assert(g_uptime_ms==20 && USART3->BRR==0x23 && USART3->CR1==USART_CR1_UE);
    assert(!errors && platform_uart_errors_total()==3 && platform_at_synchronized());
    inject_at=27;
    assert(platform_preflight_retime(500000,100)==PRE_RETIME_RX_NOT_QUIET);
    assert(g_uptime_ms==27 && USART3->BRR==0x23 && head!=tail);
    assert(platform_preflight_high_water(0)==1);
    assert(platform_preflight_retime(500000,100)==PRE_RETIME_OK && USART3->BRR==0x10 && head==tail);
    assert(platform_preflight_retime(115200,g_uptime_ms)==PRE_RETIME_DEADLINE);
    USART3->SR&=~USART_SR_TC;
    assert(platform_preflight_retime(115200,50)==PRE_RETIME_TC && g_uptime_ms==50);
    stop_at=55;
    assert(platform_preflight_retime(115200,100)==PRE_RETIME_STOP && g_uptime_ms==55);
    assert(USART3->BRR==0x10);
    USART1->SR=0;
    assert(!platform_preflight_console("PRE END",60) && g_uptime_ms==60);
    stop_at=0;
    reply_begin();
    const char *line="ready\r\n";
    for(;*line;line++)(void)reply_byte(*line,0,0);
    USART3->SR|=USART_SR_TC;
    assert(platform_preflight_esp_reset_seen() && platform_preflight_retime(115200,100)==PRE_RETIME_STOP);
    puts("FIELD01_PREFLIGHT_MMIO_PASS whitelist, RX quiet, TC, STOP, console deadline, reset");
}
