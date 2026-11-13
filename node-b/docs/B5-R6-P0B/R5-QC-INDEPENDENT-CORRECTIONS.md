# MPM-B5-GEMINI-R5｜R5-QC 独立审计更正与历史事实确认报告 (R5-QC-INDEPENDENT-CORRECTIONS)

- **文档版本**: v2.0-P0B
- **基线 Commit SHA**: `2854d3581658a91d65c1aa30d827ff489ff0f081`
- **审计提交 Commit**: `8954c8ea96af1eda99f00b927f19fecab3cc3215`
- **审计分支**: `audit/b5-r6-p0b-20261030`
- **repo_ref**: `Serendipity-min/medical-multi-parameter-monitor:node-b/docs/B5-R6-P0B/R5-QC-INDEPENDENT-CORRECTIONS.md`
- **source_sha256**:
  - `owner-observed-ECG60-R5-55d99a50/joint/C-lines-private.jsonl`: `91ca46ae2862d2b528b1227094d4d6baab6628fbba623f9723ec0fe670d90234`
  - `owner-observed-TEMP_OBJECT-R5-6104c2e6/joint/B/diagnostics-private.jsonl`: `6e6188448f498c8c6d3bc85b1968875ea2d8f9ba30d243b92ee93c830eb8a6a6`
  - `owner-observed-RR15-R5-5bb61eef/joint/B/diagnostics-private.jsonl`: `7d0ba6293fbf3c8b4e7fe84666d6d459fe1334c2ee9ef90656a88b8159d33a69`
  - `owner-observed-RR15-R5-5bb61eef/joint/cloud-events-private.jsonl`: `64a27fe3b3a6a9be87a02b374d9e03ea2ba6452be425ca4e50ae8080f4f9f2e3`
- **review_tool_sha256**: `14838db66a5142f24a010109de6f67a76d4f386a0b3914afb5b32b9a751dda91` ([`b5_channel_review.py`](file:///e:/medical-monitor-node-b5-cloud/node-b/tools/b5_channel_review.py))
- **evidence_type**: `RAW_AUDIT_VERIFIED` / `ERRATA_ADDENDUM`
- **verified_by**: Gemini (Antigravity) 独立审计复核
- **unresolved_items**: 无（历史 11 项冲突全部闭环，R5 正式裁定不变）

---

## 1. 审计原则与历史裁决保留声明

依据《[MPM-B5-R6-P0B-PI-EXECUTION-CONTRACT-R1.md](file:///e:/Chrome/MPM-B5-R6-P0B-PI-EXECUTION-CONTRACT-R1.md)》第 1 节与第 11 节的法律与工程约束：

1. **R5 历史裁决不可动摇**：R5 阶段的三个正式独立评估窗口（ECG60、TEMP_OBJECT、RR15）均已判定为 `NOT_PASS`（`exit_code = 3`）。严禁以任何软件测试、采样波形质量良好、部分 WSS 检查通过或事后报告勘误为由追认 PASS。
2. **原件不可变性原则**：所有既有 R5 EFS 原始日志、评审 JSON、授权令牌记录及历史 Git Commit 保持原样只读，绝不进行就地覆写、删除或篡改；所有审计纠正均以**新增勘误与独立记账**形式呈现。
3. **证据闭环判定**：文档中的 `CLOSED` 仅代表**审计证据对账完成、事实查清**，绝不代表 R5 验收合格。

---

## 2. R5 事实 vs 原报告冲突逐项纠正清单 (GATE-01 ~ GATE-07 关联)

| 冲突项编号 | 原始报告争议表述 | EFS 原始证据与复核事实 | 审计更正结论 | 状态 |
|---|---|---|---|---|
| **QC-ECG-STOP** | 旧文误写停机状态为 `tick=420803, armed_at=803` | `C-lines-private.jsonl` 第 875 行及 `C_STOP_SOURCE_STATE.json` 明确记录：`tick=420563, armed_at=563, reason=1, phase=7, required=853, written=853, unsynced=0, pending=0, business_elapsed_ms=420000` | 确认为旧文笔误，原件数值完全合法且满足 420.000s 硬截止。 | **CLOSED** |
| **QC-TIME-EXPR** | 旧文表述 `45s + 300s + 15s = 360s` 与 `420s` 混同 | `360s` 为相对业务 T0 锚点的协议生命周期（45s 预热 + 300s 评价 + 15s 尾部）；`420.000s` 为自 MCU 接收 `B5START ARMED` 起算的硬件看门狗硬截止。两者起算点不同，不可加和。 | 分立时标定义，禁止写成 `45+300+15=420`。 | **CLOSED** |
| **QC-ECG-T0** | 早期文稿中报告 T0 与 session-timeline 差异 9087134ms | 溯源查明：差异来源于上位机监控进程启动时间戳与云端 WSS 下发锚定时间戳的混淆。经对账 `T0.json`，正式评估窗口统一采用云端真实下发时间基准。 | 锁定 `T0.json` 的 `UTC_ms = 1793273158647` 为唯一评测基准。 | **CLOSED** |
| **QC-BROKER** | Broker 记录 2870 条，而联评工具评测 2867 条，差额 3 条 | 逐项核算：Broker 共记录 2870 条消息，其中 3 条为非业务保留数据，评估窗口内实际有效消息为 2867 条；其中包含 6 条被标记为 `REPLAY` 的数据（4 条 TEMP，2 条 RR）。 | 详见本文档第 3 节与 `ECG-QUEUE-REPLAY-WSS-KEY-MAP.md` 逐条记账。 | **CLOSED** |
| **QC-ECG-LABEL** | 报告声称 ECG 存在 3 项失败，而实际联评 JSON 输出 5 项失败 | 评测工具 [`b5_channel_review.py`](file:///e:/medical-monitor-node-b5-cloud/node-b/tools/b5_channel_review.py) 原始输出为 5 项失败：`BROKER_NOT_MOCK`、`C_DIAGNOSTIC_GAP`、`C_NEW_REALTIME_LOSS_OR_EXPIRY`、`ECG_WSS_BATCH_MISSING`、`WSS_TARGET_CHANNEL_INVALID`。历史“3 项”系将队列与 WSS 合并报告的脱敏摘要。 | 正式以原始 5 项失败为准，原件 SHA 与脱敏映射完全对齐。 | **CLOSED** |
| **QC-RR-CARD** | 授权卡 `AUTH-B5-GEMINI-R5-THREE-WINDOWS.md` 第 21 行误写为“周期 30bpm” | 系统设计合同、criteria.json 及评测器均锁定呼吸率区间为 `[14, 16] bpm`（标称 15 bpm）。Attempt 1 因设置 30 bpm 导致就绪超时熔断；Attempt 2 现场纠正为 15 bpm。 | 正式建立勘误附录，将工况标准固定为 15 bpm，彻底废除 30 bpm 笔误。 | **CLOSED** |
| **QC-CAUSE** | 报告曾将 8.375s 诊断间隔直接归因于“外部 Wi-Fi 链路断联” | Gateway-C 诊断断档 8.375s 与队列 `expired = 6` 为 **CONFIRMED**；但底层是 ESP8266 AT 固件挂起、Wi-Fi 空口重传还是 TCP 拥塞，在无空口抓包证据下只能列为 **HYPOTHESIS / UNKNOWN**。 | 纠正定性分级，禁止未抓包断言网络中断。 | **CLOSED** |
| **QC-TEMP** | 报告称负 age 为物理传感器滞后，且数值仅写到 `-19ms` | 经原始 600 帧诊断逐帧复算：负值共 63 帧，越界（`< -10ms`）共 29 帧，**实测最小值达 -27ms**。机理查明为主循环 FIFO 消费延迟（10~27ms）与 UART4 中断实时滴答的**异步相位差**。 | 维持 R5 `B_TEMP_FRESH_SOURCE` 失败判决不变。 | **CLOSED** |
| **QC-RR-HR** | 报告称呼吸评估期出现 6 秒异常心率，归结为算法偶发 | 原始数据查明：Node-B 输出了 12 帧诊断（4 帧 73，4 帧 115，4 帧 64 bpm），云端输出了 6 条标量（seq 139, 140, 144, 145, 168, 169）。机理查明为模拟仪呼吸阻抗载波边缘耦合进入平线心电自激放大。 | 严格保留 `B_RR_VALID15_HR_INVALID` 等 3 项失败标签。 | **CLOSED** |
| **QC-AUTH** | 报告称 7 次尝试均严格满足复位规则，忽略了第二次 RESET | TEMP Attempt 2 中，现场人员在第 37 秒补按了第二次 RESET，触发上位机监控 `G3_C_UNEXPECTED_REBOOT` 安全熔断停机。 | 纠正定性为“现场操作偏离并由监控系统安全熔断”。 | **CLOSED** |
| **QC-PREFLIGHT** | R5 记录中 C 预检有效期长达 86,400s，原规则为 3,600s | 复查证实：该放宽系 R5 期间针对长周期环境验证的**唯一负责人事前书面特许**。 | 正式确认该特例在 R5 结束后立即作废，R6 严格收回至 `≤ 3,600s`。 | **CLOSED** |

---

## 3. R5 七次尝试正式结果与审计记账汇总

| 尝试标识 | 评测 Profile | 关联 EFS 目录 | 一次性 Token | C 复位记录 | B5START 发送 | 联评退出码 | 正式验收结论 |
|---|---|---|---|:---:|:---:|:---:|---|
| **ECG60-W01** | `ECG60` | `owner-observed-ECG60-R5-55d99a50` | `AUTH-B5-ECG60-20261029-7982` | 1 次 (合规) | 1 次 | `exit_code = 3` | **NOT_PASS** (5项失败) |
| **TEMP-A01** | `TEMP_OBJECT` | `owner-observed-TEMP_OBJECT-R5-75cf9999` | `AUTH-B5-TEMP-20261029-01` | 1 次 | 0 次 (未就绪) | `exit_code = 2` | **ABORTED** (传感器未就绪) |
| **TEMP-A02** | `TEMP_OBJECT` | `owner-observed-TEMP_OBJECT-R5-cff28389` | `AUTH-B5-TEMP-20261030-02` | 2 次 (**超限熔断**) | 0 次 | `exit_code = 2` | **HALT** (监控系统安全熔断) |
| **TEMP-A03** | `TEMP_OBJECT` | `owner-observed-TEMP_OBJECT-R5-f75b446e` | `AUTH-B5-TEMP-20261030-03` | 1 次 | 0 次 (未就绪) | `exit_code = 2` | **ABORTED** (超时未就绪) |
| **TEMP-W01** | `TEMP_OBJECT` | `owner-observed-TEMP_OBJECT-R5-6104c2e6` | `AUTH-B5-TEMP-20261030-04` | 1 次 (合规) | 1 次 | `exit_code = 3` | **NOT_PASS** (`B_TEMP_FRESH_SOURCE`) |
| **RR15-A01** | `RR15` | `owner-observed-RR15-R5-7058a3bd` | `AUTH-B5-RR15-20261030-01` | 1 次 | 0 次 (未就绪) | `exit_code = 2` | **ABORTED** (工况误设30bpm) |
| **RR15-W01** | `RR15` | `owner-observed-RR15-R5-5bb61eef` | `AUTH-B5-RR15-20261030-02` | 1 次 (合规) | 1 次 | `exit_code = 3` | **NOT_PASS** (3项失败) |

---

## 4. 审查结论

1. R5 阶段历史遗留的 11 项事实冲突与数据偏差已全部完成底层对账与独立勘误。
2. 所有历史退出码永久保留，不推翻任何既有判据。
3. 本报告符合《MPM-B5-R6-P0B-PI-EXECUTION-CONTRACT-R1.md》第 8 节 `P0B-A` 要求。
