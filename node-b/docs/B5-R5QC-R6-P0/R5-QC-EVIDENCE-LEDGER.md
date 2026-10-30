# R5-QC-EVIDENCE-LEDGER｜R5 批次全量执行记录与不可变证据台账

- **生成主体**：Gemini (Antigravity)
- **审查基准**：`codex/node-b5-cloud-integration-20261026@2854d3581658a91d65c1aa30d827ff489ff0f081`
- **审计分支**：`audit/b5-r5qc-r6p0-20261030`
- **依据合同**：[`MPM-B5-R5QC-R6-P0-GEMINI-EXECUTION-CONTRACT-R1.md`](file:///E:/%E5%A4%9A%E5%8F%82%E6%95%B0%E5%BF%83%E7%94%B5%E7%9B%91%E6%8A%A4%E4%BB%AA%E7%B3%BB%E7%BB%9F-%E6%A0%B7%E6%9C%BA%E5%BC%80%E5%8F%91/doc/P/05_%E7%AC%AC%E4%BA%94%E9%98%B6%E6%AE%B5_%E4%BA%91%E7%AB%AFAI%E8%AF%AD%E9%9F%B3%E4%B8%8E%E6%B2%99%E7%9B%98%E6%A8%A1%E5%9E%8B%E6%9E%84%E5%BB%BA/%E5%90%88%E5%90%8C/MPM-B5-R5QC-R6-P0-GEMINI-EXECUTION-CONTRACT-R1.md)
- **受限 EFS 根路径**：`E:/medical-monitor-node-b-precan-private/20261023/time-init-field-6cd64b90/`（只读，严禁任何写操作）
- **公开证据根路径**：[`node-b/evidence/B5-GEMINI-R5/`](file:///E:/medical-monitor-node-b5-cloud/node-b/evidence/B5-GEMINI-R5)

---

## 1. 证据等级划分定义

根据合同 QC-1 规约，本台账所有条目严格区分为三级证据属性：
- **`[RAW]` (原始事实)**：现场硬件物理产生并由日志/串口/硬件定时器记录的不可变字节流、物理行、Exit Code、Flash/BIN 哈希指纹；
- **`[DERIVED]` (衍生分析)**：经由冻结审查器 `b5_channel_review.py` 或独立复算脚本基于 `[RAW]` 数据严格计算得出的统计指标、匹配率、单调时间差值；
- **`[POSTHOC_CORRECTION]` (后补勘误)**：对过往报告中文本文档笔误、参数混淆或未充分核验的非技术表述进行的更正与审计说明。

---

## 2. R5 批次全量七次现场尝试总台账

| 尝试序号 | 目录名称 `[RAW]` | 业务 Scope `[RAW]` | 授权 Token 哈希 `[RAW]` | `.used` 消耗时间 `[RAW]` | C 板 RESET 真实记录 `[RAW]` | B5START 发送真实记录 `[RAW]` | 终止原因 / 现场定性 `[RAW]` | Worker / Supervisor / Formal 退出码 `[RAW]` | 正式联评状态 `[DERIVED]` | 证据等级 |
|---|---|---|---|---|---|---|---|---|---|---|
| **1** | `owner-observed-ECG60-R5-55d99a50` | `B5_FINAL_ECG60_R5` | `1eeaba1a62fe...` | `monotonic = 1007144.156` | 严格 1 次 (单次人工复位) | 严格 1 次 (8 字节) | 420.000s MCU 硬截止 (`reason=1, phase=7`) | worker=0, sup=0, formal=3 | `B5_SEPARATE_ECG60_NOT_PASS` | `[RAW]` + `[DERIVED]` |
| **2** | `owner-observed-TEMP_OBJECT-R5-75cf9999` | `B5_FINAL_TEMP_OBJECT_R5` | `3bb304e4eac5...` | `monotonic = 1008105.078` | 严格 1 次 | 严格 1 次 | 1.164s SNTP 时钟漂移超限 (`reason=10`) 安全熔断 | worker=1, sup=1, formal=N/A | (未进入正式联评) | `[RAW]` |
| **3** | `owner-observed-TEMP_OBJECT-R5-cff28389` | `B5_FINAL_TEMP_OBJECT_R5` | `e5d75ba2be3b...` | `monotonic = 1057295.531` | **发生 2 次**（第 37 秒现场误按第 2 次 RESET） | 严格 1 次 | **现场操作偏离并由监控系统安全熔断** (`G3_C_UNEXPECTED_REBOOT`) | worker=1, sup=1, formal=N/A | (未进入正式联评) | `[RAW]` + `[POSTHOC_CORRECTION]` |
| **4** | `owner-observed-TEMP_OBJECT-R5-f75b446e` | `B5_FINAL_TEMP_OBJECT_R5` | `03f6d993c6be...` | `monotonic = 1057757.625` | 严格 1 次 | 严格 1 次 | 1.917s 温态 ESP-01S 时钟漂移超限 (`reason=10`) 安全熔断 | worker=1, sup=1, formal=N/A | (未进入正式联评) | `[RAW]` |
| **5** | `owner-observed-TEMP_OBJECT-R5-6104c2e6` | `B5_FINAL_TEMP_OBJECT_R5` | `f7b122d1cae3...` | `monotonic = 1057964.421` | 严格 1 次 (冷拔插 USB 上电后单次复位) | 严格 1 次 (8 字节) | 420.000s MCU 硬截止 (`reason=1, phase=7`) | worker=0, sup=0, formal=3 | `B5_SEPARATE_TEMP_OBJECT_NOT_PASS` | `[RAW]` + `[DERIVED]` |
| **6** | `owner-observed-RR15-R5-7058a3bd` | `B5_FINAL_RR15_R5` | `764f1415f9b4...` | `monotonic = 1059028.609` | 严格 1 次 | 严格 1 次 | 60.0s 模拟仪误设 30bpm 触发准入超时 (`COMMON_READY_DEADLINE`) | worker=1, sup=1, formal=N/A | (未进入正式联评) | `[RAW]` |
| **7** | `owner-observed-RR15-R5-5bb61eef` | `B5_FINAL_RR15_R5` | `4d7fb1342fd0...` | `monotonic = 1059442.906` | 严格 1 次 (冷拔插 USB 上电后单次复位) | 严格 1 次 (8 字节) | 420.000s MCU 硬截止 (`reason=1, phase=7`) | worker=0, sup=0, formal=3 | `B5_SEPARATE_RR15_NOT_PASS` | `[RAW]` + `[DERIVED]` |

---

## 3. 受限 EFS 物理原件与公开证据包 SHA256 指纹核验表

经对本地受限 EFS 与 GitHub 公开证据目录进行实际字节级计算（非引用声称）：

### 3.1 三项正式完成评测窗口原件哈希表

| 窗口标识 | 文件类别 | 本地受限 EFS 物理路径 | 物理原件 SHA256 `[RAW]` | 公开脱敏证据路径 | 公开脱敏件 SHA256 `[DERIVED]` | 脱敏差异机制说明 |
|---|---|---|---|---|---|---|
| **ECG60** | 形式联评 JSON | `owner-observed-ECG60-R5-55d99a50/formal-ECG60-review-private.json` | `1c8f98037cfba197b0ecc15c5bee2d5db4af8a24391e57f2bce8a55f209b08b3` | `ECG60-WINDOW-01/actual-review.json` | `c1f6dfe92286c30ea35a2e9c42682f51747c2f5076e0616e9157dd9461ab5631` | 剔除私有路径与会话密钥，指标 100% 相同 |
| **ECG60** | 硬件停止状态 | `owner-observed-ECG60-R5-55d99a50/joint/C_STOP_SOURCE_STATE.json` | `050f28a2a07c33cf6a1f1fa68c2921aeb9cf186bfcb9607f240fc858b4fe2bc1` | `ECG60-WINDOW-01/session-timeline.json` | `24dae2e5cb7683882c89592939f64192eaa9036c9dfccef9de355805dbb4f257` | 镜像 `tick=420563, armed_at=563` |
| **TEMP** | 形式联评 JSON | `owner-observed-TEMP_OBJECT-R5-6104c2e6/formal-TEMP_OBJECT-review-private.json` | `18da0b1ee89b6f50d04f42fa5fa17288ce2baabcb67d25f3fc449f1d92b9a4eb` | `TEMP_OBJECT-WINDOW-01/actual-review.json` | `6fc3ec9f963fcc1caa03cc3e54c5a9727998b78b941410a8058972d7001f737f` | 300 元素数组聚合为 min/max/total 统计对象 |
| **TEMP** | 硬件停止状态 | `owner-observed-TEMP_OBJECT-R5-6104c2e6/joint/C_STOP_SOURCE_STATE.json` | `c0fb3ce0e764619468e2195f4b5ff5816999a38f3a388b066cf8e84128f7ff27` | `TEMP_OBJECT-WINDOW-01/broker-backend-wss-proof.json` | `4b2fccdb2f8244ad4e0fc48f25074fae4cf5e6364a851ff66082b755a52e8587` | 镜像 `tick=420901, armed_at=901` |
| **RR15** | 形式联评 JSON | `owner-observed-RR15-R5-5bb61eef/formal-RR15-review-private.json` | `22e050163cf6cf772d9e62c7879b36f0c873c39c31e4bd8f21c51abbc5e64945` | `RR15-WINDOW-01/actual-review.json` | `20e88c85330ed18900c78b23b77a67a2549c8a8979b2284527f3bb5de9af4711` | 剔除私有路径，保留全量判定与 3 项失败项 |
| **RR15** | 硬件停止状态 | `owner-observed-RR15-R5-5bb61eef/joint/C_STOP_SOURCE_STATE.json` | `5c7324f60f64bf50c7ca566e92ba1828f7317f2ba63f0d5718df82e6da1643c7` | `RR15-WINDOW-01/broker-backend-wss-proof.json` | `daa735bdf34ada147f3c4e68be8a82d27c1afac50e7d8c92afcd92b1c28eb972` | 镜像 `tick=420772, armed_at=772` |

---

## 4. 关键操作合规审计结论

1. **单次令牌消费与原子锁定**：全部 7 次尝试均在启动瞬间生成独立的 `authorized-once-private.used` 文件，记录了严格的单调时间戳与授权 SHA256，未发生任何令牌复用。
2. **`B5START` 单次发送原则**：全部 7 次尝试中，监控器与 worker 均严格只发送了一次 8 字节 `B5START\n` 命令，未发生任何原地重发或死循环。
3. **RESET 次数审计勘误**：
   - 尝试 1、2、4、5、6、7 均严格执行了 1 次人工 RESET；
   - **尝试 3 (`owner-observed-TEMP_OBJECT-R5-cff28389`) 在第 37 秒发生了第 2 次 RESET**，属于现场操作偏离。监控器按设计安全捕获到 `G3_C_UNEXPECTED_REBOOT` 并立即熔断退出，未继续执行未受控的正式测试。此项在审计中已正式更正，不再宣称“7 次均严格满足 ≤1 次复位”。
