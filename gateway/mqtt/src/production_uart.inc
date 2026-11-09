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

static int production_probe(uint32_t baud,PreUart *uart){
    return at_command(ESP_AT_SYNC,PROD_UART_AT_MS) && production_uart_query(baud,uart);
}

static int production_restore(uint32_t flow,char *command,size_t size){
    PreUart reply_uart;
    /* ACK 丢失时模块可能仍在任一速率。先查默认档，只在确认候选档后发恢复 setter。 */
    if(production_retime(ESP_UART_BAUD) && production_probe(ESP_UART_BAUD,&reply_uart))
        return reply_uart.flow==flow;
    if(!production_retime(PROD_UART_BAUD) || !production_probe(PROD_UART_BAUD,&reply_uart))return 0;
    (void)pre_uart_set(PROD_UART_AT_MS,ESP_UART_BAUD,flow,command,size);
    return production_retime(ESP_UART_BAUD) && production_probe(ESP_UART_BAUD,&reply_uart) &&
           reply_uart.flow==flow;
}

static int production_uart_setup(char *command,size_t size){
    PreUart initial,selected;
    uint32_t baud=platform_esp_uart_baud();
    if(!at_command(ESP_AT_SYNC,PROD_UART_AT_MS)){
        /* MCU 单独复位或 ESP 单独复位时，另一端可能保留另一档。 */
        baud=baud==ESP_UART_BAUD?PROD_UART_BAUD:ESP_UART_BAUD;
        if(!production_retime(baud) || !at_command(ESP_AT_SYNC,PROD_UART_AT_MS))return 0;
    }
    if(!at_command(ESP_AT_ECHO_OFF,PROD_UART_AT_MS) ||
       !at_command(ESP_AT_VOLATILE,PROD_UART_AT_MS) ||
       !production_uart_query(baud,&initial))return 0;
    if(baud==PROD_UART_BAUD || uart_attempted)return 1;
    uart_attempted=1;
    if(pre_uart_set(PROD_UART_AT_MS,PROD_UART_BAUD,initial.flow,command,size) &&
       production_retime(PROD_UART_BAUD) && production_probe(PROD_UART_BAUD,&selected) &&
       selected.flow==initial.flow)return 1;
    if(!production_restore(initial.flow,command,size))return 0;
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
