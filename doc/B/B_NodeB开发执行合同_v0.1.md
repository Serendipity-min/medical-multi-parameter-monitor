# B 成员 Node-B 开发执行合同 v0.1

> 文件编号：MPM-B-SOW-001  
> 版本：v0.1  
> 日期：2026-09-21  
> 负责人：B  
> 开发分支：`dev/node-b-v07`  
> 基线：`P4@44e3bdf74c1d503abefc992406700ea719ab346c`  
> 上位基线：《多参数监护仪_总开发合同与系统方案_v0.7》

## 1. 本阶段目标

完成 STM32F407-B 上的真实 ECG/HR/RESP_RAW/TEMP 采集、本地双屏显示和 CANopen Node-B 输出，并向 P 提供真实 RESP_RAW 供 RR 算法验证。

## 2. 责任范围

B 负责：
- ADS1292R：SPI + DRDY/控制、ECG、HR、RESP_RAW；
- GY-641V3：I2C、TEMP；
- Node-B 两块本地显示屏；
- CANopen Device Node-ID=2；
- Heartbeat、NMT、PDO Producer、EMCY、SDO Server；
- 向 P 交付带采样率/时间戳/单位说明的真实 RESP_RAW；
- Node-B 测试、证据、文档和阶段验收。

B 不负责 Gateway-C、MQTT、云端、Backend、Web、Node-A 和 RR 算法设计。
RR 算法由 P 设计/验证；B 在 P 交付验证后的 C 实现后负责集成到 Node-B。

## 3. 代码目录

```text
node_b/
├── app/
├── drivers/ads1292r/
├── drivers/gy641v3/
├── display/
├── canopen/
├── rr_integration/
└── tests/
```

禁止把 Node-B 业务实现写入 `gateway/` 或 `cloud/`。

## 4. 开发顺序

1. 硬件只读核对：F407-B、ADS1292R、GY-641V3、双屏、CAN 收发器、BOOT0、供电/电平/实际引脚。
2. ADS1292R 最小驱动：SPI、DRDY、寄存器、连续 ECG/RESP 真实采样。
3. ECG / HR：记录 sample rate、单位、时间戳、滤波状态、validity；原始与滤波数据不得混写。
4. RESP_RAW：稳定输出真实呼吸阻抗原始数据，形成可交给 P 的数据文件与说明。
5. TEMP：真实采集、异常/通信失败/过期处理；不得保留旧值伪装实时。
6. 双屏显示：ECG/HR/RESP 与 TEMP/RR 状态分别显示。
7. CANopen：按现有数据字典/OD/PDO 接入 Node-ID 2。

P 未交付正式 RR 算法前，`RR validity=INVALID`，不得用固定测试值冒充真实 RR。

## 5. RR 协作

```text
B 真实 RESP_RAW
      ↓
P Python Reference
      ↓
算法验证
      ↓
P C 实现
      ↓
B 集成 Node-B
      ↓
CANopen RR
```

B 不需要等待 RR 才完成 ECG/RESP/TEMP 与其余 CANopen 对象。

## 6. CANopen 接口纪律

禁止 B 自行修改 Node-ID、OD Index/Sub-index、PDO COB-ID、位宽、单位、validity bit、synthetic 语义。
如真实 ADS1292R 暴露现有映射不足，提交 `doc/B/B_CANopen接口变更申请.md`，由 P 统一评审。

当前至少输出：`ECG / HR / RESP / TEMP / RR(reserved) / NODE_STATUS / FAULT`。
真实数据 `synthetic=false`；测试数据 `synthetic=true`。

## 7. 进度记录

每个里程碑更新 `doc/B/STATUS.md`，至少包含：日期、最新 Commit、已完成、正在做、硬件实测、测试结果、RESP_RAW 是否可交付、阻塞项、需要 P 决策的问题、下一步 3 项任务。

建议 Commit：
```text
docs(node-b): record hardware verification
feat(node-b): bring up ads1292r acquisition
feat(node-b): add ecg and heart-rate pipeline
feat(node-b): expose real respiration raw data
feat(node-b): integrate temperature module
feat(node-b): add local dual-display output
feat(node-b): publish node-b data over canopen
test(node-b): add acceptance evidence
```

## 8. Git 规则

只在 `dev/node-b-v07` 开发。禁止直接 push `P4`/`main`、force push、重写共享历史、提交凭据或本机私有烧录配置。
P4 更新由 P 指定同步点后统一同步；不要自行追 UI 工作分支。

## 9. Security Gate

Security Gate 默认不扫描。只有 P 明确授权本次目标/模式后才运行 `$security-gate quick` 或 `$security-gate pr`。
只允许防御性扫描和固定回归；禁止 Fuzzing、Exploit、公网目标扫描。Raw 结果保存在仓库外。

## 10. 准出条件

```text
[ ] ADS1292R 实物通信、DRDY、连续采样
[ ] 真实 ECG 波形与 HR
[ ] 真实 RESP_RAW 可持续输出并可交给 P
[ ] TEMP 真实采集与异常处理
[ ] 两块本地屏工作
[ ] RR 未完成时保持 INVALID
[ ] Node-ID 2
[ ] Heartbeat / NMT / SDO / PDO / EMCY 可验证
[ ] synthetic / LIVE 不混淆
[ ] STATUS.md 与阶段验收报告完成
[ ] 按授权完成 Security Gate
```

## 11. 交付与合并

交付：`node_b/`、硬件核对记录、驱动与数据流程说明、`B_RESP_RAW交付说明.md`、阶段验收报告。
最终仅创建 `dev/node-b-v07 -> P4` Pull Request，不自动合并，由 P 统一审核。

本合同准出只代表 Node-B 的 ECG/HR/RESP/TEMP、本地显示、CANopen Device 与 RR 原始输入准备完成，不代表 RR 算法、三板 CAN、整机或临床可用。