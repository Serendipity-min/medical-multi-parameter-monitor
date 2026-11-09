/* 统一帧只存固定点整数；MQTT 边界统一缩放，避免不同入口重复拼装业务字段。 */
#include "model.h"
#include "roles.h"
#include <stdio.h>
#include <stdarg.h>
#include <string.h>
#ifndef MP_MQTT_GATEWAY_ID
#define MP_MQTT_GATEWAY_ID "GW-C-001"
#endif
#ifdef MP_TRANSPORT_BENCH
#define MP_TOPIC_ROOT "mpm/bench/v1/"
#else
#define MP_TOPIC_ROOT "mpm/v1/"
#endif
static const char *names[] = {"ppg",  "spo2", "pr",   "nibp",   "ecg",   "hr",
                              "resp", "rr",   "temp", "status", "fault", "status"};
static const char *units[] = {"relative", "%",           "bpm",  "mmHg",  "mV",   "bpm",
                              "relative", "breaths/min", "degC", "state", "code", "state"};
static const int scales[] = {1000000, 100, 100, 10, 1000, 100, 1000000, 100, 100, 1, 1, 1};

__attribute__((weak)) void mp_model_poll(void)
{
}

const char *mp_stream_name(MpStream stream)
{
    return stream < MP_STREAMS ? names[stream] : "invalid";
}

/* 剩余长度包含结尾 NUL；vsnprintf 截断时返回失败，由上层放弃整个载荷。 */
static int append(char **out, size_t *left, const char *fmt, ...)
{
    va_list ap;
    va_start(ap, fmt);
    int n = vsnprintf(*out, *left, fmt, ap);
    va_end(ap);
    if (n < 0 || (size_t)n >= *left)
        return 0;
    *out += n;
    *left -= (size_t)n;
    return 1;
}

static int number(char **out, size_t *left, int32_t value, int scale)
{
    /* 放大到 int64 后取绝对值，正确处理 INT32_MIN；不依赖 nano printf 浮点扩展。 */
    uint32_t mag = value < 0 ? (uint32_t)(-(int64_t)value) : (uint32_t)value;
    unsigned decimals = scale == 1000000 ? 6 : scale == 1000 ? 3 : scale == 100 ? 2 : 1;
#ifdef MP_B5_CLOUD_CANDIDATE
    /* B5的100点批次避免逐点通用格式解析；小数位和输出字节保持原协议。 */
    char digits[24], *end = digits + sizeof(digits), *p = end;
    uint32_t fraction = mag % (uint32_t)scale, whole = mag / (uint32_t)scale;
    for (unsigned i = 0; i < decimals; i++) { *--p = (char)('0' + fraction % 10); fraction /= 10; }
    *--p = '.';
    do { *--p = (char)('0' + whole % 10); whole /= 10; } while (whole);
    if (value < 0) *--p = '-';
    size_t length = (size_t)(end - p);
    if (length >= *left) return 0;
    memcpy(*out, p, length); *out += length; *left -= length; **out = 0;
    return 1;
#else
    return append(out, left, "%s%lu.%0*lu", value < 0 ? "-" : "", (unsigned long)(mag / scale),
                  decimals, (unsigned long)(mag % scale));
#endif
}

/* 只在输出边界缩放固定点并选择 LIVE/MOCK/REPLAY，不修改原始帧的时间和序号。 */
int mp_json(const MpFrame *f, char *out, size_t size)
{
    if (!f || f->stream >= MP_STREAMS || f->count > MP_FRAME_MAX_SAMPLES || !size)
        return 0;
    char *p = out;
    size_t left = size;
    unsigned k = f->stream;
    /* 未授时的启动状态为0毫秒；不能拼成0000，否则不是合法JSON数字。 */
    char timestamp[24];
    if (f->timestamp < 1000u)
        (void)snprintf(timestamp, sizeof(timestamp), "%lu", (unsigned long)f->timestamp);
    else
        (void)snprintf(timestamp, sizeof(timestamp), "%lu%03lu", (unsigned long)(f->timestamp / 1000),
                       (unsigned long)(f->timestamp % 1000));
    const char *valid = f->valid                                          ? "VALID"
                        : (k == MP_NODE_STATUS || k == MP_GATEWAY_STATUS) ? "OFFLINE"
                                                                          : "INVALID";
    if (!append(
            &p, &left,
            "{\"timestamp\":%s,\"seq\":%lu,\"session_id\":\"can-%lu-%lu\",\"validity\":\"%s\",\"source\":\"%s\",\"synthetic\":%s,\"unit\":\"%s\",\"value\":",
            timestamp,
            (unsigned long)f->seq, (unsigned long)f->epoch, (unsigned long)f->boot, valid,
#ifndef MP_TRANSPORT_BENCH
            f->replay      ? "REPLAY" :
#endif
            f->synthetic ? "MOCK"
                           : "LIVE",
            f->synthetic ? "true" : "false", units[k]))
        return 0;
    if (k == MP_NODE_STATUS || k == MP_GATEWAY_STATUS)
    {
        if (!append(&p, &left, "\"%s\"", f->valid ? "ONLINE" : "OFFLINE"))
            return 0;
    }
    else if (k == MP_FAULT)
    {
        if (!append(&p, &left, "\"EMCY-%04lX\"", (unsigned long)(uint32_t)f->values[0]))
            return 0;
    }
    else if (f->rate)
    {
        if (!append(&p, &left, "null,\"sample_rate\":%u,\"samples\":[", f->rate))
            return 0;
        for (unsigned i = 0; i < f->count; i++)
        {
            /* 大批次格式化也需让出时间给 CAN，不能等到串口发送时才处理 RPDO。 */
            mp_model_poll();
            if (i) {
#ifdef MP_B5_CLOUD_CANDIDATE
                if (left <= 1) return 0;
                *p++ = ','; left--; *p = 0;
#else
                if (!append(&p, &left, ",")) return 0;
#endif
            }
            if (!number(&p, &left, f->values[i], scales[k]))
                return 0;
        }
        if (!append(&p, &left, "]"))
            return 0;
    }
    else if (!f->valid)
    {
        if (!append(&p, &left, "null"))
            return 0;
    }
    else if (k == MP_NIBP)
    {
        if (!append(&p, &left, "[") || !number(&p, &left, f->values[0], 10) ||
            !append(&p, &left, ",") || !number(&p, &left, f->values[1], 10) ||
            !append(&p, &left, "]"))
            return 0;
    }
    else if (!number(&p, &left, f->values[0], scales[k]))
        return 0;
    return append(&p, &left, "}") ? (int)(p - out) : 0;
}

/* 当前状态、当前事件和历史遥测使用不同 Topic，防止旧 ONLINE 或 EMCY 覆盖当前语义。 */
int mp_topic(const MpFrame *f, char *out, size_t size)
{
    int n;
    char node = mp_node_letter(f->node);
    if (f->stream >= MP_STREAMS || (f->stream != MP_GATEWAY_STATUS && !node)) return 0;
#ifdef MP_FIVE_NODE
    if (f->stream < MP_NODE_STATUS && f->node != mp_role_node((MpStream)f->stream)) return 0;
#endif
    if (f->stream == MP_GATEWAY_STATUS)
        n = snprintf(out, size, MP_TOPIC_ROOT MP_MQTT_GATEWAY_ID "/status");
    else if (f->stream == MP_NODE_STATUS || (f->stream == MP_FAULT && !f->replay))
        n = snprintf(out, size, MP_TOPIC_ROOT MP_MQTT_GATEWAY_ID "/NODE-%c/%s", node,
                     f->stream == MP_FAULT ? "event" : "status");
    else
        n = snprintf(out, size, MP_TOPIC_ROOT MP_MQTT_GATEWAY_ID "/NODE-%c/%s/%s", node,
                     f->replay ? "replay" : "telemetry", names[f->stream]);
    return n > 0 && (size_t)n < size ? n : 0;
}
