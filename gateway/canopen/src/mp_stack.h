#ifndef MP_STACK_H
#define MP_STACK_H
#include "mp_od.h"
#include "mp_can_driver.h"

typedef struct
{
    /* 每个实例独立持有 OD 与 CANopenNode 分配资源，由 mp_stack_close 统一释放。 */
    MpOD od;
    CO_config_t config;
    CO_t *co;
    MpCanPort port;
    uint32_t boot, tick;
} MpNode;

typedef struct
{
    /* 固定槽位为 Node-A、Node-B、Gateway；当前是一块板内的三实例测试系统。 */
    MpNode nodes[3];
    /* milliseconds 是调度累计毫秒；allocated 是累计分配量，不是当前堆占用。 */
    uint32_t milliseconds, epoch, allocated, emcy[2], resets[3];
} MpStack;

int mp_stack_init(MpStack *s, uint32_t epoch);
void mp_stack_close(MpStack *s);
void mp_stack_tick(MpStack *s);
void mp_stack_enable(MpStack *s, unsigned node, bool enabled);
int mp_stack_restart(MpStack *s, unsigned node);
int mp_stack_online(MpStack *s, unsigned node);
void mp_stack_nmt(MpStack *s, unsigned node, CO_NMT_command_t command);
#endif
