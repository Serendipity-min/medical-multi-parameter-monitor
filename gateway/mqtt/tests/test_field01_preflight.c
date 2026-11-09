/* 实际 PRE AT 编排，替身模拟两个 UART、回显、分频和错误。 */
#include "gateway_config.h"
#include "gateway_transport.h"
#include "preflight_baud.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>

const GatewayConfig gateway_test_config={
    GATEWAY_CONFIG_MAGIC,1700000000u,"synthetic-wifi","synthetic-pass",
    "mqtt.example.invalid","synthetic-user","synthetic-secret","synthetic-client"
};
volatile uint32_t g_uptime_ms;
enum {NORMAL, WIFI_1, WIFI_2, WIFI_3, WIFI_4, WIFI_NONE, WIFI_LONG, IP_ZERO, IP_ECHO,
      UART_MISSING, UART_BAD, NO_ACK, NO_CHANGE, MISMATCH, LOST_FAST, RESTORE_FAIL,
      STRESS_ERROR, VOLATILE_FAIL, RESET, TIMEOUT};
static unsigned scenario,local_baud,esp_baud,target,gmr_calls,uart_queries,errors,peak;
static int synced,reset_seen,volatile_set,sta_set,switched;
static unsigned deadline;
static char captured[2048],reply[5000];

int platform_at_synchronized(void) {return synced;}
int platform_preflight_esp_reset_seen(void) {return reset_seen;}
int b5_network_stopped(void) {return 0;}
uint32_t platform_uart_errors_total(void) {return errors;}
uint32_t platform_preflight_high_water(uint32_t keep) {uint32_t old=peak;peak=keep;return old;}
const char *at_response(void) {return reply;}
void esp_mqtt_reset(void) {}

int platform_preflight_console(const char *message,uint32_t end) {
    assert(end==deadline && strlen(captured)+strlen(message)<sizeof captured);
    assert(g_uptime_ms<end);
    strcat(captured,message);
    return 1;
}

int platform_preflight_retime(uint32_t baud,uint32_t end) {
    assert(preflight_brr(baud) && end<=deadline);
    g_uptime_ms+=20;
    local_baud=baud;
    synced=1;
    return 1;
}

int at_command(const char *command,uint32_t timeout) {
    assert(synced && !reset_seen && timeout && timeout<=20000u && g_uptime_ms+timeout<=deadline);
    reply[0]=0;
    g_uptime_ms+=5;
    if(local_baud!=esp_baud || (scenario==LOST_FAST && switched)){
        synced=0;
        return 0;
    }
    if(!strcmp(command,"AT") || !strcmp(command,"ATE0"))return 1;
    if(!strcmp(command,"AT+GMR")){
        if(++gmr_calls==3 && scenario==STRESS_ERROR){errors++;synced=0;return 0;}
        if(gmr_calls>1)peak=9;
        strcpy(reply,"AT+GMR\r\nAT version:2.3.0.0-dev\r\nSDK version:synthetic-private\r\nOK\r\n");
        return 1;
    }
    if(!strcmp(command,"AT+UART_CUR?")){
        if(++uart_queries==1 && scenario==UART_MISSING)return 1;
        if(uart_queries==1 && scenario==UART_BAD){strcpy(reply,"+UART_CUR:115200,8,1,0,\r\n");return 1;}
        unsigned reported=scenario==MISMATCH && local_baud!=ESP_UART_BAUD?111111u:esp_baud;
        snprintf(reply,sizeof reply,"AT+UART_CUR?\r\n+UART_CUR:%u,8,1,0,0\r\nOK\r\n",reported);
        return 1;
    }
    if(!strcmp(command,"AT+SYSSTORE=0")){
        if(scenario==VOLATILE_FAIL)return 0;
        return volatile_set=1;
    }
    if(!strcmp(command,"AT+CWMODE=1,0")){assert(volatile_set);return sta_set=1;}
    if(!strcmp(command,"AT+CWJAP=\"synthetic-wifi\",\"synthetic-pass\"")){
        assert(volatile_set && sta_set);
        if(scenario==RESET){reset_seen=1;synced=0;return 0;}
        if(scenario==TIMEOUT){g_uptime_ms+=timeout-5;return 0;}
        if(scenario==WIFI_LONG){memset(reply,'x',sizeof reply-1);reply[sizeof reply-1]=0;return 0;}
        if(scenario>=WIFI_1 && scenario<=WIFI_4){
            snprintf(reply,sizeof reply,"%s\r\n+CWJAP:%d\r\nFAIL\r\n",command,scenario-WIFI_1+1);
            return 0;
        }
        if(scenario==WIFI_NONE){snprintf(reply,sizeof reply,"%s\r\nFAIL\r\n",command);return 0;}
        return 1;
    }
    if(!strcmp(command,"AT+CWJAP?")){
        strcpy(reply,"+CWJAP:\"synthetic-wifi\",\"02:00:00:00:00:01\",11,-29,0\r\nOK\r\n");
        return 1;
    }
    if(!strcmp(command,"AT+CIPSTA?")){
        const char *body=scenario==IP_ZERO?"+CIPSTA:ip:\"0.0.0.0\"":
            scenario==IP_ECHO?"AT+CIPSTA:ip:\"192.0.2.1\"":"+CIPSTA:ip:\"192.0.2.1\"";
        snprintf(reply,sizeof reply,"%s\r\nOK\r\n",body);
        return 1;
    }
    unsigned baud=0;
    int consumed=0;
    assert(sscanf(command,"AT+UART_CUR=%u,8,1,0,0%n",&baud,&consumed)==1 && consumed && !command[consumed]);
    assert(baud==target || baud==ESP_UART_BAUD);
    if(baud!=ESP_UART_BAUD){
        if(scenario==NO_ACK){synced=0;return 0;}
        switched=1;
        if(scenario!=NO_CHANGE)esp_baud=baud;
    }else if(scenario!=RESTORE_FAIL)esp_baud=baud;
    return 1;
}

static void check(unsigned mode,unsigned baud,const char *first,const char *second,int clean) {
    scenario=mode;target=baud;esp_baud=local_baud=ESP_UART_BAUD;
    gmr_calls=uart_queries=errors=peak=0;
    synced=1;reset_seen=volatile_set=sta_set=switched=0;
    g_uptime_ms=1000;deadline=61000;
    captured[0]=reply[0]=0;
    assert(gateway_preflight(baud,deadline)==clean);
    assert(strstr(captured,first) && strstr(captured,second));
    assert(strstr(captured,clean?"PRE RESTORE result=OK":"PRE RESTORE result=FAIL"));
    assert(!strstr(captured,"synthetic") && !strstr(captured,"192.0.2.1") &&
           !strstr(captured,"02:00:00:00:00:01") && !strstr(captured,"AT+"));
    if(clean)assert(esp_baud==ESP_UART_BAUD && local_baud==ESP_UART_BAUD);
    if(strstr(captured," n=50 "))assert(gmr_calls==51);
}

int main(void) {
    assert(preflight_brr(115200)==0x45 && preflight_brr(230400)==0x23 && preflight_brr(500000)==0x10);
    assert(!preflight_brr(460800) && !preflight_baud_matches(500000,460800));
    check(NORMAL,115200,"PRE STRESS rate=115200 n=50 fail=0","PRE END result=PASS",1);
    check(NORMAL,230400,"PRE NEGOTIATE target=230400 result=OK actual=230400","PRE STRESS rate=230400 n=50",1);
    check(NORMAL,500000,"PRE NEGOTIATE target=500000 result=OK actual=500000","PRE STRESS rate=500000 n=50",1);
    for(unsigned i=1;i<=4;i++){
        char line[32];
        snprintf(line,sizeof line,"PRE WIFI ok=0 code=%u ",i);
        check(WIFI_1+i-1,115200,line,"PRE END result=BLOCKED reason=WIFI",1);
    }
    check(WIFI_NONE,115200,"PRE WIFI ok=0 code=NONE","PRE STRESS rate=115200 n=50",1);
    check(WIFI_LONG,115200,"PRE WIFI ok=0 code=NONE","PRE END result=BLOCKED reason=WIFI",1);
    check(IP_ZERO,115200,"PRE IPV4 ready=0","PRE END result=BLOCKED reason=IPV4",1);
    check(IP_ECHO,115200,"PRE IPV4 ready=0","PRE END result=BLOCKED reason=IPV4",1);
    check(UART_MISSING,230400,"PRE UART_CUR baud=NONE","PRE END result=BLOCKED reason=UART_CUR",1);
    check(UART_BAD,230400,"PRE UART_CUR baud=NONE","PRE END result=BLOCKED reason=UART_CUR",1);
    check(NO_ACK,230400,"result=NO_REPLY actual=NONE","PRE END result=BLOCKED reason=NEGOTIATE",1);
    check(NO_CHANGE,230400,"result=NO_SWITCH actual=NONE","PRE END result=BLOCKED reason=NEGOTIATE",1);
    check(MISMATCH,230400,"result=MISMATCH actual=111111","PRE END result=BLOCKED reason=NEGOTIATE",1);
    check(LOST_FAST,230400,"result=RESYNC_FAIL actual=NONE","reason=NEED_POWER_CYCLE",0);
    check(RESTORE_FAIL,500000,"PRE STRESS rate=500000 n=50 fail=0","reason=NEED_POWER_CYCLE",0);
    check(STRESS_ERROR,230400,"n=2 fail=1 uart_err=1","PRE END result=BLOCKED reason=STRESS",1);
    check(VOLATILE_FAIL,115200,"PRE WIFI ok=0 code=NONE","PRE END result=BLOCKED reason=WIFI",1);
    check(RESET,115200,"PRE WIFI ok=0 code=NONE","reason=NEED_POWER_CYCLE",0);
    check(TIMEOUT,115200,"PRE WIFI ok=0 code=NONE ms=20000","PRE END result=BLOCKED reason=WIFI",1);
    puts("FIELD01_PREFLIGHT_AT_PASS cases=22");
}
