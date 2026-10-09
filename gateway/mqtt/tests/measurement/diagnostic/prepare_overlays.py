"""由已固定Git对象生成审查patch；严格的一次精确上下文替换，绝不改生产文件。"""
import difflib
from pathlib import Path
from build_diagnostic import ALLOWED_PATCH, HERE, PINS, git

def once(text, before, after):
    if text.count(before) != 1:
        raise ValueError('exact frozen overlay context is not unique')
    return text.replace(before, after, 1)

def modified(variant):
    originals = {path: git('show', PINS[variant] + ':' + path).decode('utf-8') for path in sorted(ALLOWED_PATCH)}
    result = dict(originals)
    path = 'gateway/mqtt/src/main.c'; text = result[path]
    text = once(text, '#include "mp_adapter.h"\n', '#include "mp_adapter.h"\n#include "probe_events.h"\n')
    text = once(text, '        mp_adapter_poll(&adapter, &stack, &router);\n',
                '        mp_adapter_poll(&adapter, &stack, &router);\n        /* 仅诊断副本：记录同一计划tick的合成协作完成点。 */\n        probe_service_done(serviced);\n')
    text = once(text, "    if (c == 'D')\n        disconnect_requested = 1;", "    if (c == 'D')\n    {\n        probe_network_point(PROBE_D_REQUEST);\n        disconnect_requested = 1;\n    }")
    text = once(text, '    serviced = g_uptime_ms;\n', '    serviced = g_uptime_ms;\n    probe_service_arm(serviced);\n')
    text = once(text, '                delay_ms(30000);\n', '                delay_ms(30000);\n                probe_network_point(PROBE_PAUSE_END);\n')
    text = once(text, '                disconnect_requested = 0;\n', '                disconnect_requested = 0;\n                (void)probe_window_begin();\n                probe_cache_snapshot(1, router.cn, router.dropped, router.replayed, mp_bus_dropped());\n')
    text = once(text, '                mp_router_ack(&router, &f, ok);\n', '                mp_router_ack(&router, &f, ok);\n                probe_cache_snapshot(0, router.cn, router.dropped, router.replayed, mp_bus_dropped());\n')
    text = once(text, '        gateway_network_close();\n        delay_ms(2000);', '        probe_network_point(PROBE_CLEANUP_BEGIN);\n        gateway_network_close();\n        probe_network_point(PROBE_CLEANUP_DELAY_BEGIN);\n        delay_ms(2000);\n        probe_network_point(PROBE_CLEANUP_END);')
    result[path] = text
    path = 'gateway/mqtt/src/heap.c'; text = result[path]
    text = once(text, '#include <errno.h>\n', '#include <errno.h>\n#include "probe_events.h"\n')
    text = once(text, '        errno = ENOMEM;\n', '        probe_heap_enomem();\n        errno = ENOMEM;\n')
    text = once(text, '    current += increment;\n', '    current += increment;\n    probe_heap_peak((uint32_t)(current - &_heap_start));\n')
    result[path] = text
    path = 'gateway/esp_at_probe/src/stm32f4xx_it.c'; text = result[path]
    text = once(text, '#include "main.h"\n', '#include "main.h"\n#include "probe_events.h"\n')
    text = once(text, '    g_uptime_ms++;\n', '    g_uptime_ms++;\n    /* 定长非阻塞ISR记录，不格式化、不做网络或分配。 */\n    probe_tick(g_uptime_ms);\n')
    result[path] = text
    path = 'gateway/mqtt/src/platform.c'; text = result[path]
    text = once(text, '#include <string.h>\n', '#include <string.h>\n#include "probe_events.h"\n')
    text = once(text, '    init_uart();\n', '    init_uart();\n    probe_init(SystemCoreClock);\n')
    text = once(text, '        poll_callback();\n', '        /* CAN子区间与AT嵌套，父span只扣直接子区间一次。 */\n        ProbeToken can_span = probe_begin(PROBE_CAN_CALLBACK);\n        poll_callback();\n        probe_end(can_span, 1);\n')
    if variant == 'P4':
        before = 'static int mqtt_write(Network *network, unsigned char *data, int length, int timeout)'
        text = once(text, before, before.replace('mqtt_write', 'original_mqtt_write'))
        before = 'static int mqtt_read(Network *network, unsigned char *data, int length, int timeout)'
        text = once(text, before, before.replace('mqtt_read', 'original_mqtt_read'))
        text = once(text, '#include "probe_events.h"\n', '#include "probe_events.h"\nstatic int mqtt_write(Network *, unsigned char *, int, int);\nstatic int mqtt_read(Network *, unsigned char *, int, int);\n')
        wrappers = '''
/* 同原参数/结果包围完整AT传输，探针不会截断或改变错误传播。 */
static int mqtt_write(Network *network, unsigned char *data, int length, int timeout)
{
    ProbeToken span = probe_begin(PROBE_AT_SEND);
    int result = original_mqtt_write(network, data, length, timeout);
    probe_end(span, result >= 0);
    return result;
}
static int mqtt_read(Network *network, unsigned char *data, int length, int timeout)
{
    ProbeToken span = probe_begin(PROBE_AT_RECV);
    int result = original_mqtt_read(network, data, length, timeout);
    probe_end(span, result >= 0);
    return result;
}
'''
    else:
        text = once(text, 'int esp_mqtt_send(const unsigned char *data, int length, uint32_t timeout)',
                    'static int original_esp_mqtt_send(const unsigned char *data, int length, uint32_t timeout)')
        text = once(text, 'int esp_mqtt_recv(unsigned char *data, int length, uint32_t timeout)',
                    'static int original_esp_mqtt_recv(unsigned char *data, int length, uint32_t timeout)')
        wrappers = '''
/* 同原参数/结果包围完整AT传输，探针不会截断或改变错误传播。 */
int esp_mqtt_send(const unsigned char *data, int length, uint32_t timeout)
{
    ProbeToken span = probe_begin(PROBE_AT_SEND);
    int result = original_esp_mqtt_send(data, length, timeout);
    probe_end(span, result >= 0);
    return result;
}
int esp_mqtt_recv(unsigned char *data, int length, uint32_t timeout)
{
    ProbeToken span = probe_begin(PROBE_AT_RECV);
    int result = original_esp_mqtt_recv(data, length, timeout);
    probe_end(span, result >= 0);
    return result;
}
'''
    result[path] = text + wrappers
    path = 'gateway/mqtt/src/gateway_transport.c'; text = result[path]
    text = once(text, '#include <string.h>\n', '#include <string.h>\n#include "probe_events.h"\n')
    # 外层wrapper统一接住原函数的全部返回，不逐个改写错误分支。
    for name, argument in [('gateway_mqtt_open', 'const MpFrame *will_frame'), ('gateway_mqtt_publish', 'const MpFrame *frame'),
                           ('gateway_mqtt_yield', 'void'), ('gateway_network_open', 'void')]:
        text = once(text, f'int {name}({argument})', f'static int original_{name}({argument})')
    text = once(text, '    int ok = at_command(command, timeout);\n', '    int ok = at_command(command, timeout);\n    if (ok && !strcmp(name, "TLS"))\n        probe_network_point(PROBE_TLS_READY);\n')
    if variant == 'P4':
        text = once(text, 'static const GatewayConfig *config = GATEWAY_CONFIG;\n',
                    '#ifdef PROBE_HOST_TEST\n/* 仅Host诊断联测使用现有明确合成配置；ARM仍读原sector7。 */\nextern const GatewayConfig gateway_test_config;\nstatic const GatewayConfig *config = &gateway_test_config;\n#else\nstatic const GatewayConfig *config = GATEWAY_CONFIG;\n#endif\n')
        text = once(text, '    int ok = MQTTConnect(&client, &options) == SUCCESS;\n', '    int ok = MQTTConnect(&client, &options) == SUCCESS;\n    if (ok) probe_network_point(PROBE_CONNACK);\n')
        text = once(text, 'MQTTPublish(&client, topic, &message)', 'diagnostic_library_publish(&client, topic, &message)')
        text = once(text, 'MQTTYield(&client, 5)', 'diagnostic_library_process(&client, 5)')
        declarations = 'static int diagnostic_library_publish(MQTTClient *, const char *, MQTTMessage *);\nstatic int diagnostic_library_process(MQTTClient *, int);\n'
        extra = '''
static int diagnostic_library_publish(MQTTClient *context, const char *topic, MQTTMessage *message)
{
    ProbeToken span = probe_begin(PROBE_LIBRARY_PUBLISH);
    int result = MQTTPublish(context, topic, message);
    probe_end(span, result == SUCCESS);
    return result;
}
static int diagnostic_library_process(MQTTClient *context, int timeout)
{
    ProbeToken span = probe_begin(PROBE_PROCESS);
    int result = MQTTYield(context, timeout);
    probe_end(span, result == SUCCESS);
    return result;
}
'''
    else:
        text = once(text, 'MQTT_ProcessLoop(&client)', 'diagnostic_library_process(&client)')
        text = once(text, 'MQTT_Publish(&client, &message, pending_id)', 'diagnostic_library_publish(&client, &message, pending_id)')
        text = once(text, '    if (ok)\n        mqtt_online = 1;\n', '    if (ok)\n    {\n        mqtt_online = 1;\n        probe_network_point(PROBE_CONNACK);\n    }\n')
        declarations = 'static MQTTStatus_t diagnostic_library_publish(MQTTContext_t *, const MQTTPublishInfo_t *, uint16_t);\nstatic MQTTStatus_t diagnostic_library_process(MQTTContext_t *);\n'
        extra = '''
static MQTTStatus_t diagnostic_library_publish(MQTTContext_t *context, const MQTTPublishInfo_t *message, uint16_t id)
{
    ProbeToken span = probe_begin(PROBE_LIBRARY_PUBLISH);
    MQTTStatus_t result = MQTT_Publish(context, message, id);
    probe_end(span, result == MQTTSuccess);
    return result;
}
static MQTTStatus_t diagnostic_library_process(MQTTContext_t *context)
{
    ProbeToken span = probe_begin(PROBE_PROCESS);
    MQTTStatus_t result = MQTT_ProcessLoop(context);
    probe_end(span, result == MQTTSuccess);
    return result;
}
'''
    text = once(text, '#include "probe_events.h"\n', '#include "probe_events.h"\n' + declarations)
    wrappers = '''
/* 包围原实现整体；任何早返回、发送失败和PUBACK等待均先完成原逻辑，再原样返回。 */
int gateway_mqtt_open(const MpFrame *will_frame)
{
    ProbeToken span = probe_begin(PROBE_OPEN);
    int result = original_gateway_mqtt_open(will_frame);
    probe_end(span, result);
    return result;
}
int gateway_mqtt_publish(const MpFrame *frame)
{
    unsigned scope = frame && frame->rate && !frame->replay ? PROBE_PUBLISH_Q0 : PROBE_PUBLISH_Q1;
    ProbeToken span = probe_begin(scope);
    int result = original_gateway_mqtt_publish(frame);
    probe_end(span, result);
    int business = frame && frame->synthetic && frame->stream < MP_NODE_STATUS;
    uint32_t already = probe_state.network_valid_mask & (1U << PROBE_FIRST_BUSINESS);
    probe_frame_result(result, frame ? frame->synthetic : 0, business, frame ? frame->valid : 0, frame ? frame->replay : 0);
    if (!already && (probe_state.network_valid_mask & (1U << PROBE_FIRST_BUSINESS)))
        probe_first_business_id(frame->node, frame->stream, frame->seq, frame->epoch, frame->boot);
    return result;
}
int gateway_mqtt_yield(void)
{
    ProbeToken span = probe_begin(PROBE_YIELD);
    int result = original_gateway_mqtt_yield();
    probe_end(span, result);
    return result;
}
int gateway_network_open(void)
{
    probe_network_point(PROBE_RECOVERY_START);
    return original_gateway_network_open();
}
'''
    result[path] = text + extra + wrappers
    return originals, result

def main():
    directory = HERE / 'overlays'; directory.mkdir(exist_ok=True)
    for variant in PINS:
        before, after = modified(variant)
        chunks = []
        for path in sorted(before):
            chunks.append(f'diff --git a/{path} b/{path}\n')
            chunks.extend(difflib.unified_diff(before[path].splitlines(True), after[path].splitlines(True),
                          fromfile='a/' + path, tofile='b/' + path))
        target = directory / (variant + '.patch')
        with target.open('x', encoding='utf-8', newline='\n') as output:
            output.write(''.join(chunks))
        print(variant + ' exact frozen-source overlay written')

if __name__ == '__main__':
    main()
