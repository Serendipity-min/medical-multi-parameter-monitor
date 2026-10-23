/* 双总线网络软件目标，复用冻结H3传输源；本轮仅构建，禁止烧录或运行联网。 */
#include "b4_bxcan.h"
#include "gateway_transport.h"
static B4Gateway gateway;
static MpFrame publishing, will;
static uint32_t last_sync, status_at, gateway_seq;
static bool network_open, mqtt_connected;
uint32_t b4_hw_time(void) { return g_uptime_ms; }
static void service(void) {
    /* AT/JSON等待均协作处理CAN；每次每路16帧有界，禁止网络递归发布。 */
    b4_gateway_tick(&gateway, g_uptime_ms); b4_hw_poll(&gateway);
    if (network_open && g_uptime_ms - last_sync >= 10000u) {
        b4_gateway_sync_ms(&gateway, gateway_epoch_milliseconds(), g_uptime_ms);
        last_sync = g_uptime_ms;
    }
    if (mqtt_connected && g_uptime_ms - status_at >= 5000u) {
        MpFrame status = {0}; status.node = 3; status.stream = MP_GATEWAY_STATUS; status.valid = true;
        status.timestamp = gateway_epoch_milliseconds(); status.epoch = will.epoch; status.boot = 1;
        status.seq = ++gateway_seq; mp_router_put(&gateway.router, &status); status_at = g_uptime_ms;
    }
}
int main(void) {
    platform_init();
    if (b4_gateway_init(&gateway) || b4_hw_init()) while (1) {}
    /* 硬件准备后才请求各段的业务节点启动；入软件队列不代表获得物理ACK。 */
    (void)b4_gateway_nmt(&gateway, 1, CO_NMT_ENTER_OPERATIONAL);
    (void)b4_gateway_nmt(&gateway, 2, CO_NMT_ENTER_OPERATIONAL);
    platform_set_poll(service);
    /* 配置仍由仓库外提供，只读；本软件目标没有任何配置/Flash写入口。 */
    if (!gateway_config_valid()) while (1) { platform_poll(); }
    while (1) {
        mp_router_online(&gateway.router, false); network_open = mqtt_connected = false;
        if (!gateway_network_open()) { delay_ms(3000); continue; }
        b4_gateway_sync_ms(&gateway, gateway_epoch_milliseconds(), g_uptime_ms);
        last_sync = g_uptime_ms; network_open = true;
        will.node = 3; will.stream = MP_GATEWAY_STATUS; will.timestamp = gateway_epoch_milliseconds();
        will.seq = 0xffffffffu; will.epoch = gateway.epoch; will.boot = 1; will.valid = false;
        if (!gateway_mqtt_open(&will)) { network_open = false; gateway_network_close(); delay_ms(3000); continue; }
        mp_router_online(&gateway.router, true);
        mqtt_connected = true; status_at = g_uptime_ms - 5000u;
        while (1) {
            platform_poll();
            if (mp_router_take(&gateway.router, &publishing, g_uptime_ms)) {
                bool sent = gateway_mqtt_publish(&publishing);
                mp_router_ack(&gateway.router, &publishing, sent); if (!sent) break;
            } else if (!gateway_mqtt_yield()) break;
        }
        network_open = mqtt_connected = false; mp_router_online(&gateway.router, false);
        gateway_network_close(); delay_ms(2000);
    }
}
