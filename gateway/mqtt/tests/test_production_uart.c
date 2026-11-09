/* 真实 AT 解析与 USART3 BRR 的 Host 对端。 */
#define PLATFORM_HOST_TEST
#define console production_test_console
#include "../src/gateway_transport.c"
#undef console
#include "../src/platform.c"
#include <assert.h>

const GatewayConfig gateway_test_config={0};
TestUsart platform_usart[2];
volatile uint32_t g_uptime_ms;
enum { NORMAL, REJECT, NO_ACK_OLD, NO_ACK_FAST, GARBAGE_AFTER_ACK, FAST_NO_REPLY,
       QUERY_MISSING, BAD_FLOW, SYSSTORE_REJECT, STOP_DURING_GUARD, H_JUNK, RESTORE_REJECT, RESTORE_NO_ACK, RESTORE_PROBE_FAIL };
static unsigned scenario,peer_baud,peer_flow,setters,restore_setters,accepted;
static int stopped,tx_wrong;
static unsigned degraded,failed,wrong_commands,junk_pending,junk_errors,restore_step;
void production_test_console(const char *line){
    if(!strcmp(line,"GW UART_DEGRADED\r\n"))degraded++;
    if(!strcmp(line,"GW FAIL UART_NEGOTIATE\r\n"))failed++;
    if(!strcmp(line,"BENCH RESTORE step=SETTER\r\n"))restore_step=1;
    if(!strcmp(line,"BENCH RESTORE step=PROBE_BACK\r\n"))restore_step=2;
}
static uint32_t reply_at,garbage_at,stop_at;
static char command[64],queued[80];
static unsigned command_n,queued_i,queued_n;

uint32_t b5_business_remaining(void){return 420000;}
int b5_network_stopped(void){return stopped;}
void b5_uart_accept_baseline(void){assert(gateway_uart_negotiating());accepted++;}

static void schedule(const char *text){
    queued_n=(unsigned)strlen(text);
    memcpy(queued,text,queued_n);
    queued_i=0;reply_at=g_uptime_ms+1;
}

static void receive(unsigned char byte,unsigned status){
    USART3->DR=byte;USART3->SR|=USART_SR_RXNE|status;
    USART3_IRQHandler();USART3->SR&=~(USART_SR_RXNE|status);
}

static void tick(void){
    g_uptime_ms++;
    if(stop_at && g_uptime_ms>=stop_at)stopped=1;
    if(g_uptime_ms==garbage_at)receive('x',USART_SR_FE);
    if(queued_i<queued_n && g_uptime_ms>=reply_at)
        receive((unsigned char)queued[queued_i++],0);
}

void platform_test_tx(unsigned char byte){
    assert(gateway_uart_negotiating());
    tx_wrong|=platform_esp_uart_baud()!=peer_baud;
    assert(USART3->BRR==preflight_brr(platform_esp_uart_baud()));
    assert(command_n+1<sizeof command);
    command[command_n++]=(char)byte;
    if(byte!='\n')return;
    command[command_n]=0;command_n=0;
    if(tx_wrong){
        tx_wrong=0;wrong_commands++;
        if(scenario==H_JUNK)junk_pending=1;
        if(scenario==GARBAGE_AFTER_ACK)schedule("??\r\n");
        return;
    }
    if(!strcmp(command,"AT\r\n")){
        if(junk_pending){
            junk_pending=0;junk_errors++;
            schedule("\r\nERROR\r\n");return;
        }
        if((scenario!=FAST_NO_REPLY || peer_baud!=230400) &&
           (scenario!=RESTORE_PROBE_FAIL || peer_baud!=115200))schedule("\r\nOK\r\n");
        return;
    }
    if(!strcmp(command,"ATE0\r\n")){
        schedule("\r\nOK\r\n");return;
    }
    if(!strcmp(command,"AT+SYSSTORE=0\r\n")){
        schedule(scenario==SYSSTORE_REJECT?"\r\nERROR\r\n":"\r\nOK\r\n");return;
    }
    if(!strcmp(command,"AT+UART_CUR?\r\n")){
        if(scenario==QUERY_MISSING)return;
        char line[64];
        snprintf(line,sizeof line,"\r\n+UART_CUR:%u,8,1,0,%u\r\nOK\r\n",
                 peer_baud==115200?115273:230547,peer_flow);
        schedule(line);return;
    }
    unsigned rate=0,flow=9;
    int n=0;
    assert(sscanf(command,"AT+UART_CUR=%u,8,1,0,%u\r\n%n",&rate,&flow,&n)==2 && n && !command[n]);
    assert(flow==peer_flow);
    if(rate==115200){
        restore_setters++;
        if(scenario==RESTORE_REJECT){schedule("\r\nERROR\r\n");return;}
        peer_baud=rate;
        if(scenario!=RESTORE_NO_ACK)schedule("\r\nOK\r\n");
        return;
    }
    assert(rate==230400 && peer_baud==115200);
    setters++;
    if(scenario==REJECT){schedule("\r\nERROR\r\n");return;}
    if(scenario==NO_ACK_OLD)return;
    peer_baud=rate;
    if(scenario==NO_ACK_FAST)return;
    schedule("\r\nOK\r\n");
    if(scenario==GARBAGE_AFTER_ACK)garbage_at=g_uptime_ms+9;
    if(scenario==STOP_DURING_GUARD)stop_at=g_uptime_ms+9;
}

static void reset(unsigned mode,unsigned baud,unsigned flow){
    scenario=mode;peer_baud=baud;peer_flow=flow;
    wrong_commands=junk_pending=junk_errors=restore_step=0;
    degraded=failed=setters=restore_setters=accepted=command_n=queued_i=queued_n=0;
    g_uptime_ms=garbage_at=stop_at=0;stopped=tx_wrong=0;
    uart_attempted=uart_starting=uart_failed=0;
    io_metrics=(EspIoMetrics){0};
    head=tail=errors=uart_hw_total=uart_overflow_total=0;
    esp_uart_baud=ESP_UART_BAUD;
    USART3->BRR=preflight_brr(ESP_UART_BAUD);USART3->SR=USART_SR_TXE|USART_SR_TC;
    USART1->SR=USART_SR_TXE;USART1->DR=0;
    platform_set_poll(tick);
}
static int open_uart(void){
    char text[64];
    return production_uart_open(text,sizeof text);
}

int main(int argc,char **argv){
    if(argc==2 && !strcmp(argv[1],"--h-junk-legacy")){
        reset(H_JUNK,230400,1);
        assert(!open_uart() && junk_errors==1 && wrong_commands==1);
        reset(H_JUNK,230400,1);
        assert(production_retime(PROD_UART_BAUD));
        uart_starting=1;
        char line[64];
        assert(!production_restore(1,line,sizeof line) && junk_errors==1 && wrong_commands==1 && !restore_setters);
        puts("R9_H_JUNK_LEGACY_REPRODUCED startup=FAIL restore=FAIL wrong_rate=1 next_AT_ERROR=1");
        return 0;
    }
#ifndef R9_LEGACY_REPLAY
    reset(H_JUNK,230400,1);
    assert(open_uart() && junk_errors==1 && wrong_commands==1 && !setters && !failed);
    reset(H_JUNK,230400,1);
    assert(production_retime(PROD_UART_BAUD));
    uart_starting=1;
    char fallback[64];
    assert(production_restore(1,fallback,sizeof fallback) && junk_errors==1 && wrong_commands==1 && restore_setters==1);
    const unsigned cases[]={H_JUNK,RESTORE_REJECT,RESTORE_NO_ACK,RESTORE_PROBE_FAIL};
    for(unsigned i=0;i<sizeof cases/sizeof cases[0];i++){
        reset(cases[i],230400,1);
        assert(production_retime(PROD_UART_BAUD));
        uart_starting=1;
        char line[64];
        int ok=production_restore_fast(1,line,sizeof line,"BENCH RESTORE");
        assert(restore_setters==1 && !wrong_commands && !junk_errors);
        assert(ok==(i==0 || i==2));
        assert(restore_step==(i==1?1u:i==3?2u:0u));
        if(ok)assert(peer_baud==115200 && platform_esp_uart_baud()==115200);
    }
    puts("R9_H_JUNK_FIXED startup=PASS ambiguous=PASS known_restore_wrong_rate=0 setter_and_readback_cases=4");
#endif
    const uint32_t slow_reserve=platform_send_reserve(600);
    assert(preflight_brr(500000)==0);
    for(unsigned flow=0;flow<=1;flow++){
        reset(NORMAL,115200,flow);
        assert(open_uart() && accepted==1 && setters==1 && peer_baud==230400);
        assert(platform_esp_uart_baud()==230400 && platform_send_reserve(600)<slow_reserve);
        assert(open_uart() && accepted==2 && setters==1 && !degraded && !failed);
    }
    for(unsigned mode=REJECT;mode<=GARBAGE_AFTER_ACK;mode++){
        reset(mode,115200,1);
        assert(open_uart() && platform_esp_uart_baud()==115200 && peer_baud==115200 && setters==1);
        assert(restore_setters==(mode==NO_ACK_FAST || mode==GARBAGE_AFTER_ACK));
        assert(degraded==1 && !failed);
        assert(open_uart() && setters==1 && degraded==1 && !failed && platform_send_reserve(600)==slow_reserve);
    }
    for(unsigned mode=FAST_NO_REPLY;mode<=STOP_DURING_GUARD;mode++){
        reset(mode,115200,mode==BAD_FLOW?2:1);
        assert(!open_uart() && !degraded && failed==1 && gateway_uart_negotiation_failed() && !gateway_uart_negotiating());
        unsigned attempts=setters;
        assert(!open_uart() && !degraded && failed==1 && setters==attempts && !accepted);
        if(mode!=STOP_DURING_GUARD)assert(platform_esp_uart_baud()==115200);
        assert(setters==(mode==FAST_NO_REPLY || mode==STOP_DURING_GUARD));
    }
    reset(BAD_FLOW,115200,3);
    assert(!open_uart() && !degraded && failed==1 && !setters);
    reset(NORMAL,230400,1);
    assert(open_uart() && platform_esp_uart_baud()==230400 && !setters);
    EspCpuMetrics cpu;
    memset(&cpu,0xff,sizeof cpu);
    platform_cpu_snapshot(&cpu);
    assert(!cpu.service_calls && !cpu.irq_calls && !cpu.gmr_calls && !cpu.tx_bytes);
    puts("PRODUCTION_UART_HOST_PASS 230400 only, volatile, BRR, guard, bounded fallback, STOP and warm restart");
}
