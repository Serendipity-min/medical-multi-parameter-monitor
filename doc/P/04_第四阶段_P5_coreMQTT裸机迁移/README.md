# P5：裸机 coreMQTT v2.3.1 / MQTT 3.1.1

唯一合同：[正式 v1.0](../P5_coreMQTT裸机迁移正式执行合同_v1.0.md)。
本轮软件基线 `P4@8dee339`；实现及普通回归绑定代码提交 `505be8a9977997328e816761a3ca51cf9b7ce171`。
当前为 **P5_PENDING_HARDWARE_AND/OR_SECURITY**，附加隔离 Broker 和动态资源待测项。

软件迁移、ARM 构建、38 项 C 普通用例、6 项来源用例和既有功能回归通过。
正式真机准出、异常断连后 Will 的 Broker 行为、动态性能和统一 Security Gate 尚未完成。
用户另外授权本次 GitHub App 自动 Semgrep 检查；它与统一 Security Gate 的授权和准出分开记录。
P4/main、A/B、CANopen/Router/模型、Cloud 和历史证据未改；P6 未启动。

- [本轮重建的 P4 基线](baseline.md)
- [接口迁移与构建清单](设计/P5_接口迁移与构建清单_v1.0.md)
- [普通功能验证矩阵](验收/P5_普通功能验证报告_v1.0.md)
- [资源对照与回滚](验收/P5_资源对照与回滚记录_v1.0.md)
- [真实证据索引](验收/P5_证据索引_v1.0.md)
