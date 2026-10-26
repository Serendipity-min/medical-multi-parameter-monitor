#ifndef B5_POLICY_H
#define B5_POLICY_H
#include "../data_model/model.h"
/* 最多60秒连接准备 + 45秒预热 + 300秒共同评价 + 15秒尾段。 */
#define B5_WINDOW_MS 420000u
#define B5_CLIENT_ID "b5-c-isolated"
#define B5_USERNAME "b5-gateway"
int b5_identity_allowed(const char *client, const char *user);
/* 过期遥测只能作为历史，旧状态直接丢弃；不能重写采集时间使其复活。 */
int b5_prepare_publish(MpFrame *frame, uint64_t now);
int b5_network_stopped(void);
#endif
