# 多参数生理监护仪项目：P5 coreMQTT 功能验收、Security Gate 与 PR #6 最终审查执行合同 v1.0

> **合同编号**：MPM-P5-FINAL-SOW-001  
> **签发日期**：2026-10-09  
> **适用仓库**：`Serendipity-min/medical-multi-parameter-monitor`  
> **执行方**：Codex（仅限本合同获授权阶段）  
> **审核方**：项目负责人；ChatGPT 提供独立技术复核与合并建议  
> **本次授权结论**：`F0/F1/G0（只读、普通验证、证据整理及门禁范围提案）= AUTHORIZED`；`G1（正式 Security Gate）= WAIT_EXPLICIT_USER_AUTHORIZATION`；`R1（PR 合并）= HOLD`；`P6 = NOT AUTHORIZED`。

---

## 0. 本轮任务裁定：回到 P5 的原始目标

**P5 的唯一核心变量**：STM32F407 Gateway-C **裸机**上的活动 MQTT 客户端从 Hardened Paho Embedded C 迁为 **coreMQTT v2.3.1**，MQTT wire protocol 继续为 **3.1.1**。不迁移 FreeRTOS，不升级 MQTT 5，不改变 ESP8266 AT/TLS、CANopen 数据契约、Topic/Payload、Router LIVE/REPLAY、Backend 或 Web。

本合同的最终目的不是继续开发 H16 性能仪器，而是：

1. 整理并冻结 **coreMQTT 功能可行性证据**，形成可复核的 `P5_FUNCTIONAL_VERDICT`。
2. 核对并修正 **Security Gate 的 P5 活动客户端覆盖范围**；**获得项目负责人另行、明确、针对固定 SHA 的授权后**运行门禁。
3. 审阅 PR #6 的真正变更、残余风险与门禁结果，形成 `P5_MERGE_RECOMMENDATION`，**等待用户决定是否合并**。
4. **仅在 P5 已由用户批准并合入最新 P4 后**，另行签发 P6 FreeRTOS 迁移合同。绝不自动开始 P6。

**重要的验收口径调整提案**：H16 的增强性能测量与 P5 的核心 MQTT 功能验收分开评级。M03/M04、单次重连样本与 CAN 延迟缺口**必须明确保留**，但不能无证据地把它们解释成 coreMQTT 功能失败。是否允许这些限制随 P5 一并进入 P4，由**最终负责人书面裁定**；本合同不自动批准豁免。旧合同及其 H16 原要求保持可追溯，不得删除或悄悄改写。

**禁止**：重复开展 C2.5-R3/R4、开发新测量设备、以 70 项诊断工具测试取代 MQTT 42 项协议功能测试；未经授权连接/烧录 F407、触发 D/断电、真机 assert、生产 Broker 故障、任何 Security Gate 扫描、修改 P4/main、合并 PR 或启动 P6。

## 1. 基线身份与分支边界（执行前 F0 再核对）

| 对象 | 签发时核对的 GitHub 状态 | 含义 |
|---|---|---|
| P4 | `8dee339491cfd4edc468bb9451511d421f26db5e` | P4 稳定集成基线；禁止修改 |
| main | `50699048010c57ba10f8573461844c525b022a07` | 稳定历史主干；禁止修改 |
| P5 PR #6 分支 | `P5-coremqtt-baremetal` @ `de36cc1b9bbe7c98757d6fffb4c87b32ffde8f53` | OPEN / DRAFT；待审查主线 |
| P5 已验证固件源码 | `e598fc63719acdf49a99c6da46c656dc8c607782` | 最新 P0 功能/固件源输入；不能用后续纯文档 HEAD 冒充重新测量 |
| H16 诊断分支 | `codex/p5-c3a-diagnostic` @ `38ccef7fd7e265b848880dd2ca1015ca3f3a7099` | 独立诊断及受限性能证据；**不得自动整支合入 PR #6** |
| PR #6 | <https://github.com/Serendipity-min/medical-multi-parameter-monitor/pull/6> | 待功能冻结、安全门、最终复核和用户批准 |
| 上游 coreMQTT | tag `v2.3.1` / commit `2beef04725328923e05e576b884212d53ec97af7` | 固定第三方版本，不跟随 main 升级 |

执行前再次核实上述分支和 SHA、工作树和 Git 跟踪状态；**任何意料外漂移、脏工作树、证据身份不符 = STOP**，由 Codex 报告，不自动 reset/rebase/cherry-pick/force-push。尤其不许从 H16 诊断分支把全部工具和代码自动合并进 P5。

本轮正常工作区为**独立 P5 工作区**。既有用户未提交文档及任何私有材料原地保留。允许在 P5 分支中作小范围文档提交与普通测试；禁止产生与本合同无关的生产固件变更。若提交造成 PR HEAD 更新，要在下轮 Gate 中使用**最新真实 HEAD**。

## 2. 关口与授权表（必须顺序执行）

| 关口 | 可执行内容 | 当前授权 | 必须停止的地方 |
|---|---|---|---|
| **F0：事实与身份锁定** | 只读 Git/固件/证据索引核对 | **已授权** | 身份不一致先 STOP |
| **F1：coreMQTT 功能验收冻结** | 整理已通过测试和风险、机器摘要、必要的**普通**验证，形成简短验收包 | **已授权** | 输出 `P5_F1_FUNCTIONAL_FREEZE` |
| **G0：Security Gate 准备** | **只读**核查现有 Gate 覆盖，生成最小 profile/workflow 修正 Diff 和授权申请；不运行 Gate | **已授权** | 输出 `P5_G0_AUTH_REQUEST`，等待用户 |
| **G1：Security Gate 实际执行** | 按用户批准的准确 HEAD/模式/工具与变更范围运行 | **未授权** | 生成 Gate 结果并等待独立审核 |
| **R0：PR #6 最终审查** | 审查差异、功能证据、正式 Gate、例外申请，给出 `GO/NO_GO/HOLD` **建议** | 待 G1 证据 | 交项目负责人裁定 |
| **R1：合入 P4** | 确认允许合并后由获授权执行者操作 | **未授权** | 未经用户签字不可执行 |
| **P6：FreeRTOS 合同** | 仅在 P5 合入、当前 P4 SHA 重核对后拟定并另行签发 | **未授权** | 不创建 P6 代码分支、不实施 FreeRTOS |

**不得将 G0 的“申请授权”解释为 G1 已授权，也不得将 R0 的技术建议解释为 R1 合并命令。**

## 3. F1：P5 coreMQTT 功能验收与证据冻结（主要工作）

### 3.1 固定验收结论结构

统一输出两层结果，禁止混淆：

- `P5_FUNCTIONAL_VERDICT`：**PASS_WITH_LIMITATIONS / FAIL / BLOCKED**。只对 MQTT 客户端替换及原有业务等价性负责。
- `P5_FINAL_MERGE_STATUS`：**HOLD / ACCEPTANCE_CANDIDATE / APPROVED_TO_MERGE**。Security Gate 和负责人最终裁定未完成前只能 HOLD。

不得把原有各轮的 `NOT_RUN` 文案批量覆写为 `PASS`。采用**新综合冻结报告**指向后续独立补证，而不是改写历史原件。

### 3.2 必须冻结的已知证据（Codex 逐项核对，不虚构）

| 证据条目 | 已有结果 / 冻结输入 | 主要来源和限定 |
|---|---|---|
| 供应链与活动白名单 | coreMQTT `v2.3.1`、MIT、commit/文件哈希、active 源白名单 | `gateway/third_party/coreMQTT/upstream.json`、`verify_coremqtt_integrity.py`、ELF/构建白名单 |
| 真实 ARM 裸机构建 | PASS；P5 最后固件 BIN **35,552 B** | P5 P0 报告、`p0-resources.json`；与普通 CI 的 host 构建区分 |
| MQTT 主功能 | **42/42 C 普通功能测试** | `p0-host-summary.json`；CONNECT、QoS0、QoS1、匹配 PUBACK、异常与 keepalive；仅合成 ESP 部分 |
| 来源完整性 | **6/6** | 本轮固定第三方来源与构建清单，而非旧 Paho 身份 |
| 隔离真实 Broker | **30/30** | `P5_P0_隔离Mosquitto集成验证报告_v1.0.md`、`p0-broker-summary.json`；P4/P5 payload、Will/retain、异常断连、PUBACK |
| CAN/Router/Canonical/Backend | CANopen 12、Router 11、Canonical 41 条消息、Backend 28 项 | 原 P5 / P2 结果，识别准确源输入和执行日期 |
| F407 真机合成链路 | **B01 PASS** | CAN1 silent loopback 双合成节点 → ESP AT/TLS → Broker → Backend；不是 A/B 三板外部 CAN |
| Wi-Fi 断网与恢复 | **B02 PASS** | OFFLINE→ONLINE，LIVE 优先于 REPLAY；`lost=203` 历史窗口必须如实披露 |
| 烧录恢复 | **B04 PASS** | 1,048,576 B 双读、完整恢复和独立回读，原 DMA_ADC 恢复；不等于冷上电验证 |
| 项目级断言 | Host 4 项通过、ARM 链接告警清零 | 真机强制 assert 仍未测，不得标记硬件 PASS |
| 静态资源 | P4 RAM 总布局 **120,160 B**；P5 **120,208 B**，+48 B | 128 KiB 链接上限，24 KiB Heap / 8 KiB Stack 预留；不等于栈高水位 |
| C3A 单次性能参考 | P4/P5 `_sbrk` 峰值均 **9,400 B**；首次有效业务 5.160/5.002 s | **仅限定观测**：名义 16MHz、各一轮，整体 H16 `NOT_GRANTED` |
| CI / 托管 App | P5 PR HEAD 已有普通 CI、托管 Semgrep SUCCESS | 必须绑定精确 Git SHA；**托管 App 不是统一 Gate** |

冻结固件产物：P5 BIN SHA-256 `fd81076b9b34ad0a8f4ee35c08cd7ea14704f6d7b04620741cdf083c9c6c1069`；P5 ELF SHA-256 `c5eb2278669fe520c391c0e4dc69a13539686d724bdff6724cc4cc041e3f9a35`。这些为**生产功能固件**，不是 H16 诊断 BIN。冻结 P4 的对照 BIN SHA-256 `5fd386b8bfe0bcf54d4f53ffb1ec6483d086a1c3287b4fe6c37a3ddeacd90547`。

### 3.3 风险及例外必须保留

1. `M03=PARTIAL`：纯 CPU 协议库消耗未可比；`M04=BLOCKED_UNSAFE_SENTINEL`：Stack 高水位未测；`M01/M02` 只对完成调用/匹配服务可作限定观察；`M06` 只有单次名义时长，未完成原 20% 退化评审；`M07` 不支持无损/全量排空结论。
2. `B03=NOT_RUN`：生产 Broker 故障注入**未授权**。可由 Codex 提议 `WAIVER_REQUESTED`，依据隔离 Broker 30/30 及真机 Wi-Fi 故障结果，**只有负责人明确签字**才能标记 `WAIVED_FOR_P5`；不执行生产 Broker 重启来凑 PASS。
3. 冷断电上电、真实 assert 硬件故障路径未验证。若认为可带限制阶段准出，逐项给出风险、所有者、后续阶段和有效范围，**由负责人决定**。
4. CAN1 silent loopback 与 `MOCK/synthetic=true` 不代表真实 A/B 节点、人体数据、医疗级报警或最终 24h 稳定性；不能将 P6 的 24h 阶段性 soak 偷算为 P5 已通过。
5. 三轮诊断测试和 70 项质量解析器用例属于**H16 测量工具证据**，不计入 coreMQTT `42/42` 的功能测试分母。所有历史失败和重试原因原样保留。

### 3.4 精简交付物

仅新增/更新必要的两个主交付文件（无需大量碎片报告）：

- `doc/P/04_第四阶段_P5_coreMQTT裸机迁移/验收/P5_coreMQTT_功能验收冻结与风险清单_v1.0.md`：一份完整结论、原始证据链接、功能/非功能分界、例外请求。
- `doc/P/04_第四阶段_P5_coreMQTT裸机迁移/验收/evidence/p5-functional-freeze.json`：机器可读 `source_sha`、`firmware_bin_sha`、报告/JSON 原字节 SHA、每项 `PASS/LIMITED/NOT_RUN` 和来源路径、证据检查结果。

可对已有 `doc/P/README.md` 或 P5 README 做不改写历史的**最小导航补充**。固件、第三方源码、诊断 Patch、私人 Flash、凭据、原始非脱敏日志不允许提交。原证据位置不能访问时填写 `UNVERIFIED`，不得用旧摘要冒充当前本地 SHA 复核。

**F1 达标**：Codex 输出 `P5_F1_FUNCTIONAL_FREEZE`，至少载明 10 项关键验证、精确代码/固件指纹、风险清单、`PASS_WITH_LIMITATIONS` 或阻断原因、工作树差异和提交 SHA。必要时可在独立 P5 分支整理文档并 push；不得把 H16 诊断分支整体 merge/cherry-pick 进来。

## 4. G0：统一 Security Gate 执行前必须修正的覆盖问题（当前仅允许审计与提案）

### 4.1 已核对的实质覆盖缺口

签发时，**P5 分支现有** `.security-gate.json` 和 `tools/security_gate/profiles/medical-monitor.json` 仍包含：

- `sanitizer-fixed` → `gateway/canopen/run_security_regression.py`（检查的是历史 Paho）且 mandatory；
- `paho-integrity` → `verify_paho_integrity.py` 且 mandatory；
- **没有**明确将 `verify_coremqtt_integrity.py`、P5 coreMQTT Host 回归列作活动客户端 mandatory 检查；
- 当前普通 CI 已为 P5 另设 coreMQTT 检查，但 **普通 CI 的绿色不自动修正统一 Security Gate 的 profile 语义**。

**结论：当前 Gate profile 未证明对 P5 活动客户端具有充分覆盖。直接扫描即使显示 PASS，也不能据此签发 P5 最终安全准出。**

### 4.2 最小修正规则（先交 Diff，再获准应用与扫描）

Codex 在 G0 只能生成并审查**未应用的最小 Patch 提案**及覆盖矩阵，不执行 Gate：

1. P5 目标 profile 的 **mandatory** 至少包括：固定 coreMQTT 来源/活动白名单，实际 coreMQTT 42 项普通 Host 客户端回归，Gateway 构建与 CAN/Router/Backend 原普通检查；不得以 Paho 旧套件替代当前客户端覆盖。
2. **P5 安全测试覆盖**应包含运行当前 coreMQTT 真实源码的有界 ASan/UBSan 或等效经评审的内存安全回归；如目前只有无 sanitizer 的 42 项普通测试，应报告 `ACTIVE_COREMQTT_SANITIZER_COVERAGE_GAP`，提出最小复用已有夹具的方案，**不能假装 Paho sanitizer 已覆盖 coreMQTT**。安全回归及其首次执行属于 G1 授权范围。
3. 保留 Paho 的冻结来源和 PATCH-01/02/03 历史审计；旧 Paho 专项回归可作为历史补充，但不得被当成新客户端主证据或删除历史。
4. 检查 Semgrep、Trivy、Gitleaks、pip/npm 审计、clang-tidy 的真实目标清单，记录 coreMQTT vendor 源及 Gateway 一方适配层的实际覆盖；第三方库未扫描的部分须显式标 `COVERAGE_GAP`，不以 `0 findings` 冒充全覆盖。不得为了变绿关闭规则或降低严重性。
5. **不要默认修复或执行** `.github/workflows/security-gate.yml`：此前工作流 `jobs=[]` / workflow validation FAILURE（旧 job 级 `runner.temp` 表达式可能存在上下文问题），这是**未启动**而非漏洞扫描结果。优先考虑现有本地 HERA-C3 的确定性 `gate.py`，避免为了合并 P5 先重构 CI 基建。只有用户另外批准 CI 工作流修复时才提交准确 Diff。
6. 不得在 G0 修改 Gate 核心策略、`toolchain.lock.json`、发现接受规则、已有 P4 历史报告；不得自动安装/升级扫描器、获取新凭据或执行 `doctor/quick/pr/release`。

**执行策略**：如需要实质性修改 `.security-gate.json` 或新增 P5 gate-only sanitizer runner，先将可审阅 Diff、普通编译验证计划和受影响目录列入 `P5_G0_AUTH_REQUEST`。在用户确认**允许的 Gate 配置变更**后才应用于独立 P5 分支并提交；若 profile 已修正并发生 HEAD 漂移，Gate 授权须绑定新 HEAD。避免另开多轮“工具测试的工具测试”。

## 5. G1：单独授权后执行最终 P5 安全准出

### 5.1 本合同不是扫描授权

当前状态严格为：`SECURITY_GATE = NOT_AUTHORIZED/NOT_RUN`。用户需要在 F1/G0 回执后，明确答复**本次准确 Git SHA、模式、执行环境、允许的 profile/测试脚本变更及测试范围**。原有托管 Semgrep App 自动结果不构成这份授权。

推荐授权范围为 **工程样机 P5→P4 的 `doctor + pr` 模式**，`base=P4@8dee339...`、目标为新鲜核对的 `P5-coremqtt-baremetal` 精确 HEAD。这里的“最终安全准出”指 **P5 合入 P4 前的安全门**；不是允许真实人体数据或临床发布的 `release` 级别。`release`、ZAP、主动公共目标扫描、生产 Broker 测试和真实设备控制必须分别授权。

示例用户授权回执（**此处是模板，不代表已经授权**）：

```ini
P5_SECURITY_GATE_AUTHORIZATION
TARGET_BRANCH = P5-coremqtt-baremetal
TARGET_SHA = <完成最小Gate配置对齐后的40位SHA>
BASE_SHA = 8dee339491cfd4edc468bb9451511d421f26db5e
MODES = doctor, pr
ENVIRONMENT = approved existing HERA-C3 local runner
PROFILE = reviewed P5 active-client profile, with SHA256 recorded
AUTH_SCAN = YES
AUTH_PROFILE_PATCH = <精确文件范围，若需要>
NETWORK_SCOPE = dependency metadata / scanner rules per approved tool policy only
ZAP_TARGET = NONE
PRODUCTION_BROKER = NO
BOARD_FLASH_OR_POWERCYCLE = NO
AUTO_MERGE = NO
USER_APPROVAL = <由用户明确回复，不能由Codex代填>
```

### 5.2 G1 在获准后的执行顺序

1. 只读冻结 `git rev-parse HEAD`、branch、`git status --porcelain`、`origin/P4`、Gate profile SHA、工具锁、真实 coreMQTT 活动源；不符合就 STOP。
2. 仅在用户已授权的 profile 差异范围内完成最小改动，正常普通编译/测试 PASS 后单独提交 P5；**使用变更后最终 HEAD 重新核对授权是否仍有效**。
3. 在**已经授权**的环境执行 `doctor`（仅环境预检，不能算扫描 PASS）。工具缺失/Pro 认证不可用/Hash 不匹配时记录 `TOOL_ERROR`，不绕过锁、不擅自安装、也不以 OSS 冒充 Pro。
4. 对同一最终 HEAD 执行指定的 `pr` Gate；示意入口（**只在授权后**）：

   ```text
   python tools/security_gate/gate.py pr --repo . --base 8dee339491cfd4edc468bb9451511d421f26db5e --authorize
   ```

   上述命令应在目标 P5 工作区、既有获准工具环境执行；执行前核查 `gate.py` 实际参数、profile、工作区洁净和外部输出位置。无 `--target`、无 `--authorize-target`、无 `--real-data`。
5. 冻结运行日志、`gate-result.json`、`coverage.json`、`gate-report.md`、`report-integrity.json`、工具版本与精确输入 SHA；原始 raw 仍在仓库外，仓库只留脱敏摘要、哈希和本次 Gate 结果引用。
6. 结果按执行器口径分级：`0=PASS`、`1=FAIL`、`2=CONDITIONAL/HUMAN_REVIEW`、`3=TOOL/COVERAGE_ERROR`。发现新的 HIGH/CRITICAL、秘密、必跑项失败、活动客户端覆盖缺口，不得擅自 accept、降级严重度、关闭规则或宣布 PASS。若为 2，列残余范围与责任人，由负责人决定是否可在**工程样机**范围接受；3 一律不是安全准出。
7. 若修复安全发现导致 Gateway 活动代码变化，必须重新执行相应普通功能/ARM/接口回归、识别此前真机 SHA 证据是否失效，并在固定新 HEAD 上**重新申请必要的 Gate/验收授权**。不允许后台无限循环扫描或直接合并。

**G1 达标**：准确 SHA 的 Gate 已真实执行，有完整证据，mandatory 覆盖可审；任何不可接受的新 blocker 均已解决。否则 `P5_SECURITY_HOLD`。

## 6. R0：PR #6 最终代码与变更审查（不自动合并）

Codex 交付 `P5_PR6_FINAL_REVIEW`，由 ChatGPT/项目负责人作独立复核。审核最少包括：

- P4→P5 **全部实际变更**，活动源/链接不含 Paho client、RTOS 或 MQTT5；上游 coreMQTT 固定版本、MIT/哈希、构建白名单、替换旧 Paho 与历史证据不混淆。
- 重点审阅 `gateway_transport.c/.h`、`mqtt_transport_adapter.c/.h`、`platform.c`、`gateway_assert.c` 与 `build.py`：TLS CA/CCN/SNI/时间、短读短写、有界缓冲/超时、QoS1 PUBACK 后 Router ACK、发布边界、keepalive 与断线清理。
- `CANopen`/Router/Model/Backend/Web 的既定语义与源身份；合成测试的 RR 仍 INVALID；既有 32 帧缓存 `lost` 不作无损承诺。
- F1 冻结的功能证据及真机 BIN SHA、隔离 Broker、恢复状态；S0/G1 的准确 profile SHA、实际扫描覆盖、tool errors 与残余风险；新 HEAD 的普通 CI / 托管检查不能引用旧 HEAD 状态。
- 审阅是否有**范围外**的 H16 诊断工具变更误入 PR #6；`codex/p5-c3a-diagnostic` 默认**仅独立归档、不整支合流**。如拟选取少量 P5 验收证据进 PR，先列出文件级白名单与准确 SHA，未经复核不 cherry-pick。
- 审查新增凭据、Flash dump、原始生理数据、隐私字段、意外云端部署和未经授权的 Security Gate 触发；它们应为 **NONE**。

### R0 可以给出的三种建议

| 建议 | 判据 | 下一步 |
|---|---|---|
| **GO_TO_USER_DECISION** | coreMQTT 功能证据成立；无已知功能回归；获授权 Gate 准出且覆盖真实；所有重要限制由负责人书面接受或闭合 | **只建议**合并，等待用户明确批准 |
| **HOLD** | Gate 未授权/未运行/TOOL_ERROR，或 B03/H16/冷启动/assert 的最终风险接受尚未签字 | 保留 Draft，不执行 R1/P6 |
| **NO_GO** | 发现活动 coreMQTT 严重缺陷、错误 ACK、数据语义回归、安全新 blocker 或不能恢复的不一致 | 修复并有限复验，不隐瞒失败 |

**R0 输出**必须包含：可核对 PR diff、冻结测试与 SHA、Gate manifest、逐项残余风险/责任人、`MERGE_RECOMMENDATION`、是否可合 P4、对 P6 合同的解锁条件。ChatGPT 给出技术裁定建议；**只有用户明确授权才能执行 GitHub Merge**。

## 7. R1 与 P6：只能在后续用户决策后发生

- 如用户批准 PR #6 合并，操作前重新检查 PR 状态、HEAD、P4 目标 SHA、强制检查和授权有效性；如有漂移重新复核。执行合并后的 P4 SHA 必须回填交付记录；未经用户指令不自动删除 P5 分支。
- 如 Gate 或技术审查没有满足条件，保持 PR #6 DRAFT / P5 HOLD，不启动 P6。允许保持软件迁移的已验证功能结论，不将 HOLD 误写成“coreMQTT 完全失败”。
- **P6 合同签发前置条件**：P5 已由用户批准并合入最新 P4；再次读取仓库实树/构建入口；独立签发 `P6_FreeRTOS_coreMQTT_v2.3.1_MQTT311_正式执行合同_v1.0.md`，规划 FreeRTOS Task/Queue/ISR 规则、MQTT/ESP AT 单一所有者、CAN 实时性、静态内存/栈高水位、24h 阶段 soak 与独立 Security Gate 授权。
- P6 不自动包含 MQTT5；MQTT5 仅以后可选 P7。真实三板 CAN、RR 算法与人体数据准出仍须独立阶段验证。

## 8. 允许提交的文件及防污染策略

**本轮 F0/F1/G0 可提交的预期路径**（白名单之外先报告）：

```text
doc/P/04_第四阶段_P5_coreMQTT裸机迁移/
  合同/
    P5_coreMQTT功能验收_SecurityGate与PR6最终审查执行合同_v1.0.md
  验收/
    P5_coreMQTT_功能验收冻结与风险清单_v1.0.md
    evidence/p5-functional-freeze.json
  README.md                           # 必要时新增最小导航
```

G0 中 Gate 代码/配置仅**准备未应用的 Patch 及申请文本**（允许放在本地忽略目录或追加上述功能冻结文档的附件）；经用户批准的 G1 阶段，才允许明确文件范围内 `.security-gate.json`/测试入口的有限调整。新门禁报告如获授权，再添加短的最终安全门摘要和 Gate 证据索引，不在仓库中收集 raw 输出。

分支保护：只向 `P5-coremqtt-baremetal` 提交本轮允许变更；`codex/p5-c3a-diagnostic` 只读归档；`P4`/`main` 均不可写。每次提交前审查 `git diff --check`、staged 文件清单、第三方源 SHA 与是否误纳敏感资料；允许合并若干普通文档改动为**一至两次有逻辑的提交**，不因每个标题/链接修改独立 push。向 GitHub 的 push 可能触发平台上已有的普通 CI / 托管 App 检查；它们仍是独立的托管行为，**不得当作本合同已授权的统一 Gate**。

## 9. Codex 汇报模板与停止点

### F1 + G0（**此轮执行到这里就停止**）

```ini
P5_F1_G0_HANDOFF
P4_BASE_SHA               =
P5_PR6_BRANCH             = P5-coremqtt-baremetal
P5_PR6_HEAD               =
P5_PRODUCTION_CODE_SHA    = e598fc63719acdf49a99c6da46c656dc8c607782 / DRIFT
ACTIVE_CLIENT             = coreMQTT v2.3.1
MQTT_WIRE_VERSION         = 3.1.1
FUNCTIONAL_TESTS          = 42/42 (source-verified or UNVERIFIED)
VENDOR_INTEGRITY          = 6/6 (source-verified or UNVERIFIED)
ISOLATED_BROKER           = 30/30 (source-verified or UNVERIFIED)
HARDWARE_B01_B02_B04      = PASS (source-verified or UNVERIFIED)
H16                      = LIMITED / NOT_GRANTED
B03                      = NOT_RUN / WAIVER_REQUESTED
COLD_BOOT_ASSERT_HW       = NOT_RUN / RISK_REVIEW_PENDING
FUNCTIONAL_VERDICT        = PASS_WITH_LIMITATIONS / FAIL / BLOCKED
GATE_PROFILE_ACTIVE_LIB   = ALIGNED / GAP_IDENTIFIED
GATE_PROFILE_PATCH        = path / NONE
GATE_AUTHORIZATION        = REQUESTED_NOT_GRANTED
PR6_STATUS                = OPEN_DRAFT
MERGED_TO_P4              = NO
P6_STARTED                = NO
OUTPUTS                   = <relative repo paths + source hashes>
BLOCKERS                  =
STATUS                    = WAIT_GATE_AUTHORIZATION
```

### G1 + R0（**仅收到后续明确授权才使用**）

```ini
P5_G1_R0_FINAL_REVIEW
GATE_TARGET_HEAD          = <exact 40-digit SHA>
GATE_BASE_SHA             = <exact P4 SHA>
GATE_PROFILE_SHA256       =
GATE_MODE                 = doctor + pr / not authorized
GATE_EXIT_CODE            = 0 / 1 / 2 / 3 / NOT_RUN
MANDATORY_COVERAGE        = PASS / GAP / UNVERIFIED
COREMQTT_ASAN_UBSAN       = PASS / BLOCKED / NOT_RUN
NEW_HIGH_CRITICAL         = 0 / <ids; no secrets>
FULL_FUNCTIONAL_EVIDENCE  = PASS_WITH_LIMITATIONS / ISSUE
B03_WAIVER                = APPROVED / PENDING
H16_RISK_ACCEPTANCE       = APPROVED / PENDING
COLD_BOOT_ASSERT_RISK     = APPROVED / PENDING
PR6_REVIEW                = COMPLETE / HOLD
MERGE_RECOMMENDATION      = GO_TO_USER_DECISION / HOLD / NO_GO
PR6_MERGED               = NO
P6_STARTED               = NO
NEEDS_USER_DECISION       =
```

## 10. 发给 Codex 的首条指令（本次可执行范围）

> **现在只批准 P5 最终合同的 F0、F1、G0**。在 `P5-coremqtt-baremetal` 独立工作区阅读本合同、原 P5 合同、全部 P0/真机证据以及 PR #6；先复核 SHA、工作树及历史指纹。把 coreMQTT 功能已通过的证据整理成一份简短的功能验收冻结报告和机器清单，明确 H16 是有限性能观测而非 MQTT 功能失败，历史缺口/`lost=203` 不得删除。只读核对 `.security-gate.json`：确认旧 Paho sanitizer/完整性不能替代 coreMQTT 活动客户端安全覆盖，拟出**最小 Gate 配置/测试覆盖 Patch**及精确授权申请，暂不应用安全门修复、不得运行 doctor/quick/pr/release、ASan/UBSan、安全扫描或任何真实设备/生产 Broker 操作。普通范围内可整理文档并向 P5 分支提交；PR #6 保持 Draft。输出 `P5_F1_G0_HANDOFF` 后停止，等用户明确批准 G1 的准确 SHA、模式和允许变更。不得合并 P4 或开始 P6。

---

**最终签发声明**：本合同首先批准 **F0/F1/G0**；**没有批准 G1 Security Gate 运行，也没有批准 PR #6 合并及 P6 开发**。今后是否合并 P5 及是否签发 P6，由项目负责人依据功能冻结、真实 Gate 结果与最终代码审查另行裁定。
