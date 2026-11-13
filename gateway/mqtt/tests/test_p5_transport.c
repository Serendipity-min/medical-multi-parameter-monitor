/* 常规传输边界：真实 adapter + 合成 ESP 返回值，不接串口或网络。 */
#include "mqtt_transport_adapter.h"
#include <stdio.h>
#include <string.h>
#include <assert.h>

volatile uint32_t g_uptime_ms;
static int send_result = -2, recv_result, calls;
static unsigned char captured[2048];
static int captured_length;
void platform_poll(void) { }
int esp_mqtt_send(const unsigned char *data, int length, uint32_t timeout)
{
    assert(timeout > 0);
    calls++;
    memcpy(captured, data, (size_t)length);
    captured_length = length;
    return send_result == -2 ? length : send_result;
}
int esp_mqtt_recv(unsigned char *data, int length, uint32_t timeout)
{
    (void)length;
    assert(timeout > 0 && timeout <= 5);
    if (recv_result > 0) memset(data, 0, (size_t)recv_result);
    return recv_result;
}
#define PASS(name) puts("PASS " name)
int main(void)
{
    NetworkContext_t network;
    mqtt_adapter_reset(&network);
    mqtt_adapter_begin(&network, 5000);
    TransportInterface_t transport = mqtt_adapter_interface(&network);
    unsigned char first[] = {0x30, 0}, second[] = {1, 0, 2};
    TransportOutVector_t vectors[] = {{first, 2}, {second, 3}};
    assert(transport.writev(&network, vectors, 2) == 5);
    assert(calls == 1 && captured_length == 5 && captured[3] == 0);
    for (unsigned i = 0; i < 5; ++i) assert(network.tx[i] == 0);
    PASS("transport_writev_exact_binary_and_erasure");
    unsigned char data[4];
    recv_result = 2;
    assert(transport.recv(&network, data, 4) == 2 && data[1] == 0);
    PASS("transport_partial_receive");
    recv_result = 0;
    assert(transport.recv(&network, data, 4) == 0 && network.connected);
    PASS("transport_no_data_is_zero");
    recv_result = -1;
    assert(transport.recv(&network, data, 4) == -1 && !network.connected);
    PASS("transport_receive_error_disconnects");
    mqtt_adapter_reset(&network);
    mqtt_adapter_begin(&network, 5000);
    send_result = 2;
    assert(transport.send(&network, data, 4) == 2);
    PASS("transport_partial_send_count");
    int previous = calls;
    assert(transport.send(&network, data, 2049) < 0 && calls == previous);
    vectors[1].iov_len = 2048;
    assert(transport.writev(&network, vectors, 2) < 0 && calls == previous);
    PASS("transport_oversize_rejected_before_send");
    assert(transport.send(&network, NULL, 0) == 0);
    assert(transport.recv(&network, NULL, 0) == 0);
    assert(transport.send(&network, NULL, 1) < 0);
    PASS("transport_zero_and_null_boundaries");
    g_uptime_ms = UINT32_MAX - 20;
    mqtt_adapter_begin(&network, 30);
    g_uptime_ms = 4;
    assert(transport.send(&network, data, 4) == 2);
    g_uptime_ms = 10;
    assert(transport.send(&network, data, 4) < 0);
    PASS("transport_deadline_wraparound");
    mqtt_adapter_close(&network);
    assert(transport.recv(&network, data, 1) < 0);
    PASS("transport_closed_is_error");
    return 0;
}
