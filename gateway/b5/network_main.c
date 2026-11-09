/* 默认保留手动入口；显式五板整机构建才自动启动，不写持久配置。 */
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
#ifdef MP_FIVE_APPLIANCE
#include "stm32f4xx_gpio.h"
#include "stm32f4xx_rcc.h"
#endif
#endif
unsigned final_can_mask;
static uint32_t run_limit_ms=B5_WINDOW_MS;
static bool network_fault;
static uint32_t uart_error_baseline,can_poll_cycles_max;
#ifdef MP_ESP_UART_230400
void b5_uart_accept_baseline(void){uart_error_baseline=platform_uart_errors_total();}
#endif
static void local_control(void);
#ifdef MP_FIVE_APPLIANCE
static bool runtime_ready;
#ifndef MP_FIVE_FIELD01
static uint32_t retry_ms=2000;
static void reconnect_delay(void) {
    delay_ms(retry_ms);
    if(retry_ms<30000u)retry_ms=retry_ms<15000u?retry_ms*2u:30000u;
}
#endif
#endif
#endif
#ifndef MP_FIVE_APPLIANCE
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
#ifndef MP_FIVE_FIELD01
static uint32_t diag_at;
#endif
static uint32_t mqtt_qos0_transport_ok, mqtt_qos1_puback, mqtt_failed_count;
static uint32_t service_at;
static volatile bool armed, stopped;
#ifdef MP_FIVE_APPLIANCE
bool unified_audio_fact_current(unsigned node,unsigned stream,uint32_t seq,uint32_t epoch,uint32_t boot) {
    unsigned bus=node==1 || node==5?0:1,slot=node==4 || node==5?1:0;
    B4Segment *s=&gateway.segments[bus];B4Remote *r=&s->remote[slot];
    unsigned base=0x3100u+slot*0x100u;
    unsigned bit=stream==MP_SPO2?1:stream==MP_PR || stream==MP_HR?2:stream==MP_TEMP?4:3;
    uint32_t flags=mp_od_read(&s->od,base+0x30,1);
    bool qualified=r->seen[4] && (uint32_t)(gateway.now-r->seen_at[4])<=1500u && (flags&(1u<<bit));
    if(stream==MP_TEMP && mp_od_read(&s->od,base+0x20,4)>2500u)qualified=false;
    if(stream==MP_NIBP && (!(flags&(1u<<9)) || !r->seen[1] ||
       (uint32_t)(gateway.now-r->seen_at[1])>1500u))qualified=false;
    /* B5 emit 的事实身份是网关会话＋观察代次，不能误用原PDO generation。 */
    return qualified && gateway.utc_valid && b4_gateway_online(&gateway,node) && gateway.session==epoch &&
        r->observed_boot==boot && seq && seq<=r->seq[stream] && (stream!=MP_NIBP || seq==r->seq[stream]);
}
#endif
static bool network_open, mqtt_connected, service_seen, stop_reported;
#ifdef MP_B5_EGRESS_FINAL
#include "egress.h"
static B5Publisher publisher;
static bool drained;
static volatile bool stop_due;
static uint32_t stop_tick,stop_reason,stop_live,stop_cache;
static EspIoMetrics stop_io;
#ifdef MP_FIVE_FIELD01
#include "field01_probe.inc"
enum { PRE_UNUSED, PRE_QUEUED, PRE_RUNNING, PRE_CLEAN, PRE_DIRTY };
static volatile unsigned pre_state;
static uint32_t pre_deadline,pre_target;

static bool pre_active(void) {
    return pre_state==PRE_QUEUED || pre_state==PRE_RUNNING;
}
#endif
uint32_t b5_business_remaining(void) {
#ifdef MP_FIVE_FIELD01
    if(pre_active()){
        uint32_t now=g_uptime_ms;
        return now<pre_deadline?pre_deadline-now:0;
    }
    return field01_remaining(g_uptime_ms,field01_t0);
#elif defined(MP_FINAL_UNIFIED)
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
#ifdef MP_FIVE_FIELD01
    if(g_uptime_ms>=FIELD01_HARD_MS || (!pre_active() && !b5_business_remaining()))
        field01_latch(FIELD01_TIMER);
#else
    if(armed && !stopped && !stop_due &&
#ifdef MP_FINAL_UNIFIED
       run_limit_ms && (uint32_t)(g_uptime_ms-armed_at)>=run_limit_ms) {
#else
       (uint32_t)(g_uptime_ms-armed_at)>=B5_WINDOW_MS) {
#endif
        stop_tick=g_uptime_ms;stop_reason=1;stop_live=gateway.router.ln;stop_cache=gateway.router.cn;
        platform_io_snapshot(&stop_io);stop_due=true;
    }
#endif
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
#ifdef MP_FIVE_FIELD01
    stopped=true;
#endif
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
#ifdef MP_FIVE_FIELD01
    static char command[16];
    static unsigned length;
    for(unsigned budget=0;budget<16;budget++){
        int c=console_char();if(c<0)break;
        if(c=='\r')continue;
        if(c!='\n'){
            if(length<sizeof command)command[length++]=(char)c;
            continue;
        }
        if(length<sizeof command){
            command[length]=0;
            if(length==sizeof("FIELD01 STOP")-1 && !memcmp(command,"FIELD01 STOP",length) && !stopped)field01_latch(FIELD01_MANUAL);
            if(length==sizeof("FIELD01 START")-1 && !memcmp(command,"FIELD01 START",length) && !armed && !stopped && !stop_due &&
                !pre_active() && pre_state!=PRE_DIRTY && b5_business_remaining() && gateway_config_valid()){
                uart_error_baseline=platform_uart_errors_total();armed=true;
            }
            if(length==sizeof("FIELD01 KEY")-1 && !memcmp(command,"FIELD01 KEY",length) && field01_t0 &&
                g_uptime_ms-field01_t0<FIELD01_AUDIO_AT_MS)field_key_approved=true;
            if(pre_state==PRE_UNUSED && !armed && !stopped && !stop_due &&
                ((length==11 && !memcmp(command,"FIELD01 PRE",11)) ||
                 (length==15 && (!memcmp(command,"FIELD01 PRE 230",15) ||
                                 !memcmp(command,"FIELD01 PRE 500",15))))) {
                uint32_t now=g_uptime_ms;
                if(now<FIELD01_READY_MS){
                    pre_target=length==11?ESP_UART_BAUD:command[12]=='2'?230400u:500000u;
                    pre_deadline=now+FIELD01_PRE_MS;
                    pre_state=PRE_QUEUED;
                }
            }
        }
        length=0;
    }
#else
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
#endif
}
#endif
static void diagnostic(unsigned stage) {
#ifdef MP_TRANSPORT_PROFILE
    char line[600];
#else
    char line[300];
#endif
    /* 仅固定计数/状态，无Topic、载荷、Wi-Fi或凭据；QoS0不命名为云端接收成功。 */
    if(stage==0){
    (void)snprintf(line,sizeof(line),"B5 DIAG tick=%lu session=%lu rx=%lu txack=%lu txfail=%lu overflow=%lu esr=%lu uart_err=%lu live=%u cache=%u dropped=%lu q0_transport=%lu q1_puback=%lu mqtt_fail=%lu stop=%u"
#ifndef MP_TRANSPORT_PROFILE
        "\r\n"
#endif
        ,
        (unsigned long)g_uptime_ms,(unsigned long)gateway.session,(unsigned long)b4_hw_diag[1].received,
        (unsigned long)b4_hw_diag[1].tx_acked,(unsigned long)b4_hw_diag[1].tx_failed,
        (unsigned long)b4_hw_diag[1].overflow,(unsigned long)b4_hw_diag[1].esr,(unsigned long)platform_uart_errors_total(),gateway.router.ln,gateway.router.cn,
        (unsigned long)gateway.router.dropped,(unsigned long)mqtt_qos0_transport_ok,
        (unsigned long)mqtt_qos1_puback,(unsigned long)mqtt_failed_count,(unsigned)stopped);
#ifdef MP_TRANSPORT_PROFILE
    EspCpuMetrics cpu;
    platform_cpu_snapshot(&cpu);
    size_t used=strlen(line);
    (void)snprintf(line+used,sizeof(line)-used,
        " svc_cyc=%lu svc_n=%lu tx_cyc=%lu tx_b=%lu txe_cyc=%lu await_cyc=%lu await_b=%lu"
        " rxstep_cyc=%lu rxstep_b=%lu irq_cyc=%lu irq_n=%lu gmr_rx_b=%lu gmr_n=%lu\r\n",
        (unsigned long)cpu.service_cycles,(unsigned long)cpu.service_calls,
        (unsigned long)cpu.tx_cycles,(unsigned long)cpu.tx_bytes,(unsigned long)cpu.txe_cycles,
        (unsigned long)cpu.await_cycles,(unsigned long)cpu.await_bytes,
        (unsigned long)cpu.rx_step_cycles,(unsigned long)cpu.rx_step_bytes,
        (unsigned long)cpu.irq_cycles,(unsigned long)cpu.irq_calls,
        (unsigned long)cpu.gmr_rx_bytes,(unsigned long)cpu.gmr_calls);
#endif
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
#ifdef MP_FIVE_NODE
    B4Remote *bp=&a->remote[1];unsigned bp_base=0x3200;const char *bp_label="E_STATE";
#else
    B4Remote *bp=&a->remote[0];unsigned bp_base=0x3100;const char *bp_label="A_STATE";
#endif
    (void)snprintf(line,sizeof(line),"ABC %s boot=%lu gen=%lu flags=%lu completion=%lu packed=%lu emitted=%u emitted_tick=%lu nibp_seq=%lu\r\n",
        bp_label,(unsigned long)bp->observed_boot,(unsigned long)bp->generation,
        (unsigned long)mp_od_read(&a->od,bp_base+0x30,1),(unsigned long)mp_od_read(&a->od,bp_base+0x11,1),
        (unsigned long)mp_od_read(&a->od,bp_base+0x11,2),(unsigned)bp->nibp_emitted,
        (unsigned long)bp->nibp_tick,(unsigned long)bp->seq[MP_NIBP]);console(line);
#endif
    return;}
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
#ifdef MP_FIVE_NODE
    if(stage==23){
        (void)snprintf(line,sizeof(line),"FIVE STATE tick=%lu wrong_bus=%lu malformed=%lu resets=%lu partial_batches=%lu partial_samples=%lu\r\n",
            (unsigned long)g_uptime_ms,(unsigned long)gateway.wrong_bus,(unsigned long)gateway.malformed,
            (unsigned long)gateway.resets,(unsigned long)gateway.ppg_partial_batches,(unsigned long)gateway.ppg_partial_samples);
        console(line);
    }
    if(stage>=24 && stage<28){
        unsigned bus=(stage-24)/2,slot=(stage-24)%2;
        unsigned node=slot?(bus?4u:5u):bus+1u;
        B4Remote *r=&gateway.segments[bus].remote[slot];
        (void)snprintf(line,sizeof(line),"FIVE RX node=%u bus=%u rx=%lu hb=%lu hb_age=%lu nmt=%u boot=%lu gen=%lu p0=%lu p1=%lu p2=%lu p3=%lu p4=%lu emcy=%lu code=%u gap0=%lu gap1=%lu\r\n",
            node,bus,(unsigned long)r->rx_frames,(unsigned long)r->heartbeat_count,
            (unsigned long)(g_uptime_ms-r->heartbeat_tick),(unsigned)r->nmt_state,
            (unsigned long)r->observed_boot,(unsigned long)r->generation,
            (unsigned long)r->pdo_count[0],(unsigned long)r->pdo_count[1],(unsigned long)r->pdo_count[2],
            (unsigned long)r->pdo_count[3],(unsigned long)r->pdo_count[4],
            (unsigned long)r->emcy_errors,(unsigned)r->last_emcy_error,
            (unsigned long)r->wave_gaps[0],(unsigned long)r->wave_gaps[1]);
        console(line);
    }
#endif
#endif
}
#ifndef MP_FIVE_FIELD01
static void diagnostic_idle(void) {
#ifdef MP_FINAL_UNIFIED
    if(!unified_audio_quiet())return;
#endif
#ifdef MP_FIVE_NODE
    enum { DIAGNOSTIC_STAGES=28 };
#else
    enum { DIAGNOSTIC_STAGES=23 };
#endif
    static unsigned stage=DIAGNOSTIC_STAGES;
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
    if(stage>=DIAGNOSTIC_STAGES){if(g_uptime_ms-diag_at<5000u)return;diag_at=g_uptime_ms;stage=1;}
    if(stage==12 || stage==20)stage++;
    diagnostic(stage++);
}
#endif
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
#ifdef MP_FIVE_APPLIANCE
    /* 初始化中的AT/音频回调不能提前推进未就绪的CAN对象。 */
    if(!runtime_ready){
#ifdef MP_FIVE_FIELD01
        if(pre_active())local_control();
#endif
        b4_hw_idle();return;
    }
#endif
#ifdef MP_FINAL_UNIFIED
#ifdef MP_FIVE_FIELD01
    if(stop_due && !stopped)stop();
#endif
    if(stopped || !armed){unified_audio_local_poll();local_control();b4_hw_idle();return;}
#else
    if (stopped) { report_stop(); b4_hw_idle(); return; }
    /* 未武装时不推进CANopen/TIME，避免B尚断电时发心跳耗尽ACK并积累BOFF。 */
    if (!armed) { b4_hw_idle(); return; }
#endif
#if defined(MP_ABC_TRI_CANDIDATE) && !defined(MP_FIVE_APPLIANCE)
    if (b4_hw_diag[0].overflow || b4_hw_diag[0].busoff || b4_hw_diag[0].tx_failed) { stop(); return; }
#endif
    if (armed && (
#ifdef MP_FINAL_UNIFIED
        (run_limit_ms && (uint32_t)(g_uptime_ms-armed_at)>=run_limit_ms) ||
#else
        (uint32_t)(g_uptime_ms - armed_at) >= B5_WINDOW_MS ||
#endif
#ifndef MP_FIVE_APPLIANCE
        b4_hw_diag[1].overflow || b4_hw_diag[1].busoff || b4_hw_diag[1].tx_failed
#else
        false
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
    if(!network_fault &&
#ifdef MP_ESP_UART_230400
       !gateway_uart_negotiating() &&
#endif
       (platform_at_unsynced() || platform_uart_errors_total()!=uart_error_baseline)) {
        network_fault=true;network_open=mqtt_connected=false;
        mp_router_online(&gateway.router,false);unified_audio_network(false);
    }
    unified_audio_local_poll();local_control();
#if defined(MP_FIVE_APPLIANCE) && defined(__arm__)
#ifdef MP_FIVE_FIELD01
    static bool field_key_released;
    bool down=!(GPIOE->IDR & GPIO_Pin_3);
    uint32_t elapsed=g_uptime_ms-field01_t0;
    if(field_key_approved && field01_t0 && !stop_due &&
        elapsed>=FIELD01_AUDIO_AT_MS && elapsed<FIELD01_AUDIO_END_MS){
        if(!down)field_key_released=true;
        if(field_key_released)unified_audio_key(down);
    }
#else
    unified_audio_key(!(GPIOE->IDR & GPIO_Pin_3));
#endif
#endif
#endif
    if (network_open && g_uptime_ms - last_sync >= 10000u) {
        b4_gateway_sync_ms(&gateway, gateway_epoch_milliseconds(), g_uptime_ms);
        last_sync = g_uptime_ms;
    }
#ifdef MP_FIVE_FIELD01
    field01_poll();
    if(stop_due){stop();return;}
#endif
    if (mqtt_connected && g_uptime_ms - status_at >= 5000u) {
        MpFrame status = will; status.valid = true; status.timestamp = gateway_epoch_milliseconds();
        status.seq = ++status_seq; mp_router_put(&gateway.router, &status); status_at = g_uptime_ms;
    }
}
#ifdef MP_FIVE_FIELD01
static void field01_disarmed_step(void) {
    platform_poll();
    local_control();
    if(pre_state==PRE_QUEUED && !stop_due){
        pre_state=PRE_RUNNING;
        pre_state=gateway_preflight(pre_target,pre_deadline)?PRE_CLEAN:PRE_DIRTY;
    }
}
#endif
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
#if defined(MP_FIVE_FIELD01)
    final_can_mask=3;run_limit_ms=0;
    console("FIELD01 DISARMED C_ONLY_INSTALL TLS_28895 NO_AUTORETRY\r\n");
    while(!armed && !stop_due)field01_disarmed_step();
    if(stop_due){stopped=true;report_stop();for(;;)b4_hw_idle();}
    console("FIELD01 START_ACCEPTED\r\n");
#elif defined(MP_FIVE_APPLIANCE)
    final_can_mask=3;run_limit_ms=0;
    uart_error_baseline=platform_uart_errors_total();
    console("FIVE AUTO LOCAL_CAN KEY1_AUDIO_MAX2S NO_FLASH_WRITE\r\n");
#else
    console("UNI DISARMED V1 C_BC_ABC NO_FLASH_WRITE\r\n");
    while(!armed){platform_poll();local_control();}
#endif
    unified_audio_init();
#if defined(MP_FIVE_APPLIANCE) && defined(__arm__)
    RCC_AHB1PeriphClockCmd(RCC_AHB1Periph_GPIOE,ENABLE);
    GPIO_InitTypeDef key={0};key.GPIO_Pin=GPIO_Pin_3;key.GPIO_Mode=GPIO_Mode_IN;key.GPIO_PuPd=GPIO_PuPd_UP;
    GPIO_Init(GPIOE,&key);
#endif
    if(b4_hw_init())for(;;){}
    for(unsigned bus=0;bus<2;bus++)b4_gateway_link(&gateway,bus,(final_can_mask&(1u<<bus))!=0);
#ifdef MP_FIVE_APPLIANCE
    runtime_ready=true;armed=true;
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
#if defined(MP_B5_EGRESS_FINAL) && !defined(MP_FIVE_FIELD01)
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
#ifdef MP_FIVE_APPLIANCE
    (void)b4_gateway_nmt(&gateway, 4, CO_NMT_ENTER_OPERATIONAL);
    (void)b4_gateway_nmt(&gateway, 5, CO_NMT_ENTER_OPERATIONAL);
    if(!gateway_config_valid())console("FIVE AUTO CONFIG_MISSING LOCAL_ONLY\r\n");
#endif
    while (!stopped) {
#ifdef MP_FIVE_APPLIANCE
        if(!gateway_config_valid()){platform_poll();continue;}
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
#ifdef MP_ESP_UART_230400
            if(gateway_uart_negotiation_failed()){
                while(!stopped)platform_poll();
                break;
            }
#endif
#ifdef MP_FIVE_FIELD01
            field01_latch(FIELD01_LINK);if(!stopped)stop();gateway_network_close();break;
#elif defined(MP_B5_EGRESS_FINAL)
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
#ifdef MP_FIVE_FIELD01
            field01_latch(FIELD01_LINK);if(!stopped)stop();gateway_network_close();break;
#elif defined(MP_B5_EGRESS_FINAL)
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
#if defined(MP_FIVE_APPLIANCE) && !defined(MP_FIVE_FIELD01)
        retry_ms=2000;
#endif
#ifdef MP_FINAL_UNIFIED
        (void)gateway_audio_subscribe();unified_audio_network(true);
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
            unified_audio_step(!publisher.deferred && !gateway.router.ln && allow_new);
            if(platform_at_synchronized() && !platform_console_busy())unified_audio_report();
#endif
#ifdef MP_FIVE_FIELD01
            if(progress && !b5_network_stopped())field01_begin();
            field01_status();
#else
            diagnostic_idle();
#endif
            mqtt_qos0_transport_ok=publisher.q0;mqtt_qos1_puback=publisher.q1;mqtt_failed_count=publisher.failed;
            if(!progress)break;
            /* 预留1秒准备、5秒事务及2秒关闭；业务锁存仍在420秒。 */
#ifndef MP_FIVE_FIELD01
            if(b5_business_remaining()<=B5_DRAIN_MS) {
                if(!publisher.pending){network_open=mqtt_connected=false;gateway_network_close();drained=true;while(!stopped)platform_poll();}
                continue;
            }
#endif
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
#ifdef MP_FIVE_FIELD01
        if(!stopped){field01_latch(FIELD01_LINK);stop();}
#else
        if (!stopped) reconnect_delay();
#endif
    }
    report_stop();
#ifdef MP_B5_EGRESS_FINAL
    transaction_stop_trace();
#ifdef MP_FIVE_FIELD01
    if(field01_t0)field01_snapshot();
#endif
#endif
    for(unsigned i=0;i<23;i++)diagnostic(i);
    while (1) {
#ifdef MP_FINAL_UNIFIED
        unified_audio_local_poll();local_control();unified_audio_report();
#endif
        b4_hw_idle();
    }
}
