#include "egress.h"
#include "esp_io_metrics.h"
#include "transport_bench_control.h"
#include "transport_bench_source.h"
#include <stdio.h>

static BenchControl control;
static MpRouter router;
static B5Publisher publisher;
static uint32_t source_at,next_offer=200,operation_end=BENCH_HARD_MS,session_epoch;
static uint64_t source_utc;
static volatile int hard_stop;

int transport_bench_fast(void){return control.fast;}
int transport_bench_passthrough(void){return control.pass;}
void b5_uart_accept_baseline(void){}
int b5_network_stopped(void){return hard_stop;}
void b5_hard_tick(void){if(g_uptime_ms>=BENCH_HARD_MS)hard_stop=1;}
uint32_t b5_business_remaining(void){
    uint32_t now=g_uptime_ms;
    return now<operation_end?operation_end-now:0;
}

static void produce(void){
    if(control.state!=BENCH_RUNNING || hard_stop)return;
    uint32_t elapsed=g_uptime_ms-source_at;
    for(;next_offer<=elapsed && next_offer<=BENCH_SOURCE_MS;next_offer+=200u){
        for(unsigned i=0;i<BENCH_STREAM_COUNT;i++){
            const BenchStream *s=&bench_streams[i];
            unsigned seq=bench_sequence(s,next_offer);
            if(seq){
                MpFrame f;
                bench_frame(&f,s,seq,source_utc+next_offer,session_epoch,source_at);
                mp_router_put(&router,&f);
            }
        }
    }
}

static void diagnostics(void){
    EspCpuMetrics cpu;EspIoMetrics io;GatewayMqttMetrics mqtt;
    platform_cpu_snapshot(&cpu);platform_io_snapshot(&io);gateway_mqtt_metrics(&mqtt);
    unsigned slots=0;
    for(unsigned i=0;i<GATEWAY_TELEMETRY_SLOTS;i++)slots+=publisher.tickets[i]!=0;
    char line[440];
#define U(x) ((unsigned long)(x))
    snprintf(line,sizeof line,
        "B5 DIAG tick=%lu offered_ms=%lu live=%u history=%u slots=%u drop=%lu replace=%lu late=%lu q0=%lu q1=%lu "
        "service_cyc=%lu service_n=%lu await_cyc=%lu await_b=%lu rx_cyc=%lu rx_b=%lu "
        "tx_cyc=%lu tx_b=%lu txe_cyc=%lu irq_cyc=%lu irq_n=%lu sendok=%lu empty=%lu uart_errors=%lu rx_high=%lu ack_max=%lu\r\n",
        U(g_uptime_ms),U(next_offer-200u),router.ln,router.cn,slots,U(router.dropped),U(router.live_replaced),
        U(router.expired),U(publisher.q0),U(publisher.q1),U(cpu.service_cycles),U(cpu.service_calls),
        U(cpu.await_cycles),U(cpu.await_bytes),U(cpu.rx_step_cycles),U(cpu.rx_step_bytes),U(cpu.tx_cycles),
        U(cpu.tx_bytes),U(cpu.txe_cycles),U(cpu.irq_cycles),U(cpu.irq_calls),U(io.tx_confirmed),U(io.rx_empty),
        U(platform_uart_errors_total()),U(io.rx_high_water),U(mqtt.ack.max));
    console(line);
#undef U
}

static int close_restore(void){
    if(hard_stop)return 0;
    gateway_network_close();
    return !hard_stop && gateway_bench_restore();
}

static int connect(const MpFrame *will,uint32_t cutoff){
    operation_end=cutoff;
    int ok=gateway_network_open() && gateway_mqtt_open(will);
    operation_end=BENCH_HARD_MS;
    return ok;
}

static void finish(int clean,const char *result){
    control.state=clean?BENCH_RESTORED:BENCH_DIRTY;
    char line[120];snprintf(line,sizeof line,"BENCH END result=%s restore=%s tick=%lu\r\n",
        result,clean?"OK":"DIRTY",(unsigned long)g_uptime_ms);console(line);
}

int main(void){
    platform_init();
    console("C TRANSPORT_BENCH DISARMED MOCK CAN_OFF AUDIO_OFF\r\n");
    while(g_uptime_ms<BENCH_ARM_MS && control.state==BENCH_DISARMED){
        int c=console_char();
        if(c>=0)(void)bench_byte(&control,c,g_uptime_ms);
    }
    if(control.state==BENCH_DISARMED){finish(1,"ARM_TIMEOUT");goto idle;}
    if(!gateway_config_valid()){finish(1,"CONFIG");goto idle;}
    platform_set_poll(produce);
    mp_router_init(&router);
    MpFrame will={.node=3,.stream=MP_GATEWAY_STATUS,.synthetic=true};
    uint32_t ready_limit=BENCH_HARD_MS-BENCH_SOURCE_MS-BENCH_DRAIN_MS-BENCH_CLEAN_MS;
    uint32_t cutoff=g_uptime_ms+BENCH_OPEN_MS;
    if(cutoff>ready_limit)cutoff=ready_limit;
    if(!connect(&will,cutoff) || g_uptime_ms>ready_limit){
        finish(close_restore(),"OPEN_FAILED");goto idle;
    }
    source_at=g_uptime_ms;source_utc=gateway_epoch_milliseconds();session_epoch=(uint32_t)(source_utc/1000u);
    mp_router_online(&router,true);control.state=BENCH_RUNNING;
    char line[150];snprintf(line,sizeof line,
        "BENCH T0 mode=%c%u tick=%lu session=can-%lu-%lu utc=%lu%03lu\r\n",
        control.pass?'P':'N',control.fast?230:115,(unsigned long)source_at,(unsigned long)session_epoch,
        (unsigned long)source_at,(unsigned long)(source_utc/1000u),(unsigned long)(source_utc%1000u));console(line);
    uint32_t diag_at=source_at+1000u, end=source_at+BENCH_SOURCE_MS;
    unsigned reconnects=0;
    while(!hard_stop && g_uptime_ms<end+BENCH_DRAIN_MS){
        platform_poll();
        if(g_uptime_ms>=diag_at){diagnostics();diag_at=g_uptime_ms+1000u;}
        if(control.state==BENCH_RUNNING && next_offer>BENCH_SOURCE_MS)control.state=BENCH_DRAINING;
        if(control.state==BENCH_DRAINING && !router.ln && !router.cn && !publisher.pending && !publisher.deferred)break;
        if(b5_egress_step(&router,&publisher,true))continue;
        uint32_t detected=g_uptime_ms;
        snprintf(line,sizeof line,"BENCH LINK_LOST tick=%lu unsynced=%u\r\n",
            (unsigned long)detected,(unsigned)platform_at_unsynced());console(line);
        mp_router_online(&router,false);
        for(unsigned i=0;i<GATEWAY_TELEMETRY_SLOTS;i++)if(publisher.tickets[i]){
            mp_router_ack(&router,&publisher.inflight[i],false);publisher.tickets[i]=0;
        }
        publisher.pending=false;
        if(publisher.deferred){mp_router_ack(&router,&publisher.publishing,false);publisher.deferred=false;}
        int clean=close_restore();
        if(!clean || reconnects || g_uptime_ms>=end-12000u){
            diagnostics();finish(clean,"LINK_STOP");goto idle;
        }
        reconnects++;
        /* 给 F1 的人工热点恢复留出时间，再在同一窗口内执行一次有界重连。 */
        delay_ms(10000u);
        if(!connect(&will,end)){
            diagnostics();finish(close_restore(),"RECONNECT_FAILED");goto idle;
        }
        mp_router_online(&router,true);
        snprintf(line,sizeof line,"BENCH RECONNECTED tick=%lu outage_ms=%lu\r\n",
            (unsigned long)g_uptime_ms,(unsigned long)(g_uptime_ms-detected));console(line);
    }
    diagnostics();
    finish(close_restore(),router.ln || router.cn || publisher.pending || publisher.deferred?"DRAIN_INCOMPLETE":"DONE");
idle:
    for(;;){}
}
