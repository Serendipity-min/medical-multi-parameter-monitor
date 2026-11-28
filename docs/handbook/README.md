# 维护手册（handbook）

本目录用于维护和回顾，讲清项目里“为什么这样做、具体在哪、坏了怎么查”。和其他文档的分工如下：

| 文档 | 回答什么 |
|---|---|
| `docs/acceptance/PROJECT-BOOK.md` | 系统是什么（完整技术说明，对外交付） |
| `docs/acceptance/CLOSEOUT-TECHNICAL-OVERVIEW.md` | 全貌：技术栈、流程图、传输图、协议、成果 |
| `docs/acceptance/ACCEPTANCE-REPORT.md` | 合同逐条结论与证据 |
| **本目录** | 设计理由、实现细节、问题档案、维护要点 |

## 篇目

| 编号 | 文档 | 状态 |
|---|---|---|
| 00 | 索引与阅读路线 | 待写（第三批） |
| 01 | [硬件与接线](01-HARDWARE-AND-WIRING.md) | 第二批 |
| 02 | [节点 A、D、E 固件](02-NODES-A-D-E.md) | 第二批 |
| 03 | [节点 B：采集链路与算法](03-NODE-B-ACQUISITION-AND-ALGORITHMS.md) | 第一批 |
| 04 | [CANopen 细节](04-CANOPEN-DETAILS.md) | 第二批 |
| 05 | [网关 C](05-GATEWAY-C.md) | 第二批 |
| 06 | 云端与网页 | 待写（第三批） |
| 07 | 构建、烧录与回滚 | 待写（第三批） |
| 08 | 测试与验收方法 | 待写（第三批） |
| 09 | [问题档案与排障速查](09-ISSUE-ARCHIVE.md) | 第一批 |
| 10 | [设计决策记录](10-DESIGN-DECISIONS.md) | 第一批 |
| 12 | [数字速查与项目时间线](12-NUMBERS-AND-TIMELINE.md) | 第一批 |

编号 11 留给另行保管的材料，不在仓库中。

## 写法约定

- **事实来源**：以冻结代码和 `node-b/docs/PI-REVIEW/` 的 R 轮记录为准，每个数字注明出处。
- **代码位置**：钉在提交 SHA 上（B 为 `65803a1`）。代码再改时，以函数名为准。
- **状态词**：与验收报告一致，即 PASS / FAIL / NOT_PASS（已接受）/ NOT_EVALUATED / NOT_RUN / UNKNOWN / OPEN。
- **不入库的内容**：凭据、硬件 UID、真实端点、IP、SSID、私有固件和志愿者原始数据。志愿者只写代号。
- **流程图**：一律纵向（`flowchart TB`），连线上标注接口和协议。
