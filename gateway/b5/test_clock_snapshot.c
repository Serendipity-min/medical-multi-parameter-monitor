/* 离线复现既有B时钟接口；仅证明入口now早于回调received时的行为，不代表现场唯一根因。 */
#include "../../node-b/canopen/node_policy.h"
#include <assert.h>
#include <stdio.h>
int main(void) {
    NodeClock clock={0};uint32_t epoch,anchor;
    node_clock_set(&clock,800u,20000u,10001u);
    node_clock_read(&clock,10000u,&epoch,&anchor);
    assert(epoch==0 && anchor==10000u);
    node_clock_read(&clock,10001u,&epoch,&anchor);
    assert(epoch==clock.epoch && anchor==clock.anchor);
    node_clock_read(&clock,40002u,&epoch,&anchor);assert(epoch==0);
    puts("B_CLOCK_CALLBACK_AHEAD_OF_TASK_NOW_REPRODUCED transient_invalid_1ms expiry_preserved NO_TARGET_IO NO_B_CHANGE");
    return 0;
}
