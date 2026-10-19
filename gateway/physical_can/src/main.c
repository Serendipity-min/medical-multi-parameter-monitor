/* 第二阶段：CANopen Adapter → Canonical Model → Router → MQTT/离线缓存。 */
#include "gateway_transport.h"
#include "mp_adapter.h"
#include "physical.h"
#include <stdio.h>
#ifdef MP_CAN_RX_IRQ
#include "rx_metrics.h"
#endif

/* 大对象放静态区；发布中的独立帧副本仍由循环栈帧持有。 */
static MpStack stack;
static MpAdapter adapter;
static MpRouter router;
static uint32_t serviced, diagnostic_at;
static int disconnect_requested;
static uint32_t bus_frames_base,bus_drops_base;
#ifdef MP_CAN_RX_IRQ
/* 仅记录发送回执与最后帧身份，不记录生理值。网络重连与G不能清零累计计数。 */
static uint32_t qos1_acked,qos0_sent,publish_failed,last_seq,last_node,last_stream;
static uint64_t last_timestamp;
static uint32_t diagnostic_seq;
#endif

/* UART输出只保留固定计数与帧身份。IRQ目标在AT等待中也报告，便于发现故障。 */
static void diagnostics(void) {
    /* 仅保留有界计数摘要；溢出和补传计数不能被解释为无损采集保证。 */
    if (g_uptime_ms - diagnostic_at >= 5000)
    {
        char line[384];
        diagnostic_at = g_uptime_ms;
#ifdef MP_CAN_RX_IRQ
        diagnostic_seq++;
        (void)snprintf(line,sizeof(line),"GW DIAG_BEGIN seq=%lu lines=4\r\n",(unsigned long)diagnostic_seq);console(line);
#endif
        (void)snprintf(
            line, sizeof(line),
            "GW METRICS can=%lu drop=%lu cache=%u lost=%lu replay=%lu nodes=%d%d\r\n",
            (unsigned long)(bus_frames_base+mp_bus_frames()), (unsigned long)(bus_drops_base+mp_bus_dropped()), router.cn,
            (unsigned long)router.dropped, (unsigned long)router.replayed,
            mp_stack_online(&stack, 1), mp_stack_online(&stack, 2));
        console(line);
#ifdef MP_CAN_RX_IRQ
        /* 主循环只打印独立累计计数，禁止输出采样载荷或在CAN ISR打印。 */
        physical_rx_update_metrics();
        (void)snprintf(line,sizeof(line),"GW RXQ fovr=%lu sw=%lu bad=%lu high=%lu depth=%lu irq=%lu lag_cycles=%lu stale=%lu fault=%lu uart=%lu\r\n",
            (unsigned long)physical_rx_overflow,(unsigned long)physical_rx_metrics.rx_sw_overflow,
            (unsigned long)physical_bad_frame,(unsigned long)physical_rx_metrics.rx_high_water,
            (unsigned long)physical_rx_metrics.rx_depth,(unsigned long)physical_rx_metrics.rx_isr_calls,
            (unsigned long)physical_rx_metrics.rx_lag_cycles,(unsigned long)physical_rx_metrics.rx_stale_discard,
            (unsigned long)physical_rx_metrics.fault,(unsigned long)platform_uart_errors_total());
        console(line);
        (void)snprintf(line,sizeof(line),"GW CANPROOF hb=%lu boot=%lu p181=%lu p381=%lu p481=%lu p681=%lu txok=%lu txfail=%lu nmt=%lu time=%lu TEC=%lu REC=%lu LEC=%lu BOFF=%lu\r\n",
            (unsigned long)physical_rx_metrics.heartbeat_a,(unsigned long)physical_rx_metrics.bootup_a,
            (unsigned long)physical_rx_metrics.pdo_a[0],(unsigned long)physical_rx_metrics.pdo_a[1],
            (unsigned long)physical_rx_metrics.pdo_a[2],(unsigned long)physical_rx_metrics.pdo_a[3],
            (unsigned long)physical_rx_metrics.tx_acked,(unsigned long)physical_rx_metrics.tx_failed,
            (unsigned long)physical_rx_metrics.nmt_start_acked,(unsigned long)physical_rx_metrics.time_acked,
            (unsigned long)((physical_rx_metrics.esr>>16)&255),(unsigned long)(physical_rx_metrics.esr>>24),
            (unsigned long)((physical_rx_metrics.esr>>4)&7),(unsigned long)((physical_rx_metrics.esr>>2)&1));
        console(line);
        (void)snprintf(line,sizeof(line),"GW DELIVERY qos1_puback=%lu qos0_send=%lu failed=%lu last_node=%lu last_stream=%lu last_seq=%lu last_timestamp=%llu\r\n",
            (unsigned long)qos1_acked,(unsigned long)qos0_sent,(unsigned long)publish_failed,
            (unsigned long)last_node,(unsigned long)last_stream,(unsigned long)last_seq,(unsigned long long)last_timestamp);
        console(line);
        (void)snprintf(line,sizeof(line),"GW DIAG_END seq=%lu lines=4\r\n",(unsigned long)diagnostic_seq);console(line);
#endif
    }
}

/* 网络等待期间协作推进 CAN；只标记断网请求，真正断开在发布循环边界处理。 */
/* 仅推进 Gateway 消费者；网络等待中也处理外部 CAN。没有 A/B/E/R 测试生产入口。 */
static void service(void)
{
#ifndef MP_CAN_RX_IRQ
    mp_bus_poll();
#endif
    unsigned budget=8;
    while(serviced!=g_uptime_ms && budget--) { serviced++;mp_stack_tick(&stack);mp_adapter_poll(&adapter,&stack,&router); }
    int c=console_char();
    if(c=='D') disconnect_requested=1;
    if(c=='G') {
        /* 协议重初始化会清驱动局部统计，基数保存后累计对外报告。 */
        bus_frames_base+=mp_bus_frames();bus_drops_base+=mp_bus_dropped();
        int rc=physical_gateway_open(&stack,true);
        if(rc) console("GW PHYSICAL_CAN_RESTART_FAILED\r\n");
        else {
            /* IRQ入队使用uptime；显式重开后也必须让协议时钟同步，不能永久落后。 */
            serviced=stack.milliseconds=g_uptime_ms;
            console("GW PHYSICAL_CAN_RESTARTED_CANDIDATE NMT_QUEUED_NOT_ACKED\r\n");
        }
    }
#ifdef MP_CAN_RX_IRQ
    diagnostics();
#endif
}

#ifdef MP_CAN_RX_IRQ
/* CAN锁止后关闭隔离网络并停机，禁止靠自动重连把故障窗口接续成PASS。 */
static void stop_on_can_fault(void) {
    if(physical_link_ready)return;
    mp_router_online(&router,false);gateway_network_close();
    console("GW CAN_FAULT_NETWORK_CLOSED_STOP\r\n");while(1) {}
}
#endif

int main(void)
{
    platform_init();
    console("GW BOOT CANOPENNODE PHYSICAL_CAN1 CANDIDATE_NOT_ACCEPTED\r\n");
    if (!gateway_config_valid())
    {
        console("GW CONFIG_REQUIRED\r\n");
        while (1)
        {
        }
    }

    /* 时间未校准前可以收发 CAN，但 Adapter 不生成可上云的采集时间戳。 */
    /* 与 G 路径共用初始化次序；入队成功不宣称真实总线已 ACK。 */
    int rc = physical_gateway_open(&stack, false);
    if (rc)
    {
        char line[80];
        (void)snprintf(line, sizeof(line), "GW CAN_INIT_FAIL code=%d\r\n", rc);
        console(line);
        while (1)
        {
        }
    }
#ifdef MP_H3_VOLATILE_CONFIG
    /* 隔离下载期间A按现场要求断电；CAN已正常应答，但不在无人ACK时发NMT。
       收到A实际心跳才推进协议，不用此等待位冒充A在线，更不生成模拟A/B。 */
    console("GW WAIT_NODE_A_FIRST_HEARTBEAT NO_NETWORK_YET\r\n");
    while(!physical_peer_seen()) {
        physical_rx_update_metrics();
        if(physical_rx_overflow || physical_rx_metrics.rx_sw_overflow) {
            console("GW WAIT_NODE_A_RX_FAULT_STOP\r\n");while(1) {}
        }
        delay_ms(1);
    }
#endif
    /* 同一时钟域：IRQ接收时刻不能永远位于协议milliseconds的未来。 */
    serviced = stack.milliseconds = g_uptime_ms;
    mp_adapter_init(&adapter);
    mp_router_init(&router);
    platform_set_poll(service);
    /* 外层管理连接生命周期，内层发送实时/历史帧；网络失败不停止 CAN 采集。 */
    while (1)
    {
        mp_router_online(&router, false);
        int network_ok=gateway_network_open();
#ifdef MP_CAN_RX_IRQ
        stop_on_can_fault();
#endif
        if (!network_ok)
        {
            delay_ms(3000);
            continue;
        }

        /* 启动时间基准只设一次，重连不能改变缓存帧的会话身份和采集时间。 */
        if (!stack.epoch)
            stack.epoch = gateway_epoch() - stack.milliseconds / 1000;
        MpFrame will = {0};
        will.node = 3;
        will.stream = MP_GATEWAY_STATUS;
        will.timestamp = physical_now(&stack);
        will.seq = 0xffffffffU;
        will.epoch = stack.epoch;
        will.boot = stack.nodes[2].boot << 16;
        will.synthetic = false;
        if (!gateway_mqtt_open(&will))
        {
            delay_ms(3000);
            continue;
        }
        mp_router_online(&router, true);
        adapter.status_tick =
            stack.milliseconds - 5000U; /* 重连立即生成当前状态，再允许历史补传。 */
        while (1)
        {
            platform_poll();
#ifdef MP_CAN_RX_IRQ
            stop_on_can_fault();
#endif
            if (disconnect_requested)
            {
                disconnect_requested = 0;
                mp_router_online(&router, false);
                (void)at_command("AT+CWQAP", 3000);
                console("GW WIFI_TEST_DISCONNECTED\r\n");
                delay_ms(30000);
                break;
            }

            /* take 返回独立副本，发送等待中的新采样不会覆盖正在发布的载荷。 */
            MpFrame f;
            if (mp_router_take(&router, &f, g_uptime_ms))
            {
                bool ok = gateway_mqtt_publish(&f);
#ifdef MP_CAN_RX_IRQ
                if(ok) {
                    if(!f.rate || f.replay)qos1_acked++;else qos0_sent++;
                    last_seq=f.seq;last_node=f.node;last_stream=f.stream;last_timestamp=f.timestamp;
                } else publish_failed++;
#endif
                mp_router_ack(&router, &f, ok);
                if (!ok)
                    break;
            }
            else if (!gateway_mqtt_yield())
                break;

#ifndef MP_CAN_RX_IRQ
            diagnostics();
#endif
        }
        mp_router_online(&router, false);
        console("GW RECONNECT\r\n");
        gateway_network_close();
        delay_ms(2000);
    }
}
