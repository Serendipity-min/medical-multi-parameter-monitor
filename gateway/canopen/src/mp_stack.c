/* 两个测试生产者和一个 Gateway 使用独立 OD/协议状态；仅共享有界 CAN 驱动。 */
#include "mp_stack.h"
#include <string.h>
static MpStack *active;

/* 先停止调度，再由上游删除部分或完整实例；删除会注销CAN端口，最后清空外部关联。 */
static void stop_node(MpNode *n)
{
    n->port.enabled = false;
    if (n->co)
        CO_delete(n->co);
    n->co = NULL;
    n->port.module = NULL;
}

/* 上游 EMCY 回调没有项目实例参数；当前单测试系统通过 active 保存 A/B 最新故障码。 */
static void emergency(uint16_t id, uint16_t code, uint8_t reg, uint8_t bit, uint32_t info)
{
    (void)reg;
    (void)bit;
    (void)info;
    if (active && id >= 0x81 && id <= 0x82)
        active->emcy[id - 0x81] = code;
}

/* 每次初始化递增 RAM 代际，重新绑定 OD、驱动和 PDO；此代际不具备掉电持久性。 */
static int init_node(MpStack *s, unsigned number)
{
    MpNode *n = &s->nodes[number - 1];
    uint32_t used = 0, err = 0;
    int rc;
    /* 初始化过程不参与调度；仅在全部CANopen/PDO步骤成功后开放该节点。 */
    n->port = (MpCanPort){number, false, NULL};
    n->tick = 0;
    n->boot++;
    if (mp_od_init(&n->od, number, &n->config))
    {
        rc = -1;
        goto failed;
    }
    n->co = CO_new(&n->config, &used);
    s->allocated += used;
    if (!n->co || CO_CANinit(n->co, &n->port, 500) != CO_ERROR_NO)
    {
        rc = -2;
        goto failed;
    }
    /* 测试节点先进入 PRE-OP；只有 Gateway 启动后才广播 NMT START。 */
    uint16_t control = number == 3 ? CO_NMT_STARTUP_TO_OPERATIONAL : 0;
    if (CO_CANopenInit(n->co, NULL, NULL, &n->od.od, NULL, control, 100, 1000, 1000, false, number,
                       &err) != CO_ERROR_NO)
    {
        rc = -(int)(100 + err);
        goto failed;
    }
    if (CO_CANopenInitPDO(n->co, n->co->em, &n->od.od, number, &err) != CO_ERROR_NO)
    {
        rc = -(int)(10000 + err);
        goto failed;
    }
    if (number == 3)
        CO_EM_initCallbackRx(n->co->em, emergency);
    CO_CANsetNormalMode(n->co->CANmodule);
    n->port.enabled = true;
    return 0;

failed:
    /* 保留原错误码和累计分配计数；失败仅停用本节点，不清空其它节点或共享总线。 */
    stop_node(n);
    return rc;
}

int mp_stack_init(MpStack *s, uint32_t epoch)
{
    memset(s, 0, sizeof(*s));
    s->epoch = epoch;
    active = s;
    mp_bus_reset();
    for (unsigned i = 1; i <= 3; i++)
    {
        int rc = init_node(s, i);
        if (rc)
        {
            mp_stack_close(s);
            return rc;
        }
    }
    mp_stack_nmt(s, 0, CO_NMT_ENTER_OPERATIONAL);
    return 0;
}

/* 释放各实例由 CANopenNode 分配的资源，再清理共享驱动表，避免保留悬空端口。 */
void mp_stack_close(MpStack *s)
{
    for (unsigned i = 0; i < 3; i++)
        stop_node(&s->nodes[i]);
    if (active == s)
        active = NULL;
    mp_bus_reset();
}

void mp_stack_nmt(MpStack *s, unsigned node, CO_NMT_command_t command)
{
    /* Gateway重建失败时没有NMT发送者；保留其它节点运行，等待明确重初始化。 */
    if (!s->nodes[2].co || !s->nodes[2].co->NMT)
        return;
    CO_NMT_sendCommand(s->nodes[2].co->NMT, command, node);
}

/* 重建指定协议实例并恢复 NMT 运行状态；这是通信重启，不等同于整块设备复位。 */
int mp_stack_restart(MpStack *s, unsigned node)
{
    if (node < 1 || node > 3)
        return -1;
    stop_node(&s->nodes[node - 1]);
    s->resets[node - 1]++;
    int rc = init_node(s, node);
    if (!rc)
        mp_stack_nmt(s, node == 3 ? 0 : node, CO_NMT_ENTER_OPERATIONAL);
    return rc;
}

void mp_stack_enable(MpStack *s, unsigned node, bool enabled)
{
    if (node >= 1 && node <= 3)
    {
        MpNode *n = &s->nodes[node - 1];
        /* enable只恢复已有实例的链路，不能让失败实例重新调度或隐式重试分配。 */
        n->port.enabled = enabled && n->co && n->port.module;
    }
}

int mp_stack_online(MpStack *s, unsigned node)
{
    if (node < 1 || node > 2)
        return 0;
    /* 失败节点及缺失的Gateway观察者均返回离线，不读取已释放的心跳对象。 */
    if (!s->nodes[node - 1].co || !s->nodes[2].co || !s->nodes[2].co->HBcons)
        return 0;
    CO_NMT_internalState_t state;
    CO_HBconsumer_t *hb = s->nodes[2].co->HBcons;
    return CO_HBconsumer_getState(hb, node - 1) == CO_HBconsumer_ACTIVE &&
           CO_HBconsumer_getNmtState(hb, node - 1, &state) == 0 && state == CO_NMT_OPERATIONAL;
}

static void request(MpNode *n, unsigned pdo)
{
    CO_TPDOsendRequest(&n->co->TPDO[pdo]);
}

static void sample(MpStack *s, MpNode *n, unsigned id)
{
    n->tick++;
    /* 固定整数锯齿仅用于验证映射，质量位 bit31 永久标识合成来源。RR 无算法输入，保持无效。 */
    if (n->tick == 1 || n->tick % 1000 == 0)
    {
        mp_od_write(&n->od, 0x2100, 1, s->epoch ? s->epoch + s->milliseconds / 1000 : 0);
        /* anchor 对应整秒边界，即使节点在秒中间重启也不引入一秒的时间偏移。 */
        mp_od_write(&n->od, 0x2100, 2, n->tick - s->milliseconds % 1000);
        request(n, 3);
        mp_od_write(&n->od, 0x2130, 1, 0x80000000U | (id == 1 ? 0x0FU : 0x17U));
        mp_od_write(&n->od, 0x2130, 2, n->boot);
        request(n, 4);
        const uint16_t a[4] = {9700, 7300, 1160, 740}, b[4] = {7300, 0, 3670, 0};
        for (unsigned j = 0; j < 4; j++)
            mp_od_write(&n->od, 0x2120, j + 1, id == 1 ? a[j] : b[j]);
        request(n, 2);
    }
    if (n->tick % (id == 1 ? 20 : 4) == 0)
    {
        mp_od_write(&n->od, 0x2110, 1,
                    id == 1 ? (n->tick % 1000) * 1000 : (uint32_t)((int)(n->tick % 1000) - 500));
        mp_od_write(&n->od, 0x2110, 2, n->tick);
        request(n, 0);
    }
    if (id == 2 && n->tick % 20 == 0)
    {
        mp_od_write(&n->od, 0x2111, 1, (uint32_t)((int)(n->tick % 4000) * 500 - 1000000));
        mp_od_write(&n->od, 0x2111, 2, n->tick);
        request(n, 1);
    }
}

/* 调用一次代表推进 1ms；先更新测试样本，再让核心处理 NMT/SDO/心跳与 PDO。 */
void mp_stack_tick(MpStack *s)
{
    s->milliseconds++;
    for (unsigned i = 0; i < 2; i++)
        if (s->nodes[i].port.enabled && s->nodes[i].co)
            sample(s, &s->nodes[i], i + 1);
    mp_bus_poll();
    for (unsigned i = 0; i < 3; i++)
    {
        MpNode *n = &s->nodes[i];
        if (!n->port.enabled || !n->co)
            continue;
        CO_NMT_reset_cmd_t reset = CO_process(n->co, false, 1000, NULL);
        if (reset != CO_RESET_NOT)
        {
            (void)mp_stack_restart(s, i + 1);
            continue;
        }
        CO_process_RPDO(n->co, false, 1000, NULL);
        CO_process_TPDO(n->co, false, 1000, NULL);
    }
    mp_bus_poll();
}
