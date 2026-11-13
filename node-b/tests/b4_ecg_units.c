/* 本测试输入为合成显示量；串起真实B队列/PDO与网关mV序列化，不作为电压校准。 */
#include "ecg_units.h"
#include "b_canopen_app.h"
#include "bio_v2.h"
#include "CANopen.h"
#include "model.h"
#include "core_mqtt.h"
#include <assert.h>
#include <limits.h>
#include <math.h>
#include <stdio.h>
#include <string.h>

extern void b4_host_now(uint32_t now);
extern void b4_host_wire(FILE *file);
extern void b4_host_receive(uint32_t id, uint8_t dlc, const uint8_t *data);
typedef struct { int32_t display, uv; } Point;
static const Point points[] = {
    {0, 0}, {1, 0}, {-1, 0}, {2, 1}, {-2, -1}, {3, 1}, {-3, -1},
    {199, 120}, {-199, -120}, {200, 121}, {-200, -121},
    {1000000, 605000}, {-1000000, -605000},
    {INT32_MAX, 1299227761}, {INT32_MIN, -1299227761}
};
static void time_frame(uint32_t now) {
    uint64_t relative = UINT64_C(1792713600000) + now - UINT64_C(441763200000);
    uint8_t data[6]; CO_setUint32(data, (uint32_t)(relative % 86400000));
    CO_setUint16(data + 4, (uint16_t)(relative / 86400000));
    b4_host_receive(0x100, 6, data);
}
static void wire_path(void) {
    FILE *wire = tmpfile(); assert(wire); b4_host_wire(wire);
    BioV2_Init(0); CanOpen_Init(); assert(!g_b_can.error);
    for (unsigned i = 0; i < sizeof(points) / sizeof(points[0]); i++) {
        uint32_t tick = 1000u + i * 4u; b4_host_now(tick);
        if (!i) time_frame(tick);
        /* 仅替代测试输入；生产BIO源和寄存器均不改，检查入队到PDO的实际字节。 */
        g_bio_v2.ecg_filtered = points[i].display;
        BCan_Sample(tick, i + 1u, 0); CanOpen_Task(tick);
    }
    b4_host_wire(NULL); rewind(wire);
    unsigned tick, id, dlc, bytes[8], count = 0;
    while (fscanf(wire, "%u %u %u", &tick, &id, &dlc) == 3) {
        uint8_t data[8] = {0}; assert(dlc <= 8);
        for (unsigned i = 0; i < dlc; i++) { assert(fscanf(wire, "%u", &bytes[i]) == 1); data[i] = (uint8_t)bytes[i]; }
        if (id != 0x182) continue;
        assert(count < sizeof(points) / sizeof(points[0]) && dlc == 8);
        int32_t value; uint32_t raw = CO_getUint32(data); memcpy(&value, &raw, 4);
        assert(value == points[count].uv && CO_getUint32(data + 4) == 1000u + count * 4u);
        count++;
    }
    fclose(wire); assert(count == sizeof(points) / sizeof(points[0]));
    assert(!g_b_can.overflow && !g_b_can.discontinuities);
}
int main(int argc, char **argv) {
    assert(argc == 2 && B4_ECG_CH2SET == 0x40 && B4_ECG_GAIN == 4 && B4_ECG_VREF_UV == 2420000);
    for (unsigned i = 0; i < sizeof(points) / sizeof(points[0]); i++)
        assert(b4_ecg_display_to_uv(points[i].display) == points[i].uv);
    double max_conversion = 0, max_ui_chain = 0;
    for (int32_t display = -1000000; display <= 1000000; display++) {
        double error = fabs(b4_ecg_display_to_uv(display) - display * (2420000.0 / 4.0 / 1000000.0) * (8388608.0 / 8388607.0));
        assert(error < 1.000001); if (error > max_conversion) max_conversion = error;
    }
    /* 再覆盖全int32显示输入及有符号24位ADC范围，独立浮点物理公式计算误差。
     * UI链测试只评合成单个code的缩放量化，不评滤波增益/时钟/参考源校准误差。 */
    uint32_t random = 0x41735a29u;
    for (unsigned i = 0; i < 65536; i++) {
        random ^= random << 13; random ^= random >> 17; random ^= random << 5;
        int32_t display; memcpy(&display, &random, 4);
        assert(fabs(b4_ecg_display_to_uv(display) - display * .605 * (8388608.0 / 8388607.0)) < 1.000001);
        int32_t code = (int32_t)(random & 0xffffffu) - 8388608;
        int32_t ui = (int32_t)((float)code * .11920928955f);
        double error = fabs(b4_ecg_display_to_uv(ui) - code * (2420000.0 / 4.0 / 8388607.0));
        assert(error < 1.7); if (error > max_ui_chain) max_ui_chain = error;
    }
    wire_path();
    MpFrame frame = {0}; frame.node = 2; frame.stream = MP_ECG; frame.rate = 250;
    frame.count = 100; frame.valid = true; frame.synthetic = true;
    frame.timestamp = UINT64_C(1792713600000); frame.seq = 1; frame.epoch = 1; frame.boot = 1;
    for (unsigned i = 0; i < 100; i++) frame.values[i] = points[i % (sizeof(points) / sizeof(points[0]))].uv;
    char json[2048], topic[128]; int n = mp_json(&frame, json, sizeof(json)); assert(n > 0 && n < 2048);
    assert(strstr(json, "\"unit\":\"mV\"") && strstr(json, "605.000,-605.000"));
    assert(mp_topic(&frame, topic, sizeof(topic)) > 0);
    MQTTPublishInfo_t publish = {0}; publish.pTopicName = topic; publish.topicNameLength = (uint16_t)strlen(topic);
    publish.pPayload = json; publish.payloadLength = (size_t)n;
    size_t remaining, bytes; assert(MQTT_GetPublishPacketSize(&publish, &remaining, &bytes) == MQTTSuccess && bytes <= 2048);
    uint8_t buffer[2048]; MQTTFixedBuffer_t fixed = {buffer, sizeof(buffer)};
    assert(MQTT_SerializePublish(&publish, 0, remaining, &fixed) == MQTTSuccess);
    FILE *out = fopen(argv[1], "w"); assert(out); fprintf(out, "%s\t%s\n", topic, json); fclose(out);
    printf("gain4/PDO/mV PASS: 2000001 display values + 65536 int32/24-bit inputs; conversion max=%.9f uV, UI chain max=%.9f uV; JSON=%d MQTT=%u bytes; nominal only\n",
           max_conversion, max_ui_chain, n, (unsigned)bytes);
    return 0;
}
