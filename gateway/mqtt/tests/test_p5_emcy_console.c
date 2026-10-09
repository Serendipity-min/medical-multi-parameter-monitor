/* GEMINI-P5-001 专项回归测试：调用真实 production service() 分支验证本地 E 命令守卫。
 * 验证：
 * 1. co == NULL + 'E'：安全拒绝，不调 CO_error，输出 UNAVAILABLE，不翻转 fault。
 * 2. co != NULL && co->em == NULL + 'E'：安全拒绝，输出 UNAVAILABLE，不翻转 fault。
 * 3. 恢复有效节点后，首次有效 'E'：正确触发 CO_errorReport（证实未被前序错误翻转）。
 * 4. 连续第二次有效 'E'：正确触发 CO_errorReset。
 * 5. 其它字符（如 'C'）及正常逻辑不受影响。
 */

#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>

#include "gateway_transport.h"
#include "mp_adapter.h"

/* Mock 跟踪变量 */
static int co_error_calls = 0;
static bool last_set_error = false;
static uint8_t last_error_bit = 0;
static uint16_t last_error_code = 0;
static uint32_t last_info_code = 0;

static char captured_console[256];
static int captured_console_calls = 0;
static int mock_char = -1;

/* Mock console 接口 */
void console(const char *message)
{
    captured_console_calls++;
    if (message)
    {
        strncpy(captured_console, message, sizeof(captured_console) - 1);
        captured_console[sizeof(captured_console) - 1] = '\0';
    }
}

int console_char(void)
{
    int c = mock_char;
    mock_char = -1;
    return c;
}

/* Mock CANopen CO_error 接口 */
void CO_error(CO_EM_t *em, bool_t setError, const uint8_t errorBit, uint16_t errorCode, uint32_t infoCode)
{
    (void)em;
    co_error_calls++;
    last_set_error = (bool)setError;
    last_error_bit = errorBit;
    last_error_code = errorCode;
    last_info_code = infoCode;
}

/* Mock main.c 所依赖的其它平台与硬件调用，确保 host 测试隔离 */
volatile uint32_t g_uptime_ms = 0;

void platform_init(void) {}
void platform_poll(void) {}
void platform_set_poll(void (*poll)(void)) { (void)poll; }
int gateway_config_valid(void) { return 1; }
int mp_bxcan_init(void) { return 0; }
int mp_stack_init(MpStack *s, uint32_t epoch) { (void)s; (void)epoch; return 0; }
void mp_adapter_init(MpAdapter *a) { (void)a; }
void mp_router_init(MpRouter *r) { (void)r; }
int gateway_network_open(void) { return 0; }
void gateway_network_close(void) {}
void delay_ms(uint32_t ms) { (void)ms; }
uint32_t gateway_epoch(void) { return 0; }
int gateway_mqtt_open(const MpFrame *will) { (void)will; return 0; }
int at_command(const char *cmd, uint32_t timeout) { (void)cmd; (void)timeout; return 0; }
bool mp_router_take(MpRouter *r, MpFrame *f, uint32_t now) { (void)r; (void)f; (void)now; return false; }
int gateway_mqtt_publish(const MpFrame *f) { (void)f; return 0; }
void mp_router_ack(MpRouter *r, const MpFrame *f, bool ok) { (void)r; (void)f; (void)ok; }
int gateway_mqtt_yield(void) { return 0; }
uint32_t mp_bus_frames(void) { return 0; }
uint32_t mp_bus_dropped(void) { return 0; }
int mp_stack_online(MpStack *s, unsigned n) { (void)s; (void)n; return 0; }
void mp_router_online(MpRouter *r, bool online) { (void)r; (void)online; }

void mp_bus_poll(void) {}
void mp_stack_tick(MpStack *s) { (void)s; }
void mp_adapter_poll(MpAdapter *a, MpStack *s, MpRouter *r) { (void)a; (void)s; (void)r; }
void mp_stack_enable(MpStack *s, unsigned n, bool e) { (void)s; (void)n; (void)e; }
static bool s_mock_bus_online = true;
void mp_bus_set_online(bool o) { s_mock_bus_online = o; }
int mp_stack_restart(MpStack *s, unsigned n) { (void)s; (void)n; return 0; }

/* 重命名 main.c 的 main 为 production_main，直接引入生产源码进行白盒测试 */
#define main production_main
#include "../src/main.c"
#undef main

#define PASS(name) puts("PASS " name)

int main(void)
{
    /* 创建用于测试的真实 CO_t 和 CO_EM_t 结构体 */
    CO_t valid_co;
    CO_EM_t valid_em;
    memset(&valid_co, 0, sizeof(valid_co));
    memset(&valid_em, 0, sizeof(valid_em));

    /* 用例 1: co == NULL 情况下按下 'E' */
    stack.nodes[0].co = NULL;
    mock_char = 'E';
    captured_console[0] = '\0';
    co_error_calls = 0;

    service();

    assert(co_error_calls == 0);
    assert(strcmp(captured_console, "GW EMCY_TEST_NODE_UNAVAILABLE\r\n") == 0);
    PASS("emcy_console_null_co_rejected_without_fault_flip");

    /* 用例 2: co != NULL 但 co->em == NULL 情况下按下 'E' */
    stack.nodes[0].co = &valid_co;
    valid_co.em = NULL;
    mock_char = 'E';
    captured_console[0] = '\0';
    co_error_calls = 0;

    service();

    assert(co_error_calls == 0);
    assert(strcmp(captured_console, "GW EMCY_TEST_NODE_UNAVAILABLE\r\n") == 0);
    PASS("emcy_console_null_em_rejected_without_fault_flip");

    /* 用例 3: 恢复有效节点，第一次有效 'E' 必须触发 report（setError=true） */
    valid_co.em = &valid_em;
    stack.nodes[0].co = &valid_co;
    mock_char = 'E';
    captured_console[0] = '\0';
    co_error_calls = 0;

    service();

    assert(co_error_calls == 1);
    assert(last_set_error == true); /* 必须是 report，说明此前异常输入未翻转 fault 状态 */
    assert(last_error_bit == CO_EM_GENERIC_ERROR);
    assert(last_error_code == CO_EMC_GENERIC);
    assert(strcmp(captured_console, "GW EMCY_TEST_CHANGED\r\n") == 0);
    PASS("emcy_console_first_valid_triggers_report");

    /* 用例 4: 连续第二次有效 'E' 必须触发 reset（setError=false） */
    mock_char = 'E';
    captured_console[0] = '\0';
    co_error_calls = 0;

    service();

    assert(co_error_calls == 1);
    assert(last_set_error == false); /* 翻转为 reset */
    assert(last_error_bit == CO_EM_GENERIC_ERROR);
    assert(last_error_code == CO_EMC_NO_ERROR);
    assert(strcmp(captured_console, "GW EMCY_TEST_CHANGED\r\n") == 0);
    PASS("emcy_console_second_valid_triggers_reset");

    /* 用例 5: 其它控制命令行为不受影响（如 'C' 切换 CAN 状态） */
    mock_char = 'C';
    captured_console[0] = '\0';
    service();
    assert(strcmp(captured_console, "GW CAN_TEST_DISCONNECTED\r\n") == 0);
    assert(!s_mock_bus_online);
    PASS("emcy_console_other_commands_unaffected");

    return 0;
}
