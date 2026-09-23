# P 端云网关维护手册与工作流程 v1.1

> RUNBOOK/MAINTENANCE；适用基线：P4 `09695ff2023ef6fd8dadaf5ecd64268b384a9190`。旧 v1.0 为阶段历史，不再作为现行操作入口。本文只记录维护路径，不扩大测试或部署授权。

## 当前范围

Gateway 为 STM32F407 裸机 + Hardened Paho Embedded C/MQTT 3.1.1，ESP8266 AT/TLS；P2 只完成 CANopenNode 测试节点链路。Cloud 为 Broker/Backend/Web；Web 六页面为工程样机。真实 A/B、外部三板 CAN、RR、Flash 持久化、FreeRTOS、24 小时及 Release Security Gate 尚未验收。

## 接管与变更步骤

1. 在独立分支确认目标基线、工作树状态和对应合同；不得把历史合同描述改作当前实现。
2. 对 Gateway 改动，先定位 `gateway/mqtt/README.md`、`gateway/canopen/`、`gateway/third_party/paho-embedded-c/PATCHES.md`。第三方文件变更时核对 `upstream.json`、`patched.json` 及 `verify_paho_integrity.py`；检查允许编入固件的源文件。
3. 对 Cloud/Web 改动，先核对对应 README、接口、构建和浏览器回归。Web 当前为 Vite 7.3.5 + TypeScript + Vanilla DOM/Canvas/Hash Router。
4. 运行与改动相关的既有单元/构建/固定回归。Paho/CANopen 安全固定回归入口为 `gateway/canopen/run_security_regression.py`（ASan/UBSan）。Security Gate 只有在该轮明确授权时按其文档运行；不要把文档对齐当作扫描授权。
5. 保存可追溯的提交、测试摘要和验收记录；PR 合并由当前审核流程决定。部署前核对实际服务配置及回滚点。

## 运行观察与排障

先区分设备采集、MQTT 发布、Broker 接收、Backend 校验/WebSocket、浏览器渲染五段。`/health` 与 `/api/health` 只能反映对应服务状态，不能证明真实传感器和三板 CAN 已通过。检查日志时间、设备/节点状态、帧序号和 LIVE/REPLAY 标记，避免把重放或模拟数据当作实时真机数据。

Broker 与 Backend 的日志策略见 [运行日志与排障](运行日志与排障.md)：轮转 JSONL/服务日志保留用于追因，不记录 payload、令牌或密码。排查鉴权失败时只记录错误类别、相关时间与脱敏标识；凭据从本机私有配置/外部注入，不能粘入工单或仓库。连接故障按 DNS/TLS 时间与 CA、MQTT CONNACK、订阅/推送链路顺序缩小范围。

Web 冻结表示显示暂停，不表示停止接收；右上接收帧计数继续变化是预期行为。SessionHistory 仅保留当前浏览器会话的有界记录；CSV 是本地会话导出，不是服务端数据库或长期监护记录。切换数据源或断连按界面既有会话语义处理。

## 发布与回滚

发布前核对 Git SHA、配置来源、构建产物和当前分支；不要将私有凭据或主机地址写入脚本/文档。若回归失败，保留错误日志摘要和失败 SHA，退回上一个已验证产物并单独定位。涉及 Flash/RR/FreeRTOS 的后续功能应另立实施与验收，不通过本手册默认启用。

## 关联文档

[Gateway 接管手册 v1.1](../01_第一阶段_MQTT云端/合同/P_云网关实现原理_代码设计与维护接管手册_v1.1.md) · [P2 结项说明](../02_第二阶段_CANopen可靠性/验收/P_第二阶段_CANopen汇聚与Gateway可靠性结项说明_v0.2.md) · [MQTT/RTOS ADR](ADR_Gateway_MQTT客户端与FreeRTOS迁移路线_v0.1.md) · [P 文档入口](../README.md)。
