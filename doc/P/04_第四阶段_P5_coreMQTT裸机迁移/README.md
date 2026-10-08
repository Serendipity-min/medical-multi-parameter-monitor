# P5：裸机 coreMQTT v2.3.1 / MQTT 3.1.1

唯一合同：[正式 v1.0](../P5_coreMQTT裸机迁移正式执行合同_v1.0.md)。
本轮软件基线 `P4@8dee339`；首轮软件证据绑定 `505be8a`；最新 P0 实现与验证绑定
`e598fc63719acdf49a99c6da46c656dc8c607782`。历史报告原样保留，最新证据见下方 P0 补充。
当前为 **P5_PENDING_HARDWARE_AND/OR_SECURITY**，动态资源仍待测。

软件迁移、ARM 构建、42 项 C 普通用例、6 项来源用例通过；隔离真实 Mosquitto 的 30 项
P4/P5 对照与 Will/retain/PUBACK/保活通过。assert 的 OS 桩依赖已由获授权的有界诊断停机替换。
正式 ESP/TLS 真机准出、动态性能和统一 Security Gate 尚未完成。
用户另外授权本次 GitHub App 自动 Semgrep 检查；它与统一 Security Gate 的授权和准出分开记录。
P4/main、A/B、CANopen/Router/模型、Cloud 和历史证据未改；P6 未启动。

- [本轮重建的 P4 基线](baseline.md)
- [接口迁移与构建清单](设计/P5_接口迁移与构建清单_v1.0.md)
- [普通功能验证矩阵](验收/P5_普通功能验证报告_v1.0.md)
- [资源对照与回滚](验收/P5_资源对照与回滚记录_v1.0.md)
- [真实证据索引](验收/P5_证据索引_v1.0.md)
- [P0 assert 审查与处置](验收/P5_P0_assert只读复核与处置报告_v1.0.md)
- [P0 隔离 Mosquitto 实测](验收/P5_P0_隔离Mosquitto集成验证报告_v1.0.md)
- [P0 最新证据及资源](验收/P5_P0_证据与资源补充_v1.0.md)
- [已授权真机窗口：AT前置STOP及原Flash恢复](验收/P5_真机窗口预检STOP与恢复报告_20261008.md)
