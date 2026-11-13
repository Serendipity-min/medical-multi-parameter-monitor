/* 真实CANopenNode的普通Host故障回归；仅链接测试包装，不修改上游或启用sanitizer。 */
#include "mp_adapter.h"
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>

static MpStack stack;
static MpAdapter adapter;
static MpRouter router;
static void *blocks[512];
static unsigned live_blocks, calloc_calls, fail_calloc_call;
static unsigned fail_node;
static enum { NO_FAILURE, CAN_FAILURE, CORE_FAILURE, PDO_FAILURE } failure;

void *__real_calloc(size_t count, size_t size);
void __real_free(void *ptr);

void *__wrap_calloc(size_t count, size_t size)
{
    /* 计数包含失败请求，用于证明停用后没有偷偷反复分配；跟踪全部真实分配的归还。 */
    if (++calloc_calls == fail_calloc_call)
        return NULL;
    void *ptr = __real_calloc(count, size);
    assert(ptr);
    for (unsigned i = 0; i < 512; i++)
        if (!blocks[i])
        {
            blocks[i] = ptr;
            live_blocks++;
            return ptr;
        }
    abort();
}

void __wrap_free(void *ptr)
{
    if (!ptr)
        return;
    for (unsigned i = 0; i < 512; i++)
        if (blocks[i] == ptr)
        {
            blocks[i] = NULL;
            live_blocks--;
            __real_free(ptr);
            return;
        }
    abort(); /* 未登记的释放或重复释放必须令用例失败。 */
}

CO_ReturnError_t __real_CO_CANinit(CO_t *co, void *port, uint16_t rate);
CO_ReturnError_t __wrap_CO_CANinit(CO_t *co, void *port, uint16_t rate)
{
    CO_ReturnError_t rc = __real_CO_CANinit(co, port, rate);
    if (failure == CAN_FAILURE && ((MpCanPort *)port)->id == fail_node)
    {
        assert(rc == CO_ERROR_NO);
        failure = NO_FAILURE;
        /* 已经注册端口后才返回失败，验证清理会注销驱动关联。 */
        return CO_ERROR_ILLEGAL_ARGUMENT;
    }
    return rc;
}

CO_ReturnError_t __real_CO_CANopenInit(CO_t *, CO_NMT_t *, CO_EM_t *, OD_t *, OD_entry_t *,
                                     uint16_t, uint16_t, uint16_t, uint16_t, bool_t, uint8_t,
                                     uint32_t *);
CO_ReturnError_t __wrap_CO_CANopenInit(CO_t *co, CO_NMT_t *nmt, CO_EM_t *em, OD_t *od,
                                     OD_entry_t *status, uint16_t control, uint16_t hb,
                                     uint16_t srv, uint16_t cli, bool_t block, uint8_t node,
                                     uint32_t *err)
{
    CO_ReturnError_t rc = __real_CO_CANopenInit(co, nmt, em, od, status, control, hb, srv, cli,
                                             block, node, err);
    if (failure == CORE_FAILURE && node == fail_node)
    {
        assert(rc == CO_ERROR_NO);
        failure = NO_FAILURE;
        *err = 73;
        return CO_ERROR_ILLEGAL_ARGUMENT;
    }
    return rc;
}

CO_ReturnError_t __real_CO_CANopenInitPDO(CO_t *, CO_EM_t *, OD_t *, uint8_t, uint32_t *);
CO_ReturnError_t __wrap_CO_CANopenInitPDO(CO_t *co, CO_EM_t *em, OD_t *od, uint8_t node,
                                        uint32_t *err)
{
    CO_ReturnError_t rc = __real_CO_CANopenInitPDO(co, em, od, node, err);
    if (failure == PDO_FAILURE && node == fail_node)
    {
        assert(rc == CO_ERROR_NO);
        failure = NO_FAILURE;
        *err = 75;
        return CO_ERROR_ILLEGAL_ARGUMENT;
    }
    return rc;
}

static void run(unsigned ticks)
{
    while (ticks--)
    {
        mp_stack_tick(&stack);
        /* 与主循环一样继续Adapter/Router，覆盖Gateway观察者缺失后的查询路径。 */
        mp_adapter_poll(&adapter, &stack, &router);
    }
}

static void start(void)
{
    assert(live_blocks == 0);
    fail_calloc_call = 0;
    failure = NO_FAILURE;
    assert(mp_stack_init(&stack, 1790000000U) == 0);
    mp_adapter_init(&adapter);
    mp_router_init(&router);
    run(1200);
    assert(mp_stack_online(&stack, 1) && mp_stack_online(&stack, 2));
}

static void stopped(unsigned node)
{
    MpNode *n = &stack.nodes[node - 1];
    assert(!n->port.enabled && !n->co && !n->port.module);
    /* OD条目留在静态节点内，不能继续指向已删除的NMT/EM/HB/PDO扩展对象。 */
    for (unsigned i = 0; i < n->od.nentry; i++)
        assert(!n->od.entries[i].extension);
}

static void restart_case(unsigned node, unsigned kind)
{
    start();
    unsigned baseline_blocks = live_blocks;
    CO_t *others[3] = {stack.nodes[0].co, stack.nodes[1].co, stack.nodes[2].co};
    fail_node = node;
    if (kind < 2)
        fail_calloc_call = calloc_calls + (kind == 0 ? 1 : 3);
    else
        failure = kind == 2 ? CAN_FAILURE : kind == 3 ? CORE_FAILURE : PDO_FAILURE;
    assert(mp_stack_restart(&stack, node) == (kind < 3 ? -2 : kind == 3 ? -173 : -10075));
    stopped(node);
    unsigned calls_after_failure = calloc_calls, blocks_after_failure = live_blocks;
    uint32_t ticks_before[2] = {stack.nodes[0].tick, stack.nodes[1].tick};
    mp_stack_enable(&stack, node, true);
    stopped(node); /* enable不能恢复失败实例，也不能自动重试。 */
    mp_stack_nmt(&stack, node, CO_NMT_ENTER_OPERATIONAL);
    run(3000);
    stopped(node);
    assert(calloc_calls == calls_after_failure && live_blocks == blocks_after_failure);
    for (unsigned i = 0; i < 3; i++)
        if (i != node - 1)
        {
            assert(stack.nodes[i].co == others[i] && stack.nodes[i].port.enabled);
            assert(CO_NMT_getInternalState(stack.nodes[i].co->NMT) == CO_NMT_OPERATIONAL);
            if (i < 2)
                assert(stack.nodes[i].tick > ticks_before[i]);
        }
    if (node == 3)
        assert(!mp_stack_online(&stack, 1) && !mp_stack_online(&stack, 2));
    else
        assert(!mp_stack_online(&stack, node) && mp_stack_online(&stack, 3 - node));
    fail_calloc_call = 0;
    assert(mp_stack_restart(&stack, node) == 0);
    run(1200);
    assert(live_blocks == baseline_blocks);
    assert(mp_stack_online(&stack, 1) && mp_stack_online(&stack, 2));
    OD_entry_t *heartbeat = OD_find(&stack.nodes[node - 1].od.od, 0x1017);
    assert(heartbeat->extension == &stack.nodes[node - 1].co->NMT->OD_1017_extension);
    mp_stack_close(&stack);
    for (unsigned closed = 1; closed <= 3; closed++)
        stopped(closed);
    assert(live_blocks == 0);
}

int main(void)
{
    /* 三节点各覆盖首个/部分分配失败，以及CAN、核心、PDO成功部分资源后的失败。 */
    for (unsigned node = 1; node <= 3; node++)
        for (unsigned kind = 0; kind < 5; kind++)
            restart_case(node, kind);

    /* CANopen NMT触发的自动通信重启也只能失败一次，随后等待明确恢复。 */
    start();
    fail_calloc_call = calloc_calls + 1;
    mp_stack_nmt(&stack, 2, CO_NMT_RESET_COMMUNICATION);
    run(20);
    stopped(2);
    unsigned calls = calloc_calls;
    run(3000);
    assert(calloc_calls == calls && mp_stack_online(&stack, 1));
    fail_calloc_call = 0;
    assert(mp_stack_restart(&stack, 2) == 0);
    run(1200);
    assert(mp_stack_online(&stack, 2));
    mp_stack_close(&stack);
    assert(live_blocks == 0);

    /* 首次整体初始化中途失败仍保留原错误语义，但清理所有已建实例、允许安全查询。 */
    fail_node = 2;
    failure = CORE_FAILURE;
    assert(mp_stack_init(&stack, 1790000000U) == -173);
    for (unsigned node = 1; node <= 3; node++)
        stopped(node);
    assert(live_blocks == 0);
    mp_stack_nmt(&stack, 0, CO_NMT_ENTER_OPERATIONAL);
    run(50);
    assert(!mp_stack_online(&stack, 1) && !mp_stack_online(&stack, 2));
    start();
    mp_stack_close(&stack);
    assert(live_blocks == 0);
    printf("{\"restart_reliability_cases\":17,\"live_allocations_after_close\":0,\"sanitizer\":false}\n");
    return 0;
}
