# 多参数生理监护仪样机｜P5 PR #6 专项收尾与分闸验收执行合同 v1.0

> 合同编号：MPM-P5-CLOSEOUT-SOW-001  
> 签发日期：2026-10-08  
> 适用仓库：[Serendipity-min/medical-multi-parameter-monitor](https://github.com/Serendipity-min/medical-multi-parameter-monitor)  
> 适用 PR：[Draft PR #6](https://github.com/Serendipity-min/medical-multi-parameter-monitor/pull/6)  
> **合同性质：P5 现有实施成果的补充收尾合同；不替代 P5 核心迁移正式合同 v1.0，不重启 P5，不签发 P6。**  
> **本合同当前授权：C0（只读核验）＋C1（只读审计／常规软件复测）＋C2（动态测量方案和非侵入工具准备）。其余全部 HOLD。**  
> 负责人逐阶段裁定；Codex 不得根据上一阶段 PASS 自行跨越授权关口。

---

## 0. 签发决议（最高优先级）

1. **停止新增 P5 功能。** Paho → coreMQTT v2.3.1 的软件迁移已经实施，保持 STM32F407 裸机、MQTT wire protocol 3.1.1、publish-only、ESP8266 AT/TLS、CANopen 测试节点、Canonical Model、Router、LIVE/REPLAY、Topic/Payload、Cloud/Web 不变。**禁止为补齐性能数据而重构主链路**。
2. 只围绕 **PR #6 的已知缺口**工作：H16 动态资源/延迟与 P4 对照、冷上电条件、项目级 assert 的真机可观察性、Security Gate 待授权与 CI 工作流校验失败、负责人最终验收。已有 B01/B02/B04 和隔离 Broker 合格证据应继承但不得扩张其覆盖范围。
3. 本次**只自动授权 C0/C1/C2**。硬件烧录、Flash 读写、J-Link 运行控制、断电重启、主动故障触发须在 C3 获得负责人**针对新窗口、新测试单的独立授权**。历史的 COM15/J-Link 可写窗口不可视为永久授权。
4. **统一 Security Gate 依旧未授权。** 不得自动运行 `doctor/quick/pr/release`、Semgrep 本地扫描、clang-tidy 安全项目扫描、Trivy、Gitleaks、ASan/UBSan、Fuzzing、公共目标验证。先前用户独立授权的 *Hosted Semgrep App* 检查成功不等于本次统一 Gate 授权。
5. **生产 Broker 故障注入 B03 未授权**：严禁停止、重启腾讯云 Broker、改变生产 ACL/TLS/服务配置或对公网注入测试流；使用既有隔离 Mosquitto 对照证据。若最终确需 B03，先提交独立测试申请；负责人也可书面裁定为 `WAIVED_FOR_P5`，但不得记 `PASS`。
6. **禁止在正常 F407 项目固件中主动制造 assert、HardFault 或看门狗事件。** C3 的 assert 路径只能在明确批准的受控独立诊断场景执行；没有授权则保持 `NOT_RUN`。
7. Git 操作仅针对 `P5-coremqtt-baremetal`：允许 C1/C2 在通过预检后，按本合同限定范围增补测试方案、诊断脚本与证据索引并提交/推送；**不允许直接写入 P4/main、force push、自动合并 PR、关闭 Draft、删除历史报告或删除共享/仓库外文件**。任何变更固件生产源码须另请负责人批准，不可由测试脚本顺手修复。
8. P5 与 Node-A/B/真实三板 CAN 集成可继续并行，但本收尾合同**不负责真实 A/B、三板外部 CAN、RR 算法、Flash 持久缓存、P6/FreeRTOS、MQTT5 或 GEC6818**。

> 总目标：先把 **“事实与待测项”唯一化**，再形成 **P4/P5 公平可复现的测量方案**，只在另获许可的硬件窗口测量，最后按单一准出表裁定。遇到 STOP 不要自行另起新分支、新项目或无限尝试。

## 1. 当前冻结事实（来自 2026-10-08 GitHub 实际核对）

| 项目 | 当前事实 |
|---|---|
| P4 HEAD | `8dee339491cfd4edc468bb9451511d421f26db5e` |
| main HEAD | `50699048010c57ba10f8573461844c525b022a07` |
| P5 branch | `P5-coremqtt-baremetal` |
| PR #6 HEAD | `ae6fecf8766b78224082673b5c3f0848778a3d96`，OPEN / DRAFT |
| 最后正式受测应用源码提交 | `e598fc63719acdf49a99c6da46c656dc8c607782`，后续文档提交须核对受测输入摘要确未变化 |
| 上游客户端 | `FreeRTOS/coreMQTT` `v2.3.1` / `2beef04725328923e05e576b884212d53ec97af7` |
| 软件等价验证 | C 42/42，来源完整性 6/6，隔离 Mosquitto 30/30，普通 PR CI SUCCESS |
| 真机验证 | B01、B02、B04 已有实际 PASS；真机为 CAN1 silent-loopback **双合成节点**，不是 A/B 真板 |
| 已测 Wi-Fi 恢复 | D 后 OFFLINE 27.375 s；首条有效业务数据 36.234 s；REPLAY 37.219 s；`lost=203` |
| 原程序恢复 | 原 1MiB Flash 双读/完整恢复/独立回读相同，SHA256 `852d7618f8fc46c80cbe035ebd41f4e21e4d5a76a26cf10a39e0600f7a89ffb8`；见原始报告 |
| 已测固件 | BIN 35552 B / SHA256 `fd81076b9b34ad0a8f4ee35c08cd7ea14704f6d7b04620741cdf083c9c6c1069` |
| 静态布局 | RAM 总布局 P4 120160 B、P5 120208 B（+48 B），P5 上限 131072 B |
| 当前缺口 | H16 CPU/Stack/CAN/最大 MQTT 等待/P4 真机对照；冷上电；assert 真机路径；统一 Security Gate；最终审查 |

**事实解释**：上表是所载 HEAD 的证据快照，不是对 Codex 本机、目标板当前状态的现场保证。Codex 必须在 C0 重新核对。历史第一次 Wi-Fi 25 秒观察超时、AT 前置 STOP，以及后续复测通过均必须保留原记录，不得改成“从未失败”。**合成双节点 `physical_nodes=false`、`real_patient_data=false`； `lost=203` 是缓存淘汰事实，不得描述为无损。**

### 1.1 优先读取的文件（按顺序）

1. `doc/P/P5_coreMQTT裸机迁移正式执行合同_v1.0.md`（原主合同、授权边界）
2. `doc/P/04_第四阶段_P5_coreMQTT裸机迁移/README.md`
3. `doc/P/04_第四阶段_P5_coreMQTT裸机迁移/验收/P5_证据索引_v1.0.md`
4. `.../验收/P5_普通功能验证报告_v1.0.md`、`.../验收/P5_P0_证据与资源补充_v1.0.md`、`.../验收/P5_资源对照与回滚记录_v1.0.md`
5. `.../验收/P5_真机合成Smoke与WiFi恢复报告_20261008.md`、`P5_ESP8266_AT独立复核报告_20261008.md`、`P5_真机窗口预检STOP与恢复报告_20261008.md`
6. `gateway/mqtt/{build.py,README.md,STM32F407ZGT6_FLASH.ld}`、`gateway/mqtt/src/{main.c,gateway_transport.c,mqtt_transport_adapter.c,platform.c,gateway_assert.c,heap.c}`
7. `gateway/mqtt/tests/`、`gateway/storage/router.c`、`gateway/canopen/tools/board_acceptance.py`
8. `doc/P/90_维护/多参数监护仪_P端云网关维护手册与工作流程_v1.1.md` 及 P5 CI、`.github/workflows/security-gate.yml` **只读**。

绝不能用 Windows 的 `E:/...` 路径当作 GitHub 可访问资源，也不能把仅存在于私有目录的 Flash dump、配置、证书、凭据复制入公开仓库。

---

## 2. 流程图与阶段闸门（不得跳步）

```text
C0  事实冻结与前置核验（只读）
 │ GO（或负责人书面裁定）
 ▼
C1  缺口审计 / 正常回归 / 代码与证据一致性检查（已授权）
 │ STOP：出现来源/代码/报告漂移；只汇报，不擅自修
 ▼
C2  H16 公平测量方案＋非侵入工具准备（已授权）
 │ ├── 假设、指标、脚本、风险/回滚审核
 │ └── C2_READY：STOP，等待负责人确认新硬件窗口
 ▼
C3  F407 P4/P5 对照、冷上电、受控 assert 诊断（未授权 / HOLD）
 │ 所有硬件步骤受独立授权、备份/恢复与故障窗口约束
 ▼
C4  统一 Security Gate 专项（未授权 / HOLD，须独立签发）
 │ 先解决工作流校验，再按指定模式执行；不能由 C1/C2触发
 ▼
C5  最终证据对账与提交负责人（只读整合可先准备；合并权保留）
 │ 审核和必要豁免均有明示记录
 ▼
负责人批准后另行决定：PR #6 Ready → Merge P4 → 后续 P6 签发
```

**C1/C2 的 Codex 应在发出 `P5_C2_READY` 后主动停止本轮，不得预占先前硬件授权。** 如 C0/C1 出现阻塞也应停，不做超出合同的“顺手修好”。

---

## 3. 目标文件树与变更白名单

以下 `[E]` 表示已有路径、`[N]` 表示拟新增、`[U]` 表示允许追加导航/当前结论。**不要求机械新建所有文件**：以同一类证据只存一份为原则，先检查是否已存在等价材料；有则直接复用。

```text
doc/P/
├─ P5_coreMQTT裸机迁移正式执行合同_v1.0.md                       [E] 原合同，不覆盖
├─ 04_第四阶段_P5_coreMQTT裸机迁移/
│  ├─ README.md                                                 [U] 仅更新当前状态/导航
│  ├─ baseline.md                                               [E] 保持历史冻结
│  ├─ 合同/
│  │  └─ P5_PR6_专项收尾与分闸验收执行合同_v1.0.md                 [N] 本合同
│  ├─ 设计/
│  │  ├─ P5_接口迁移与构建清单_v1.0.md                            [E] 现有
│  │  └─ P5_H16动态资源与P4对照测量计划_v1.0.md                   [N] C2交付
│  └─ 验收/
│     ├─ P5_真机合成Smoke与WiFi恢复报告_20261008.md               [E] 禁止改写
│     ├─ P5_ESP8266_AT独立复核报告_20261008.md                    [E] 禁止改写
│     ├─ P5_真机窗口预检STOP与恢复报告_20261008.md                [E] 禁止改写
│     ├─ P5_P0_隔离Mosquitto集成验证报告_v1.0.md                 [E] 禁止改写
│     ├─ P5_证据索引_v1.0.md                                     [U] 仅追加新证据/新状态
│     ├─ P5_C1_证据一致性审计与阻塞清单_v1.0.md                   [N] C1交付
│     ├─ P5_C3_动态性能与冷启动验收报告_v1.0.md                   [N] 仅C3获授权且真实执行后创建
│     ├─ P5_C4_统一安全门准出报告_v1.0.md                         [N] 仅C4获授权执行后创建
│     ├─ P5_最终准出裁定单_v1.0.md                                [N] C5草案，负责人最终签署
│     └─ evidence/
│        ├─ hardware-smoke-wifi-20261008.json                    [E] 原封保存
│        ├─ p0-broker-summary.json / p0-resources.json          [E] 原封保存
│        ├─ c1-audit-manifest.json                               [N] C1只读证据摘要
│        └─ c3-measurement-summary.json                         [N] 仅C3获授权后写入
├─ README.md                                                    [U] 更新阶段导航须轻量

gateway/mqtt/
├─ src/{gateway_transport.c,mqtt_transport_adapter.c,platform.c,gateway_assert.c}
│                                                                 [E] C1/C2默认只读，生产代码不得修改
├─ tests/                                                        [E] 允许复用普通测试
│  └─ measurement/                                                [N] 仅必要时新增**脱机**解析/审查脚本
└─ build/                                                        [IGNORED] 编译和测量中间文件，不提交

.github/workflows/security-gate.yml                             [E] C1只读；本合同不授权改写或运行
```

C1/C2 **允许写**：本合同在 P5 分支的归档副本、C1 审计报告/manifest、C2 测量计划、纯脱机数据解析器/演示夹具、阶段 README/索引的追加更新。**默认禁止写** `gateway/mqtt/src/**`、`gateway/canopen/**`、`gateway/storage/**`、`cloud/**`、`gateway/third_party/**`、链接脚本、ESP 固件、`.github/workflows/**`。一旦必须修改生产源码或工具链，写 `CHANGE_REQUEST`，等待负责人批准及新的受测 SHA/回归策略。

仓库外：原始 Flash dump、私有 Wi-Fi/MQTT JSON、J-Link 临时烧录脚本、未脱敏串口记录、物理诊断私有日志继续在原私有目录保管。**不得移动、删除、改写，也不要求执行受策略拒绝的清理。**

---

## 4. C0：一轮只读 PRECHECK（现已授权）

只允许执行以下不修改 Git/硬件/生产服务的命令或等价只读命令：

```bash
git status --short
git branch --show-current
git rev-parse HEAD
git rev-parse origin/P4
git rev-parse origin/main
git log --oneline -n 12
git diff --name-status origin/P4...HEAD
```

可使用 `git ls-remote origin P4 P5-coremqtt-baremetal main` 只读校验远端；如果本地远端跟踪引用过期，可 `git fetch --prune`（只更新本地远端引用，不更改工作树），并保留抓取前后的状态。

**阻断规则**：

- 当前工作树有未提交文件：先列明归属，不覆盖、清理或暂存，不自动切换分支。可改用已有干净 P5 worktree；没有则 STOP 并报告。
- P4 SHA 或 P5 HEAD 与第1节不一致：报告最新 SHA、对比差异和提交来源；**以当前 Git 为事实**，不得盲目 `reset --hard` 或覆盖历史。
- 如无法证明真机报告对应 ELF/BIN 等于 `e598fc6` 受测输入，判 `SOURCE_IDENTITY_UNVERIFIED`，不复用该报告作为当前新固件验证。
- 允许远端 P5 领先当前快照，但必须重新核对改动是否仅限文档；存在生产代码变化即 STOP，重新决定是否需要重跑 B01/B02/H16。

**C0 唯一输出**：`P5_C0_PRECHECK`，包含 `HEAD/P4/main`、工作树、最近代码 SHA、对应 BIN SHA、已验证证据、阻塞项、`GO/STOP`。仅当 `GO` 才做 C1。

## 5. C1：一致性审计与普通软件复测（现已授权）

执行**一次**、按下表给出证据。不是再做一轮全项目重构。

| ID | 动作 | 必须产出 | PASS 定义 |
|---|---|---|---|
| C1-01 | 校验当前 HEAD 与最后软件提交之间的固件相关文件实际 diff、输入 SHA | `source_identity` 矩阵 | 若只变文档/证据则先前 B01/B02/P0 测试可继承；否则 STOP |
| C1-02 | 对已有真机记录核对 UID、BIN hash、双读/回读 hash、来源标记、时间轴 | B01/B02/B04 证据映射 | 只能核对已有证据，不伪造或重跑 |
| C1-03 | 核对旧 AT STOP→24/24 复核→B01/B02 两轮历史时间线 | 失败/通过并存的冲突表 | 首轮 Wi-Fi 25s 超时必须仍在报告中 |
| C1-04 | 复核资源记录 P4/P5 相同工具链/链接范围 | 静态资源表 | `P4=120160`、`P5=120208` 仅在输入同一性证实后继承 |
| C1-05 | 只读检查 assert 标志/输出/WFI 编译与已完成 host 测试 | `ASSERT_HOST_PASS_HARDWARE_PENDING` | 不将4个 host 用例写成真机 assert PASS |
| C1-06 | 审计现有 `B03 NOT_RUN`、Gate `jobs=[]`、清理 `BLOCKED` 各自影响 | `waiver_requests` | 只归类，不擅自豁免、不自动重跑 |
| C1-07 | 可执行必要常规 host/ARM/CAN/Backend 构建回归（本机工具就绪时） | 真实命令、exit code、输出摘要、输入hash | 缺工具则 `BLOCKED`；禁止安装新系统工具/跑安全门 |

**正常测试推荐入口**（必须先检查运行条件、禁用硬件/外网参数）：

```bash
python gateway/third_party/verify_coremqtt_integrity.py
python gateway/mqtt/tests/run_p5_host_tests.py
python -m unittest discover -s gateway/mqtt/tests -p 'test_p5_integrity.py'
python gateway/canopen/build_host.py
python gateway/canopen/tools/check_canonical.py
python -m pytest cloud/backend/tests -q
python gateway/mqtt/build.py
```

以上是普通构建/功能回归，不包含 `gateway/canopen/run_security_regression.py`、Unified Security Gate，**也不包括联网 Broker 集成工具或任何 `board_acceptance.py` 真机命令**。已有隔离 Mosquitto 30/30 不因这里未重跑而失效；确有必要重跑时须确认本机已核验且绑定 loopback 的运行时、无生产目标，不得因工具缺失下载/安装系统软件。

C1 审计报告应只引用已存在真实源，特别区分 GitHub 证据与仓库外证据；对源输入不完整处写 `UNVERIFIED`。若无新问题直接 C1 PASS，不许无意义重复重构。

### C1 必须回答的五个关键问题

1. 文档 HEAD `ae6fecf...` 与受测源码 `e598fc6...` 是否存在**任何**固件/构建/CAN/Router/Backend 逻辑漂移？
2. 本轮固件 BIN 35552 B 的 SHA，是否与真机烧录记录及回滚证据相同？
3. 32 帧 RAM 缓存、`lost=203`、LIVE 先于 REPLAY 是否准确呈现，不把成功首帧当作缓存完全排空？
4. 原 assert 的 host 软件证据与未测真机路径是否明确区分？
5. Security Gate 的 `jobs=[]` 是“未启动”而非“安全扫描 FAIL”；暂存包拒绝删除是独立运维事项而非 P5 MQTT 失败，是否正确分类？

输出必须是 `P5_C1_AUDIT`（PASS / ISSUE / BLOCKED），并关联 exact commit 和依据路径。

---

## 6. C2：H16 测量方案与工具准备（现已授权；**不得操作真机**）

### 6.1 测量变量与可比性原则

必须拟定两套固件：

- **P4 对照**：固定 `8dee339491cfd4edc468bb9451511d421f26db5e`、Hardened Paho、相同板卡/配置/工具链；P4 构建产物必须有自己的 SHA。
- **P5 目标**：固定最后已验证的 P5 生产源码输入和 BIN SHA；若为了诊断另外编译测量版，必须提供原始生产版与测量版的 diff、hash、插桩开销说明，**不可把测量版误写为已验收生产版**。

使用同一块 STM32F407、同一 ESP8266、同一供电/AP/2.4 GHz Wi-Fi、Broker/时间/CA/权限、相同测试数据和负载、相同串口/J-Link观察方式，记录环境漂移。CAN1 silent loopback 只测**同一类合成 CAN 协作链路**，不等于三板外部 CAN 性能。

### 6.2 H16 度量定义（不得用固定延时掩盖差异）

| 指标 | 采样起点→终点 | 要求 | 例外/边界 |
|---|---|---|---|
| M01 最大单次 MQTT 前台阻塞 | 进入 `gateway_mqtt_open/publish/yield` → 返回 | 单次最大、分布摘要、失败/成功分类 | 不可用仅带 5s 合成时钟的 host 单测代替 |
| M02 CAN 协作服务延迟 | 调度计划到期或 CAN 已有输入 → `mp_bus_poll`/采集服务完成 | 同条件 P4/P5 最大/分位；队列 overflow/drop | 计时方案和中断时延须区分；不得称外部三板数据 |
| M03 CPU 开销 | 以相同业务帧的 `MQTT_Publish`、ProcessLoop 路径为分段 | 使用 DWT CYCCNT 或等价可靠计数器测 cycles/帧、窗口占用 | 裸机 busy-poll 下“CPU 使用率100%”无辨识力；计数器回绕和插桩开销需控制 |
| M04 Stack 高水位 | 相同 workload/可安全观测区 → 最高消耗点 | 记录测量手段、最小剩余、安全界 | 禁止向正在使用的栈填哨兵、覆盖 ISR 栈/向量/配置；不可用 ELF 预留 8KiB 冒充实测 |
| M05 Heap 边界 | 当前 `_sbrk` 高水位与预留 24KiB | 比对峰值、余量与失败返回 | newlib/CANopen 初始化占用要纳入；不允许改为无界堆 |
| M06 网络阶段重连 | Wi-Fi恢复开始→TLS连接→MQTT CONNACK→首条 `VALID MOCK` 业务帧 | 各段时刻、端到端总长、3轮重复或书面说明缺失 | `D→首帧 36.234s` 内含固定 30s Wi-Fi停顿，不能作为单独重连性能 |
| M07 缓存行为 | 故障前→恢复窗口→回放终点 | `cache/lost/replay/drop` 以及 LIVE/REPLAY顺序 | 32帧缓存可能淘汰，不承诺无损；未观察至排空则注明 |

C2 **先判断测量工具是否可用**。如本机/板端无法非侵入观测，不得为了交数值而扩大固件范围；提出最小测量插桩 diff、可逆部署和对 P4/P5 相同处理的方案，等负责人签字后再实施。特别注意 DWT 循环计数为有限位宽，必须考虑频率、回绕、校准和取样周期；主机 Windows 计时分辨率不能替代 MCU 周期级指标。

### 6.3 比较统计与准出规则

- 计划每个固件至少 **3 个有明确起止标记的有效样本**。若无法重复三次，必须 `INSUFFICIENT_SAMPLES` 并解释，不能编造中位数和 p95。
- 保存每轮 raw observation、有效性、异常/丢样、总线/网络重连阶段、相同的测试设置和固件 SHA。少量样本优先报告逐次和 min/median/max，不要用不稳定的分位数制造精度。
- 原 P5 合同中**相对 P4 重连退化 >20% 的评审界线**：仅针对**同口径、可比较的真实网络重连阶段**计算 `(P5-P4)/P4`；若无法测量，则 `NOT_COMPARABLE`，不得依据 36.234s 直接宣告通过。
- **静态 RAM**当前 +48 B 是已有事实，不代表动态栈余量达标；单次阻塞/CAN 延迟若造成实时采集缺口，必须判需审核，不得仅靠 CPU 低占用“通过”。
- 已有 42/42 + 6/6 + 30/30 与 B01/B02/B04 原证据无需为了 C2 再全部运行。C2 只设计/检查测量工具，不真正生成新的真机性能数值。

### 6.4 工具链与策略

可生成**纯离线解析脚本**（仅接受脱敏合成示例输入）和 `measurement-plan.md`，包括计时点、命令建议、采样次数、失败分类、导出 JSON schema、回滚流程。不得向设备写入程序，不得通过 COM15 发送 D/A/B/R/G/E，不得重新启动 Broker，不得提前创建带 `PASS` 的测量报告。

C2 完成后只输出：`P5_C2_READY`，列“需要负责人批准的具体硬件动作清单、预计次数、终止恢复路径、是否需要生产源码插桩、不能测量的风险”；**然后暂停。**

---

## 7. C3：真机动态对照与有限故障验证（HOLD，须独立授权）

> 这一节只是**下次新硬件窗口的操作合同候选**。**没有负责人明确回复 `授权 C3 硬件窗口` 并确认测试单与现场条件之前，Codex 不得执行本节任何写操作。**

### 7.1 窗口申请单（必须事前汇报）

```text
P5_C3_HARDWARE_AUTH_REQUEST
BOARD              = STM32F407 / 历史UID待现场比对
CONNECTION         = COM15 / J-Link (现场复核)
P4_BIN_SHA         = <冻结后再填>
P5_BIN_SHA         = fd81076b9b34ad0a8f4ee35c08cd7ea14704f6d7b04620741cdf083c9c6c1069
TESTS              = M01...M07 / cold-boot / assert(若单独批准)
WRITE_LIST         = <明确每个 Flash扇区、诊断版/生产版及配置范围>
CREDENTIALS        = existing private only; NO PRINT/UPLOAD
BROKER_ACTION      = NO / local observer only
PRE_BACKUP         = full 1MiB double-read SHA match required
ROLLBACK           = full 1MiB restored, verifybin + independent readback
STOP_ON_FAILURE    = yes
USER_APPROVAL      = PENDING
```

冷断电涉及板子/ESP8266 状态和实验接线，必须由现场人员确认供电、接线与安全。不可由 Codex 随意切换设备电源或复用历史复位假设。

### 7.2 仅在获授权后按此顺序

1. **硬件身份与环境**：设备 UID/芯片型号/Flash 容量/电压、COM15/J-Link、ESP AT/证书状态，记录测试仪表/版本/网络条件；不得用旧记录替代当前检测。
2. **原程序全片备份**：烧录任何固件前，**双读 1,048,576 字节并逐字节一致**，SHA 归档在仓库外；必须与预期原程序/配置确认。不同则 `STOP`。
3. **只读或最小安全测量**：先决定是否可通过 SWD/现有日志获得指标。若测量需插桩、写配置或更换程序，确认独立测量 BIN、程序与配置 sector7 的范围和恢复步骤；不可自动生成新生产固件。
4. **P4 真机对照**：经批准安装冻结 P4 产物，按 C2 同一脚本/同一网络条件测 M01–M07，保存每轮完整时间轴。禁止改 P4 历史提交。
5. **P5 真机测量**：安装冻结 P5 产物，保持测试变量相同，得到同口径数据。若无法交叉比较则标 `NOT_COMPARABLE` 并说明环境差异。
6. **冷上电**（若明确批准）：在指定时刻完全断电/重上电，观察正常启动、AT→TLS→MQTT→首帧及服务恢复。**J-Link reset-halt 或 UART 重启不等于冷上电。**
7. **assert 真机**（单项特别授权）：只允许独立受控诊断固件/隔离场景，不允许用生产云端 MQTT、真实传感器或实际人体数据触发；确认 `GW ASSERT_FATAL` 最佳努力串口输出、RAM latch、停机终点，随后完整恢复。无法保持隔离则 `NOT_RUN`。
8. **完整恢复**：退出 ESP 暂态，验证原 ESP 模式/STORE（仅依据实际查询能证实的项）；完整恢复原 1MiB Flash（含 `0x080E0000` sector7），VerifyBin + 独立回读字节比对；恢复后 `DMA_ADC` 被动观察。需要断电验原程序时须有单项授权。

### 7.3 任何时刻立即 STOP

- UID/双读/hash/工具状态不匹配；J-Link 目标状态不明；上电/接线/供电异常。
- 密钥、私有配置可能被打印或外传；运行时无法保证原 Flash 可恢复。
- 普通合成源未经确认变成非合成/真实人体数据，或波形/缓存证据漂移。
- 生产 Broker 被意外接入故障测试、CAN 中断丢失/阻塞异常、断言终止出现在非诊断场景。
- 恢复任一步未达到双重验证；**先保留证据、尝试已授权的恢复流程，报告失败，不继续测下一固件**。

C3 最终应输出 `P5_C3_MEASURED` 或 `P5_C3_STOP`。未授权则始终 `P5_C3_NOT_AUTHORIZED`，不填写性能数值。

---

## 8. C4：统一 Security Gate（HOLD；另签合同/授权）

1. GitHub 现有 `.github/workflows/security-gate.yml` 有过**工作流校验 FAILURE / jobs=[]** 的记录。这不是正式扫描结果；不得写成 PASS，也不得写成已发现 CVE。
2. C1 允许**只读**查找可能的 workflow YAML/Actions 问题、记录触发上下文和官方日志。**不得在 C1/C2 修复工作流、触发 workflow_dispatch 或扫描**。
3. 如需修复该 workflow：Codex 提交 `P5_SECURITY_WORKFLOW_CHANGE_REQUEST`，列最小 diff、是否触及其它分支/保护策略、普通 YAML 语法检查建议；等负责人对变更和独立 Gate 模式分别授权。
4. 负责人指定 `doctor/quick/pr/release`、目标 HEAD、仓库范围及是否需要本地/托管工具时，才允许执行相应门禁；外网主动扫描、ZAP、Fuzzing 等依各自独立许可，不随一般 Gate 自动扩大。
5. Hosted Semgrep App 在 `ae6fecf...` 的 SUCCESS 只保留为**独立检查证据**，不可作为统一 Gate 的替代物或以旧 SHA 的结论套用新 HEAD。

**C4 未执行时**：`SECURITY_GATE=NOT_AUTHORIZED/NOT_RUN`；**C4 工作流语法失败时**：`INFRA_FAIL/NO_SCAN`；**实际已启动并成功/失败时**：需提供精确 SHA 与 runner 结果，不能混淆。

---

## 9. B03、暂存清理与未完成事项裁定（不允许反复试错）

| 项 | 本轮分类 | 推荐处理 |
|---|---|---|
| B03 生产 Broker 停止/重启 | `NOT_AUTHORIZED/NOT_RUN` | 已有隔离 Broker 30/30 + 真机 Wi-Fi 故障及真实 LWT；为避免影响服务，**建议申请 `WAIVED_FOR_P5`，由负责人书面裁定**；不同意豁免时再申请独立测试窗口 |
| Debian 6 包精确删除被策略拒绝 | `BLOCKED_BY_POLICY` | 保持原私有/暂存位置，不再重试越权命令；另列运维清理单，**不作为 MQTT 软件功能失败**；不要伪造已删除 |
| 首次 25s OFFLINE 观察超时 | `HISTORICAL_FAIL_RETAINED` | 第二轮 60s 覆盖通过；保持原始失败与修正依据，不删除不重写 |
| 32 帧缓存 `lost=203` | `EXPECTED_BOUNDED_LOSS_OBSERVED` | 属有界 RAM 机制，已丢弃必须保留；可在 P6/独立存储阶段再谈优化，不在 P5 扩大范围 |
| 工作流校验 `jobs=[]` | `INFRA_FAIL_NO_SCAN` | 单独申请修复和 Gate 执行，不重复 push 试图撞绿灯 |
| A/B 与外部三板 CAN | `OUT_OF_SCOPE` | 允许并行，但不在 P5 验收中写 PASS |

任何需要豁免的关键准出项，必须有人类负责人在裁定单签字。Codex 只能提出 `WAIVER_REQUESTED`，不能自行决定 `WAIVED`。

---

## 10. C5：最终准出表（Codex 只能提交候选，负责人最终决策）

| 检查 | 必须满足的结论 | 当前状态 |
|---|---|---|
| 版本/协议 | coreMQTT v2.3.1、裸机、MQTT 3.1.1、publish-only | 已有证据 PASS |
| 固定来源与构建 | SHA/白名单与 ARM 构建可复核，生产源码未漂移 | 已有证据 PASS，C1 重核对 |
| QoS1 ACK / LIVE-REPLAY | 真实 PUBACK 匹配、等价失败回存，不宣称无损 | Host/Broker 与真机证据 PASS，界限保留 |
| 隔离 Broker | P4/P5 30项正常/Will/retain/保活/故障对照 | PASS |
| B01/B02/B04 | 合成真机/断网恢复/原片恢复 | PASS，须保持原证据身份 |
| H16 动态指标与 P4 对照 | 可比的 CPU/Stack/CAN/阻塞/重连或经审核的真实 `NOT_MEASURED` 原因与明确拒绝准出 | PENDING |
| 冷上电 | 真机明确条件下测试，或负责人接受带限制准出 | PENDING |
| assert 硬件路径 | 受控真机观测，或负责人接受独立诊断不执行并注明风险 | PENDING |
| B03 生产故障 | PASS 或负责人签字 `WAIVED_FOR_P5` | NOT_AUTHORIZED |
| Security Gate | 单独授权并按指定模式实际运行且无新 blocker；未授权不可冒充通过 | NOT_AUTHORIZED |
| P4/main、历史证据完整 | 只向 P5 分支提交新证据，无擅自 Merge/历史篡改 | 当前满足，结束前重核 |
| 最终人类决议 | 项目负责人审查全部阻塞、豁免、测试身份证并明确允许 Merge | 未批准 |

**判定规则**：

- `P5_C1_C2_READY`：仅说明收尾方案已准备完，不意味着动态性能通过。
- `P5_PENDING_HARDWARE_AND_SECURITY`：硬件新窗口和统一 Gate 未授权/未准出。
- `P5_ACCEPTANCE_CANDIDATE`：所有必需项获证据或有负责人书面豁免，Gate 已实际通过；**仍不得自动合并**。
- `P5_RELEASED_TO_P4`：只有负责人明确签字、PR #6 真正合并后才能写此状态。
- `P6_READY_FOR_SIGNING`：P5 已正式合并后的最新 P4 且 P6 独立合同准备就绪；本合同不授权启动 P6。

历史未完成项不得一并改写为 PASS。若 C3 需要改生产代码，旧测试绑定被破坏，必须执行增量复核和必要的再次真机/安全准出，否则不能候选合并。

---

## 11. Git 提交、报告与回滚规则

- 只在干净 `P5-coremqtt-baremetal` worktree 写 C1/C2 允许路径；其他 worktree 的未提交文件不得碰。
- C1/C2 软件收尾最多分为 **两次逻辑提交**：`docs(p5): reconcile acceptance evidence and blockers`；`docs(p5): prepare H16 baseline comparison plan`（若纯脱机脚本则可独立一个 `test(p5): add offline measurement parser`）。不要每修一个 Markdown 链接就 push 一次。
- 每个提交前 `git diff --check`、检查 diff 限定白名单、核验敏感文件未被 stage；没有改动则不生成空提交。
- 本合同签发后，如需将本文件加入仓库，放 `doc/P/04_第四阶段_P5_coreMQTT裸机迁移/合同/`，并在同一 C1/C2 文档提交中归档；不要修改历史 v1.0 主合同。
- 如 C1 发现版本漂移或异常，**不允许**用 `git reset --hard`、自动 cherry-pick、rebase/force push 解决；保留 P5 原基线报告并汇报。
- 被忽略的固件 BIN/ELF/map 与全片备份只在本地管理，不公开上传。文档证据只写摘要、计数、散列、符号和脱敏时间戳。
- PR #6 保持 Draft；可以追加 C1/C2 状态回执（无需大量重复评论），**不请求合并、不标 Ready、不开始 P6**。

## 12. Codex 标准汇报模板（每个 Gate 恰好一份）

### C0 只读预检

```ini
P5_C0_PRECHECK
BRANCH                  =
HEAD                    =
ORIGIN_P4_SHA           =
ORIGIN_MAIN_SHA         =
SOURCE_COMMIT           =
SOURCE_MATCH            = YES/NO/UNVERIFIED
WORKTREE                = CLEAN/DIRTY
UNCOMMITTED_FILES       =
PR6_DRAFT               = YES/NO
GO_NO_GO                = GO/STOP
BLOCKERS                =
```

### C1 审计

```ini
P5_C1_AUDIT
SOURCE_IDENTITY          = PASS/ISSUE/UNVERIFIED
HISTORICAL_EVIDENCE      = PASS/ISSUE
STATIC_RESOURCE_CHECK    = PASS/ISSUE
ASSERT_HOST_PATH         = PASS/ISSUE (HARDWARE NOT_RUN)
BROKER_B03               = NOT_AUTHORIZED / WAIVER_REQUESTED
SECURITY_GATE            = NOT_AUTHORIZED/NOT_RUN
WORKFLOW_VALIDATION      = INFRA_FAIL_NO_SCAN / <真实新证据>
C1_RESULT                = PASS/ISSUE/BLOCKED
REPORT                   = <repo relative path>
```

### C2 待授权测量计划

```ini
P5_C2_READY
P4_MEASURE_BASELINE      = <SHA and BIN hash or BLOCKED>
P5_MEASURE_BASELINE      = <SHA and BIN hash>
MEASUREMENT_PLAN         = <repo relative path>
INSTRUMENTATION_NEEDED   = YES/NO/UNKNOWN
REQUIRES_SOURCE_CHANGE   = YES/NO
COLD_POWER_CYCLE         = HOLD
ASSERT_HARDWARE          = HOLD
FLASH_WRITE              = HOLD
SECURITY_GATE            = HOLD
B03_PRODUCTION_BROKER    = HOLD
NEXT_REQUIRED_APPROVAL   = <precise actions>
STATUS                   = WAIT_USER_AUTHORIZATION
```

### C3 / C4 完成后（另行授权，非本轮自动执行）

```ini
P5_CLOSEOUT_REPORT
HEAD / TESTED_SOURCE / BIN_SHA256 =
C0/C1/C2                 =
C3_HARDWARE              = PASS/FAIL/NOT_RUN/BLOCKED
M01..M07                 = <actual values / NOT_MEASURED>
COLD_BOOT                = PASS/FAIL/NOT_RUN
ASSERT_REAL_HW           = PASS/FAIL/NOT_RUN
FULL_FLASH_RESTORE       = PASS/FAIL/NOT_RUN (current window only)
SECURITY_GATE            = PASS/FAIL/NOT_AUTHORIZED/INFRA_FAIL
B03                      = PASS/WAIVED_FOR_P5/NOT_AUTHORIZED
DRAFT_PR_6               = OPEN/DRAFT
MERGED_TO_P4             = NO
P6_STARTED               = NO
FINAL_VERDICT            = HOLD / ACCEPTANCE_CANDIDATE
BLOCKERS                 =
```

---

## 13. 本次给 Codex 的首条执行指令（可直接复制）

> **只授权合同的 C0、C1、C2；不得自行进入 C3/C4/C5 的写入或执行部分。** 读取本文件与 `doc/P/P5_coreMQTT裸机迁移正式执行合同_v1.0.md`、PR #6 现有报告，以 P5 当前远端 HEAD 为事实。先输出 `P5_C0_PRECHECK`；GO 后核对既有证据和代码 SHA，不重做已验收 P0/真机工作，形成 C1 单一缺口审计；接着只准备 H16 同条件 P4/P5 真机对照的 C2 测量计划、必要的纯脱机工具，并按白名单最多做两次文档/测试工具逻辑提交，推送原 P5 分支。输出 `P5_C1_AUDIT` 和 `P5_C2_READY` 后**立刻停止**，等待我对 COM15/J-Link、Flash 写入、冷断电、assert、生产 Broker、统一 Security Gate 的分别授权。本轮不得进行新的固件烧写、断网故障注入、安全扫描、PR 合并或 P6 开发。遇到任何 SHA 漂移、工作树不干净、测试条件不满足或越权操作需要，先 STOP 反馈，不自行修复或扩大范围。

---

## 14. 签发状态

| 门禁 | 签发状态 |
|---|---|
| C0 只读事实冻结 | **AUTHORIZED** |
| C1 证据一致性审计/普通软件测试 | **AUTHORIZED** |
| C2 动态测量方案/纯脱机工具准备 | **AUTHORIZED** |
| C3 真机写入/测量/冷上电/受控 assert | **NOT AUTHORIZED — HOLD** |
| C4 统一 Security Gate 及工作流修复/执行 | **NOT AUTHORIZED — HOLD** |
| B03 生产 Broker 故障 | **NOT AUTHORIZED — HOLD** |
| PR #6 Ready/Merge→P4 | **NOT AUTHORIZED — HOLD** |
| P6 FreeRTOS / MQTT5 / GEC6818 | **OUT OF SCOPE** |

**本合同签发终点**：仅要求 Codex 先把 P5 的事实、缺口与未来测量路径收束成**一个可审查的 C1/C2 交付包**。C3/C4 的启动及 P5 最终合并必须等负责人下一轮明确裁定。
