# A 成员 Node-A 开发执行合同 v0.1

> 文件编号：MPM-A-SOW-001  
> 版本：v0.1  
> 日期：2026-09-21  
> 负责人：A  
> 开发分支：`dev/node-a-v07`  
> 基线：`P4@44e3bdf74c1d503abefc992406700ea719ab346c`  
> 上位基线：《多参数监护仪_总开发合同与系统方案_v0.7》

## 1. 本阶段目标

完成 STM32F407-A 上的真实血氧 + 无创血压采集、本地双屏显示和 CANopen Node-A 输出，为后续三板实物联调提供真实 Node-A。

## 2. 责任范围

A 负责：
- AFE4490 Arduino：SPI + DRDY/控制、Red/IR、PPG、SpO2、PR；
- HKB-08：UART、SYS/DIA、测量结果有效性；
- Node-A 两块本地显示屏；
- CANopen Device Node-ID=1；
- Heartbeat、NMT、PDO Producer、EMCY、SDO Server；
- Node-A 测试、证据、文档和阶段验收。

A 不负责 Gateway-C、MQTT、云端、Backend、Web、Node-B 和 RR 算法。
旧 HKS 血氧 UART 方案仅作历史对比，不得重新作为当前运行路径。

## 3. 代码目录

新增实现默认放在：

```text
node_a/
├── app/
├── drivers/afe4490/
├── drivers/hkb08/
├── display/
├── canopen/
└── tests/
```

禁止把 Node-A 业务实现写入 `gateway/` 或 `cloud/`。

## 4. 开发顺序

1. 硬件只读核对：F407-A、AFE4490、HKB-08、双屏、CAN 收发器、BOOT0、供电/电平、实际引脚。
2. AFE4490 最小通信：SPI、DRDY、寄存器、连续 Red/IR。
3. PPG / SpO2 / PR：记录采样率、单位/缩放、validity、无信号行为和算法版本。
4. HKB-08：完成一次完整真实测量链；失败/过期不得继续显示旧值为新值。
5. 双屏显示：血氧模块与 NIBP 模块分别显示；显示层不得反向控制采集状态机。
6. CANopen：按现有数据字典/OD/PDO 接入 Node-ID 1。

## 5. CANopen 接口纪律

禁止 A 自行修改 Node-ID、OD Index/Sub-index、PDO COB-ID、位宽、单位、validity bit、synthetic 语义。
如现有接口不足，提交 `doc/A/A_CANopen接口变更申请.md`，由 P 统一评审。

当前至少输出：`PPG / SPO2 / PR / NIBP / NODE_STATUS / FAULT`。
真实数据 `synthetic=false`；测试数据 `synthetic=true`，不得混用。

## 6. 进度记录

每个里程碑更新 `doc/A/STATUS.md`，至少包含：日期、最新 Commit、已完成、正在做、硬件实测、测试结果、阻塞项、需要 P 决策的问题、下一步 3 项任务。

建议 Commit：
```text
docs(node-a): record hardware verification
feat(node-a): bring up afe4490 acquisition
feat(node-a): integrate spo2 and pulse-rate pipeline
feat(node-a): integrate hkb08 nibp
feat(node-a): add local dual-display output
feat(node-a): publish node-a data over canopen
test(node-a): add acceptance evidence
```

## 7. Git 规则

只在 `dev/node-a-v07` 开发。禁止直接 push `P4`/`main`、force push、重写共享历史、提交凭据或本机私有烧录配置。
P4 后续更新由 P 指定同步点后统一同步；不要自行追 UI 工作分支。

## 8. Security Gate

Security Gate 默认不扫描。只有 P 明确授权本次目标/模式后才运行 `$security-gate quick` 或 `$security-gate pr`。
只允许防御性 SAST、Secret、依赖、C 静态检查、固定内存回归和项目测试；禁止 Fuzzing、Exploit、公网目标扫描。Raw 结果留仓库外。

## 9. 准出条件

```text
[ ] AFE4490 实物通信与真实 Red/IR
[ ] PPG 真实波形
[ ] SpO2 / PR 有明确 validity
[ ] HKB-08 完成真实测量链
[ ] NIBP 失败/过期处理正确
[ ] 两块本地屏工作
[ ] Node-ID 1
[ ] Heartbeat / NMT / SDO / PDO / EMCY 可验证
[ ] synthetic / LIVE 不混淆
[ ] STATUS.md 与阶段验收报告完成
[ ] 按授权完成 Security Gate
```

## 10. 交付与合并

交付：`node_a/`、硬件核对记录、驱动与数据流程说明、阶段验收报告。
最终仅创建 `dev/node-a-v07 -> P4` Pull Request，不自动合并，由 P 统一审核。

本合同准出只代表 Node-A 独立真实采集 + 本地显示 + CANopen Device 完成，不代表三板 CAN、整机或临床可用。