/* UART3 中断接收、主循环同步 AT；敏感命令和原始回复不写入控制台。 */
#include "gateway_platform.h"
#ifdef PLATFORM_HOST_TEST
#include "../tests/mocks/platform_mmio.h"
#else
#include "stm32f4xx.h"
#include "stm32f4xx_gpio.h"
#include "stm32f4xx_rcc.h"
#include "stm32f4xx_usart.h"
#endif
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdbool.h>
#ifdef MP_B5_CLOUD_CANDIDATE
#include "b5_policy.h"
static int closing_network;
#define NETWORK_STOPPED() (b5_network_stopped() && !closing_network)
#else
#define NETWORK_STOPPED() 0
#endif
#ifdef MP_CAN_RX_IRQ
#include "esp_io_metrics.h"
static EspIoMetrics io_metrics;
#ifdef MP_B5_EGRESS_FINAL
static int reply_boundary;
#ifdef MP_FINAL_UNIFIED
static uint32_t last_prompt_ms,last_send_ok_ms;
void platform_last_send_timing(uint32_t *prompt_ms,uint32_t *send_ok_ms) {
    *prompt_ms=last_prompt_ms;*send_ok_ms=last_send_ok_ms;
}
#endif
static uint32_t serial_deadline;
static void phase(unsigned p){
    EspAtEvent *e=&io_metrics.events[io_metrics.event_count++%4];
    *e=(EspAtEvent){g_uptime_ms,p,io_metrics.written,io_metrics.reply_bytes,io_metrics.wait_reason,io_metrics.reply_flags};
    io_metrics.at_phase=p;io_metrics.phase_at=g_uptime_ms;
}
static void unsync(void){io_metrics.unsynced=1;phase(ESP_AT_UNSYNCED);}
int platform_at_synchronized(void){return !io_metrics.unsynced &&
    (io_metrics.at_phase==ESP_AT_IDLE || io_metrics.at_phase==ESP_AT_CLOSED);}
int platform_at_unsynced(void){return io_metrics.unsynced!=0;}
#endif
static unsigned console_depth;
void platform_io_snapshot(EspIoMetrics *out) {*out=io_metrics;}
int platform_console_busy(void) {return console_depth!=0;}
#endif
#define CAPACITY 8192U
static volatile unsigned char ring[CAPACITY];
static volatile uint32_t head, tail, errors;
/* 重连可清当前错误门禁，但累计诊断绝不随之清零。 */
static volatile uint32_t uart_hw_total,uart_overflow_total;
uint32_t platform_uart_errors_total(void) {return uart_hw_total+uart_overflow_total;}
static unsigned char reply[4096], network_bytes[256];
static unsigned int reply_length, network_length, network_offset;
unsigned platform_mqtt_buffered(void){return network_length-network_offset;}
static unsigned line_start,binary_left,binary_offset,binary_length,binary_seen;
static int reply_closing;
#ifdef MP_B5_EGRESS_FINAL
static unsigned rx_state,rx_tx;
static uint32_t rx_deadline,rx_retry_at;
static int rx_step(void);
#endif
static void (*poll_callback)(void);
static int polling;
static uint32_t poll_at;
#ifdef MP_FINAL_UNIFIED
static bool poll_started;
#endif
/* AT 内部单调计时独立于 MQTT 库和 SNTP epoch，不再导出 Paho Timer 类型。 */
typedef struct
{
    uint32_t deadline;
} Timer;

void platform_set_poll(void (*callback)(void))
{
    poll_callback = callback;
#ifdef MP_FINAL_UNIFIED
    poll_started=false;
#endif
}

void mp_model_poll(void)
{
    platform_poll();
}

void platform_poll(void)
{
    /* 回调只跑 CAN/采集/入队，不调用网络，重入保护覆盖控制台诊断。 */
    if (poll_callback && !polling)
    {
#ifdef MP_FINAL_UNIFIED
        /* CAN中断照常入队；同一毫秒不逐字节重复运行整套采集服务。 */
        if(poll_started && g_uptime_ms==poll_at)return;
        poll_started=true;
#endif
#ifdef MP_B5_EGRESS_FINAL
        uint32_t gap=g_uptime_ms-poll_at;
        if(poll_at && gap>io_metrics.service_gap_max)io_metrics.service_gap_max=gap;
        poll_at=g_uptime_ms;
#else
        (void)poll_at;
#endif
        polling = 1;
        poll_callback();
        polling = 0;
    }
}

/* 中断仅生产字节，主线程消费；满队列不覆盖未读数据，错误交给网络层触发重连。 */
void USART3_IRQHandler(void)
{
    uint32_t status = USART3->SR;
    if (!(status & (USART_SR_RXNE | USART_SR_ORE | USART_SR_NE | USART_SR_FE)))
        return;
    unsigned char value = (unsigned char)USART3->DR;
    if (status & (USART_SR_ORE | USART_SR_NE | USART_SR_FE)) {
        errors++;uart_hw_total++;
    }
    if (status & USART_SR_RXNE)
    {
        uint32_t next = (head + 1U) % CAPACITY;
        if (next == tail) {
            errors++;uart_overflow_total++;
        }
        else
        {
            ring[head] = value;
            head = next;
#ifdef MP_B5_EGRESS_FINAL
            uint32_t n=(head+CAPACITY-tail)%CAPACITY;
            if(n>io_metrics.rx_high_water)io_metrics.rx_high_water=n;
#endif
        }
    }
}

static int receive_byte(void)
{
    if (tail == head)
        return -1;
    int value = ring[tail];
    tail = (tail + 1U) % CAPACITY;
    return value;
}

static unsigned send_bytes(const unsigned char *data, unsigned int length)
{
    for (unsigned int i = 0; i < length; ++i)
    {
        platform_poll();
        if (NETWORK_STOPPED()) return i;
#ifdef MP_B5_EGRESS_FINAL
        if((int32_t)(g_uptime_ms-serial_deadline)>=0)return i;
#endif
        while (!(USART3->SR & USART_SR_TXE))
        {
            platform_poll();
            if (NETWORK_STOPPED()) return i;
#ifdef MP_B5_EGRESS_FINAL
            if((int32_t)(g_uptime_ms-serial_deadline)>=0)return i;
#endif
        }
#ifdef PLATFORM_HOST_TEST
        platform_test_tx(data[i]);
#else
        USART3->DR = data[i];
#endif
#ifdef MP_B5_EGRESS_FINAL
        if(io_metrics.at_phase==ESP_AT_DATA)io_metrics.written=i+1;
#endif
    }
    return length;
}

void console(const char *message)
{
#ifdef MP_B5_EGRESS_FINAL
    uint32_t at=g_uptime_ms;
#endif
#ifdef MP_CAN_RX_IRQ
    /* 等TXE仍推进CAN；只让周期诊断避开正在输出的行，避免重入串口截断MQTT错误。 */
    console_depth++;
#endif
    while (*message)
    {
        while (!(USART1->SR & USART_SR_TXE))
        {
            platform_poll();
        }
        USART1->DR = (unsigned char)*message++;
    }
#ifdef MP_CAN_RX_IRQ
    console_depth--;
#ifdef MP_B5_EGRESS_FINAL
    uint32_t elapsed=g_uptime_ms-at;
    if(elapsed>io_metrics.console_max)io_metrics.console_max=elapsed;
#endif
#endif
}

int console_char(void)
{
    return (USART1->SR & USART_SR_RXNE) ? (int)(USART1->DR & 255U) : -1;
}

/* 有符号差适用于小于半个 uint32 周期的短超时，可跨毫秒计数回绕比较。 */
static char TimerIsExpired(Timer *timer)
{
    return (int32_t)(g_uptime_ms - timer->deadline) >= 0;
}

static void TimerCountdownMS(Timer *timer, unsigned int ms)
{
    timer->deadline = g_uptime_ms + ms;
}

void delay_ms(uint32_t ms)
{
    Timer timer;
    TimerCountdownMS(&timer, ms);
    while (!TimerIsExpired(&timer))
    {
        platform_poll();
        if (NETWORK_STOPPED()) break;
    }
}

static int line_is(const char *word)
{
    size_t n=strlen(word);
    return reply_length-line_start==n+2 && !memcmp(reply+line_start,word,n)
        && reply[reply_length-2]=='\r' && reply[reply_length-1]=='\n';
}

static int wait_end(int ok,unsigned reason) {
#ifdef MP_B5_EGRESS_FINAL
    io_metrics.wait_reason=reason;io_metrics.reply_bytes=reply_length;
#else
    (void)reason;
#endif
    return ok;
}

static void reply_begin(void) {
    reply_length = 0;
    line_start=binary_left=binary_offset=binary_length=binary_seen=0;
#ifdef MP_B5_EGRESS_FINAL
    reply_boundary=0;
    io_metrics.wait_reason=0;io_metrics.reply_bytes=0;io_metrics.reply_flags=0;
#endif
}

/* 长度头先于终态解析；数据中的NUL、控制词和URC字节均不参与AT判断。 */
static int reply_byte(int value,int prompt,int sent) {
    if(reply_length>=sizeof(reply)-1)return -9;
    reply[reply_length++]=(unsigned char)value;reply[reply_length]=0;
    if(binary_left){if(!--binary_left)line_start=reply_length;return 0;}
    unsigned n=reply_length-line_start;
    if(n==13 && !memcmp(reply+line_start,"+CIPRECVDATA",12) && value!=':')return -12;
    if(n>=13 && !memcmp(reply+line_start,"+CIPRECVDATA:",13)) {
        if(value==',') {
            unsigned size=0;
            if(binary_seen || n==14)return -12;
            for(unsigned i=line_start+13;i+1<reply_length;i++) {
                if(reply[i]<'0' || reply[i]>'9' || size>256)return -12;
                size=size*10u+(reply[i]-'0');
            }
            if(size>sizeof(network_bytes))return -12;
            binary_seen=1;binary_offset=reply_length;binary_left=binary_length=size;
            if(!size)line_start=reply_length;
        }else if(n>13 && (value<'0' || value>'9'))return -12;
        return 0;
    }
    if(prompt && value=='>' && (n==1 || (n==2 && reply[line_start]==' ')))return 2;
    if(value!='\n')return 0;
    unsigned flags=line_is("CLOSED")?1u:line_is("ready")?2u:
        (line_is("busy p...") || line_is("busy s..."))?4u:0u;
#ifdef MP_B5_EGRESS_FINAL
    io_metrics.reply_flags|=flags;
#endif
    /* 主动关闭仍须等末尾OK；只有本命令预期的CLOSED可作为中间URC。 */
    if(flags && !(flags==1u && reply_closing))return -11;
    if(line_is("ERROR") || line_is("FAIL") || line_is("SEND FAIL"))return -4;
    if(sent?line_is("SEND OK"):!prompt && line_is("OK"))return sent?3:1;
    line_start=reply_length;
    return 0;
}

static int reply_result(int result) {
#ifdef MP_B5_EGRESS_FINAL
    reply_boundary=result>0 || result==-4;
#endif
    return wait_end(result>0,(unsigned)(result<0?-result:result));
}

/* 同步命令和跨切片接收共享同一个解析器和唯一命令owner。 */
static int await_reply(uint32_t timeout, int prompt, int sent)
{
    Timer timer;
    TimerCountdownMS(&timer, timeout);
    reply_begin();
    while (!TimerIsExpired(&timer))
    {
        platform_poll();
        if (errors || NETWORK_STOPPED())
            return wait_end(0,errors?7:8);
        int value = receive_byte();
        if (value < 0)
            continue;
        int result=reply_byte(value,prompt,sent);
        if(result)return reply_result(result);
    }
    return wait_end(0,10);
}

int at_command(const char *command, uint32_t timeout)
{
#ifdef MP_B5_EGRESS_FINAL
    if(rx_state && !strcmp(command,"AT+CIPCLOSE")) {
        uint32_t at=g_uptime_ms;
        while(rx_state && (uint32_t)(g_uptime_ms-at)<timeout){platform_poll();if(rx_step()<0)return 0;}
        uint32_t spent=g_uptime_ms-at;
        if(rx_state || spent>=timeout)return 0;
        timeout-=spent;
    }
    if(!platform_at_synchronized())return 0;
    bool close=!strcmp(command,"AT+CIPCLOSE");
    if(!close && b5_business_remaining()<timeout+B5_CLOSE_RESERVE_MS){io_metrics.budget_refused++;return 0;}
    uint32_t started=g_uptime_ms;serial_deadline=started+timeout;phase(ESP_AT_COMMAND);
#endif
#ifdef MP_B5_CLOUD_CANDIDATE
    /* 硬停禁止继续发业务，但仍允许唯一的有界CIPCLOSE清理TLS连接。 */
    closing_network = b5_network_stopped() && !strcmp(command,"AT+CIPCLOSE");
#endif
    if (NETWORK_STOPPED()) return 0;
    unsigned written=send_bytes((const unsigned char *)command, strlen(command));
    unsigned ending=written==strlen(command)?send_bytes((const unsigned char *)"\r\n", 2):0;
#ifdef MP_B5_EGRESS_FINAL
    if(written!=strlen(command) || ending!=2){unsync();closing_network=0;return 0;}
    bool prompt=!strncmp(command,"AT+CIPSEND=",11);
    phase(prompt?ESP_AT_WAIT_PROMPT:ESP_AT_COMMAND);
    uint32_t elapsed=g_uptime_ms-started;
    if(elapsed>=timeout){unsync();closing_network=0;return 0;}
    timeout-=elapsed;
#else
    (void)ending;
#endif
    reply_closing=!strcmp(command,"AT+CIPCLOSE");
    int ok=await_reply(timeout, strncmp(command, "AT+CIPSEND=", 11) == 0, 0);
    reply_closing=0;
#ifdef MP_B5_EGRESS_FINAL
    b5_latency_add(prompt?&io_metrics.prompt:&io_metrics.command,g_uptime_ms-started);
#ifdef MP_FINAL_UNIFIED
    if(prompt)last_prompt_ms=g_uptime_ms-started;
#endif
    if(!ok && !reply_boundary)unsync();
    else phase(ok&&prompt?ESP_AT_DATA:ok&&close?ESP_AT_CLOSED:ESP_AT_IDLE);
#endif
#ifdef MP_B5_CLOUD_CANDIDATE
    closing_network=0;
#endif
    return ok;
}

const char *at_response(void)
{
    return (const char *)reply;
}

/* 先请求精确长度，再发送 MQTT 二进制并确认 ESP 结果；这不是 Broker 的 PUBACK。 */
int esp_mqtt_send(const unsigned char *data, int length, uint32_t timeout)
{
    if (length <= 0 || length > 2048)
        return -1;
    char command[40];
#ifdef MP_B5_EGRESS_FINAL
    uint32_t transaction_budget=timeout;
    if(timeout<=((unsigned)length+24u)*10000u/115200u){io_metrics.budget_refused++;return -1;}
    /* keepalive可能在ProcessLoop内发出；先结束唯一在途接收，绝不交叉命令。 */
    uint32_t owner_at=g_uptime_ms;
    while(rx_state && (uint32_t)(g_uptime_ms-owner_at)<timeout) {
        platform_poll();if(rx_step()<0)return -1;
    }
    uint32_t owner_elapsed=g_uptime_ms-owner_at;
    if(owner_elapsed>=timeout || rx_state)return -1;
    timeout-=owner_elapsed;
    if(!platform_at_synchronized() || b5_business_remaining()<timeout+B5_CLOSE_RESERVE_MS){io_metrics.budget_refused++;return -1;}
    io_metrics.required=(uint32_t)length;io_metrics.written=0;
#endif
#ifdef MP_CAN_RX_IRQ
    uint32_t started=g_uptime_ms;
    io_metrics.tx_calls++;io_metrics.tx_length=(uint32_t)length;io_metrics.tx_phase=1;
#endif
    (void)snprintf(command, sizeof(command), "AT+CIPSEND=%d", length);
    if (!at_command(command, (uint32_t)timeout))
    {
#ifdef MP_CAN_RX_IRQ
        io_metrics.tx_ms=g_uptime_ms-started;
#endif
        console("GW WRITE_PROMPT_FAIL\r\n");
        return -1;
    }
#ifdef MP_B5_EGRESS_FINAL
    serial_deadline=started+timeout;
#endif
    unsigned written=send_bytes(data, (unsigned int)length);
#ifdef MP_B5_EGRESS_FINAL
    io_metrics.written=written;b5_latency_add(&io_metrics.data,g_uptime_ms-io_metrics.phase_at);
    if(written!=(unsigned)length){unsync();return -1;}
    phase(ESP_AT_WAIT_SEND_OK);
    uint32_t elapsed=g_uptime_ms-started;
    if(elapsed>=timeout){unsync();return -1;}
    timeout-=elapsed;
#else
    (void)written;
#endif
#ifdef MP_CAN_RX_IRQ
    io_metrics.tx_phase=2;
#endif
    if (!await_reply((uint32_t)timeout, 0, 1))
    {
#ifdef MP_B5_EGRESS_FINAL
        if(!reply_boundary)unsync();else phase(ESP_AT_IDLE);
#endif
#ifdef MP_CAN_RX_IRQ
        io_metrics.tx_ms=g_uptime_ms-started;
#endif
#ifdef MP_B5_EGRESS_FINAL
        char detail[160];(void)snprintf(detail,sizeof(detail),"GW WRITE_DETAIL reason=%lu reply_n=%lu flags=%lu budget=%lu elapsed=%lu written=%lu required=%lu\r\n",
            (unsigned long)io_metrics.wait_reason,(unsigned long)io_metrics.reply_bytes,(unsigned long)io_metrics.reply_flags,
            (unsigned long)transaction_budget,(unsigned long)(g_uptime_ms-started),(unsigned long)written,(unsigned long)length);
        console(detail);
#endif
        console("GW WRITE_SEND_FAIL\r\n");
        return -1;
    }
#ifdef MP_B5_EGRESS_FINAL
    b5_latency_add(&io_metrics.send_ok,g_uptime_ms-io_metrics.phase_at);
#ifdef MP_FINAL_UNIFIED
    last_send_ok_ms=g_uptime_ms-io_metrics.phase_at;
#endif
    phase(ESP_AT_IDLE);
#endif
#ifdef MP_CAN_RX_IRQ
    /* SEND OK只证明ESP协议栈接受，不当作Broker接收或PUBACK。 */
    io_metrics.tx_confirmed++;io_metrics.tx_ms=g_uptime_ms-started;io_metrics.tx_phase=3;
#endif
    if (data[0] == 0x10U)
        console("GW CONNECT_PACKET_SENT\r\n");
    return length;
}

#ifdef MP_B5_EGRESS_FINAL
/* 准入下界包括串口8N1、提示/终态各1秒和ACK接收余量；不是ESP成功时延保证。 */
uint32_t platform_send_reserve(unsigned bytes) {
    return ((bytes+24u)*10000u+115199u)/115200u+2100u;
}
int platform_send_admissible(unsigned bytes,uint32_t budget) {
    return platform_at_synchronized() && !rx_state && budget>=platform_send_reserve(bytes);
}
void platform_tx_context(unsigned qos,unsigned stream,uint32_t seq,unsigned pending,uint32_t age,uint32_t budget) {
    io_metrics.tx_id++;io_metrics.tx_at=g_uptime_ms;io_metrics.tx_budget=budget;
    io_metrics.qos=qos;io_metrics.stream=stream;io_metrics.frame_seq=seq;
    io_metrics.pending_id=pending;io_metrics.pending_age=age;
}
static void rx_begin(unsigned state) {
    reply_closing=0;
    rx_state=state;rx_tx=0;rx_deadline=g_uptime_ms+1000u;
    serial_deadline=rx_deadline;phase(ESP_AT_COMMAND);reply_begin();
    if(state==1)io_metrics.rx_queries++;
}
static int rx_step(void) {
    if(errors || NETWORK_STOPPED() || (int32_t)(g_uptime_ms-rx_deadline)>=0) {
        wait_end(0,errors?7:NETWORK_STOPPED()?8:10);unsync();return -1;
    }
    const char *command=rx_state<=2?"AT+CIPRECVLEN?\r\n":"AT+CIPRECVDATA=256\r\n";
    if(rx_state==1 || rx_state==3) {
        if(!(USART3->SR & USART_SR_TXE))return 0;
#ifdef PLATFORM_HOST_TEST
        platform_test_tx((unsigned char)command[rx_tx]);
#else
        USART3->DR=(unsigned char)command[rx_tx];
#endif
        if(!command[++rx_tx])rx_state++;
        return 0;
    }
    int byte=receive_byte();if(byte<0)return 0;
    int result=reply_byte(byte,0,0);if(!result)return 0;
    if(!reply_result(result)){if(!reply_boundary)unsync();else phase(ESP_AT_IDLE);rx_state=0;return -1;}
    b5_latency_add(&io_metrics.command,1000u-(rx_deadline-g_uptime_ms));
    if(rx_state==2) {
        char *p=strstr((char *)reply,"+CIPRECVLEN:"),*end;
        if(!p || p[12]<'0' || p[12]>'9'){unsync();return -1;}
        unsigned long n=strtoul(p+12,&end,10);
        if(*end!=',' && *end!='\r'){unsync();return -1;}
        io_metrics.rx_hint=(uint32_t)n;
        if(n){rx_begin(3);return 0;}
        io_metrics.rx_empty++;rx_retry_at=g_uptime_ms+5u;
    }else {
        if(!binary_seen){unsync();return -1;}
        memcpy(network_bytes,reply+binary_offset,binary_length);
        network_offset=0;network_length=binary_length;io_metrics.rx_reads++;
    }
    rx_state=0;phase(ESP_AT_IDLE);return 1;
}
#endif

/* 先消费上次剩余字节；SSL 被动读取分块到缓存，短读按实际字节数交给适配层。 */
int esp_mqtt_recv(unsigned char *data, int length, uint32_t timeout)
{
#ifdef MP_B5_EGRESS_FINAL
    uint32_t until=g_uptime_ms+timeout;int copied=0;
    while(copied<length) {
        if(errors || NETWORK_STOPPED() || io_metrics.unsynced)return -1;
        if(network_offset<network_length){data[copied++]=network_bytes[network_offset++];io_metrics.rx_bytes++;continue;}
        if(copied)break;
        if((int32_t)(g_uptime_ms-until)>=0)break;
        if(!rx_state) {
            if(!platform_at_synchronized())return -1;
            if((int32_t)(g_uptime_ms-rx_retry_at)>=0)rx_begin(1);
        }
        platform_poll();
        if(rx_state){int result=rx_step();if(result<0)return -1;if(result>0 && !network_length)break;}
    }
    return copied;
#else
    int copied = 0;
    Timer timer;
    TimerCountdownMS(&timer, (unsigned int)(timeout > 0 ? timeout : 1));
    while (copied < length)
    {
        platform_poll();
        if (NETWORK_STOPPED()) return -1;
        if (network_offset < network_length)
        {
            data[copied++] = network_bytes[network_offset++];
#ifdef MP_CAN_RX_IRQ
            io_metrics.rx_bytes++;
#endif
            continue;
        }
        if (TimerIsExpired(&timer))
            break;
        network_offset = network_length = 0;
#ifdef MP_CAN_RX_IRQ
        io_metrics.rx_queries++;
#endif
        /* 此固件在 SSL 尚无数据时读数据返回 ERROR，先查询接收长度再读取。 */
        if (!at_command("AT+CIPRECVLEN?", 1000))
        {
#ifdef MP_CAN_RX_IRQ
            /* 此处原来静默返回，导致无法区分AT查询失败和MQTT确认失败。 */
            console("GW READ_AVAILABLE_FAIL\r\n");
#endif
            return -1;
        }
        char *available = strstr((char *)reply, "+CIPRECVLEN:");
        if (!available)
        {
#ifdef MP_CAN_RX_IRQ
            console("GW READ_AVAILABLE_HEADER_FAIL\r\n");
#endif
            return -1;
        }
        unsigned long available_bytes=strtoul(available + 12, NULL, 10);
#ifdef MP_CAN_RX_IRQ
        io_metrics.rx_hint=(uint32_t)available_bytes;
        if(!available_bytes)io_metrics.rx_empty++;
#endif
        if (!available_bytes)
        {
            delay_ms(10);
            continue;
        }
        if (!at_command("AT+CIPRECVDATA=256", 1000))
        {
            console("GW READ_AT_FAIL\r\n");
            return -1;
        }
        /* 固件被动接收模式：长度明确，原样保留二进制包；未收到数据不伪造字节。 */
        char *header = strstr((char *)reply, "+CIPRECVDATA:");
        if (!header)
        {
            console("GW READ_HEADER_FAIL\r\n");
            return -1;
        }
        char *end = NULL;
        unsigned long size = strtoul(header + 13, &end, 10);
        if (!end || *end != ',' || size > sizeof(network_bytes) ||
            (unsigned char *)(end + 1) + size > reply + reply_length)
        {
            console("GW READ_LENGTH_FAIL\r\n");
            return -1;
        }
        memcpy(network_bytes, end + 1, size);
#ifdef MP_CAN_RX_IRQ
        io_metrics.rx_reads++;
#endif
        network_length = (unsigned int)size;
        /* 只报告 CONNACK 状态码，不输出 MQTT CONNECT 内容或通用载荷。 */
        if (size == 4U && network_bytes[0] == 0x20U)
        {
            char diagnostic[40];
            (void)snprintf(diagnostic, sizeof(diagnostic), "GW CONNACK_CODE %u\r\n",
                           network_bytes[3]);
            console(diagnostic);
        }
        if (!size)
            delay_ms(5);
    }
    return copied;
#endif
}

void esp_mqtt_reset(void)
{
    network_length = network_offset = 0;
    /* 上一连接留下的异步提示不是新 MQTT 包，建立 SSL 前重新初始化队列。 */
    __disable_irq();
    tail = head;
    errors = 0;
#ifdef MP_B5_EGRESS_FINAL
    if(!rx_state)rx_retry_at=g_uptime_ms;
#endif
    __enable_irq();
}


#ifndef PLATFORM_HOST_TEST
static void init_uart(void)
{
    GPIO_InitTypeDef gpio;
    USART_InitTypeDef uart;
    RCC_AHB1PeriphClockCmd(RCC_AHB1Periph_GPIOA | RCC_AHB1Periph_GPIOB, ENABLE);
    RCC_APB2PeriphClockCmd(RCC_APB2Periph_USART1, ENABLE);
    RCC_APB1PeriphClockCmd(RCC_APB1Periph_USART3, ENABLE);
    GPIO_StructInit(&gpio);
    gpio.GPIO_Pin = GPIO_Pin_9 | GPIO_Pin_10;
    gpio.GPIO_Mode = GPIO_Mode_AF;
    gpio.GPIO_OType = GPIO_OType_PP;
    gpio.GPIO_PuPd = GPIO_PuPd_UP;
    gpio.GPIO_Speed = GPIO_Speed_50MHz;
    GPIO_PinAFConfig(GPIOA, GPIO_PinSource9, GPIO_AF_USART1);
    GPIO_PinAFConfig(GPIOA, GPIO_PinSource10, GPIO_AF_USART1);
    GPIO_Init(GPIOA, &gpio);
    gpio.GPIO_Pin = GPIO_Pin_10 | GPIO_Pin_11;
    GPIO_PinAFConfig(GPIOB, GPIO_PinSource10, GPIO_AF_USART3);
    GPIO_PinAFConfig(GPIOB, GPIO_PinSource11, GPIO_AF_USART3);
    GPIO_Init(GPIOB, &gpio);
    USART_StructInit(&uart);
    uart.USART_BaudRate = 115200;
    USART_Init(USART1, &uart);
    USART_Init(USART3, &uart);
    USART_Cmd(USART1, ENABLE);
    USART_Cmd(USART3, ENABLE);
    USART_ITConfig(USART3, USART_IT_RXNE, ENABLE);
    NVIC_EnableIRQ(USART3_IRQn);
}

void platform_init(void)
{
#ifdef MP_CAN_RX_IRQ
    /* USB ROM GO不保证VTOR指向应用；与H2R相同，在UART/SysTick中断前定位应用向量。
       这是C应用自身正常启动初始化，不对A手工改PC/MSP/VTOR。 */
    SCB->VTOR=0x08000000u;__DSB();__ISB();
#endif
    init_uart();
#ifdef MP_CAN_RX_IRQ
    /* H3外部晶体失败时只报告并停机，禁止带着错误采集时钟继续联网。 */
    extern int physical_clock_ready(void);
    if(!physical_clock_ready()) {console("GW FAIL HSE_CLOCK\r\n");while(1) {}}
    console("GW CLOCK hse=1 core_hz=8000000\r\n");
#endif
    if (SysTick_Config(SystemCoreClock / 1000U))
        while (1)
        {
        }
}
#endif
