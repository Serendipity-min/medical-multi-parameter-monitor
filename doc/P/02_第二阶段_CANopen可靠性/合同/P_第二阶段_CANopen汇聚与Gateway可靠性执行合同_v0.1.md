# P 第二阶段执行方案合同：CANopen 汇聚、Gateway 可靠性与真实节点接入准备

> **文件编号**：MPM-P-SOW-002  
> **版本**：v0.1  
> **日期**：2026-09-20  
> **负责人**：P  
> **上位合同**：《多参数监护仪_总开发合同与系统方案_v0.7》  
> **前置合同**：`MPM-P-SOW-001 v0.2`  
> **前置 PR**：#2 `dev/p-gateway-cloud-v07`  
> **阶段定位**：在第一阶段 MQTT/TLS → Broker → Backend → Web 已经打通的基础上，完成 **CANopen 标准协议落地、统一数据字典、Gateway-C CANopen Adapter、离线缓存骨架和真实 Node-A/B 接入准备**。A/B 实物未就绪时允许使用 CANopen 测试节点，不等待传感器。

---

# 1. 准入条件

开始第二阶段前应完成：

```text
[ ] PR #2 的 G0 旧方案冲突已修正
[ ] 部署脚本关键 assert 已改为显式检查
[ ] Broker 最低限度 error/warning 日志策略已确定
[ ] 最小 CI 已建立或形成明确实施记录
[ ] 第一阶段测试报告归档
```

24h 稳定性不要求作为第二阶段开始条件，但必须在最终系统验收前完成。

---

# 2. 第二阶段目标

本阶段完成后，Gateway-C 数据入口从：

```text
Synthetic Data
      ↓
Gateway Data Model
      ↓
MQTT
```

升级为：

```text
Node-A / Node-B
      ↓
CANopen
      ↓
Gateway-C
      ↓
统一数据模型
      ↓
MQTT/TLS
      ↓
Cloud / Web
```

A/B 尚未完成时：

```text
CANopen Test Node / Loopback
      ↓
Gateway-C
      ↓
MQTT/TLS
      ↓
Cloud / Web
```

---

# 3. 第二阶段 P 责任

P 主责：

- CANopenNode / STM32 CANopen 栈选型和版本冻结；
- Gateway-C CANopen 角色设计；
- CANopen Object Dictionary；
- PDO / SDO / NMT / Heartbeat / EMCY 使用边界；
- 项目统一生理参数数据字典；
- CANopen → Gateway Canonical Data Model；
- Canonical Data Model → MQTT Topic/Payload；
- Gateway 节点状态；
- Gateway 离线缓存骨架；
- Backend 对真实 LIVE 数据的兼容；
- 与 A/B 的接口联调合同；
- CANopen/MQTT 端到端测试；
- P 的 RR 数据接口预留。

A/B 不需要修改 P 的云端代码，只按冻结 OD/PDO 提供各自节点数据。

---

# 4. 数据字典 v1

本阶段建立一份简洁、可追踪的数据字典。

至少包含：

| 对象 | 来源 |
|---|---|
| PPG / SpO2 / PR | Node-A / AFE4490 |
| NIBP | Node-A / HKB-08 |
| TEMP | Node-B / GY-641V3 |
| ECG / HR / RESP_RAW | Node-B / ADS1292R |
| RR | P 算法，最终运行在 Node-B |
| NODE_STATUS | Node-A / Node-B |
| FAULT | Node-A / Node-B |
| GATEWAY_STATUS | Gateway-C |

每项只冻结：

- 名称；
- 单位；
- 数据类型；
- 来源；
- 有效性；
- 更新类别（波形/周期标量/事件）；
- CANopen OD 映射；
- MQTT Stream 映射。

---

# 5. CANopen 方案

## 5.1 角色

```text
Gateway-C
├── NMT 管理/汇聚
├── PDO Consumer
├── Heartbeat Consumer
├── EMCY Consumer
└── 必要时 SDO Client

Node-A / Node-B
├── NMT Device
├── PDO Producer
├── Heartbeat Producer
├── EMCY Producer
└── SDO Server
```

## 5.2 实施原则

优先使用成熟 CANopenNode / STM32 端口，不自行实现 CiA 301 核心协议。

本阶段形成：

```text
doc/P/CANopen_对象字典_v0.1.md
doc/P/CANopen_PDO映射_v0.1.md
```

总合同阶段没有写死的 Index/Sub-index/PDO，在本阶段结合吞吐和 A/B 接口需求后冻结。

---

# 6. Gateway-C 软件结构

第二阶段开始拆分现有阶段验证 `main.c`：

```text
CANopen Adapter
      ↓
Canonical Data Model
      ↓
Data Router
   ┌──┴──────────┐
   ↓             ↓
MQTT Publisher   Offline Buffer
```

网络层继续复用第一阶段：

```text
MQTT Client
      ↓
ESP8266 SSL Socket
```

CANopen 不得直接拼 MQTT JSON，必须先经过统一数据模型。

---

# 7. 离线缓存第二阶段范围

本阶段实现“骨架 + 可验证最小版本”，不要求最终容量优化。

至少完成：

- 写入队列；
- LIVE 与 REPLAY 标记；
- 网络断开后缓存；
- 网络恢复后实时优先；
- 历史低优先级补传；
- 序号/时间保留；
- 掉电恢复策略设计。

若板载 Flash 尚未最终确认，可先用 RAM/测试 Flash 验证状态机，实际 Flash 布局后续冻结。

---

# 8. MQTT 可靠性调整

第二阶段必须明确：

- Gateway Clean Session 策略；
- Backend MQTT Session 策略；
- QoS1 在 Backend/Broker 重启时的真实边界；
- Gateway 离线缓存作为最终可恢复数据的主要机制；
- Retain 只保存最新状态，不保存波形历史；
- REPLAY 不触发当前实时报警。

---

# 9. A/B 接口联调

A/B 未完成时：

- CAN loopback；
- 第二块 F407 测试 Node；
- 或 CANopen 测试工具。

A/B 完成后：

```text
Node-A
  ↓ PDO
Gateway-C

Node-B
  ↓ PDO
Gateway-C
```

验收必须覆盖：

- 只断 Node-A；
- 只断 Node-B；
- 两节点同时在线；
- Heartbeat 超时；
- EMCY；
- Gateway 重启；
- Node 重启；
- PDO 继续上云；
- MQTT 不因 CAN 错误永久阻塞。

---

# 10. RR 并行工作

P 的 RR 算法作为并行子任务：

```text
B 提供 RESP_RAW
      ↓
P Python Reference
      ↓
RR 算法验证
      ↓
C 实现
      ↓
Node-B
      ↓
CANopen RR Object
      ↓
Gateway / MQTT / Web
```

若 B 尚未提供真实 RESP_RAW，本阶段只冻结 RR 数据对象，不写成算法完成。

---

# 11. 第二阶段测试

至少包括：

- CANopen 栈启动；
- NMT；
- Heartbeat；
- TPDO/RPDO；
- SDO 基础访问；
- EMCY；
- 双节点；
- CAN 断线/恢复；
- Gateway 重启；
- MQTT Broker 重启；
- CANopen → MQTT 数据一致；
- LIVE / REPLAY；
- 缓存补传；
- 浏览器不因数据源从 MOCK 变 LIVE 而重构。

---

# 12. 时间建议

建议 **8～12 个工作日**，A/B 真机联调等待时间不计入 P 单独开发时间。

| 阶段 | 工作 |
|---|---|
| Day 1-2 | P1 审计整改、CI、维护基线 |
| Day 2-4 | CANopenNode 引入、Gateway 栈启动 |
| Day 4-5 | 数据字典 / OD / PDO |
| Day 5-6 | Canonical Data Model Adapter |
| Day 6-8 | 双测试节点 + MQTT 端到端 |
| Day 8-10 | 离线缓存骨架 / REPLAY |
| Day 10-12 | 故障注入、文档、阶段验收 |

---

# 13. 第二阶段交付物

```text
doc/P/
├── P_第二阶段_CANopen汇聚与Gateway可靠性执行合同_v0.1.md
├── MPM_统一数据字典_v0.1.md
├── CANopen_对象字典_v0.1.md
├── CANopen_PDO映射_v0.1.md
├── Gateway_离线缓存设计_v0.1.md
└── P_第二阶段测试报告.md

gateway/
├── canopen/
├── data_model/
├── mqtt/
└── storage/
```

---

# 14. 准出条件

```text
[ ] Gateway-C CANopen 栈可运行
[ ] 双节点/测试节点可同时接入
[ ] Heartbeat / NMT / EMCY 行为验证
[ ] PDO 数据进入统一数据模型
[ ] 同一数据模型正确发布 MQTT
[ ] Cloud/Web 不因协议替换而重构
[ ] Node-A/B 可独立上下线
[ ] Gateway 网络断开可缓存
[ ] 网络恢复后 LIVE 优先、REPLAY 补传
[ ] 数据字典/OD/PDO 文档冻结
[ ] 第二阶段测试报告完成
```

完成后进入“真实四模块全链路联调 + RR + 24h 稳定性”阶段。
