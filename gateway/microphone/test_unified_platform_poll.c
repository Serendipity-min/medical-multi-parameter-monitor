/* 真实platform入口；模拟SysTick，检查同毫秒重复服务及回绕，不触碰设备。 */
#include "gateway_platform.h"
#include "esp_io_metrics.h"
#include "../mqtt/tests/mocks/platform_mmio.h"
#include <assert.h>
#include <stdio.h>

volatile uint32_t g_uptime_ms;
TestUsart platform_usart[2];
static unsigned calls;
static void service(void){calls++;platform_poll();}

int main(void){
    platform_set_poll(service);
    for(unsigned i=0;i<10000;i++)platform_poll();
    assert(calls==1);
    for(unsigned ms=1;ms<=1000;ms++){
        g_uptime_ms=ms;
        for(unsigned i=0;i<100;i++)platform_poll();
        assert(calls==ms+1);
    }
    platform_set_poll(NULL);g_uptime_ms++;platform_poll();assert(calls==1001);
    platform_set_poll(service);platform_poll();assert(calls==1002);
    g_uptime_ms=UINT32_MAX;platform_poll();assert(calls==1003);
    g_uptime_ms=0;platform_poll();assert(calls==1004);
    platform_poll();assert(calls==1004);
    EspIoMetrics io;platform_io_snapshot(&io);assert(io.service_gap_max);
    puts("REAL_PLATFORM_1MS_SERVICE_REENTRY_AND_SYSTICK_WRAP_PASS hardware=NOT_RUN");
    return 0;
}
