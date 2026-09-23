# P 文档导航与当前基线

更新于 2026-09-23。总需求仍以[最终总合同 v0.7](<../多参数监护仪_总开发合同与系统方案_v0.7 .md>)为准；**当前 P 集成基线**为 `P4@09695ff2023ef6fd8dadaf5ecd64268b384a9190`（[PR #4](https://github.com/Serendipity-min/medical-multi-parameter-monitor/pull/4) 已合并）。`main@50699048010c57ba10f8573461844c525b022a07` 是稳定历史主干；`dev/node-a-v07` 和 `dev/node-b-v07` 是 A/B 各自的开发分支。历史报告中的 `dev/p-gateway-cloud-v07`、`dev/p-web-ui-v07` 和旧 SHA 只描述当时的工作，不是当前系统基线。

| 分类 | 入口 | 当前结论 |
|---|---|---|
| CONTRACT | [第一阶段合同](01_第一阶段_MQTT云端/合同/P_第一阶段_GatewayC云端Web执行方案合同_v0.2.md)、[第二阶段合同](02_第二阶段_CANopen可靠性/合同/P_第二阶段_CANopen汇聚与Gateway可靠性执行合同_v0.1.md)、[UI v0.2](03_第三阶段_UI重构/合同/P_Web监护大屏_UI重构专项合同_v0.2.md) | 保留当时授权；v0.2 UI 记录 P4 最终实现 |
| ADR / DESIGN | [MQTT 与 RTOS 路线 ADR](90_维护/ADR_Gateway_MQTT客户端与FreeRTOS迁移路线_v0.1.md)、[第二阶段设计](02_第二阶段_CANopen可靠性/README.md) | 当前接口与未来候选明确分开 |
| RUNBOOK / MAINTENANCE | [云网关接管 v1.1](01_第一阶段_MQTT云端/合同/P_云网关实现原理_代码设计与维护接管手册_v1.1.md)、[统一维护手册 v1.1](90_维护/多参数监护仪_P端云网关维护手册与工作流程_v1.1.md) | P4 现行维护入口；v1.0 留作历史 |
| EVIDENCE / ACCEPTANCE | [第一阶段](01_第一阶段_MQTT云端/README.md)、[第二阶段结项](02_第二阶段_CANopen可靠性/验收/P_第二阶段_CANopen汇聚与Gateway可靠性结项说明_v0.2.md)、[六页 UI 验收](03_第三阶段_UI重构/验收/02_Stitch六页面最终替换与安全准出报告_2026-09-22.md)、[安全证据](90_维护/README.md) | 记录当时真实测试和未覆盖范围，不回填伪历史 |
| HISTORY | [99 历史](99_历史/README.md) | 被替代合同及 WSS 成果，仅供追溯 |

阶段状态：第一阶段 MQTT/Cloud 已完成；第二阶段在 **CANopen 测试节点和 Router** 范围内阶段准出；第三阶段完成 Vite 7.3.5 六页面工程样机 UI。Paho P4.1 安全整改与统一 Security Gate 已建立，PR #4 的最终 HEAD 取得条件通过，**不等于 release 或真实数据准出**。当前仍未完成真实 Node-A/B、外部三板 CAN、正式 RR 算法、Flash 持久缓存、FreeRTOS 迁移、24h 稳定性和 Release Security Gate。

A/B 文档继续归各自目录，总合同与全系统资料留在 `doc/` 根目录。[旧状态检索与分类](90_维护/P4_文档旧状态检索与分类_2026-09-23.md)说明哪些旧分支和旧 SHA 保留为历史证据。
