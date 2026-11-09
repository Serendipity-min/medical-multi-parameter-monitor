#include "preflight_baud.h"
#include "b5_policy.h"
#include "field01_window.h"

#define PRE_RESTORE_RESERVE_MS 9000u
#define PRE_REPORT_RESERVE_MS 250u
#define PRE_STRESS_COUNT 50u
#define PRE_STRESS_AT_MS 300u
typedef struct {uint32_t baud,data,stop,parity,flow;} PreUart;

/* 只接受行首的独立回复，忽略命令回显和其它字段。 */
static const char *pre_reply_field(const char *tag) {
    const char *start=at_response(),*found=start;
    size_t size=strlen(tag);
    while((found=strstr(found,tag))!=NULL){
        if(found==start || found[-1]=='\n')return found+size;
        found+=size;
    }
    return NULL;
}

static int pre_number(const char **cursor,uint32_t max,uint32_t *value) {
    const char *p=*cursor;
    uint32_t result=0;
    unsigned digits=0;
    while(*p>='0' && *p<='9'){
        if(++digits>7)return 0;
        result=result*10u+(uint32_t)(*p++-'0');
        if(result>max)return 0;
    }
    if(!digits)return 0;
    *cursor=p;
    *value=result;
    return 1;
}

static int pre_eol(const char *p) {return *p=='\n' || (*p=='\r' && p[1]=='\n');}

static int pre_uart_parse(PreUart *out) {
    const char *p=pre_reply_field("+UART_CUR:");
    PreUart v;
    if(!p || !pre_number(&p,4500000u,&v.baud) || v.baud<80u || *p++!=',' ||
       !pre_number(&p,8,&v.data) || v.data<5u || *p++!=',' ||
       !pre_number(&p,3,&v.stop) || !v.stop || *p++!=',' ||
       !pre_number(&p,2,&v.parity) || *p++!=',' ||
       !pre_number(&p,3,&v.flow) || !pre_eol(p))return 0;
    *out=v;
    return 1;
}

static int pre_ipv4_ready(void) {
    const char *p=pre_reply_field("+CIPSTA:ip:\"");
    unsigned nonzero=0;
    if(!p)return 0;
    for(unsigned i=0;i<4;i++){
        uint32_t octet;
        const char *begin=p;
        if(!pre_number(&p,255,&octet) || p-begin>3 || *p++!=(i==3?'"':'.'))return 0;
        nonzero|=octet;
    }
    return nonzero && pre_eol(p);
}

static uint32_t pre_timeout(uint32_t limit,uint32_t requested) {
    uint32_t now=g_uptime_ms;
    if(b5_network_stopped() || platform_preflight_esp_reset_seen() || !platform_at_synchronized() ||
       now>=limit || limit-now<=B5_CLOSE_RESERVE_MS)return 0;
    uint32_t left=limit-now-B5_CLOSE_RESERVE_MS;
    return requested<left?requested:left;
}

static int pre_at(uint32_t limit,const char *command,uint32_t requested) {
    uint32_t ms=pre_timeout(limit,requested);
    return ms && at_command(command,ms);
}

static int pre_version(uint32_t limit,uint32_t timeout,char version[32]) {
    uint32_t ms=pre_timeout(limit,timeout);
    return ms && esp_version(ms,version);
}

static int pre_uart_query(uint32_t limit,PreUart *out) {
    return pre_at(limit,"AT+UART_CUR?",1000u) && pre_uart_parse(out);
}

static int pre_uart_matches(const PreUart *uart,uint32_t target) {
    return uart->data==8 && uart->stop==1 && !uart->parity && !uart->flow &&
           preflight_baud_matches(target,uart->baud);
}

static int pre_uart_set(uint32_t limit,uint32_t baud,char *buffer,size_t size) {
    (void)snprintf(buffer,size,"AT+UART_CUR=%lu,8,1,0,0",(unsigned long)baud);
    return pre_at(limit,buffer,1000u);
}

static int pre_confirm(uint32_t limit,uint32_t baud) {
    PreUart reply_uart;
    return pre_at(limit,ESP_AT_SYNC,1000u) && pre_uart_query(limit,&reply_uart) &&
           pre_uart_matches(&reply_uart,baud);
}

/* 清理只在已知原速率上做一次，保留错误计数并要求完整的五元组。 */
static int pre_restore(uint32_t limit,uint32_t rate,int candidate_seen,char *buffer,size_t size) {
    if(candidate_seen){
        if(!platform_at_synchronized() &&
           (!platform_preflight_retime(rate,limit) || !pre_confirm(limit,rate)))return 0;
        /* ACK 可能在换速时丢失，实际回读才决定是否恢复。 */
        (void)pre_uart_set(limit,ESP_UART_BAUD,buffer,size);
    }
    if((rate!=ESP_UART_BAUD || !platform_at_synchronized()) &&
       !platform_preflight_retime(ESP_UART_BAUD,limit))return 0;
    return pre_confirm(limit,ESP_UART_BAUD);
}

int gateway_preflight(uint32_t target,uint32_t deadline) {
    char line[256],version[32];
    PreUart initial={0},selected={0};
    uint32_t limit=deadline-PRE_RESTORE_RESERVE_MS,restore_limit=deadline-PRE_REPORT_RESERVE_MS;
    uint32_t rate=ESP_UART_BAUD,actual=0,errors,n=0,fail=0,high=0;
    int candidate_seen=0,restore=-1;
    const char *negotiation="NO_REPLY";
#define PRE_OUT(...) do { \
    (void)snprintf(line,sizeof line,__VA_ARGS__); \
    (void)platform_preflight_console(line,deadline); \
} while(0)
    PRE_OUT("PRE BEGIN boot_ms=%lu target=%lu\r\n",(unsigned long)(deadline-FIELD01_PRE_MS),(unsigned long)target);
    /* 冷启动串口可能含 ESP 启动字节，首次事务前清输入，保留累计错误。 */
    if(!b5_network_stopped())esp_mqtt_reset();
    int at=pre_at(limit,ESP_AT_SYNC,1000u);
    PRE_OUT("PRE AT ok=%u\r\n",(unsigned)at);
    int echo=at && pre_at(limit,ESP_AT_ECHO_OFF,1000u);
    int gmr=at && pre_version(limit,1000u,version);
    PRE_OUT("PRE GMR ver=%s\r\n",gmr?version:"NONE");
    int uart=at && pre_uart_query(limit,&initial);
    if(uart)PRE_OUT("PRE UART_CUR baud=%lu data=%lu stop=%lu parity=%lu flow=%lu\r\n",
        (unsigned long)initial.baud,(unsigned long)initial.data,(unsigned long)initial.stop,
        (unsigned long)initial.parity,(unsigned long)initial.flow);
    else PRE_OUT("PRE UART_CUR baud=NONE\r\n");

    int config_ok=gateway_config_valid();
    int wifi=0,ipv4=0;
    uint32_t wifi_ms=0;
    char code[2]={0};
    if(echo && config_ok && pre_at(limit,ESP_AT_VOLATILE,1000u) &&
       pre_at(limit,"AT+CWMODE=1,0",2000u)){
        uint32_t ms=pre_timeout(limit,20000u);
        if(ms){
            uint32_t start=g_uptime_ms;
            wifi=wifi_join(line,sizeof line,ms);
            wifi_ms=g_uptime_ms-start;
            if(!wifi)code[0]=gateway_wifi_join_code(at_response());
        }
    }
    PRE_OUT("PRE WIFI ok=%u code=%s ms=%lu\r\n",(unsigned)wifi,code[0]?code:"NONE",(unsigned long)wifi_ms);
    int channel,rssi;
    if(wifi && pre_at(limit,"AT+CWJAP?",1000u) && gateway_wifi_signal(at_response(),&channel,&rssi))
        PRE_OUT("PRE WIFI_SIGNAL channel=%d rssi=%d\r\n",channel,rssi);
    ipv4=pre_at(limit,"AT+CIPSTA?",1000u) && wifi && pre_ipv4_ready();
    PRE_OUT("PRE IPV4 ready=%u\r\n",(unsigned)ipv4);

    int initial_valid=uart && pre_uart_matches(&initial,ESP_UART_BAUD);
    if(uart && !initial_valid){
        negotiation="MISMATCH";actual=initial.baud;
    }else if(initial_valid && target==ESP_UART_BAUD && platform_at_synchronized()){
        negotiation="OK";actual=initial.baud;
    }else if(initial_valid && preflight_brr(target) && pre_uart_set(limit,target,line,sizeof line)){
        if(platform_preflight_retime(target,limit)){
            rate=target;
            candidate_seen=pre_at(limit,ESP_AT_SYNC,1000u);
        }
        if(candidate_seen){
            int reported=pre_uart_query(limit,&selected);
            actual=reported?selected.baud:0;
            negotiation=reported && pre_uart_matches(&selected,target)?"OK":"MISMATCH";
        }else{
            restore=pre_restore(restore_limit,rate,0,line,sizeof line);
            negotiation=restore?"NO_SWITCH":"RESYNC_FAIL";
        }
    }
    if(actual)PRE_OUT("PRE NEGOTIATE target=%lu result=%s actual=%lu\r\n",
        (unsigned long)target,negotiation,(unsigned long)actual);
    else PRE_OUT("PRE NEGOTIATE target=%lu result=%s actual=NONE\r\n",(unsigned long)target,negotiation);

    uint32_t started=g_uptime_ms;
    errors=platform_uart_errors_total();
    if(!strcmp(negotiation,"OK")){
        uint32_t prior=platform_preflight_high_water(0);
        for(;n<PRE_STRESS_COUNT && pre_timeout(limit,PRE_STRESS_AT_MS)==PRE_STRESS_AT_MS;n++){
            if(!pre_version(limit,PRE_STRESS_AT_MS,version))fail++;
        }
        high=platform_preflight_high_water(prior);
    }
    uint32_t stress_ms=g_uptime_ms-started,uart_err=platform_uart_errors_total()-errors;
    int timed_out=n<PRE_STRESS_COUNT && g_uptime_ms+B5_CLOSE_RESERVE_MS+PRE_STRESS_AT_MS>=limit;
    PRE_OUT("PRE STRESS rate=%lu n=%lu fail=%lu uart_err=%lu rx_high=%lu ms=%lu\r\n",
        (unsigned long)rate,(unsigned long)n,(unsigned long)fail,(unsigned long)uart_err,
        (unsigned long)high,(unsigned long)stress_ms);
    int after=rate==ESP_UART_BAUD || (n && pre_at(limit,ESP_AT_SYNC,1000u));
    if(restore<0)restore=pre_restore(restore_limit,rate,candidate_seen,line,sizeof line);
    PRE_OUT("PRE RESTORE result=%s\r\n",restore?"OK":"FAIL");
    const char *reason=!restore?"NEED_POWER_CYCLE":b5_network_stopped()?"STOP":
        timed_out?"TIMEOUT":
        !at || !echo?"AT":!gmr?"GMR":!uart?"UART_CUR":!config_ok?"CONFIG":
        strcmp(negotiation,"OK")?"NEGOTIATE":!wifi?"WIFI":!ipv4?"IPV4":
        n!=PRE_STRESS_COUNT || fail || uart_err || !after?"STRESS":"NONE";
    PRE_OUT("PRE END result=%s reason=%s uart_err=%lu\r\n",
        !strcmp(reason,"NONE")?"PASS":"BLOCKED",reason,(unsigned long)platform_uart_errors_total());
#undef PRE_OUT
    return restore;
}
