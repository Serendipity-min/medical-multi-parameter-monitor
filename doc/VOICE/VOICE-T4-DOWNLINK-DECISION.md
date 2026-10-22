# VOICE T4｜下行方案裁定准备

本轮用户优先目标为本地喇叭发声；本文件是设计比较，T4真实Broker接入与T5均未执行。

当前H3 `mqtt_event()`收到PUBLISH即关闭连接；512B接收缓存、单个在途QoS1和5s预算不能因语音退化。P6V1为54B固定头+≤240B UTF-8、最长15s TTL、非retain、QoS1、5s间隔；fact_digest绑定事实，不是MAC。已授权普通AI回归通过不代表当前C能接收语音。

仓库 `cloud/broker/acl` 是受版本管理的参考规则：gateway-c仅write自身网关，Backend reader读授权网关，未给语音read。未SSH读取当前正式ACL，不把参考文件写成正式生效ACL。本轮不写云端、不调用豆包、不对正式Broker订阅/发布。

| 方案 | 最小改动/阻断 | 裁定 |
|---|---|---|
| A 同一MQTT会话精确订阅voice/reply | 仅voice-enabled候选加SUBSCRIBE/SUBACK、PUBLISH/PUBACK、固定Topic白名单；Broker分角色精确read/write；验证最大帧和5s预算 | 优先设计候选，尚未实现/选择上线 |
| B 独立语音TLS连接 | 需ESP实际多socket/SSL/CIPMUX、RAM、功耗、超时共存证据；当前没有 | NO_GO_PENDING_CAPABILITY_EVIDENCE，不自动开第二连接 |

未来时序：用户第七页勾选/点击“播报此条”→鉴权API产生最小非人体短文本→专用发布角色精确Topic→Broker PUBACK→C真实订阅/严格P6V1校验/入站PUBACK→单槽→UART TX_DONE→41→4F→人工可闻。每层分开记，不用PUBACK替代声音。

拒绝条件包括：错Gateway/Topic、QoS0、retain、大小/UTF-8不符、控制标签、时间不可信/过期、旧ID/乱序/重启回放、播报开关关闭、取消和源切换。设备没有通用控制命令。最小文本保留“模拟数据”提示，不接受身份、诊断或用药建议。

本轮状态：`T4_DESIGN_ONLY / T5_CLOUD_AUDIO_NOT_AUTHORIZED`。现有生产语音保持PAUSED/DISABLED，麦克风/ASR不在范围。
