/* 实验构建保留手工武装；显式ABC样机构建自动启动，均不写配置。 */
#include "b5_policy.h"
#include "../dual_can/b4_bxcan.h"
#include "gateway_transport.h"
#include "esp_io_metrics.h"
#include <string.h>
#include <stdio.h>
#ifdef MP_FINAL_UNIFIED
#include "unified_audio.h"
#include "mic_protocol.h"
#ifdef __arm__
#include "stm32f4xx.h"
#include "stm32f4xx_gpio.h"
#include "stm32f4xx_rcc.h"
#endif
unsigned final_can_mask;
static uint32_t run_limit_ms=B5_WINDOW_MS;
static bool network_fault;
static uint32_t uart_error_baseline,can_poll_cycles_max;
static void local_control(void);
#ifdef MP_ABC_APPLIANCE
static uint32_t retry_ms=2000;
static void reconnect_delay(void) {
    delay_ms(retry_ms);
    if(retry_ms<30000u)retry_ms=retry_ms<15000u?retry_ms*2u:30000u;
}
#endif
#endif
#ifndef MP_ABC_APPLIANCE
#define reconnect_delay() delay_ms(2000)
#endif
#if defined(MP_B5_EGRESS_FINAL) && defined(__arm__)
#include "ram_watermark.h"
#endif
static B4Gateway gateway;
static MpFrame will;
#ifndef MP_B5_EGRESS_FINAL
static MpFrame publishing;
#endif
static uint32_t armed_at, last_sync, status_at, connection, status_seq;
static uint32_t diag_at, mqtt_qos0_transport_ok, mqtt_qos1_puback, mqtt_failed_count;
static uint32_t service_at;
static volatile bool armed, stopped;
static bool network_open, mqtt_connected, service_seen, stop_reported;
#ifdef MP_B5_EGRESS_FINAL
#include "egress.h"
static B5Publisher publisher;
static bool drained;
static volatile bool stop_due;
static uint32_t stop_tick,stop_reason,stop_live,stop_cache;
static EspIoMetrics stop_io;
uint32_t b5_business_remaining(void) {
#ifdef MP_FINAL_UNIFIED
    if(!run_limit_ms)return 0x3fffffffu;
    if(!armed)return run_limit_ms;
    uint32_t used=g_uptime_ms-armed_at;return used>=run_limit_ms?0:run_limit_ms-used;
#else
    if(!armed)return B5_WINDOW_MS;
    uint32_t used=g_uptime_ms-armed_at;return used>=B5_WINDOW_MS?0:B5_WINDOW_MS-used;
#endif
}
void b5_hard_tick(void) {
    /* 中断只锁存截止和取证，不执行CAN库、AT、printf或关闭网络。 */
    if(armed && !stopped && !stop_due &&
#ifdef MP_FINAL_UNIFIED
       run_limit_ms && (uint32_t)(g_uptime_ms-armed_at)>=run_limit_ms) {
#else
       (uint32_t)(g_uptime_ms-armed_at)>=B5_WINDOW_MS) {
#endif
        stop_tick=g_uptime_ms;stop_reason=1;stop_live=gateway.router.ln;stop_cache=gateway.router.cn;
        platform_io_snapshot(&stop_io);stop_due=true;
    }
}
#endif
uint32_t b4_hw_time(void) { return g_uptime_ms; }
int b5_network_stopped(void) { return stopped
#ifdef MP_FINAL_UNIFIED
    ||network_fault
#endif
#ifdef MP_B5_EGRESS_FINAL
    ||stop_due
#endif
    ; }
static void report_stop(void) {
    if (!stop_reported && !platform_console_busy()) {
        stop_reported = true;
        console("B5 STOPPED NO_AUTOREARM\r\n");
#ifdef MP_B5_EGRESS_FINAL
        char line[240];
        (void)snprintf(line,sizeof(line),"B5 STOP_STATE tick=%lu armed_at=%lu reason=%lu phase=%lu required=%lu written=%lu unsynced=%lu pending=%u live=%lu cache=%lu\r\n",
            (unsigned long)stop_tick,(unsigned long)armed_at,(unsigned long)stop_reason,(unsigned long)stop_io.at_phase,
            (unsigned long)stop_io.required,(unsigned long)stop_io.written,(unsigned long)stop_io.unsynced,
            (unsigned)publisher.pending,(unsigned long)stop_live,(unsigned long)stop_cache);console(line);
#endif
    }
}
static void stop(void) {
#ifdef MP_FINAL_UNIFIED
    unified_audio_stop();
#endif
#ifdef MP_B5_EGRESS_FINAL
    if(!stop_due){stop_tick=g_uptime_ms;stop_live=gateway.router.ln;stop_cache=gateway.router.cn;platform_io_snapshot(&stop_io);
        stop_reason=stop_io.unsynced?2:b5_business_remaining()==0?1:3;}
#endif
    stopped = true; gateway.utc_valid = false;
    mp_router_online(&gateway.router, false); b4_hw_stop();
    report_stop();
}
#ifdef MP_FINAL_UNIFIED
static void local_control(void) {
    static char line[32];static unsigned used,config_count;
    static uint8_t config_packet[249];static uint32_t config_at;
    if(config_count && (uint32_t)(g_uptime_ms-config_at)>=5000u) {
        config_count=0;memset(config_packet,0,sizeof config_packet);console("UNI CONFIG_TIMEOUT\r\n");
    }
    for(unsigned budget=0;budget<16;budget++) {
        int c=console_char();if(c<0)break;
        if(config_count || (!used && c=='F')) {
            if(!config_count){config_at=g_uptime_ms;mic_config_byte(config_packet,&config_count,'C');}
            else if(mic_config_byte(config_packet,&config_count,(uint8_t)c)==2) {
                int ok=!armed && gateway_audio_configure(config_packet,sizeof config_packet);
                memset(config_packet,0,sizeof config_packet);console(ok?"UNI CONFIG_OK\r\n":"UNI CONFIG_REJECTED\r\n");
            }
            continue;
        }
        if(armed || stopped) {
            if(c=='I')console("UNI ID V1 DUAL_CAN_MIC_MQTT_TTS CONFIG_RAM\r\n");
            else if(c=='X' && !stopped)stop();
            else if(c=='L' || c=='l')console(b4_hw_set_replay(c=='L')?(c=='L'?"UNI C_ONLY_SOFTWARE_REPLAY_ON\r\n":"UNI C_ONLY_SOFTWARE_REPLAY_OFF\r\n"):"UNI REPLAY_REJECTED\r\n");
            else if(c=='R' && stopped)console("UNI RECORD_REJECTED_GATEWAY_STOPPED\r\n");
            else unified_audio_command(c,stopped);
            continue;
        }
        if(c=='I' && !used){console("UNI ID V1 DUAL_CAN_MIC_MQTT_TTS CONFIG_RAM\r\n");continue;}
        if(c=='\r')continue;
        if(c=='\n') {
            if(!strcmp(line,"UNISTART C")){final_can_mask=0;run_limit_ms=0;}
            else if(!strcmp(line,"UNISTART BC")){final_can_mask=2;run_limit_ms=0;}
            else if(!strcmp(line,"UNISTART ABC")){final_can_mask=3;run_limit_ms=0;}
            else if(!strcmp(line,"B5START")){final_can_mask=3;run_limit_ms=B5_WINDOW_MS;}
            else {used=0;memset(line,0,sizeof line);continue;}
            if(gateway_config_valid()){
                /* 启动前累计错误留档；仅把本轮武装后的新增错误判为网络故障。 */
                uart_error_baseline=platform_uart_errors_total();armed=true;
            }
            used=0;memset(line,0,sizeof line);
        } else if(used<sizeof line-1)line[used++]=(char)c;
        else used=sizeof line-1;
    }
}
#endif
static void diagnostic(unsigned stage) {
    char line[300];
    /* 仅固定计数/状态，无Topic、载荷、Wi-Fi或凭据；QoS0不命名为云端接收成功。 */
    if(stage==0){
    (void)snprintf(line,sizeof(line),"B5 DIAG tick=%lu session=%lu rx=%lu txack=%lu txfail=%lu overflow=%lu esr=%lu uart_err=%lu live=%u cache=%u dropped=%lu q0_transport=%lu q1_puback=%lu mqtt_fail=%lu stop=%u\r\n",
        (unsigned long)g_uptime_ms,(unsigned long)gateway.session,(unsigned long)b4_hw_diag[1].received,
        (unsigned long)b4_hw_diag[1].tx_acked,(unsigned long)b4_hw_diag[1].tx_failed,
        (unsigned long)b4_hw_diag[1].overflow,(unsigned long)b4_hw_diag[1].esr,(unsigned long)platform_uart_errors_total(),gateway.router.ln,gateway.router.cn,
        (unsigned long)gateway.router.dropped,(unsigned long)mqtt_qos0_transport_ok,
        (unsigned long)mqtt_qos1_puback,(unsigned long)mqtt_failed_count,(unsigned)stopped);
    console(line);
#ifdef MP_FINAL_UNIFIED
    snprintf(line,sizeof line,"UNI CAN water_a=%lu water_b=%lu mask=%u limit_ms=%lu network_fault=%u replay_a=%lu replay_b=%lu can_poll_cycles_max=%lu\r\n",
        (unsigned long)b4_hw_diag[0].high_water,(unsigned long)b4_hw_diag[1].high_water,
        final_can_mask,(unsigned long)run_limit_ms,(unsigned)network_fault,
        (unsigned long)b4_replayed[0],(unsigned long)b4_replayed[1],(unsigned long)can_poll_cycles_max);console(line);
#ifdef __arm__
    snprintf(line,sizeof line,"UNI IRQ group=%lu can_a=%u can_b=%u dma=%u calls_a=%lu calls_b=%lu\r\n",
        (unsigned long)((SCB->AIRCR>>8)&7u),(unsigned)NVIC_GetPriority(CAN1_RX0_IRQn),
        (unsigned)NVIC_GetPriority(CAN2_RX0_IRQn),(unsigned)NVIC_GetPriority(DMA1_Stream0_IRQn),
        (unsigned long)b4_irq_entries[0],(unsigned long)b4_irq_entries[1]);console(line);
#endif
#endif
#ifdef MP_ABC_TRI_CANDIDATE
    (void)snprintf(line,sizeof(line),"ABC A_CAN rx=%lu txack=%lu txfail=%lu overflow=%lu esr=%lu\r\n",
        (unsigned long)b4_hw_diag[0].received,(unsigned long)b4_hw_diag[0].tx_acked,
        (unsigned long)b4_hw_diag[0].tx_failed,(unsigned long)b4_hw_diag[0].overflow,
        (unsigned long)b4_hw_diag[0].esr);console(line);
    B4Segment *a=&gateway.segments[0];
    (void)snprintf(line,sizeof(line),"ABC A_STATE boot=%lu gen=%lu flags=%lu completion=%lu packed=%lu emitted=%u emitted_tick=%lu nibp_seq=%lu\r\n",
        (unsigned long)a->observed_boot,(unsigned long)a->generation,
        (unsigned long)mp_od_read(&a->od,0x3130,1),(unsigned long)mp_od_read(&a->od,0x3111,1),
        (unsigned long)mp_od_read(&a->od,0x3111,2),(unsigned)a->nibp_emitted,
        (unsigned long)a->nibp_tick,(unsigned long)a->seq[MP_NIBP]);console(line);
#endif
    return;}
    if(stage==1){
    (void)snprintf(line,sizeof(line),"B5 WAVE gaps=%lu quality_resets=%lu partial_discarded=%lu unstamped=%lu\r\n",
        (unsigned long)gateway.wave_gaps,(unsigned long)gateway.quality_resets,
        (unsigned long)gateway.partial_discarded,(unsigned long)gateway.unstamped);
    console(line);
#ifdef MP_FINAL_UNIFIED
    (void)snprintf(line,sizeof line,"UNI WAVE_FLOW ag=%lu bg0=%lu bg1=%lu aq=%lu bq0=%lu bq1=%lu ad=%lu bd0=%lu bd1=%lu us=%lu up=%lu ut=%lu\r\n",
        (unsigned long)gateway.flow_gaps[0][0],(unsigned long)gateway.flow_gaps[1][0],(unsigned long)gateway.flow_gaps[1][1],
        (unsigned long)gateway.flow_quality[0][0],(unsigned long)gateway.flow_quality[1][0],(unsigned long)gateway.flow_quality[1][1],
        (unsigned long)gateway.flow_discarded[0][0],(unsigned long)gateway.flow_discarded[1][0],(unsigned long)gateway.flow_discarded[1][1],
        (unsigned long)gateway.unstamped_stream[MP_SPO2],(unsigned long)gateway.unstamped_stream[MP_PR],(unsigned long)gateway.unstamped_stream[MP_TEMP]);console(line);
    (void)snprintf(line,sizeof line,"UNI PPG_PARTIAL batches=%lu samples=%lu tail=%u\r\n",(unsigned long)gateway.ppg_partial_batches,(unsigned long)gateway.ppg_partial_samples,(unsigned)gateway.segments[0].wave[0].count);console(line);
#endif
    return;}
    EspIoMetrics io; platform_io_snapshot(&io);
    if(stage==2){
    (void)snprintf(line,sizeof(line),"B5 IO tx_calls=%lu tx_ok=%lu tx_ms=%lu rx_queries=%lu rx_empty=%lu rx_reads=%lu\r\n",
        (unsigned long)io.tx_calls,(unsigned long)io.tx_confirmed,(unsigned long)io.tx_ms,
        (unsigned long)io.rx_queries,(unsigned long)io.rx_empty,(unsigned long)io.rx_reads);
    console(line);return;}
#ifdef MP_B5_EGRESS_FINAL
    GatewayMqttMetrics mq;gateway_mqtt_metrics(&mq);
    const B5Latency *lat[]={&io.command,&io.prompt,&io.data,&io.send_ok,&mq.json,&mq.send,&mq.ack,&gateway.router.residence,&gateway.router.source_age};
    for(unsigned i=0;i<9;i++) {
        if(stage!=3+i)continue;
        const B5Latency *s=lat[i];
        (void)snprintf(line,sizeof(line),"B5 LAT stage=%u n=%lu p50_upper=%lu p95_upper=%lu p99_upper=%lu max=%lu\r\n",i,
            (unsigned long)s->count,(unsigned long)b5_latency_percentile(s,50),(unsigned long)b5_latency_percentile(s,95),
            (unsigned long)b5_latency_percentile(s,99),(unsigned long)s->max);console(line);
    }
    if(stage==12){
    (void)snprintf(line,sizeof(line),"B5 QUEUE high=%lu replaced=%lu overflow=%lu expired=%lu phase=%lu unsynced=%lu budget_refused=%lu\r\n",
        (unsigned long)gateway.router.high_water,(unsigned long)gateway.router.live_replaced,
        (unsigned long)gateway.router.live_overflow,(unsigned long)gateway.router.expired,
        (unsigned long)io.at_phase,(unsigned long)io.unsynced,(unsigned long)io.budget_refused);console(line);return;}
    const unsigned streams[]={MP_ECG,MP_RESP,MP_HR,MP_RR,MP_TEMP,MP_NODE_STATUS,MP_GATEWAY_STATUS};
    for(unsigned i=0;i<7;i++){
        if(stage!=13+i)continue;
        unsigned k=streams[i];(void)snprintf(line,sizeof(line),"B5 FLOW stream=%u put=%lu take=%lu history=%lu\r\n",k,
            (unsigned long)gateway.router.enqueued[k],(unsigned long)gateway.router.taken[k],
            (unsigned long)gateway.router.historized[k]);console(line);
    }
    if(stage==20 && gateway.router.temp_reported<gateway.router.temp_written) {
        B5TempEntry t=gateway.router.temp_entry[gateway.router.temp_reported++%8];
        (void)snprintf(line,sizeof(line),"B5 TEMP_ENTRY seq=%lu epoch=%lu boot=%lu report_utc=%lu%03lu arrival_utc=%lu%03lu centi=%ld valid=%lu lost=%lu\r\n",
            (unsigned long)t.seq,(unsigned long)t.epoch,(unsigned long)t.boot,(unsigned long)(t.report_utc/1000u),(unsigned long)(t.report_utc%1000u),
            (unsigned long)(t.arrival_utc/1000u),(unsigned long)(t.arrival_utc%1000u),(long)t.centi,(unsigned long)t.valid,
            (unsigned long)gateway.router.temp_trace_lost);console(line);
    }
#ifdef __arm__
    if(stage==21){(void)snprintf(line,sizeof(line),"B5 RAM stack_used_upper=%lu\r\n",(unsigned long)b5_stack_used_upper());console(line);}
#endif
    if(stage==22){(void)snprintf(line,sizeof(line),"B5 SCHED service_gap=%lu console_ms=%lu rx_high=%lu\r\n",
        (unsigned long)io.service_gap_max,(unsigned long)io.console_max,(unsigned long)io.rx_high_water);console(line);}
#endif
}
static void diagnostic_idle(void) {
#ifdef MP_FINAL_UNIFIED
    if(!unified_audio_quiet())return;
#endif
    static unsigned stage=23;
    static uint32_t essential_at;
    static bool queue_due;
    if(platform_console_busy())return;
#ifdef MP_B5_EGRESS_FINAL
#ifdef MP_ABC_TRI_CANDIDATE
    /* 双板标量持续等待PUBACK时仍有AT空档，不能饿死温度入口取证。 */
    if(!platform_at_synchronized())return;
#else
    if(publisher.pending || publisher.deferred || !platform_at_synchronized())return;
#endif
#endif
    /* 主诊断和队列按固定时隙优先，不能等完整细项轮转后才留证。 */
    uint32_t elapsed=g_uptime_ms-essential_at;
    if(elapsed>=5000u){essential_at+=elapsed/5000u*5000u;queue_due=true;diagnostic(0);return;}
    if(queue_due){queue_due=false;diagnostic(12);return;}
    if(gateway.router.temp_reported<gateway.router.temp_written){diagnostic(20);return;}
    if(stage>=23){if(g_uptime_ms-diag_at<5000u)return;diag_at=g_uptime_ms;stage=1;}
    if(stage==12 || stage==20)stage++;
    diagnostic(stage++);
}
#ifdef MP_B5_EGRESS_FINAL
static void transaction_stop_trace(void) {
    char line[256];const EspIoMetrics *s=&stop_io;
    (void)snprintf(line,sizeof(line),"B5 TX_CONTEXT id=%lu at=%lu qos=%lu stream=%lu seq=%lu pending=%lu age=%lu budget=%lu required=%lu written=%lu\r\n",
        (unsigned long)s->tx_id,(unsigned long)s->tx_at,(unsigned long)s->qos,(unsigned long)s->stream,
        (unsigned long)s->frame_seq,(unsigned long)s->pending_id,(unsigned long)s->pending_age,
        (unsigned long)s->tx_budget,(unsigned long)s->required,(unsigned long)s->written);console(line);
    unsigned n=s->event_count<4?s->event_count:4;
    for(unsigned i=0;i<n;i++){
        const EspAtEvent *e=&s->events[(s->event_count-n+i)%4];
        (void)snprintf(line,sizeof(line),"B5 AT_EVENT tick=%lu phase=%lu written=%lu reply=%lu reason=%lu flags=%lu\r\n",
            (unsigned long)e->tick,(unsigned long)e->phase,(unsigned long)e->written,
            (unsigned long)e->reply,(unsigned long)e->reason,(unsigned long)e->flags);console(line);
    }
}
#endif
static void service(void) {
#ifdef MP_FINAL_UNIFIED
    if(stopped || !armed){unified_audio_local_poll();local_control();b4_hw_idle();return;}
#else
    if (stopped) { report_stop(); b4_hw_idle(); return; }
    /* 未武装时不推进CANopen/TIME，避免B尚断电时发心跳耗尽ACK并积累BOFF。 */
    if (!armed) { b4_hw_idle(); return; }
#endif
#ifdef MP_ABC_TRI_CANDIDATE
    if (b4_hw_diag[0].overflow
#ifndef MP_ABC_APPLIANCE
        || b4_hw_diag[0].busoff || b4_hw_diag[0].tx_failed
#endif
       ) { stop(); return; }
#endif
    if (armed && (
#ifdef MP_FINAL_UNIFIED
        (run_limit_ms && (uint32_t)(g_uptime_ms-armed_at)>=run_limit_ms) ||
#else
        (uint32_t)(g_uptime_ms - armed_at) >= B5_WINDOW_MS ||
#endif
        b4_hw_diag[1].overflow
#ifndef MP_ABC_APPLIANCE
        || b4_hw_diag[1].busoff || b4_hw_diag[1].tx_failed
#endif
#ifndef MP_FINAL_UNIFIED
        || platform_uart_errors_total()
#ifdef MP_B5_EGRESS_FINAL
        || platform_at_unsynced()
#endif
#endif
        )) {
        stop(); return;
    }
    /* 停机仍逐次检查；CAN IRQ保留原始到达时刻，每5ms批量推进CANopen。 */
    if (service_seen && (uint32_t)(g_uptime_ms - service_at) < B5_SERVICE_MS) return;
    service_seen = true; service_at = g_uptime_ms;
    b4_gateway_tick(&gateway, g_uptime_ms);
#if defined(MP_FINAL_UNIFIED) && defined(__arm__)
    uint32_t poll_began=*(volatile uint32_t *)0xe0001004;
#endif
    b4_hw_poll(&gateway);
#if defined(MP_FINAL_UNIFIED) && defined(__arm__)
    uint32_t cycles=*(volatile uint32_t *)0xe0001004-poll_began;
    if(cycles>can_poll_cycles_max)can_poll_cycles_max=cycles;
#endif
#ifdef MP_FINAL_UNIFIED
    if(!network_fault && (platform_at_unsynced() || platform_uart_errors_total()!=uart_error_baseline)) {
        network_fault=true;network_open=mqtt_connected=false;
        mp_router_online(&gateway.router,false);unified_audio_network(false);
    }
    unified_audio_local_poll();local_control();
#if defined(MP_ABC_APPLIANCE) && defined(__arm__)
    unified_audio_key(!(GPIOE->IDR&(1u<<3)));
#endif
#endif
    if (network_open && g_uptime_ms - last_sync >= 10000u) {
        b4_gateway_sync_ms(&gateway, gateway_epoch_milliseconds(), g_uptime_ms);
        last_sync = g_uptime_ms;
    }
    if (mqtt_connected && g_uptime_ms - status_at >= 5000u) {
        MpFrame status = will; status.valid = true; status.timestamp = gateway_epoch_milliseconds();
        status.seq = ++status_seq; mp_router_put(&gateway.router, &status); status_at = g_uptime_ms;
    }
}
int main(void) {
    platform_init();
#if defined(MP_B5_EGRESS_FINAL) && defined(__arm__)
    b5_stack_watermark_init();
#endif
    if (b4_gateway_init(&gateway)
#ifndef MP_FINAL_UNIFIED
        || b4_hw_init()
#endif
       ) while (1) {}
#ifndef MP_ABC_TRI_CANDIDATE
    b4_gateway_link(&gateway, 0, false);
#endif
    platform_set_poll(service);
#ifdef MP_FINAL_UNIFIED
#ifdef MP_ABC_APPLIANCE
    final_can_mask=3;run_limit_ms=0;
    uart_error_baseline=platform_uart_errors_total();
    console("UNI AUTO ABC AUDIO_MAX2S NO_FLASH_WRITE\r\n");
#else
    console("UNI DISARMED V1 C_BC_ABC NO_FLASH_WRITE\r\n");
    while(!armed){platform_poll();local_control();}
#endif
    unified_audio_init();
#if defined(MP_ABC_APPLIANCE) && defined(__arm__)
    RCC_AHB1PeriphClockCmd(RCC_AHB1Periph_GPIOE,ENABLE);
    GPIO_InitTypeDef key={0};key.GPIO_Pin=GPIO_Pin_3;key.GPIO_Mode=GPIO_Mode_IN;key.GPIO_PuPd=GPIO_PuPd_UP;
    GPIO_Init(GPIOE,&key);
#endif
    if(b4_hw_init())for(;;){}
    for(unsigned bus=0;bus<2;bus++)b4_gateway_link(&gateway,bus,(final_can_mask&(1u<<bus))!=0);
#ifdef MP_ABC_APPLIANCE
    armed=true;
#endif
    char uart_start[96];
    snprintf(uart_start,sizeof uart_start,"UNI UART baseline=%lu total=%lu\r\n",
        (unsigned long)uart_error_baseline,(unsigned long)platform_uart_errors_total());console(uart_start);
#else
#ifdef MP_ABC_TRI_CANDIDATE
    console("B5 DISARMED MOCK ABC_DUAL_CAN NO_FLASH_WRITE\r\n");
#else
    console("B5 DISARMED MOCK B_ONLY NO_FLASH_WRITE\r\n");
#endif
    char command[9] = {0}; unsigned used = 0;
    /* 固定完整命令才武装；上电串口杂字节、旧H3配置和重复命令均不能自动联网。 */
    while (!armed) {
        platform_poll(); int ch = console_char(); if (ch < 0 || ch == '\r') continue;
        if (ch == '\n') {
            if (!strcmp(command, "B5START") && gateway_config_valid()) armed = true;
            used = 0; memset(command, 0, sizeof(command));
        } else if (used < sizeof(command) - 1) command[used++] = (char)ch;
        /* 超长整行保持拒绝，不能把其尾部误识别成新的完整命令。 */
        else used = sizeof(command) - 1;
    }
#endif
    armed_at = g_uptime_ms;
#ifdef MP_B5_EGRESS_FINAL
    unsigned startup_ntp_retries=0;
#endif
#ifdef MP_ABC_TRI_CANDIDATE
#ifdef MP_FINAL_UNIFIED
    if(final_can_mask&1)
#endif
    (void)b4_gateway_nmt(&gateway, 1, CO_NMT_ENTER_OPERATIONAL);
#endif
#ifdef MP_FINAL_UNIFIED
    if(final_can_mask&2)
#endif
    (void)b4_gateway_nmt(&gateway, 2, CO_NMT_ENTER_OPERATIONAL);
#ifdef MP_ABC_APPLIANCE
    bool configured=gateway_config_valid();
    if(!configured)console("UNI AUTO CONFIG_MISSING LOCAL_ONLY\r\n");
#endif
    while (!stopped) {
#ifdef MP_ABC_APPLIANCE
        if(!configured){platform_poll();continue;}
#endif
#ifdef MP_FINAL_UNIFIED
        if(network_fault) {
            /* AT边界未知只停网络，CAN/本地STOP继续；不能盲目重发未知半帧。 */
            if(!platform_at_synchronized()){platform_poll();continue;}
            network_fault=false;uart_error_baseline=platform_uart_errors_total();
        }
#endif
#ifdef MP_B5_EGRESS_FINAL
        if(b5_business_remaining()<=B5_DRAIN_MS){while(!stopped)platform_poll();break;}
        drained=false;
#endif
        mp_router_online(&gateway.router, false); network_open = mqtt_connected = false;
        if (!gateway_network_open()) {
#ifdef MP_B5_EGRESS_FINAL
            if(!stopped && gateway_network_retryable() && startup_ntp_retries<2u) {
                startup_ntp_retries++;
                console("GW SNTP_NEXT_ENDPOINT\r\n");
                delay_ms(3000);continue;
            }
#ifdef MP_FINAL_UNIFIED
            unified_audio_network(false);gateway_network_close();reconnect_delay();continue;
#else
            if(!stopped)stop();
            gateway_network_close();break;
#endif
#else
            if (!stopped) delay_ms(3000); continue;
#endif
        }
        uint64_t now = gateway_epoch_milliseconds();
        b4_gateway_sync_ms(&gateway, now, g_uptime_ms); gateway.session = (uint32_t)now;
        network_open = true; last_sync = g_uptime_ms;
        memset(&will, 0, sizeof(will)); will.node = 3; will.stream = MP_GATEWAY_STATUS;
        will.synthetic = true; will.timestamp = now; will.epoch = gateway.session;
        will.boot = ++connection; will.seq = UINT32_MAX;
        if (stopped || !gateway_mqtt_open(&will)) {
#ifdef MP_B5_EGRESS_FINAL
#ifdef MP_FINAL_UNIFIED
            unified_audio_network(false);gateway_network_close();reconnect_delay();continue;
#else
            if(!stopped)stop();
            gateway_network_close();break;
#endif
#else
            gateway_network_close(); continue;
#endif
        }
        mp_router_online(&gateway.router, true); mqtt_connected = true;
#ifdef MP_FINAL_UNIFIED
        (void)gateway_audio_subscribe();unified_audio_network(true);
#ifdef MP_ABC_APPLIANCE
        retry_ms=2000;
#endif
#endif
        status_at = g_uptime_ms - 5000u;
        while (!stopped
#ifdef MP_FINAL_UNIFIED
               && !network_fault
#endif
              ) {
            platform_poll();
#ifdef MP_B5_EGRESS_FINAL
            bool allow_new=b5_business_remaining()>B5_DRAIN_MS;
            int progress=b5_egress_step(&gateway.router,&publisher,allow_new);
#ifdef MP_FINAL_UNIFIED
            unified_audio_step(false);
            if(platform_at_synchronized() && !platform_console_busy())unified_audio_report();
#endif
            diagnostic_idle();
            mqtt_qos0_transport_ok=publisher.q0;mqtt_qos1_puback=publisher.q1;mqtt_failed_count=publisher.failed;
            if(!progress)break;
            /* 预留1秒准备、5秒事务及2秒关闭；业务锁存仍在420秒。 */
            if(b5_business_remaining()<=B5_DRAIN_MS) {
                if(!publisher.pending){network_open=mqtt_connected=false;gateway_network_close();drained=true;while(!stopped)platform_poll();}
                continue;
            }
#else
            if (mp_router_take(&gateway.router, &publishing, g_uptime_ms)) {
                if (!b5_prepare_publish(&publishing, gateway_epoch_milliseconds())) continue;
                bool sent = gateway_mqtt_publish(&publishing);
                if (stopped) break;
                if(!sent)mqtt_failed_count++;
                else if(publishing.rate && !publishing.replay)mqtt_qos0_transport_ok++;
                else mqtt_qos1_puback++;
                mp_router_ack(&gateway.router, &publishing, sent); if (!sent) break;
            } else if (!gateway_mqtt_yield()) break;
#endif
        }
        network_open = mqtt_connected = false; mp_router_online(&gateway.router, false);
#ifdef MP_B5_EGRESS_FINAL
#ifdef MP_FINAL_UNIFIED
        unified_audio_network(false);
        if(!drained)gateway_network_close();
        memset(&publisher,0,sizeof publisher);
#else
        if(!stopped)stop();
        if(!drained)gateway_network_close();
#endif
#else
        gateway_network_close();
#endif
        if (!stopped) reconnect_delay();
    }
    report_stop();
#ifdef MP_B5_EGRESS_FINAL
    transaction_stop_trace();
#endif
    for(unsigned i=0;i<23;i++)diagnostic(i);
    while (1) {
#ifdef MP_FINAL_UNIFIED
        unified_audio_local_poll();local_control();unified_audio_report();
#endif
        b4_hw_idle();
    }
}
