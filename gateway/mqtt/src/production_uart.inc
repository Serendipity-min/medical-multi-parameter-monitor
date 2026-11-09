#define PROD_UART_BAUD 230400u
#define PROD_UART_AT_MS 500u
#define PROD_UART_GUARD_BUDGET_MS 80u

static int uart_starting, uart_failed, uart_attempted;

int gateway_uart_negotiating(void){return uart_starting;}
int gateway_uart_negotiation_failed(void){return uart_failed;}

static int production_retime(uint32_t baud){
    return platform_preflight_retime(baud,g_uptime_ms+PROD_UART_GUARD_BUDGET_MS)==PRE_RETIME_OK;
}

static int production_uart_query(uint32_t baud,PreUart *uart){
    return at_command("AT+UART_CUR?",PROD_UART_AT_MS) && pre_uart_parse(uart) &&
           pre_uart_matches(uart,baud);
}

static int production_explicit_error(void){
    static const char error[]="ERROR\r\n";
    const char *reply=at_response();
    size_t len=strlen(reply),n=sizeof error-1;
    return platform_at_synchronized() && len>=n &&
           (len==n || reply[len-n-1]=='\n') && !memcmp(reply+len-n,error,n);
}

static int production_sync(void){
    /* 错速探测可能给 ESP 留下乱码。只在收到完整 ERROR 时再同步一次。 */
    return at_command(ESP_AT_SYNC,PROD_UART_AT_MS) ||
           (production_explicit_error() && at_command(ESP_AT_SYNC,PROD_UART_AT_MS));
}

static int production_probe(uint32_t baud,PreUart *uart){
    return production_sync() && production_uart_query(baud,uart);
}

static int production_restore_failure(const char *label,const char *step){
    char line[72];
    (void)snprintf(line,sizeof line,"%s step=%s\r\n",label,step);
    console(line);
    return 0;
}

/* 只有确认 ESP 在快档后才进入；setter 丢 ACK 时以慢档回读为准。 */
static int production_restore_fast(uint32_t flow,char *command,size_t size,const char *label){
    if(!pre_uart_set(PROD_UART_AT_MS,ESP_UART_BAUD,flow,command,size) &&
       production_explicit_error())return production_restore_failure(label,"SETTER");
    if(!production_retime(ESP_UART_BAUD))return production_restore_failure(label,"RETIME_BACK");
    PreUart uart;
    if(!production_probe(ESP_UART_BAUD,&uart) || uart.flow!=flow)
        return production_restore_failure(label,"PROBE_BACK");
    return 1;
}

static int production_restore(uint32_t flow,char *command,size_t size){
    const char *label="GW UART_RESTORE";
    PreUart uart;
    /* 升档 ACK 丢失时 ESP 可能仍在任一档，先确认其所在速率。 */
    if(production_retime(ESP_UART_BAUD) && production_probe(ESP_UART_BAUD,&uart)){
        if(uart.flow!=flow)return production_restore_failure(label,"PROBE115");
        return 1;
    }
    if(!production_retime(PROD_UART_BAUD))return production_restore_failure(label,"RETIME230");
    if(!production_probe(PROD_UART_BAUD,&uart))return production_restore_failure(label,"PROBE230");
    return production_restore_fast(flow,command,size,label);
}

static int production_uart_setup(char *command,size_t size){
    PreUart initial,selected;
    uint32_t baud=platform_esp_uart_baud();
    if(!production_sync()){
        /* MCU 单独复位或 ESP 单独复位时，另一端可能保留另一档。 */
        baud=baud==ESP_UART_BAUD?PROD_UART_BAUD:ESP_UART_BAUD;
        if(!production_retime(baud) || !production_sync())return 0;
    }
    if(!at_command(ESP_AT_ECHO_OFF,PROD_UART_AT_MS) ||
       !at_command(ESP_AT_VOLATILE,PROD_UART_AT_MS) ||
       !production_uart_query(baud,&initial))return 0;
    if(baud==PROD_UART_BAUD || uart_attempted)return 1;
    uart_attempted=1;
    if(pre_uart_set(PROD_UART_AT_MS,PROD_UART_BAUD,initial.flow,command,size) &&
       production_retime(PROD_UART_BAUD) && production_probe(PROD_UART_BAUD,&selected)){
        if(selected.flow==initial.flow)return 1;
        if(!production_restore_fast(initial.flow,command,size,"GW UART_RESTORE"))return 0;
    }else if(!production_restore(initial.flow,command,size))return 0;
    console("GW UART_DEGRADED\r\n");
    return 1;
}

static int production_uart_open(char *command,size_t size){
    if(uart_failed)return 0;
    uart_starting=1;
    int ok=production_uart_setup(command,size);
    if(ok)b5_uart_accept_baseline();
    else if(platform_esp_uart_baud()!=ESP_UART_BAUD)(void)production_retime(ESP_UART_BAUD);
    uart_starting=0;
    if(!ok){
        uart_failed=1;
        console("GW FAIL UART_NEGOTIATE\r\n");
    }
    return ok;
}
