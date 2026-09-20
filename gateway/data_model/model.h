#ifndef MP_MODEL_H
#define MP_MODEL_H
#include <stdint.h>
#include <stdbool.h>
#include <stddef.h>

typedef enum
{
    /* 枚举顺序与 model.c 的名称、单位及缩放表一一对应，不可只调整其中一处。 */
    MP_PPG,
    MP_SPO2,
    MP_PR,
    MP_NIBP,
    MP_ECG,
    MP_HR,
    MP_RESP,
    MP_RR,
    MP_TEMP,
    MP_NODE_STATUS,
    MP_FAULT,
    MP_GATEWAY_STATUS,
    MP_STREAMS
} MpStream;

typedef struct
{
    /* 毫秒采集时间；波形记录批次末样本时间，补传时不改成发送时间。 */
    uint64_t timestamp;
    /* seq 按节点/流递增；epoch 与 boot 共同区分采集会话。 */
    uint32_t seq, epoch, boot;
    /* 保留固定点原值，统一在 MQTT 边界缩放；最大容纳 1 秒 250 Hz ECG。 */
    int32_t values[250];
    /* rate=0 表示标量或事件；count 表示有效值/样本数量。 */
    uint16_t count, rate;
    uint8_t node, stream;
    /* synthetic 是原始来源，replay 是发送类别；历史合成数据仍保留 synthetic。 */
    bool valid, synthetic, replay;
} MpFrame;

const char *mp_stream_name(MpStream stream);
/* 返回写入长度，失败返回 0；调用者不能发送截断结果。 */
int mp_json(const MpFrame *f, char *out, size_t size);
int mp_topic(const MpFrame *f, char *out, size_t size);
#endif
