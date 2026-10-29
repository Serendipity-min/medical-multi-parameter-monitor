/* 唯一B5候选：手工武装、B段、非人体MOCK；默认不自动入网，不写配置。 */
#include "b5_policy.h"
#include "../dual_can/b4_bxcan.h"
#include "gateway_transport.h"
#include "esp_io_metrics.h"
#include <string.h>
#include <stdio.h>
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
    if(!armed)return B5_WINDOW_MS;
    uint32_t used=g_uptime_ms-armed_at;return used>=B5_WINDOW_MS?0:B5_WINDOW_MS-used;
}
void b5_hard_tick(void) {
    /* 中断只锁存截止和取证，不执行CAN库、AT、printf或关闭网络。 */
    if(armed && !stopped && !stop_due && (uint32_t)(g_uptime_ms-armed_at)>=B5_WINDOW_MS) {
        stop_tick=g_uptime_ms;stop_reason=1;stop_live=gateway.router.ln;stop_cache=gateway.router.cn;
        platform_io_snapshot(&stop_io);stop_due=true;
    }
}
#endif
uint32_t b4_hw_time(void) { return g_uptime_ms; }
int b5_network_stopped(void) { return stopped
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
#ifdef MP_B5_EGRESS_FINAL
    if(!stop_due){stop_tick=g_uptime_ms;stop_live=gateway.router.ln;stop_cache=gateway.router.cn;platform_io_snapshot(&stop_io);
        stop_reason=stop_io.unsynced?2:b5_business_remaining()==0?1:3;}
#endif
    stopped = true; gateway.utc_valid = false;
    mp_router_online(&gateway.router, false); b4_hw_stop();
    report_stop();
}
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
    console(line);return;}
    if(stage==1){
    (void)snprintf(line,sizeof(line),"B5 WAVE gaps=%lu quality_resets=%lu partial_discarded=%lu unstamped=%lu\r\n",
        (unsigned long)gateway.wave_gaps,(unsigned long)gateway.quality_resets,
        (unsigned long)gateway.partial_discarded,(unsigned long)gateway.unstamped);
    console(line);return;}
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
    static unsigned stage=23;
    static uint32_t essential_at;
    static bool queue_due;
    if(platform_console_busy())return;
#ifdef MP_B5_EGRESS_FINAL
    if(publisher.pending || publisher.deferred || !platform_at_synchronized())return;
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
    if (stopped) { report_stop(); b4_hw_idle(); return; }
    /* 未武装时不推进CANopen/TIME，避免B尚断电时发心跳耗尽ACK并积累BOFF。 */
    if (!armed) { b4_hw_idle(); return; }
    if (armed && ((uint32_t)(g_uptime_ms - armed_at) >= B5_WINDOW_MS ||
        b4_hw_diag[1].overflow || b4_hw_diag[1].busoff || b4_hw_diag[1].tx_failed || platform_uart_errors_total()
#ifdef MP_B5_EGRESS_FINAL
        || platform_at_unsynced()
#endif
        )) {
        stop(); return;
    }
    /* 停机仍逐次检查；CAN IRQ保留原始到达时刻，每5ms批量推进CANopen。 */
    if (service_seen && (uint32_t)(g_uptime_ms - service_at) < B5_SERVICE_MS) return;
    service_seen = true; service_at = g_uptime_ms;
    b4_gateway_tick(&gateway, g_uptime_ms); b4_hw_poll(&gateway);
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
    if (b4_gateway_init(&gateway) || b4_hw_init()) while (1) {}
    b4_gateway_link(&gateway, 0, false); platform_set_poll(service);
    console("B5 DISARMED MOCK B_ONLY NO_FLASH_WRITE\r\n");
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
    armed_at = g_uptime_ms;
#ifdef MP_B5_EGRESS_FINAL
    unsigned startup_ntp_retries=0;
#endif
    (void)b4_gateway_nmt(&gateway, 2, CO_NMT_ENTER_OPERATIONAL);
    while (!stopped) {
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
            if(!stopped)stop();
            gateway_network_close();break;
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
            if(!stopped)stop();
            gateway_network_close();break;
#else
            gateway_network_close(); continue;
#endif
        }
        mp_router_online(&gateway.router, true); mqtt_connected = true;
        status_at = g_uptime_ms - 5000u;
        while (!stopped) {
            platform_poll();
#ifdef MP_B5_EGRESS_FINAL
            bool allow_new=b5_business_remaining()>B5_DRAIN_MS;
            int progress=b5_egress_step(&gateway.router,&publisher,allow_new);
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
        if(!stopped)stop();
        if(!drained)gateway_network_close();
#else
        gateway_network_close();
#endif
        if (!stopped) delay_ms(2000);
    }
    report_stop();
#ifdef MP_B5_EGRESS_FINAL
    transaction_stop_trace();
#endif
    for(unsigned i=0;i<23;i++)diagnostic(i);
    while (1) b4_hw_idle();
}
