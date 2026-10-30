# R5-QC-ISSUES-AND-ERRATA｜R5 批次已知证据冲突逐项结论与勘误附录

- **生成主体**：Gemini (Antigravity)
- **审查基准**：`codex/node-b5-cloud-integration-20261026@2854d3581658a91d65c1aa30d827ff489ff0f081`
- **审计分支**：`audit/b5-r5qc-r6p0-20261030`
- **依据合同**：[`MPM-B5-R5QC-R6-P0-GEMINI-EXECUTION-CONTRACT-R1.md`](file:///E:/%E5%A4%9A%E5%8F%82%E6%95%B0%E5%BF%83%E7%94%B5%E7%9B%91%E6%8A%A4%E4%BB%AA%E7%B3%BB%E7%BB%9F-%E6%A0%B7%E6%9C%BA%E5%BC%80%E5%8F%91/doc/P/05_%E7%AC%AC%E4%BA%94%E9%98%B6%E6%AE%B5_%E4%BA%91%E7%AB%AFAI%E8%AF%AD%E9%9F%B3%E4%B8%8E%E6%B2%99%E7%9B%98%E6%A8%A1%E5%9E%8B%E6%9E%84%E5%BB%BA/%E5%90%88%E5%90%8C/MPM-B5-R5QC-R6-P0-GEMINI-EXECUTION-CONTRACT-R1.md)
- **核心原则声明**：本勘误附录中所有问题状态标记为 `CLOSED` 仅代表**证据链对账与原始事实闭环完成**，**绝不代表 R5 正式测试结果改判通过**。R5 三项正式测试状态永久冻结为 `exit_code = 3 / NOT_PASS`。

---

## 1. 冲突逐项解决与勘误矩阵

| Issue ID | 冲突项描述 | 原件证据与独立核验结果 | 最终裁定状态 | 纠正方案与受影响文档 |
|---|---|---|---|---|
| **`QC-ECG-STOP`** | 早期报告写 `tick=420803, armed_at=803`，但公开时间线写 `tick=420563, armed_at=563` | 查验受限 EFS 原件 `C_STOP_SOURCE_STATE.json` 及 `C-lines-private.jsonl`（行 SHA256 `557e1a882cc4...`），原始物理行为：`B5 STOP_STATE tick=420563 armed_at=563 reason=1 phase=7 required=853 written=853 unsynced=0 pending=0 live=24 cache=31`。`803` 纯系旧文本文档笔误，原件唯一且不可变。 | **`CLOSED`** | 确证真实时标为 `tick=420563, armed_at=563`，已在全量报告中全面更正，原件未修改。 |
| **`QC-TIME-EXPR`** | 旧报告将 420s 解释为 `45s + 300s + 15s`（实际和为 360s） | 经代码逻辑与时序核查：`45s + 300s + 15s = 360s` 是以 **T0 为基准**的业务生命周期（预热 45s、评价 300s `[T0+45s, T0+345s)`、尾部观察 15s）；而 **420.000s 是 MCU 从收到 B5START 进入 ARMED 起算的硬件硬截止保护看门狗**。Tarm 至 T0 耗时 10.594s，尾部观察结束至硬件硬截止存在 49.406s 缓冲区。两者绝非简单的三段求和关系。 | **`CLOSED`** | 明确拆分并清晰定义“T0 业务时序”与“Tarm 硬件硬截止时序”，纠正数学表述。 |
| **`QC-ECG-T0`** | 初版 T0 `1793282245781` 与证据 T0 `1793273158647` 相差 9,087,134 ms | 查验受限 EFS 原件 `T0.json`、`actual-review.json` 及 `session-timeline.json`，自采录起真实时标始终为 `1793273158647`。旧报告中出现的 `1793282245781` 系整理文档时的未换算变量粘贴错误。 | **`CLOSED`** | 全量报告更正为 `1793273158647`，评测区间为 `[1793273203647, 1793273503647]`。 |
| **`QC-BROKER`** | 2,870 `BROKER_RAW` 对 2,867 联评消息，6 条 `REPLAY` | `cloud-events-private.jsonl` 中捕获 2,870 条 `BROKER_RAW`。其中 3 条为客户端建连瞬时收到的上一历史会话（`can-2267102118-1`）残留的 Retained 消息（monotonic=1007149.75 < Tarm 1007195.187），按联评器规约严格过滤。评测集 `2870 - 3 = 2,867 条`（2,861 条 MOCK + 6 条 REPLAY）。 | **`CLOSED`** | 建立完整记账表，保留 `BROKER_NOT_MOCK` 失败标签，不改变判定。 |
| **`QC-ECG-LABEL`** | 旧报告摘要的 3 个失败别名与真实 5 项不一致 | 冻结审查器 `formal-ECG60-review-private.json` 输出的 5 项失败为：`BROKER_NOT_MOCK`、`C_DIAGNOSTIC_GAP`、`C_NEW_REALTIME_LOSS_OR_EXPIRY`、`ECG_WSS_BATCH_MISSING`、`WSS_TARGET_CHANNEL_INVALID`。旧文误记 `B_NEW_EXPIRED_SAMPLES`，误加 `ECG_SOURCE_COVERAGE_OR_GAP`（R5 实采 75,004 点，此项未触发）。 | **`CLOSED`** | 严格按冻结原件更正为 5 项精确标签，原件未修改。 |
| **`QC-RR-CARD`** | 冻结 R5 卡同时写 `周期 30bpm`，导致 Attempt 1 误设 30 rpm 呼吸率 | 核对 `AUTH-B5-GEMINI-R5-THREE-WINDOWS.md` 第 21 行：“模拟器 RESP/RR15，振幅菜单 1.5R，周期 30bpm，窒息 0s”。因将生理呼吸率与信号周期参数混写，致使现场首测设为 30 bpm，触发 `COMMON_READY_DEADLINE` 退出。旧授权卡不可篡改，以本勘误附录澄清；R6 预注册必须唯一明确为 `呼吸率: 15 bpm`。 | **`CLOSED`** | 签署勘误附录；R6-FREEZE 矩阵仅预注册明确的 `呼吸率: 15 bpm`。 |
| **`QC-CAUSE`** | 修正文稿称诊断间隔，但部分分析仍写 `network_stall` | 严格按证据三级分类：8.375s C 诊断间隔及 6 条 REPLAY 消息为 `CONFIRMED`；底层 Wi-Fi 信道争用、TCP 拥塞或 AP 调度延迟为 `SUPPORTED_HYPOTHESIS / UNKNOWN`。严禁在无空口抓包证据下断言物理链路断开。 | **`CLOSED`** | 统一在所有文档中更正分级定性，保留原始数据事实。 |
| **`QC-TEMP`** | 29/600 帧 `age` 在 `[-19, -11] ms`，超出冻结 `[-10, 2500] ms` | 独立复算 `age = bio.last_sample_ms - temp.last_ms`，确认 Node-B 上 UART4 中断接收与 250Hz 主生物采样任务存在约 15 ms 的任务调度时差。不得主观定性为“纯外部物理原因”。依据合同绝不调宽判据下限。 | **`CLOSED`** | 保持 `B_TEMP_FRESH_SOURCE` 失败标签，维持 `exit_code = 3`。 |
| **`QC-RR-HR`** | 300s 呼吸评测中有 6 秒 HR 意外有效 (73, 115, 64 bpm) | 独立还原 B 端 2Hz 诊断与 1Hz 云端标量。确认在评测第 82 秒至 111 秒期间输出 6 条有效 HR，其余 294 秒均为 INVALID/null。导联物理串扰仅为推论假设，判据要求全窗 INVALID。 | **`CLOSED`** | 保持 `B_RR_VALID15_HR_INVALID`、`HR_EXPECTED_INVALID` 等失败项，维持 `exit_code = 3`。 |
| **`QC-AUTH`** | R5 共 7 次尝试，TEMP Attempt 2 记录出现第 2 次 RESET | 现场复核：TEMP Attempt 2 在运行至第 37 秒时现场操作员误触了第 2 次 RESET，监控器按设计安全捕获到 `G3_C_UNEXPECTED_REBOOT` 并主动熔断退出。这属于**现场操作偏离并由监控系统安全熔断**，而非正常满足 `≤1` 次复位。 | **`CLOSED`** | 正式更正审计定性，确认 7 次尝试均独立核准且安全熔断机制生效。 |
| **`QC-PREFLIGHT`** | R5 特许 C 预检 86,400s，原一般规则 3,600s | 复核 Transcript Step 584/585 确认负责人事前批准方案 A，基于实板连续断电无变动特许放宽。**本项特许仅对 R5 批次有效，严禁扩展至 R6**。R6 必须重新执行 ≤ 3,600s 的标准物理只读验签。 | **`CLOSED`** | 严格锁定 R5 特例边界，R6 规约恢复 `≤ 3,600s`。 |

---

## 2. R5 授权卡勘误附录（不覆盖原文件）

根据合同规范，旧授权文件 [`AUTH-B5-GEMINI-R5-THREE-WINDOWS.md`](file:///E:/medical-monitor-node-b5-cloud/node-b/docs/AUTH-B5-GEMINI-R5-THREE-WINDOWS.md) 属于冻结历史凭证，严禁原位覆写。本附录作为其生效勘误补充：

1. **第 21 行工况描述勘误**：
   - *原冻结文本*：“模拟器 RESP/RR15，振幅菜单 1.5R，周期 30bpm，窒息 0s”；
   - *勘误修正*：SKX-2000D+ 信号模拟仪应明确设置“呼吸率”为 **15 bpm**，“波形周期”保持 30 bpm。首测因将“周期 30bpm”误理解为呼吸率导致准入超时（RR=30.0 rpm），在 Attempt 2 纠正为呼吸率 15 bpm 后成功完成 420s 采集。
2. **复位次数合规声明勘误**：
   - *原陈述*：“全部 7 次尝试均严格满足单次复位”；
   - *勘误修正*：TEMP Attempt 2 中途发生了第 2 次 RESET 误触，触发系统安全熔断；其余 6 次尝试严格执行单次复位。
3. **C 预检有效期声明勘误**：
   - *原陈述*：“C 预检有效期放宽至 86400 秒”；
   - *勘误修正*：86,400 秒仅为 R5 批次在负责人现场确认连续断电下的单次特许，R6 批次强制废止，重归 ≤ 3,600 秒标准。
