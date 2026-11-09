/* 直接编译实际授时函数，只替换ESP边界，确保不放宽1秒门。 */
#include "../mqtt/src/gateway_transport.c"
#include <assert.h>
const GatewayConfig gateway_test_config={GATEWAY_CONFIG_MAGIC,1700000000U,
    "synthetic-wifi","synthetic-password","mqtt.example.invalid","b5-gateway","synthetic-password","b5-c-isolated"};
volatile uint32_t g_uptime_ms;
static int mode,part,opens,closes;
#ifdef MP_FIVE_FIELD01
static uint32_t remaining_ms;
static int stopped;
uint32_t b5_business_remaining(void){return remaining_ms;}
int b5_network_stopped(void){return stopped;}
uint32_t platform_uart_errors_total(void){return 0;}
#endif
static unsigned char request_bytes[48],previous_nonce[8];
static const char *response="+CIPSNTPCFG:1,0,\"ntp-0.example.invalid\",\"ntp-1.example.invalid\",\"ntp-2.example.invalid\"\r\nOK\r\n";
void console(const char *text){(void)text;}
void platform_poll(void){g_uptime_ms++;}
void delay_ms(uint32_t ms){g_uptime_ms+=ms;}
int platform_at_synchronized(void){return mode!=5;}
int platform_at_unsynced(void){return mode==5;}
int platform_send_admissible(unsigned bytes,uint32_t budget){(void)bytes;(void)budget;return 1;}
void platform_tx_context(unsigned qos,unsigned stream,uint32_t seq,unsigned pending,uint32_t age,uint32_t budget){(void)qos;(void)stream;(void)seq;(void)pending;(void)age;(void)budget;}
int at_command(const char *command,uint32_t timeout){
    (void)timeout;
    if(!strncmp(command,"AT+CIPSTART=",12)){
        char selected[32];snprintf(selected,sizeof(selected),"ntp-%d.example.invalid",opens%3);
        assert(strstr(command,selected));opens++;
    }
    if(!strcmp(command,"AT+CIPCLOSE")){closes++;return mode!=4;}
    return 1;
}
const char *at_response(void){return response;}
void esp_mqtt_reset(void){}
int esp_mqtt_send(const unsigned char *data,int length,uint32_t timeout){
    assert(length==48 && timeout==1000);memcpy(request_bytes,data,48);
    if(opens>1)assert(memcmp(previous_nonce,data+40,8));
    memcpy(previous_nonce,data+40,8);return mode==2?47:48;
}
int esp_mqtt_recv(unsigned char *data,int length,uint32_t timeout){
    if(mode==0 || mode==4 || mode==5 || (mode==3 && part++) || (mode==7 && opens==1)){
        g_uptime_ms+=timeout;return 0;
    }
    unsigned char reply[48]={0};reply[0]=0x24;reply[1]=1;
    memcpy(reply+24,request_bytes+40,8);if(mode==6)reply[24]^=1;
    sntp_put32(reply+32,1800000000U+2208988800U);sntp_put32(reply+40,1800000000U+2208988800U);
#ifdef MP_FIVE_FIELD01
    if(mode==7){
        uint32_t elapsed=g_uptime_ms+50u-epoch_tick;
        uint32_t second=epoch+elapsed/1000u+2208988800u;
        uint32_t fraction=(uint32_t)(((uint64_t)(elapsed%1000u)<<32)/1000u);
        sntp_put32(reply+32,second);sntp_put32(reply+36,fraction);
        sntp_put32(reply+40,second);sntp_put32(reply+44,fraction);
    }
#endif
    g_uptime_ms+=50;int n=mode==3?24:48;assert(length>=n);memcpy(data,reply,n);return n;
}
#ifdef MP_FIVE_FIELD01
static void check_field01(int fixture_mode,uint32_t budget,unsigned targets,int stop,int valid,int attempts){
    mode=fixture_mode;opens=closes=part=0;remaining_ms=budget;stopped=stop;
    sntp_server_cursor=0;sntp_target_count=targets;opening_ntp_retry=0;
    epoch=1800000000u;epoch_fraction=0;epoch_tick=g_uptime_ms;epoch_query_ms=0;
    assert(field01_fresh_sntp()==valid);
    assert(opens==attempts && closes==attempts);
}
#endif
int main(void){
    mode=0;epoch=1800000000;g_uptime_ms=10;
    for(unsigned i=0;i<3;i++){
        opening_ntp_retry=0;assert(!fresh_sntp());assert(gateway_network_retryable());
        assert(sntp_server_cursor==(i+1)%3);g_uptime_ms+=3000;
    }
    assert(opens==3 && closes==3);
    for(mode=1;mode<=6;mode++){
        opens=closes=part=0;sntp_server_cursor=0;opening_ntp_retry=0;
        epoch=1800000000u;epoch_fraction=0;epoch_tick=g_uptime_ms;epoch_query_ms=0;
        int valid=fresh_sntp();assert(valid==(mode==1));assert(!gateway_network_retryable());assert(closes==1);
    }
    mode=0;opens=closes=0;opening_ntp_retry=1;
    assert(!gateway_network_open());assert(!gateway_network_retryable());assert(opens==0);
#ifdef MP_FIVE_FIELD01
    check_field01(7,16000,3,0,1,2);
    check_field01(0,16000,3,0,0,2);
    check_field01(0,15999,3,0,0,1);
    check_field01(0,16000,1,0,0,1);
    check_field01(0,16000,3,1,0,1);
    check_field01(1,16000,3,0,1,1);
    for(int fixture_mode=2;fixture_mode<=6;fixture_mode++)
        check_field01(fixture_mode,16000,3,0,0,1);
    puts("FIELD01_FRESH_SNTP_ONE_FALLBACK_WITHIN_BUDGET_PASS");
#endif
    puts("ACTUAL_SNTP_ROTATION_ONLY_ZERO_REPLY_CLOSED_SYNCED_NEW_NONCE_PASS");
    puts("PARTIAL_SEND_PARTIAL_REPLY_BAD_NONCE_CLOSE_FAILURE_UNSYNC_AND_COARSE_TIME_FAILURE_DO_NOT_RETRY");
    return 0;
}
