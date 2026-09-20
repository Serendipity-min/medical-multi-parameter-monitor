#ifndef MP_ADAPTER_H
#define MP_ADAPTER_H
#include "mp_stack.h"
#include "../../storage/router.h"

typedef struct
{
    /* A/B 各自维护采样时钟、代际和质量；seq 另含 Gateway 自身状态流。 */
    uint32_t tick[2][2], anchor[2], boot[2], seq[3][MP_STREAMS], quality[2], fault[2], status_tick;
    bool online[2];
    /* 三个未完成批次依次为 A-PPG、B-ECG、B-RESP；重启/采样断裂时清空。 */
    MpFrame waves[3];
} MpAdapter;

void mp_adapter_init(MpAdapter *a);
void mp_adapter_poll(MpAdapter *a, MpStack *s, MpRouter *r);
#endif
