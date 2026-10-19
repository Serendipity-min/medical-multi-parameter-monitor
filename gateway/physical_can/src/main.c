/* 第二阶段：CANopen Adapter → Canonical Model → Router → MQTT/离线缓存。 */
#include "gateway_transport.h"
#include "mp_adapter.h"
#include "physical.h"
#include <stdio.h>

/* 大对象放静态区；发布中的独立帧副本仍由循环栈帧持有。 */
static MpStack stack;
static MpAdapter adapter;
static MpRouter router;
static uint32_t serviced, diagnostic_at;
static int disconnect_requested;
extern int mp_bxcan_init(void);

/* 网络等待期间协作推进 CAN；只标记断网请求，真正断开在发布循环边界处理。 */
/* 仅推进 Gateway 消费者；网络等待中也处理外部 CAN。没有 A/B/E/R 测试生产入口。 */
static void service(void)
{
    mp_bus_poll();unsigned budget=8;
    while(serviced!=g_uptime_ms && budget--) { serviced++;mp_stack_tick(&stack);mp_adapter_poll(&adapter,&stack,&router); }
    int c=console_char();
    if(c=='D') disconnect_requested=1;
    if(c=='G') {
        int rc=mp_stack_restart(&stack,3);
        if(rc || !mp_bxcan_init()) console("GW PHYSICAL_CAN_RESTART_FAILED\r\n");
        else console("GW PHYSICAL_CAN_RESTARTED_CANDIDATE\r\n");
    }
}

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
    int rc = mp_stack_init(&stack, 0);
    int hardware = rc ? 0 : mp_bxcan_init();
    if (rc || !hardware)
    {
        char line[80];
        (void)snprintf(line, sizeof(line), "GW CAN_INIT_FAIL code=%d hardware=%d\r\n", rc,
                       hardware);
        console(line);
        while (1)
        {
        }
    }
    serviced = g_uptime_ms;
    mp_adapter_init(&adapter);
    mp_router_init(&router);
    platform_set_poll(service);
    /* 外层管理连接生命周期，内层发送实时/历史帧；网络失败不停止 CAN 采集。 */
    while (1)
    {
        mp_router_online(&router, false);
        if (!gateway_network_open())
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
        will.timestamp = (uint64_t)gateway_epoch() * 1000;
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
                mp_router_ack(&router, &f, ok);
                if (!ok)
                    break;
            }
            else if (!gateway_mqtt_yield())
                break;

            /* 仅保留有界计数摘要；溢出和补传计数不能被解释为无损采集保证。 */
            if (g_uptime_ms - diagnostic_at >= 5000)
            {
                char line[160];
                diagnostic_at = g_uptime_ms;
                (void)snprintf(
                    line, sizeof(line),
                    "GW METRICS can=%lu drop=%lu cache=%u lost=%lu replay=%lu nodes=%d%d\r\n",
                    (unsigned long)mp_bus_frames(), (unsigned long)mp_bus_dropped(), router.cn,
                    (unsigned long)router.dropped, (unsigned long)router.replayed,
                    mp_stack_online(&stack, 1), mp_stack_online(&stack, 2));
                console(line);
            }
        }
        mp_router_online(&router, false);
        console("GW RECONNECT\r\n");
        gateway_network_close();
        delay_ms(2000);
    }
}
