/* 运行实际platform.c，仅USART寄存器及对端字节为夹具。 */
#include "gateway_platform.h"
#include "esp_io_metrics.h"
#include "../mqtt/tests/mocks/platform_mmio.h"
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
volatile uint32_t g_uptime_ms;
TestUsart platform_usart[2]={{USART_SR_TXE,0},{USART_SR_TXE,0}};
static unsigned stop_at=100000,cut_phase,wire_bytes,required,data_written;
static char command[80],response[80];static unsigned used,ri,rn;
static const char *terminal;
void USART3_IRQHandler(void);
int b5_network_stopped(void){return g_uptime_ms>=stop_at;}
uint32_t b5_business_remaining(void){return g_uptime_ms>=stop_at?0:stop_at-g_uptime_ms;}
static void queue(const char *s){strcpy(response,s);ri=0;rn=(unsigned)strlen(s);}
void platform_test_tx(unsigned char byte){
    wire_bytes++;
    if(required){data_written++;if(data_written==required){required=0;queue(terminal?terminal:"\r\nSEND OK\r\n");}return;}
    command[used++]=(char)byte;
    if(used>=2 && command[used-2]=='\r' && byte=='\n'){
        command[used]=0;
        if(sscanf(command,"AT+CIPSEND=%u",&required)==1)queue(">");else queue("\r\nOK\r\n");
        used=0;
    }
}
static void tick(void){
    g_uptime_ms++;
    EspIoMetrics io;platform_io_snapshot(&io);
    if(cut_phase && io.at_phase==cut_phase && (cut_phase!=ESP_AT_DATA || data_written>=3))stop_at=g_uptime_ms;
    if(ri<rn){USART3->DR=(unsigned char)response[ri++];USART3->SR|=USART_SR_RXNE;USART3_IRQHandler();USART3->SR&=~USART_SR_RXNE;}
}
int main(int argc,char **argv){
    if(argc>1 && !strcmp(argv[1],"short854")){
        platform_set_poll(tick);unsigned char data[854]={0x30};int result=esp_mqtt_send(data,854,50);
#ifdef EXPECT_OLD_DEFECT
        assert(result<0 && wire_bytes>0 && data_written<854);
        printf("DEPLOYED_REAL_PLATFORM_854B_50MS_STARTS_IMPOSSIBLE_SEND wire=%u data=%u\n",wire_bytes,data_written);
#else
        assert(result<0 && !wire_bytes && platform_at_synchronized());
        puts("854B_50MS_NOT_ADMITTED_ZERO_UART_PASS");
#endif
        return 0;
    }
    if(argc>1 && !strcmp(argv[1],"budget")){
        platform_set_poll(tick);stop_at=6000;unsigned char data[12]={0x30};
        assert(esp_mqtt_send(data,12,5000)<0 && !wire_bytes && platform_at_synchronized());
        puts("INSUFFICIENT_5S_PLUS_2S_BUDGET_REFUSED_BEFORE_ANY_UART_BYTE");return 0;
    }
    if(argc>1) {
        if(!strcmp(argv[1],"closed"))terminal="\r\nCLOSED\r\n";
        if(!strcmp(argv[1],"ready"))terminal="\r\nready\r\n";
        if(!strcmp(argv[1],"busy"))terminal="busy s...\r\n";
        if(!strcmp(argv[1],"silent"))terminal="";
        if(!strcmp(argv[1],"sendfail"))terminal="SEND FAIL\r\n";
    }
    cut_phase=argc>1?(unsigned)atoi(argv[1]):0;platform_set_poll(tick);
    unsigned char payload[12]={0x30};int result=esp_mqtt_send(payload,12,5000);EspIoMetrics io;platform_io_snapshot(&io);
    if(terminal) {
        assert(result<0 && io.written==12);
        if(!strcmp(argv[1],"sendfail")){assert(io.wait_reason==4 && !io.unsynced);assert(at_command("AT+CIPCLOSE",2000));}
        else{assert(io.wait_reason==(!strcmp(argv[1],"silent")?10u:11u) && io.unsynced);unsigned expected=!strcmp(argv[1],"closed")?1u:!strcmp(argv[1],"ready")?2u:!strcmp(argv[1],"busy")?4u:0u;assert(io.reply_flags==expected);unsigned before=wire_bytes;assert(!at_command("AT+CIPCLOSE",2000) && wire_bytes==before);}
        puts("SEND_TERMINAL_DIAGNOSTICS_WITHOUT_WEAKENING_BOUNDARY_PASS");
    }else if(cut_phase){assert(result<0 && io.unsynced);unsigned before=wire_bytes;assert(!at_command("AT+CIPCLOSE",2000) && wire_bytes==before);
        esp_mqtt_reset();assert(!platform_at_synchronized() && !at_command("AT+CIPCLOSE",2000) && wire_bytes==before);
        if(cut_phase==ESP_AT_DATA)assert(io.written==3 && io.required==12);
        printf("STOP_PHASE_%u_UNSYNCED_NO_BLIND_CLOSE written=%lu required=%lu\n",cut_phase,(unsigned long)io.written,(unsigned long)io.required);
    }else{assert(result==12 && !io.unsynced && io.written==12);assert(at_command("AT+CIPCLOSE",2000));puts("EXACT_DATA_AND_SAFE_CLOSE_PASS");}
    return 0;
}
