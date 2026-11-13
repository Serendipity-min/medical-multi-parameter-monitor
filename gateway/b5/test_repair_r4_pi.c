/* PI摘录反例移到真实platform.c；仅寄存器、时钟和ESP对端字节为桩。 */
#include "gateway_platform.h"
#include "esp_io_metrics.h"
#include "../mqtt/tests/mocks/platform_mmio.h"
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#ifndef REPAIR_PLATFORM_SOURCE
#define REPAIR_PLATFORM_SOURCE "../mqtt/src/platform.c"
#endif
#include REPAIR_PLATFORM_SOURCE
volatile uint32_t g_uptime_ms;
TestUsart platform_usart[2]={{USART_SR_TXE,0},{USART_SR_TXE,0}};
static unsigned char input[2048];
static unsigned input_n,input_i,commands,used,ready_at;
static char command[80];
int b5_network_stopped(void){return 0;}
uint32_t b5_business_remaining(void){return 400000;}
void platform_test_tx(unsigned char b){
    command[used++]=(char)b;
    if(used>=2 && command[used-2]=='\r' && b=='\n'){
        command[used]=0;commands++;used=0;
        if(strstr(command,"CIPRECVLEN")){
            static const char empty[]="\r\n+CIPRECVLEN:0,0,0,0,0\r\n\r\nOK\r\n";
            memcpy(input,empty,sizeof(empty)-1);input_n=sizeof(empty)-1;input_i=0;ready_at=g_uptime_ms+200;
        }
    }
}
static void tick(void){
    g_uptime_ms++;
    if(g_uptime_ms>=ready_at && input_i<input_n){USART3->DR=input[input_i++];USART3->SR|=USART_SR_RXNE;USART3_IRQHandler();USART3->SR&=~USART_SR_RXNE;}
}
int main(int argc,char **argv){
    platform_set_poll(tick);
#ifndef EXPECT_OLD_DEFECT
    if(argc>1 && !strcmp(argv[1],"parser-matrix")){
        static const char *bad[]={"+CIPRECVDATA,48,\r\nOK\r\n","+CIPRECVDATA:257,\r\nOK\r\n",
            "+CIPRECVDATA:-1,\r\nOK\r\n","+CIPRECVDATA:1,\"x\"\r\nOK\r\n"};
        for(unsigned k=0;k<3;k++){
            reply_begin();int result=0;
            for(unsigned i=0;bad[k][i] && !result;i++)result=reply_byte((unsigned char)bad[k][i],0,0);
            assert(result<0);
        }
        reply_begin();static const unsigned char combined[]={'+','C','I','P','R','E','C','V','D','A','T','A',':','4',',',0x40,2,0,1,'\r','\n','+','I','P','D',',','4','\r','\n','O','K','\r','\n'};
        int result=0;for(unsigned i=0;i<sizeof(combined);i++){result=reply_byte(combined[i],0,0);assert(i==sizeof(combined)-1?result==1:result==0);}
        assert(binary_length==4 && binary_seen && !memcmp(reply+binary_offset,"\x40\x02\x00\x01",4));
        puts("REAL_PARSER_BAD_MODE_LENGTH_AND_INTERLEAVED_IPD_PASS");
    }else
#endif
    if(argc>1 && !strncmp(argv[1],"poll",4)){
        unsigned budget=argv[1][4]?(unsigned)atoi(argv[1]+4):5;
        unsigned char out[4];unsigned start=g_uptime_ms;
        int result=esp_mqtt_recv(out,4,budget);
        printf("poll requested=%u elapsed=%u commands=%u result=%d\n",budget,g_uptime_ms-start,commands,result);
#ifdef EXPECT_OLD_DEFECT
        assert(g_uptime_ms-start>5);
#else
        assert(g_uptime_ms-start<=budget && result==0 && commands<=1);
        for(unsigned i=0;i<60;i++){start=g_uptime_ms;assert(esp_mqtt_recv(out,4,5)==0);assert(g_uptime_ms-start<=5);}
        assert(commands<=g_uptime_ms/200u+1u);
#endif
    }else{
        const char *token=argc>1?argv[1]:"\r\nOK\r\n";
        input_n=(unsigned)sprintf((char *)input,"+CIPRECVDATA:48,");
        memset(input+input_n,0,48);memcpy(input+input_n+24,token,strlen(token));input_n+=48;
        memcpy(input+input_n,"\r\nOK\r\n",6);input_n+=6;
        int result=await_reply(1000,0,0);
        printf("binary result=%d consumed=%u total=%u\n",result,input_i,input_n);
#ifdef EXPECT_OLD_DEFECT
        assert(input_i<input_n);
#else
        assert(result==1 && input_i==input_n);
#endif
    }
    return 0;
}
