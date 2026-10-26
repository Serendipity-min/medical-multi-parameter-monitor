/* 唯一B5候选：手工武装、B段、非人体MOCK；默认不自动入网，不写配置。 */
#include "b5_policy.h"
#include "../dual_can/b4_bxcan.h"
#include "gateway_transport.h"
#include "esp_io_metrics.h"
#include <string.h>
#include <stdio.h>
static B4Gateway gateway;
static MpFrame publishing, will;
static uint32_t armed_at, last_sync, status_at, connection, status_seq;
static uint32_t diag_at, mqtt_qos0_transport_ok, mqtt_qos1_puback, mqtt_failed_count;
static bool armed, stopped, network_open, mqtt_connected;
uint32_t b4_hw_time(void) { return g_uptime_ms; }
int b5_network_stopped(void) { return stopped; }
static void stop(void) {
    stopped = true; gateway.utc_valid = false;
    mp_router_online(&gateway.router, false); b4_hw_stop();
}
static void diagnostic(void) {
    char line[300];
    /* 仅固定计数/状态，无Topic、载荷、Wi-Fi或凭据；QoS0不命名为云端接收成功。 */
    (void)snprintf(line,sizeof(line),"B5 DIAG tick=%lu session=%lu rx=%lu txack=%lu txfail=%lu overflow=%lu esr=%lu uart_err=%lu live=%u cache=%u dropped=%lu q0_transport=%lu q1_puback=%lu mqtt_fail=%lu stop=%u\r\n",
        (unsigned long)g_uptime_ms,(unsigned long)gateway.session,(unsigned long)b4_hw_diag[1].received,
        (unsigned long)b4_hw_diag[1].tx_acked,(unsigned long)b4_hw_diag[1].tx_failed,
        (unsigned long)b4_hw_diag[1].overflow,(unsigned long)b4_hw_diag[1].esr,(unsigned long)platform_uart_errors_total(),gateway.router.ln,gateway.router.cn,
        (unsigned long)gateway.router.dropped,(unsigned long)mqtt_qos0_transport_ok,
        (unsigned long)mqtt_qos1_puback,(unsigned long)mqtt_failed_count,(unsigned)stopped);
    console(line);
}
static void service(void) {
    if (stopped) { b4_hw_idle(); return; }
    /* 未武装时不推进CANopen/TIME，避免B尚断电时发心跳耗尽ACK并积累BOFF。 */
    if (!armed) { b4_hw_idle(); return; }
    b4_gateway_tick(&gateway, g_uptime_ms); b4_hw_poll(&gateway);
    if (armed && ((uint32_t)(g_uptime_ms - armed_at) >= B5_WINDOW_MS ||
        b4_hw_diag[1].overflow || b4_hw_diag[1].busoff || b4_hw_diag[1].tx_failed || platform_uart_errors_total())) {
        stop(); return;
    }
    if (network_open && g_uptime_ms - last_sync >= 10000u) {
        b4_gateway_sync_ms(&gateway, gateway_epoch_milliseconds(), g_uptime_ms);
        last_sync = g_uptime_ms;
    }
    if (mqtt_connected && g_uptime_ms - status_at >= 5000u) {
        MpFrame status = will; status.valid = true; status.timestamp = gateway_epoch_milliseconds();
        status.seq = ++status_seq; mp_router_put(&gateway.router, &status); status_at = g_uptime_ms;
    }
    if (g_uptime_ms-diag_at>=5000u && !platform_console_busy()) {diag_at=g_uptime_ms;diagnostic();}
}
int main(void) {
    platform_init();
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
    (void)b4_gateway_nmt(&gateway, 2, CO_NMT_ENTER_OPERATIONAL);
    while (!stopped) {
        mp_router_online(&gateway.router, false); network_open = mqtt_connected = false;
        if (!gateway_network_open()) { if (!stopped) delay_ms(3000); continue; }
        uint64_t now = gateway_epoch_milliseconds();
        b4_gateway_sync_ms(&gateway, now, g_uptime_ms); gateway.session = (uint32_t)now;
        network_open = true; last_sync = g_uptime_ms;
        memset(&will, 0, sizeof(will)); will.node = 3; will.stream = MP_GATEWAY_STATUS;
        will.synthetic = true; will.timestamp = now; will.epoch = gateway.session;
        will.boot = ++connection; will.seq = UINT32_MAX;
        if (stopped || !gateway_mqtt_open(&will)) { gateway_network_close(); continue; }
        mp_router_online(&gateway.router, true); mqtt_connected = true;
        status_at = g_uptime_ms - 5000u;
        while (!stopped) {
            platform_poll();
            if (mp_router_take(&gateway.router, &publishing, g_uptime_ms)) {
                if (!b5_prepare_publish(&publishing, gateway_epoch_milliseconds())) continue;
                bool sent = gateway_mqtt_publish(&publishing);
                if(!sent)mqtt_failed_count++;
                else if(publishing.rate && !publishing.replay)mqtt_qos0_transport_ok++;
                else mqtt_qos1_puback++;
                mp_router_ack(&gateway.router, &publishing, sent); if (!sent) break;
            } else if (!gateway_mqtt_yield()) break;
        }
        network_open = mqtt_connected = false; mp_router_online(&gateway.router, false);
        gateway_network_close(); if (!stopped) delay_ms(2000);
    }
    diagnostic();console("B5 STOPPED NO_AUTOREARM\r\n");
    while (1) b4_hw_idle();
}
