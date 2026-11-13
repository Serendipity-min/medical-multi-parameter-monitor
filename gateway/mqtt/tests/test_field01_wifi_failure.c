/* 真实入网失败路径，仅替换 ESP 和控制台。 */
#include "gateway_config.h"
#include "gateway_transport.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>

const GatewayConfig gateway_test_config={
    GATEWAY_CONFIG_MAGIC,1700000000u,"synthetic-wifi","synthetic-pass",
    "mqtt.example.invalid","synthetic-user","synthetic-secret","synthetic-client"
};
volatile uint32_t g_uptime_ms;
static const char *reply;
static unsigned steps;
static char captured[256];

void console(const char *message)
{
    assert(strlen(captured)+strlen(message)<sizeof captured);
    strcat(captured,message);
}

void esp_mqtt_reset(void) {}
void delay_ms(uint32_t ms) {(void)ms;assert(0);}
uint32_t platform_uart_errors_total(void) {return 7;}
const char *at_response(void) {return steps==5?"AT version:2.3.0.0\r\n":reply;}

int at_command(const char *command,uint32_t timeout)
{
    static const char *const prefix[]={"AT","ATE0","AT+SYSSTORE=0","AT+CWMODE=1","AT+GMR"};
    unsigned step=steps++;
    if (step<sizeof prefix/sizeof prefix[0]) {
        assert(!strcmp(command,prefix[step]));
        return 1;
    }
    assert(step==5 && timeout==30000 && !strncmp(command,"AT+CWJAP=",9));
    return 0;
}

static void check(const char *response,const char *code)
{
    static const char prefix[]="GW OK AT\r\nGW OK ECHO\r\nGW OK VOLATILE\r\nGW OK STA\r\n"
        "GW AT_VERSION value=2.3.0.0\r\n";
    char expected[sizeof captured];
    reply=response;
    steps=0;
    captured[0]='\0';
    assert(!gateway_network_open() && steps==6);
    snprintf(expected,sizeof expected,"%sGW FAIL WIFI code=%s uart_errors=7\r\n",prefix,code);
    assert(!strcmp(captured,expected));
}

int main(void)
{
    check("\r\n+CWJAP:1\r\nFAIL\r\n","1");
    check("+CWJAP:2\r\nFAIL\r\n","2");
    check("+CWJAP:3\r\nFAIL\r\n","3");
    check("+CWJAP:4\r\nFAIL\r\n","4");
    check("FAIL\r\n","NONE");
    check("+CWJAP:21\r\n+CWJAP:5\r\n+CWJAP:","NONE");
    check("AT+CWJAP=\"synthetic-wifi\",\"synthetic-pass\"\r\n+CWJAP:2\r\nFAIL\r\n","2");
    check("AT+CWJAP=\"+CWJAP:2\",\"synthetic-pass\"\r\nFAIL\r\n","NONE");
    char oversized[8192];
    memset(oversized,'x',sizeof oversized);
    memcpy(oversized+sizeof oversized-sizeof "+CWJAP:1","+CWJAP:1",sizeof "+CWJAP:1");
    check(oversized,"NONE");
    puts("FIELD01_WIFI_FAILURE_CODES_AND_REDACTION_PASS cases=9");
    return 0;
}
