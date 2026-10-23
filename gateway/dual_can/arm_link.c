/* 仅链接验证入口，不是H3生产网络固件；不读取配置、不连接Wi-Fi/MQTT。 */
#include "b4_bxcan.h"
#include "b4_resources.h"
#include "stm32f4xx.h"
volatile uint32_t b4_milliseconds;
uint32_t b4_hw_time(void) { return b4_milliseconds; }
static B4Gateway gateway;
static char json[B4_JSON_CAPACITY];
static MpFrame publishing;
volatile uint32_t b4_link_error, b4_formatted;
void SysTick_Handler(void) { b4_milliseconds++; }
int main(void) {
    b4_link_error = b4_gateway_init(&gateway) != 0;
    if (!b4_link_error) b4_link_error = b4_hw_init() != 0;
    SysTick_Config(SystemCoreClock / 1000u);
    /* 这里没有可信UTC源，数据不会获准LIVE有效；正式网络整合仍需PI准入。 */
    while (1) {
        if (b4_link_error) continue;
        b4_gateway_tick(&gateway, b4_milliseconds); b4_hw_poll(&gateway);
        if (mp_router_take(&gateway.router, &publishing, b4_milliseconds)) {
            if (mp_json(&publishing, json, sizeof(json))) b4_formatted++;
            mp_router_ack(&gateway.router, &publishing, false);
        }
    }
}
