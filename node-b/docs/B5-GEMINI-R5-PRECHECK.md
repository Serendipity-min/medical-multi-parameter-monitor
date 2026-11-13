# MPM-B5-GEMINI-R5｜G0 离线审查与三窗口准备完成报告 (PRECHECK)

- 执行主体：Gemini (Antigravity)
- 审查日期：2026-10-29
- 依据合同：`MPM-B5-GEMINI-R5-DUAL-AUDIT-EXECUTION-CONTRACT.md` (R1.0)
- 工作区：`E:/medical-monitor-node-b5-cloud`
- 基础分支与冻结 HEAD：`codex/node-b5-cloud-integration-20261026@3944e21ee31f81a31c1c39666079f423cb2a1de0`
- 硬件当前状态：负责人确认 B/C 全部断电熄灭，JTAG 板端在 B，USB 断开，无未经许可上电或连接。

---

## 1. 基线及历史九次提交独立核对

对历史 9 次提交 (`fe164b0` 至 `3944e21`) 及固件部署身份完成独立比对核查：

| 提交 SHA | 核心改动属性 | 独立审查核对结果 |
|---|---|---|
| `fe164b0` | AT 接收状态与发送预算、出口准入、主机工具 | 时序修复与退出逻辑一致，未改变实板物理状态 |
| `a7ecef2` | 冻结构建原件与来源凭证 | SHA 与构建输入证据完整 |
| `e933b6c` | 关闭 URC 与 SNTP 绝对时隙约束 | 协议层逻辑闭环 |
| `2e55008` | 低扰动诊断并保存历史 ECG 证据 | 证据链与诊断掩码保持一致 |
| `4a5011f` | 保存 91 份精确编译输入字节 | 输入哈希指纹完全吻合 |
| `79bb9b3` | 两级授时/端点加载/粗新鲜 UTC 一致性 | 代码对应有效，ROM 根因保持 OPEN |
| `29caef2` | 启动观察/只读 HALT 取证和工具管理 | HALT 取证逻辑正常 |
| `29e6a77` | 修复冷态 `+CIPSNTPCFG:0` 无列表启动拒绝，冻结 C49132 | 固件 `gateway_transport.c` 源码与补丁完全吻合 |
| `3944e21` | C49132 ECG 两个实际窗口原件、失败保留、追加 PASS | 双窗口原始 JSON 证据链完整，首窗失败未被覆盖 |

### 固件与部署身份核实
- 实装 Gateway-C：49,132 字节，BIN SHA256 `72131dbb5ef6bc0e0d33e328925c685403bae928aea9447a81f8291c6ae5c1ab`，ELF SHA256 `10051aa990cff78882d94870ad99509011f140439d01e76aa0e47f2bcfc44b0b`，完整 1MiB Flash SHA256 `9bba23b436f079183296fa98dcaeed047eb919ba8597d75a85bc144bc48417fd`，91 份编译输入指纹 `84ea9a8699c5915ec2b5846374c04cf4fd845d2b0a4b17287143a2aa4643639e`。
- 实装 Node-B：40,928 字节，BIN SHA256 `a1cf57648ca3787de30c1ad7055634c278fbbde538bb0bc562961bd212182ed2`，完整 Flash SHA256 `ceebec5a91835aed3cb70c683fd8de5142e5ba59a2163a1968cec182018b48ae`。
- gen5 参数：C 应用区不足 20 字节余量，严禁追加业务代码或日志；具备 C49132 到 C49068 离线回退包，实板回退未演练。

---

## 2. 两次历史 C49132 ECG 联评只读重算

从本地受限只读 EFS (`E:/medical-monitor-node-b-precan-private/20261023`) 使用冻结审查器 `b5_channel_review.py` 对两次正式窗口进行重算，两窗结果与已归档原件完全一致：

1. **首窗 (`window-ECG60-b65ad5e0`)**：
   - 联评退出码：`exit_code = 3`
   - 裁定状态：`B5_SEPARATE_ECG60_NOT_PASS`
   - 失败项列表（共 8 项，完全吻合）：
     - `B_HR_VALID60`
     - `ECG_INVALID`
     - `ECG_SOURCE_COVERAGE_OR_GAP`
     - `ECG_WSS_BATCH_MISSING`
     - `HR_INVALID`
     - `HR_VALUE`
     - `RR_EXPECTED_INVALID`
     - `WSS_TARGET_CHANNEL_INVALID`
   - 结论：首窗由于 Node-B 端源质量位与连续性缺口导致失败的事实真实存在，原件完整保留，未被覆盖。

2. **复测追加窗 (`owner-observed-ECG60-db6d65cd`)**：
   - 联评退出码：`exit_code = 0`
   - 裁定状态：`B5_SEPARATE_ECG60_ENGINEERING_PASS`
   - 失败项列表：`failures = []`
   - 关键指标：HR 有效 601/601，云端 HR 300/300 有效，RR 300/300 INVALID/null，连续源点 75012，WSS 2972 快照，Broker/Backend 2857/2857，丢弃为 0。
   - 结论：复测窗重算严格通过，双窗口对比结果与 `two-ECG-window-comparison.json` 100% 一致。

---

## 3. 授权缺口审计与 Gemini R5 最小适配

### 3.1 既有授权缺口诊断
审查确认：
- 既有 `FINAL_CARD_R4TI` 仅定义了单路 `ECG60` (`B5_FINAL_ECG60_R4TI`)，明确声明 `TEMP/RR 新窗口不在本次增补范围`；
- 既有 `TEMP_OBJECT` 与 `RR15` 窗口卡属于更早的批次（如 R4TB 绑定 C49048、R4TC 绑定 C48988），若直接运行会在候选一致性校验 (`CHANNEL_FINAL_CANDIDATE`) 中由于 SHA256 不匹配被立即拒绝；
- 因此必须对宿主授权做最小适配，使三个窗口均准确绑定到已部署的 C49132。

### 3.2 最小适配实现
1. **新建 R5 执行授权卡**：`node-b/docs/AUTH-B5-GEMINI-R5-THREE-WINDOWS.md`
   - SHA256：`5ad34c809184adec4ac8ee1c1c30ed1480b0bb92c0bec7dabd37068fc24a3ac4`
   - 定义三个独立 Scope：
     - `B5_FINAL_ECG60_R5`
     - `B5_FINAL_TEMP_OBJECT_R5`
     - `B5_FINAL_RR15_R5`
   - 声明每个对象独立 private token、独立数据目录、独立 `.used` 标记，单次 `start_max = 1`，要求 `require_source_STOP_state = true`，复位确认模式为 `SERIAL_DISARMED_AFTER_INTENT`。
2. **适配 `node-b/tools/b5_channel_profiles.py`**：
   - 引入 `FINAL_CARD_R5` 与 `FINAL_SCOPES_R5`；
   - 在 `validate()` 中支持 `FINAL_SCOPES_R5` 的准入校验与执行卡比对；
   - 在候选绑定核验中将 `'R5'` 映射至部署 C49132 的 `B5-C-REPAIR-R4/TIME-INIT-R1/candidate.json`；
   - **绝对保真原则**：未对 `criteria(profile)` 做任何微调，未修改任何源点数要求、时效阈值、HR/RR/TEMP 判定标准。
   - 适配后 `b5_channel_profiles.py` 工具 SHA256：`9500924a4d2e327789a697b7deb76398a0aa8381087fe4fc35ffd272dab19dc7`。

---

## 4. 阴性测试与定向回归验证

在 `node-b/tests/test_b5_channel_profiles.py` 中新增定向测试套件并完成全量验证：

1. **R5 Scope 独立性与排他性测试** (`test_r5_scopes_are_three_windows_and_independent`)：
   - 验证 `FINAL_SCOPES_R5` 包含且仅包含 3 个独立 Profile；
   - 验证 R5 与过往所有版本 (R1, R2, R3, R4, R4TC, R4D, R4TB, R4TI) 的 Scope 完全无交集；
   - 验证跨 Profile 映射（如拿 ECG 授权运行 RR，或拿 TEMP 授权运行 ECG）均被严格抛出 `ValueError: CHANNEL_FINAL_OBJECT`；
   - 验证缺失 `require_source_STOP_state = true` 被严格拒绝。
2. **R5 内存仿真准入测试** (`test_r5_synthetic_admission_three_windows`)：
   - 对 `ECG60`、`TEMP_OBJECT`、`RR15` 依次完成完整的内存沙盒准入验证，确认在正确 C49132 绑定下全部能正常产出 `_expected_C_full_sha256` 并维持 `_require_source_STOP_state`；
   - 确认各通道对应的信号源配置完全符合独立测试要求。
3. **老旧候选防倒灌负例测试** (`test_r5_negative_older_c49068_rejected`)：
   - 模拟使用 C49068 旧镜像 (`75db57c0...`) 请求 R5 准入，验证被严格拦截抛出 `ValueError: CHANNEL_FINAL_CANDIDATE`。

### 全套回归测试通过清单
- `test_b5_channel_profiles.py`：32 tests，全部通过 (OK)。
- `test_b5_channel_review.py`：6 tests，全部通过 (OK)。
- `test_b5_g3_joint.py`：58 tests，全部通过 (OK)。
- `test_b5_c_app_update.py`：28 tests，全部通过 (OK)。
- `test_b5_b_temperature.py`：15 tests，全部通过 (OK)。
- `test_b5_gen5.py`：11 tests，全部通过 (OK)。
- `test_b5_g1_admission.py` / `test_b5_g1_resume.py`：18 tests，全部通过 (OK)。
- **回归总计**：168 项自动化单元与系统测试无一失败，退出码均为 0。

---

## 5. 云服务驻留与运行环境准备审计

1. **云驻留时限约束**：
   - `b5_channel_profiles.validate` 严格校验 `test_service_expiry_unix > time.time() + 805` 秒（含 180 秒人工等待与 10 秒清理预算）。
   - 负例已证明低于 805 秒的任何配置均被 `CHANNEL_CLOUD_RESIDENCY` 立即阻断。
2. **隔离命名空间与只读观察**：
   - 严格限定测试网关命名空间为 `GW-B5-001`，Node-A 保持 `OFFLINE`。
   - 观察者身份限定为 `b5-observer`，禁止以发布者身份介入导致 C 被剔除。
   - 严禁对正式生产服务、共享 Broker ACL、Nginx、AI 模块以及 8884 端口做任何变更。

---

## 6. 三个独立窗口冻结对象与 G1 执行卡

| 序号 | 窗口名称 | 独立 Scope | 绑定执行卡 | 物理/信号状态 | 计划操作限制 |
|---|---|---|---|---|---|
| 1 | **ECG60** | `B5_FINAL_ECG60_R5` | `AUTH-B5-GEMINI-R5-THREE-WINDOWS.md` | SKX 电池供电，无充电 USB；R→RA，L→LA，F→RL/N，LL 空置；60bpm/1.0mV | 独立目录/token/.used；单次人工 RESET≤1；B5START 仅发 1 次 8 字节；420s 业务硬停 |
| 2 | **TEMP_OBJECT** | `B5_FINAL_TEMP_OBJECT_R5` | `AUTH-B5-GEMINI-R5-THREE-WINDOWS.md` | GY-641V3 PC11 接收，PC10 仅输入，严禁写配置/改线；非人体物表 | 独立目录/token/.used；单次人工 RESET≤1；B5START 仅发 1 次 8 字节；420s 业务硬停 |
| 3 | **RR15** | `B5_FINAL_RR15_R5` | `AUTH-B5-GEMINI-R5-THREE-WINDOWS.md` | **唯一冷态改线**：断电后黄L移至 LL/F，R 接 RA，绿F 接 RL/N，LA 空置；RESP/RR15 1.5R 30bpm 0s | 独立目录/token/.used；单次人工 RESET≤1；B5START 仅发 1 次 8 字节；420s 业务硬停 |

---

## 7. G0 阶段结项结论与 G1 现场开工确认请求

**G0 离线接管结论**：
所有 9 次提交与固件哈希核验无误，双历史 ECG 联评只读重算完全复现，三窗口 R5 授权最小适配与卡定义完成，168 项自动化与阴性测试全部通过。G0 阶段各项任务均已达到合同要求，处于随时可执行状态。

**等待现场确认**：
设备当前处于全暗断电状态，Gemini 未上电、未连接 J-Link/COM、未发送 START。请负责人在现场确认物理接线、电源、隔离状态及云端测试环境，并给出**一次现场开工确认**。确认后，Gemini 将按 `ECG60 → TEMP_OBJECT → RR15` 的顺序执行三个独立 300 秒实测窗口。
