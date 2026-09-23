# ADR：Gateway MQTT 客户端与 FreeRTOS 迁移路线 v0.1

> 状态：提议，未实施、未授权迁移；基线：P4 `09695ff2023ef6fd8dadaf5ecd64268b384a9190`。本 ADR 不改写第一阶段合同及 P4.1 Paho 安全结论。

## 背景与当前实现

当前 Gateway 是 STM32F407 **裸机 + Hardened Paho Embedded C + MQTT 3.1.1**，ESP8266 AT/TLS。Paho PATCH-01/02/03、完整性清单和固定安全回归属于已实现的 P4.1 治理。现行 P4 不包含 coreMQTT、FreeRTOS 或 MQTT 5.0。

## 分阶段候选

| 阶段 | 系统与客户端 | 协议 | 状态 |
| --- | --- | --- | --- |
| Current/P4 | 裸机 + Hardened Paho Embedded C | MQTT 3.1.1 | 已实现 |
| P5 | 裸机 + coreMQTT v2.3.1 | MQTT 3.1.1 | 候选，需独立授权与验收 |
| P6 | FreeRTOS + coreMQTT v2.3.1 | MQTT 3.1.1 | 候选，需独立授权与验收 |
| P7 | 可选 coreMQTT v5.0.2 | MQTT 5.0 | 独立协议升级候选 |

上游 [FreeRTOS/coreMQTT 官方仓库](https://github.com/FreeRTOS/coreMQTT) 列明 MQTT 3.1.1 对应 v2.3.1、MQTT 5.0 对应 v5.0.2；[官方 MQTT 5 迁移指南](https://github.com/FreeRTOS/coreMQTT/blob/main/MQTTv5Guide.md) 为后续协议迁移的参考。不能把 v5.0.2 当作 MQTT 3.1.1 客户端的替代版本。

## 决策与准出

路线按客户端替换、任务调度迁移、协议升级三步隔离，保留每步可回退基线。P5 应先验证现有 topic/payload、QoS、TLS、断线重放、RAM 上限和 publish-only 边界；P6 再验证任务调度、栈/堆、优先级、并发和重启恢复；P7 单独评估 MQTT 5 能力、Broker/Backend 兼容性及协议回退。各阶段要有独立代码评审、测试、依赖来源与安全报告，不能继承 P4.1 对 Paho 的风险结论。

这是一份技术方向记录，不等于采购、烧录、部署或真实 A/B/外部三板验收的许可。
