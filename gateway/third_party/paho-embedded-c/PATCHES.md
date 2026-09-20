# 本项目补丁与许可证

上游固定提交见 `upstream.json`，其中 SHA-256 为下载时已按 Git blob SHA-1 核验的原始文件。
本项目选择 Eclipse Distribution License 1.0；随源码保留 `edl-v10` 和 `epl-v20`。

仅修改 `MQTTClient-C/src/MQTTClient.c` 的 `MQTTSubscribeWithResults`：
用局部 `int` 在 QoS 枚举与序列化 API 之间转换，避免 ARM 默认短枚举被强制转换为
`int *` 后越界读写。MQTT 订阅路径目前不用于 Gateway 发布器，但必须消除构建时暴露的
接口大小不匹配；不采用与工具链运行库不一致的全局枚举 ABI。
