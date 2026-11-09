/* 仅 FIELD01 编译，使用现有网络所有者；以下取证均为累计值。 */
#include "field01_window.h"
#include "mic_api.h"

enum { FIELD01_TIMER=10, FIELD01_MANUAL, FIELD01_CAN, FIELD01_LINK, FIELD01_DMA, FIELD01_SOURCE };
static volatile uint32_t field01_t0;
static uint32_t field_live[MP_STREAMS],field_history[MP_STREAMS],field_age_max[MP_STREAMS];
static uint32_t field_age_sum[MP_STREAMS];
static uint32_t field_admit_deferred,field_idle_backlog,field_busy_backlog,field_sample_at,field_net_at;
static uint32_t field_health_at,field_esr[2],field_wave_at[3],field_wave_count[3];
static unsigned field_tec_rises[2],field_rec_rises[2];
#ifndef MP_AUDIO_DISABLED
static bool field_key_approved;
#endif

static unsigned field_queue_phase;
static const unsigned field_waves[]={MP_ECG,MP_RESP,MP_PPG};

#if defined(MP_TRANSPORT_PROFILE) && defined(MP_ESP_PASSTHROUGH) && !defined(MP_ESP_UART_230400)
#define FIELD01_WORK_CUT
static uint32_t field_work_base;
static uint32_t field_work_tx_cycles,field_work_tx_bytes;
static bool field_work_cut_logged;

static uint32_t field01_enqueued(void) {
    uint32_t total=0;
    for(unsigned i=0;i<MP_STREAMS;i++)total+=gateway.router.enqueued[i];
    return total;
}

static void field01_work_cut(void) {
    if(!field01_t0 || field_work_cut_logged)return;
    field_work_cut_logged=true;
    uint32_t tick=g_uptime_ms;
    EspCpuMetrics cpu;platform_cpu_snapshot(&cpu);
    char line[208];
    snprintf(line,sizeof line,"FIELD01 WORK_CUT tick=%lu elapsed=%lu enqueued=%lu base=%lu high=%lu overflow=%lu replaced=%lu drop=%lu tx_cyc=%lu tx_b=%lu\r\n",
        (unsigned long)tick,(unsigned long)(tick-field01_t0),(unsigned long)field01_enqueued(),(unsigned long)field_work_base,
        (unsigned long)gateway.router.high_water,(unsigned long)gateway.router.live_overflow,(unsigned long)gateway.router.live_replaced,
        (unsigned long)gateway.router.dropped,(unsigned long)(cpu.tx_cycles-field_work_tx_cycles),
        (unsigned long)(cpu.tx_bytes-field_work_tx_bytes));
    console(line);
}
#endif

static void field01_latch(unsigned reason) {
#ifdef __arm__
    uint32_t primask=__get_PRIMASK();__disable_irq();
#endif
    if(!stop_due && !stopped){
        stop_tick=g_uptime_ms;stop_reason=reason;stop_live=gateway.router.ln;stop_cache=gateway.router.cn;
        platform_io_snapshot(&stop_io);stop_due=true;
    }
#ifdef __arm__
    __set_PRIMASK(primask);
#endif
}
static bool field01_nodes_ready(void) {
    for(unsigned bus=0;bus<2;bus++)for(unsigned slot=0;slot<2;slot++){
        unsigned node=slot?(bus?4u:5u):bus+1u;
        if(!gateway.segments[bus].remote[slot].seen[4] || !b4_gateway_online(&gateway,node))return false;
    }
    return true;
}
static void field01_published(const MpFrame *frame) {
    unsigned stream=frame->stream;
    if(frame->replay){field_history[stream]++;return;}
    field_live[stream]++;
    uint64_t now=gateway_epoch_milliseconds();
    uint32_t age=now>=frame->timestamp?(uint32_t)(now-frame->timestamp):0;
    field_age_sum[stream]+=age;
    if(age>field_age_max[stream])field_age_max[stream]=age;
}
static void field01_admission(void) {field_admit_deferred++;}
static void field01_poll(void) {
    uint32_t now=g_uptime_ms,t0=field01_t0;
    if(field_queue_phase==1)field_idle_backlog+=now-field_sample_at;
    if(field_queue_phase==2)field_busy_backlog+=now-field_sample_at;
    field_sample_at=now;
    field_queue_phase=gateway.router.ln?(platform_at_synchronized()?1:2):0;
    if(network_fault){field01_latch(FIELD01_LINK);return;}
    for(unsigned bus=0;bus<2;bus++){
        if(b4_hw_diag[bus].busoff || b4_hw_diag[bus].overflow){
            field01_latch(FIELD01_CAN);return;
        }
    }
    if(now-field_health_at>=100u){
        field_health_at=now;
        for(unsigned bus=0;bus<2;bus++){
            uint32_t esr=b4_hw_diag[bus].esr,prev=field_esr[bus];
            field_tec_rises[bus]=((esr>>16)&255u)>((prev>>16)&255u)?field_tec_rises[bus]+1u:0u;
            field_rec_rises[bus]=(esr>>24)>(prev>>24)?field_rec_rises[bus]+1u:0u;
            field_esr[bus]=esr;
            if(field_tec_rises[bus]>=3 || field_rec_rises[bus]>=3){field01_latch(FIELD01_CAN);return;}
        }
    }
    if(!t0)return;
    if(!field01_nodes_ready() || !gateway.utc_valid || !gateway_audio_ready()){
        field01_latch(FIELD01_LINK);return;
    }
    for(unsigned i=0;i<3;i++){
        uint32_t count=gateway.router.enqueued[field_waves[i]];
        if(count!=field_wave_count[i]){field_wave_count[i]=count;field_wave_at[i]=now;}
        if(now-field_wave_at[i]>=5000u){field01_latch(FIELD01_SOURCE);return;}
    }
#ifndef MP_AUDIO_DISABLED
    MicDiag mic;mic_diagnostics(&mic);
    if(mic.dma_errors || mic.overruns)field01_latch(FIELD01_DMA);
#endif
}
static void field01_begin(void) {
    if(field01_t0 || !gateway.utc_valid || !gateway_audio_ready() || !field01_nodes_ready())return;
    uint32_t now=g_uptime_ms;
    if(stop_due || !field01_remaining(now,0))return;
    for(unsigned i=0;i<3;i++){
        field_wave_at[i]=now;field_wave_count[i]=gateway.router.enqueued[field_waves[i]];
    }
#ifdef MP_TRANSPORT_PROFILE
    platform_cpu_reset_service_max();
#endif
#ifdef FIELD01_WORK_CUT
    field_work_base=field01_enqueued();
    EspCpuMetrics cpu;platform_cpu_snapshot(&cpu);
    field_work_tx_cycles=cpu.tx_cycles;field_work_tx_bytes=cpu.tx_bytes;
#endif
    field01_t0=now;
    console("FIELD01 T0\r\n");
}
static void field01_snapshot(void) {
    uint32_t now=g_uptime_ms,elapsed=now-field01_t0,ack_count,ack_ms,ack_max;
    EspIoMetrics io;platform_io_snapshot(&io);
    GatewayMqttMetrics mqtt;gateway_mqtt_metrics(&mqtt);
    field01_mqtt_reclaim(&ack_count,&ack_ms,&ack_max);
    char line[400];
#define F(x) ((unsigned long)(x))
    snprintf(line,sizeof line,"FIELD01 AT tick=%lu elapsed=%lu idle=%lu cmd_all=%lu cmd_send=%lu prompt=%lu payload=%lu sendok=%lu waitack=%lu unsync=%lu closed=%lu empty=%lu/%lu nonempty=%lu/%lu read=%lu/%lu tx=%lu/%lu bytes=%lu\r\n",
        F(now),F(elapsed),F(io.phase_ms[ESP_AT_IDLE]),F(io.phase_ms[ESP_AT_COMMAND]),F(io.send_command_ms),
        F(io.phase_ms[ESP_AT_WAIT_PROMPT]),F(io.phase_ms[ESP_AT_DATA]),F(io.phase_ms[ESP_AT_WAIT_SEND_OK]),
        F(io.phase_ms[ESP_AT_WAIT_PUBACK]),F(io.phase_ms[ESP_AT_UNSYNCED]),F(io.phase_ms[ESP_AT_CLOSED]),
        F(io.rx_empty),F(io.rx_empty_ms),F(io.rx_nonempty),F(io.rx_nonempty_ms),F(io.rx_reads),F(io.rx_read_ms),
        F(io.tx_confirmed),F(io.tx_calls),F(io.tx_bytes_total));console(line);
    snprintf(line,sizeof line,"FIELD01 QUEUE tick=%lu live=%u cache=%u high=%lu overflow=%lu replaced=%lu expired=%lu drop=%lu replay=%lu q0=%lu q1=%lu failed=%lu reclaim=%lu/%lu/%lu json=%lu/%lu/%lu age_p95=%lu admission_wait=%lu backlog_idle_busy_sampled_ms=%lu/%lu\r\n",
        F(now),gateway.router.ln,gateway.router.cn,F(gateway.router.high_water),F(gateway.router.live_overflow),
        F(gateway.router.live_replaced),F(gateway.router.expired),F(gateway.router.dropped),F(gateway.router.replayed),
        F(publisher.q0),F(publisher.q1),F(publisher.failed),F(ack_count),F(ack_ms),F(ack_max),
        F(mqtt.json.count),F(mqtt.field01_json_ms),F(mqtt.json.max),F(b5_latency_percentile(&gateway.router.source_age,95)),
        F(field_admit_deferred),F(field_idle_backlog),F(field_busy_backlog));console(line);
    for(unsigned bus=0;bus<2;bus++){
        const volatile B4HwDiag *d=&b4_hw_diag[bus];
        B4Remote *a=&gateway.segments[bus].remote[0],*b=&gateway.segments[bus].remote[1];
        snprintf(line,sizeof line,"FIELD01 CAN tick=%lu bus=%u esr=%lu rx=%lu overflow=%lu busoff=%lu txfail=%lu nmt=%u/%u hb=%lu/%lu hb_age=%lu/%lu boot=%lu/%lu emcy=%lu/%lu\r\n",
            F(now),bus,F(d->esr),F(d->received),F(d->overflow),F(d->busoff),F(d->tx_failed),a->nmt_state,b->nmt_state,
            F(a->heartbeat_count),F(b->heartbeat_count),F(now-a->heartbeat_tick),F(now-b->heartbeat_tick),
            F(a->observed_boot),F(b->observed_boot),F(a->emcy_errors),F(b->emcy_errors));console(line);
    }
    for(unsigned k=0;k<MP_STREAMS;k+=4){
        int used=snprintf(line,sizeof line,"FIELD01 FLOW tick=%lu",F(now));
        for(unsigned j=k;j<k+4 && j<MP_STREAMS;j++){
            used+=snprintf(line+used,sizeof line-(unsigned)used," %u=%lu/%lu/%lu/%lu/%lu/%lu/%lu",j,
                F(gateway.router.enqueued[j]),F(gateway.router.taken[j]),F(gateway.router.historized[j]),
                F(field_live[j]),F(field_history[j]),F(field_age_sum[j]),F(field_age_max[j]));
        }
        snprintf(line+used,sizeof line-(unsigned)used,"\r\n");console(line);
    }
#undef F
}
#ifdef MP_TRANSPORT_PROFILE
#define FIELD01_PROFILE_DIAG 255u
static void diagnostic(unsigned stage);
#endif

static void field01_status(void) {
    if(!field01_t0 || platform_console_busy() || !platform_at_synchronized() || !unified_audio_quiet())return;
    uint32_t elapsed=g_uptime_ms-field01_t0;
    /* 固定边界与10秒点独立记录；输出时使用实际单调时间。 */
    uint32_t slot=elapsed/10000u*2u+1u+(elapsed>=35000u && elapsed<40000u);
    if(slot==field_net_at)return;
    field_net_at=slot;field01_snapshot();
#ifdef MP_TRANSPORT_PROFILE
    diagnostic(FIELD01_PROFILE_DIAG);
#endif
    unified_audio_command('Q',false);unified_audio_report();
}
