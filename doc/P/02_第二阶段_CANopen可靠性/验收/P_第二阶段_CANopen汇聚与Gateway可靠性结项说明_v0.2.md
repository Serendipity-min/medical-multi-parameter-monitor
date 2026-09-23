# 第二阶段 CANopen 汇聚与 Gateway 可靠性结项说明 v0.2

> 文档类型：EVIDENCE/ACCEPTANCE 的范围说明；对齐 P4 `09695ff2023ef6fd8dadaf5ecd64268b384a9190`。原 [执行合同 v0.1](../合同/P_第二阶段_CANopen汇聚与Gateway可靠性执行合同_v0.1.md) 与 [阶段测试报告](P_第二阶段测试报告.md) 保留当时事实。本文件只界定现有准出范围，不补造新测试结果。

## 已完成的 P 侧测试节点范围

CANopenNode 测试节点已覆盖 OD/PDO、NMT、Heartbeat、EMCY、SDO；Gateway 的 Canonical Model 与 Router 完成汇聚路径。当前有 32 帧 RAM 缓存与实时队列，LIVE 优先、断线后按协议 REPLAY；C→Backend 链路做过验证。F407 CAN1 静默环回和 ESP TLS 链路均有既有验收记录。具体断言、环境和证据以原阶段测试报告及代码为准。

上述结果仅说明 **测试节点/Router 的阶段准出**。环回测试没有覆盖外部 CAN 物理总线、三板同时工作或真实采样模块；软件队列与 RAM 缓存不能替代 Flash 持久缓存验证。

## 尚未完成的整机范围

真实 Node-A、真实 Node-B、三板外部 CAN、RR、Flash 持久缓存、FreeRTOS、24 小时稳定运行均未完成该阶段的实机验收。Release Security Gate 也属于后续最终 RC 条件。不得把本文件标题中的“结项”解读为上述功能已经交付或医疗级可靠性获证。

后续每项须在相应合同/计划中定义硬件配置、成功标准与证据，并按实际 SHA 留存测试记录。
