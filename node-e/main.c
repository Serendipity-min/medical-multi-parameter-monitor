/* E 只初始化血压模块、操作屏和 CAN，不启动血氧串口。 */
#include "stm32f4xx.h"
#include "sys.h"
#include "debug.h"
#include "app_bp.h"
#include "hmi_dacai.h"
#include "screen_watch.h"
#include "sys_wdt.h"
#include "canopen_app.h"

uint32_t g_rtc_epoch_tick;
int main(void) {
    SysTick_Init(); DEBUG_UART_Init();
    app_init();
    screen_watch_init();
    screen_watch_register(SCREEN_ID_BP,"BP",hmi_get_screen,hmi_beep,bp_resync);
    if(canopen_app_init()) for(;;) {}
    WDT_Init();
    for(;;) { WDT_Feed();screen_watch_tick();app_loop();canopen_app_process(); }
}
