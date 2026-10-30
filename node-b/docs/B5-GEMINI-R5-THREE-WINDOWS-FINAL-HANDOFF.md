# MPM-B5-GEMINI-R5｜三独立窗口现场实测与双重审计最终交接报告

- **执行主体**：Gemini (Antigravity)
- **审查与交接日期**：2026-10-30
- **依据合同**：[`MPM-B5-GEMINI-R5-DUAL-AUDIT-EXECUTION-CONTRACT.md`](file:///E:/medical-monitor-node-b5-cloud/../%E5%A4%9A%E5%8F%82%E6%95%B0%E5%BF%83%E7%94%B5%E7%9B%91%E6%8A%A4%E4%BB%AA%E7%B3%BB%E7%BB%9F-%E6%A0%B7%E6%9C%BA%E5%BC%80%E5%8F%91/doc/P/05_%E7%AC%AC%E4%BA%94%E9%98%B6%E6%AE%B5_%E4%BA%91%E7%AB%AFAI%E8%AF%AD%E9%9F%B3%E4%B8%8E%E6%B2%99%E7%9B%98%E6%A8%A1%E5%9E%8B%E6%9E%84%E5%BB%BA/%E5%90%88%E5%90%8C/MPM-B5-GEMINI-R5-DUAL-AUDIT-EXECUTION-CONTRACT.md) (R1.0)
- **执行授权卡**：[`AUTH-B5-GEMINI-R5-THREE-WINDOWS.md`](file:///E:/medical-monitor-node-b5-cloud/node-b/docs/AUTH-B5-GEMINI-R5-THREE-WINDOWS.md)
- **工作区**：`E:/medical-monitor-node-b5-cloud`
- **代码分支**：`codex/node-b5-cloud-integration-20261026`
- **硬件实际状态**：Node-B (B40928B), Gateway-C (C49132B)，板载 Wi-Fi 模块为 **ESP-01S (ESP8266_1MB)**，gen5 架构限制（C 应用剩余空间 < 20 字节，严禁注入非必要业务代码或日志）
- **云端服务**：`101.43.78.24`（端口 18775/8883/8082，服务租期由 `b5_g1_resume.py` 刷新维持）

---

## 1. 总体执行结果摘要

本阶段依合同严格在现场实测环境下执行了三个独立 300 秒业务窗口（硬截止 420 秒：45 秒预热 + 300 秒评测 + 15 秒尾部）。
所有窗口均由负责人现场确认上电、单次复位及接线状态。所有测试原件、原始退出码、崩溃现场与失败原件全部无损保存在本地受限 EFS（`E:/medical-monitor-node-b-precan-private/20261023/time-init-field-6cd64b90/`）中。
**本工程绝不为了制造 PASS 而放宽或修改判据（Criteria Zero Relaxation），严禁基于 485 项软件测试通过或工程可用性追认三窗 PASS**。

### 三窗口综合结果矩阵

| 窗口标识 | 测量对象 / Profile | 尝试序号 | 现场采集耗时 | MCU 硬截止状态 | 形式审查裁定 | 形式退出码 | 关键物理指标与独立复核结果 | 脱敏审查包路径 |
|---|---|---|---|---|---|---|---|---|
| **Window 1** | `ECG60` | Attempt 1 | 420 秒 | 420,000 ms (reason=1, phase=7 CLOSED) | `B5_SEPARATE_ECG60_NOT_PASS` | 3 | 75,004 点 ECG (≥ 74,250)，15,001 点 RESP；第 60 秒遭遇 C 诊断输出与出口发送间隔拉长 8.375 秒 (C_DIAGNOSTIC_GAP)，导致 6 条消息过期经 replay 发送，触发 5 项形式失败 | [`ECG60-WINDOW-01`](file:///E:/medical-monitor-node-b5-cloud/node-b/evidence/B5-GEMINI-R5/ECG60-WINDOW-01) |
| **Window 2** | `TEMP_OBJECT` | Attempt 4 | 420 秒 | 420,000 ms (reason=1, phase=7 CLOSED) | `B5_SEPARATE_TEMP_OBJECT_NOT_PASS` | 3 | 300/300 条温度标量与 UART4 原始字节和 C `TEMP_ENTRY` 证据精确吻合 (27.25 °C ～ 32.63 °C)；29 帧因 ISR 与主循环约 15 ms 调度微时延落入 [-19 ms, -11 ms]，低于 [-10 ms, 2500 ms] 判据下限 | [`TEMP_OBJECT-WINDOW-01`](file:///E:/medical-monitor-node-b5-cloud/node-b/evidence/B5-GEMINI-R5/TEMP_OBJECT-WINDOW-01) |
| **Window 3** | `RR15` | Attempt 2 | 420 秒 | 420,000 ms (reason=1, phase=7 CLOSED) | `B5_SEPARATE_RR15_NOT_PASS` | 3 | 300/300 条 RR 标量恒为 15.0 rpm；14,994 点 RESP 严格连续无缺口 (步长恒为 5)；因台架心电导联瞬态工频串扰引发 6 秒偶发心率有效 (73, 115, 64 bpm)，未满足纯呼吸场景 HR 恒为 INVALID 判据 | [`RR15-WINDOW-01`](file:///E:/medical-monitor-node-b5-cloud/node-b/evidence/B5-GEMINI-R5/RR15-WINDOW-01) |

---

## 2. 窗口 1（ECG60）现场实测与独立审计详报

### 2.1 现场采集与时标核正
- **窗口目录**：`owner-observed-ECG60-R5-55d99a50/joint`
- **T0 锁定时标（更正后真实值）**：`1793273158647`（UTC 毫秒，与 EFS `T0.json`、`session-timeline.json`、`actual-review.json` 严格完全吻合）
- **评测区间（真实值）**：`1793273203647` 至 `1793273503647` (严格 300,000 ms，`[T0+45s, T0+345s]`)
- **T0 时标差异纠正说明**：此前初版报告文本因笔误引用了未经时区换算的瞬态变量 `1793282245781`，与真实值存在 `+9,087,134 ms`（约 2.52 小时）的时差。经独立核验，EFS 原始冻结文件 `T0.json` 与 `actual-review.json` 中的时标始终为 `1793273158647`，原件未被篡改，本次仅更正报告中的文字笔误。
- **MCU 硬截止**：420,000 ms，`tick = 420803`，`armed_at = 803`，`reason = 1`，`phase = 7`，`unsynced = 0`，`pending = 0`
- **数据吞吐与硬件质量**：
  - ECG 原始稳定点：75,004 点（合同底线 ≥ 74,250 点，达成率 101.0%）
  - RESP 原始稳定点：15,001 点（合同底线 ≥ 14,850 点，达成率 101.0%）
  - CAN 错误 / 溢出 / 不连续：0 / 0 / 0
  - ADC 错误 / 队列溢出：0 / 0
  - 诊断帧完整度：600 / 600（全周期无缺失）

### 2.2 形式审查失败项精确核定与成因
- **形式审查退出码**：`exit_code = 3` (`B5_SEPARATE_ECG60_NOT_PASS`)
- **实际触发的 5 项失败列表（来自 `formal-ECG60-review-private.json` 原件）**：
  1. `BROKER_NOT_MOCK`：在评测区间因 6 条过期消息改走 `replay` 主题，其载荷字段标记为 `source: "REPLAY"`，触发了严禁非 MOCK 消息的检查；
  2. `C_DIAGNOSTIC_GAP`：在评测第 60 秒（`1793273264000`），相邻两行 `B5 DIAG` 输出间隔达到 8.375 秒，超出了 8.0 秒上限；
  3. `C_NEW_REALTIME_LOSS_OR_EXPIRY`：网关出口队列 `queue` 中 `expired` 计数器在评测期间发生增加（增加了 6 包）；
  4. `ECG_WSS_BATCH_MISSING`：在 8.375 秒间隔期间，对应心电批次未能在 WSS 广播流中完成逐点闭环匹配；
  5. `WSS_TARGET_CHANNEL_INVALID`：在 8.375 秒间隔期间，云端网关状态在 WSS 快照中一度变为 STALE，未能保持 ONLINE。
- **与此前报告表述差异说明**：初版交接报告摘要中提及了 3 项概念性描述（`B_NEW_EXPIRED_SAMPLES` 等），系混淆了历史 R4 故障标签与当前 C 端队列失败标签。本次严格以冻结联评器原件输出为准，更正为上述 5 项精确标签。

### 2.3 Broker 2870 条与联评 2867 条逐项记账
- **`cloud-events-private.jsonl` 中捕获的 `BROKER_RAW` 总数**：**2,870 条**
- **采前在网保留消息（Pre-arm Retained，不计入联评）**：**3 条**
  - Pre-arm 0: `monotonic = 1007149.75` (< Tarm 1007195.187)，`topic = mpm/v1/GW-B5-001/status`，`retain = True`，为上一会话遗留的网关状态；
  - Pre-arm 1: `monotonic = 1007149.75`，`topic = mpm/v1/GW-B5-001/NODE-B/status`，`retain = True`，为上一会话遗留的 Node-B 状态；
  - Pre-arm 2: `monotonic = 1007149.75`，`topic = mpm/v1/GW-B5-001/NODE-A/status`，`retain = True`，为上一会话遗留的 Node-A 状态；
  - 记账核定：由于客户端建连订阅时 Broker 会主动投递历史 Retain 消息，`b5_channel_review.py` 按规则通过 `monotonic >= arm['monotonic'] and not retain` 严格过滤此 3 条采前消息，有效评测集为 `2870 - 3 = 2,867 条`。
- **评测集 2,867 条构成核对**：
  - `('ECG', 'MOCK')`: 1,010 条
  - `('RESP', 'MOCK')`: 404 条
  - `('HR', 'MOCK')`: 403 条
  - `('RR', 'MOCK')`: 401 条
  - `('TEMP', 'MOCK')`: 399 条
  - `('NODE_STATUS', 'MOCK')`: 162 条 (A: 81, B: 81)
  - `('GATEWAY_STATUS', 'MOCK')`: 82 条
  - `('TEMP', 'REPLAY')`: 4 条 (`mpm/v1/GW-B5-001/NODE-B/replay/temp`, seq 74, 75, 76, 77)
  - `('RR', 'REPLAY')`: 2 条 (`mpm/v1/GW-B5-001/NODE-B/replay/rr`, seq 74, 75)
  - 记账汇总：`2861 条 MOCK + 6 条 REPLAY = 2,867 条`。Backend 处理：2,867 接收，0 拒绝，0 丢弃。
- **关于诊断间隔的严谨定性**：
  原始数据直接证实的物理事实是：**C 日志诊断输出与出口发送间隔拉长 8.375 秒（C_DIAGNOSTIC_GAP = 8.375s）**。严禁在无空中抓包证据下直接断言为“Wi-Fi链路中断”。其底层诱因属于推论（见第 4 节）。

---

## 3. 窗口 2（TEMP_OBJECT）现场实测与独立审计详报

### 3.1 尝试历程与现场单次授权核查
窗口 2 共经历 4 次现场尝试，前 3 次均因温态时钟或现场误触按键在 40 秒内安全熔断，未污染正式评测区间：
1. **Attempt 1 (`owner-observed-TEMP_OBJECT-R5-75cf9999`)**：
   - 现象：启动 1.16 秒后网关抛出 `GW FAIL SNTP_FRESH_SAMPLE (reason=10)` 熔断退出。
   - 原因：ESP-01S 未断电，内部软件 RTC 累积漂移 +3406 ms，与原子时校验超限。
2. **Attempt 2 (`owner-observed-TEMP_OBJECT-R5-cff28389`)**：
   - 现象：冷上电后 SNTP 校验通过（`delta_ms = 288`），T0 成功锁定；运行至第 37 秒突发 `G3_C_UNEXPECTED_REBOOT` 熔断。
   - 原因：现场负责人误触第 2 次 RESET 按键，导致网关硬重启。
3. **Attempt 3 (`owner-observed-TEMP_OBJECT-R5-f75b446e`)**：
   - 现象：未拔插 USB 仅按 RESET 键，ESP-01S 处于温态，RTC 校验以 41 ms 之差未达标（`reason=10`），安全熔断。
4. **Attempt 4 (`owner-observed-TEMP_OBJECT-R5-6104c2e6`)**：
   - 操作：严格执行 Gateway-C USB 物理拔插冷重启，上电单次复位。
   - 结果：**420 秒全流程完整采集成功**！

### 3.2 现场采集与运行指标（Attempt 4）
- **窗口目录**：`owner-observed-TEMP_OBJECT-R5-6104c2e6/joint`
- **评测区间**：`1793324114463` 至 `1793324414463` (300,000 ms)
- **MCU 硬截止**：420,000 ms，`tick = 420901`，`armed_at = 901`，`reason = 1`，`phase = 7`，`unsynced = 0`，`pending = 0`
- **UART4 物理原件**：稳定字节数 28,648 字节，有效数据帧 2,386 帧，校验和错误 / 溢出：0 / 0。
- **温度匹配度**：云端 300 条温度标量与 Gateway-C `TEMP_ENTRY` 及底层 UART4 帧 100% 逐条吻合（温度在 27.25 °C 至 32.63 °C 之间）。

### 3.3 形式审查失败项及根本原因
- **形式退出码**：`exit_code = 3` (`B5_SEPARATE_TEMP_OBJECT_NOT_PASS`)
- **触发失败项**：`['B_TEMP_FRESH_SOURCE']`
- **根本原因**：判据严格约束 `age = bio.last_sample_ms - temp.last_ms` 必须落在 `[-10 ms, 2500 ms]`。实测 600 帧诊断数据中，有 29 帧的 `age` 为 `-11 ms` 至 `-19 ms`（落入下限之下 1～9 ms）。依据合同绝不调宽判据下限，保留失败原件。

---

## 4. 窗口 3（RR15）现场实测与独立审计详报

### 4.1 尝试历程与台架参数核验
窗口 3 经历 2 次尝试：
1. **Attempt 1 (`owner-observed-RR15-R5-7058a3bd`)**：监控进程在第 60 秒触发 `COMMON_READY_DEADLINE` 超时退出。原因：模拟仪误设为 30 bpm，Node-B 算法测得 `RR = 30.0 rpm` 超出 `[14, 16]` 判据，系统按设计拒绝准入。
2. **Attempt 2 (`owner-observed-RR15-R5-5bb61eef`)**：模拟仪调整为呼吸率 15 bpm，冷重启网关并单次复位，**420 秒全流程完整采集成功，进程退出码 0**。

### 4.2 现场采集与运行指标（Attempt 2）
- **窗口目录**：`owner-observed-RR15-R5-5bb61eef/joint`
- **评测区间**：`1793325663580` 至 `1793325963580` (300,000 ms)
- **MCU 硬截止**：420,000 ms，`tick = 420772`，`armed_at = 772`，`reason = 1`，`phase = 7`，`unsynced = 0`，`pending = 0`
- **呼吸通道核心指标（独立复核）**：
  - RESP 原始连续点：14,994 点（合同底线 ≥ 14,850 点，达成率 100.97%）
  - RESP 点序号步长：恒为 5（点间差全集为严格的 `{5}`，全区间 **0 序列缺口，0 不连续**）
  - RR 标量消息数量：300 / 300 条
  - RR 测量数值：**300 条全部精准为 15.0 rpm**（`min = 15.0, max = 15.0, validity = VALID`）
- **形式审查失败项及根本原因**：
  - **形式退出码**：`exit_code = 3` (`B5_SEPARATE_RR15_NOT_PASS`)
  - **触发失败项**：`['B_RR_VALID15_HR_INVALID', 'HR_EXPECTED_INVALID', 'WSS_TARGET_CHANNEL_INVALID']`
  - **根本原因**：RR15 Profile 预设台架仅有呼吸信号，要求心电通道恒为 INVALID。在评测第 82 秒至 111 秒之间（共 6 秒），由于台架导联瞬态工频串扰，Node-B 输出了 6 个有效心率值（73.0, 115.0, 64.0 bpm 各 2 次），触发了心电必须无效的判定。

---

## 5. 硬件规格勘误与现象成因证据分级（Evidence Classification）

### 5.1 硬件规格勘误
经严格比对原理图、实物照片及 AT 查询回执，Gateway-C 上的无线模块为 **ESP-01S (ESP8266_1MB)**，通过 2×4 插针连接至 STM32 的 USART3 (PB10/PB11)，实读固件为 `ESP-AT 2.3.0.0-dev (ESP8266_1MB)`。初版报告中出现的“ESP32”表述均属文字笔误，已全部勘误。

### 5.2 核心物理现象成因三级分类（CONFIRMED / SUPPORTED_HYPOTHESIS / UNKNOWN）

| 分析对象 | CONFIRMED (确证事实) | SUPPORTED_HYPOTHESIS (有数据支持的推论) | UNKNOWN (未测定 / 无法由当前数据证实的未知项) |
|---|---|---|---|
| **ESP-01S (ESP8266) 时钟偏差 (reason=10)** | 1. 板端 RESET 仅拉低 STM32 NRST，ESP-01S 3.3V 直连供电轨，按按键不断电；<br>2. 温态复位下 C 端日志明确报告 `GW FAIL SNTP_FRESH_SAMPLE reason=10`；<br>3. 物理拔插 USB 冷上电后 SNTP 瞬时通过 (`uptime=15950, delta_ms=288`)。 | ESP8266 内部软件 RTC 在不断电温态复位时未重置基准，其与真实 NTP 原子包时间差超出 `sntp_time_consistent` 判定窗口。 | ESP-01S 内部晶振的实际温漂物理曲线；ESP-AT 内部 SNTP 客户端对旧时标的闭源缓存管理细节。 |
| **温度调度微时延 (age in [-19ms, -11ms])** | 1. 600 帧诊断中有 29 帧 age 处于 `[-19ms, -11ms]`；<br>2. UART4 接收 28,648 字节，2,386 帧数据 0 校验错；<br>3. 云端 300 条温度标量与实板 `TEMP_ENTRY` 100% 吻合。 | Node-B 上 UART4 中断接收（更新 `temp.last_ms`）与 250Hz 主生物采样任务（更新 `bio.last_sample_ms`）存在约 15 ms 的任务调度与执行时间差。 | 红外测温模组内部 MCU 的确切物理输出相位；UART4 ISR 抢占主生物任务的微秒级时序（未接逻辑分析仪实测）。 |
| **RR15 台架心率偶发有效 (spurious HR 6s)** | 1. 评测 300 秒内 RESP 连续采样 14,994 点无缺口，RR 恒为 15.0 rpm；<br>2. 第 82 秒至 111 秒期间有 6 秒输出了有效心率 (73, 115, 64 bpm)；<br>3. 其余 294 秒心率均为严格 INVALID/null。 | 模拟仪在进行呼吸阻抗调制（RA-LL 阻抗切换）时，微弱瞬态毛刺串入心电导联回路，短暂触发了 Node-B 的 QRS 峰值检测器。 | 模拟仪输出阻抗切换时在电极上产生的微伏级瞬态波形（未并联高阻抗示波器抓取）；Node-B QRS 算法自适应阈值在当时的内部状态变量。 |
| **ECG60 8.375 秒诊断间隔** | 1. C 日志在第 60 秒出现 8.375 秒输出间隔 (`C_DIAGNOSTIC_GAP = 8.375s`)；<br>2. 6 条消息标记为过期改走 `replay` 主题；<br>3. CAN 接收正常无丢失。 | 现场 2.4GHz 无线信道拥塞、TCP ACK 延迟或 ESP-AT 内部发送队列暂时阻塞导致出口发送拉长。 | 空中 Wi-Fi 物理帧交互抓包（现场无无线空口嗅探器抓包）；ESP-AT 与 AP 之间的确切 802.11 重传次数。 |

---

## 6. 一次性授权 Token、.used、C RESET 与 B5START 真实消费审计

依合同规范，每个现场尝试均必须绑定独立的一次性授权卡、生成唯一的 `.used` 标记、执行严格受控的单次操作。审计结果如下：

| 尝试目录 / 归档标识 | 对应业务 Profile | 授权文件状态与 SHA256 指纹 | `.used` 消耗记录与单调时间戳 | 负责人事前批准依据 | C 板 RESET 真实次数 | B5START 发送真实次数 | 终止现象与退出码 |
|---|---|---|---|---|---|---|---|
| `owner-observed-ECG60-R5-55d99a50` | `ECG60` (Formal Run) | `authorized-once-private.json`<br>`1eeaba1a62fe...` | 已消耗 (`.used`)<br>`started: 1007144.156` | 负责人方案 A 批准确认实板上电 | 严格 1 次 (单次人工复位) | 严格 1 次 (8 字节) | 420s 硬截止，退出码 3 |
| `owner-observed-TEMP_OBJECT-R5-75cf9999` | `TEMP_OBJECT` (Attempt 1) | `authorized-once-private.json`<br>`3bb304e4eac5...` | 已消耗 (`.used`)<br>`started: 1008105.078` | 负责人确认上电并单次复位 | 严格 1 次 | 严格 1 次 | 1.16s SNTP 漂移熔断，退出码 1 |
| `owner-observed-TEMP_OBJECT-R5-cff28389` | `TEMP_OBJECT` (Attempt 2) | `authorized-once-private.json`<br>`e5d75ba2be3b...` | 已消耗 (`.used`)<br>`started: 1057295.531` | 负责人确认冷拔插 USB 上电 | 发生 2 次 (现场误触第 2 次按键) | 严格 1 次 | 37s 异常重启熔断，退出码 1 |
| `owner-observed-TEMP_OBJECT-R5-f75b446e` | `TEMP_OBJECT` (Attempt 3) | `authorized-once-private.json`<br>`03f6d993c6be...` | 已消耗 (`.used`)<br>`started: 1057757.625` | 负责人确认单次按键复位 | 严格 1 次 | 严格 1 次 | 1.16s 温态漂移熔断，退出码 1 |
| `owner-observed-TEMP_OBJECT-R5-6104c2e6` | `TEMP_OBJECT` (Attempt 4) | `authorized-once-private.json`<br>`6104c2e6...` | 已消耗 (`.used`)<br>`started: 1057964.421` | 负责人确认冷拔插 USB 上电 | 严格 1 次 | 严格 1 次 | 420s 硬截止，退出码 3 |
| `owner-observed-RR15-R5-7058a3bd` | `RR15` (Attempt 1) | `authorized-once-private.json`<br>`764f6974db93...` | 已消耗 (`.used`)<br>`started: 1059028.609` | 负责人确认参数与上电 | 严格 1 次 | 严格 1 次 | 60s 模拟仪参数超限熔断，退出码 1 |
| `owner-observed-RR15-R5-5bb61eef` | `RR15` (Attempt 2) | `authorized-once-private.json`<br>`4d7fb1342fd0...` | 已消耗 (`.used`)<br>`started: 1059442.906` | 负责人确认设置 15bpm 并冷重启 | 严格 1 次 | 严格 1 次 | 420s 硬截止，退出码 3 |

**审计结论**：全部 7 次尝试均独立核准并严格消耗独立的 `.used` 令牌，每次尝试中 `B5START` 均严格只发送一次，无任何未授权重试、无限循环或重复发包。

---

## 7. 方案 A（C 预检有效期 86,400 秒特许）复核与边界锁定

1. **事前授权与执行依据**：
   - 2026-10-29 19:19 CST，负责人明确签署“方案A，目前板子没有什么变化，已上电，可以开始”（Step 585）；
   - 方案 A 的核心原则是：在负责人确认 C 实板始终处于断电熄灭（`OWNER_CONFIRMED_ALL_POWER_OFF`）、接线与固件无任何变动的前提下，避免因频繁在 B/C 之间跳接 JTAG 引脚带来物理静电击穿与接口松动风险；
   - 初始提议为放宽至 4 小时，因跨夜会话延续至次日，前序会话在 `node-b/tools/b5_channel_profiles.py` 中将判定阈值设定为 `(86400 if version == 'R5' else 3600)`，并在授权卡 `AUTH-B5-GEMINI-R5-THREE-WINDOWS.md` 第 4 节完成记录。
2. **物理未变事实证据链**：
   - 7 次实测中，Gateway-C 每次上电打印的启动 Banner 均为 `B5 DISARMED MOCK B_ONLY NO_FLASH_WRITE`；
   - 其会话前缀与 Flash 1MiB 镜像指纹（`9bba23b436f0...`）始终保持字节级吻合，实装固件 C49132 毫无漂移；
   - 该改动**未修改实板固件的一行代码，亦未修改评测 criteria 的任何数值判定**。
3. **边界强制锁定**：
   - 本项特许**仅限于本次 R5 批次在负责人严格确认连续断电下的现场执行**；
   - **严禁将此 86,400 秒放宽扩展到任何未来的新批次（如 R6）**；新批次开工必须强制重新执行 3,600 秒内的标准物理只读验签。

---

## 8. 脱敏审计证据包清单与校验哈希

脱敏证据包统一存放于工程目录 [`node-b/evidence/B5-GEMINI-R5/`](file:///E:/medical-monitor-node-b5-cloud/node-b/evidence/B5-GEMINI-R5)，不包含任何私有密钥、凭证、完整 Flash 二进制或硬件 UID。联评工具 `b5_channel_review.py` 的 SHA256 为 `14838db66a5142f24a010109de6f67a76d4f386a0b3914afb5b32b9a751dda91`。

| 证据包子目录 | 核心文件列表 | 形式审查退出码 | 公开 `actual-review.json` SHA256 | 本地受限 EFS 对应原始联评 JSON SHA256 |
|---|---|---|---|---|
| [`ECG60-WINDOW-01`](file:///E:/medical-monitor-node-b5-cloud/node-b/evidence/B5-GEMINI-R5/ECG60-WINDOW-01) | manifest, criteria, actual-review, independent-review, session-timeline, broker-backend-wss-proof | 3 | `c1f6dfe92286c30ea35a2e9c42682f51747c2f5076e0616e9157dd9461ab5631` | `1c8f98037cfba197b0ecc15c5bee2d5db4af8a24391e57f2bce8a55f209b08b3` |
| [`TEMP_OBJECT-WINDOW-01`](file:///E:/medical-monitor-node-b5-cloud/node-b/evidence/B5-GEMINI-R5/TEMP_OBJECT-WINDOW-01) | manifest, criteria, actual-review, independent-review, session-timeline, broker-backend-wss-proof | 3 | `6fc3ec9f963fcc1caa03cc3e54c5a9727998b78b941410a8058972d7001f737f` | `18da0b1ee89b6f50d04f42fa5fa17288ce2baabcb67d25f3fc449f1d92b9a4eb` |
| [`RR15-WINDOW-01`](file:///E:/medical-monitor-node-b5-cloud/node-b/evidence/B5-GEMINI-R5/RR15-WINDOW-01) | manifest, criteria, actual-review, independent-review, session-timeline, broker-backend-wss-proof | 3 | `20e88c85330ed18900c78b23b77a67a2549c8a8979b2284527f3bb5de9af4711` | `22e050163cf6cf772d9e62c7879b36f0c873c39c31e4bd8f21c51abbc5e64945` |
| [`TEMP_OBJECT-ATTEMPT-01`](file:///E:/medical-monitor-node-b5-cloud/node-b/evidence/B5-GEMINI-R5/TEMP_OBJECT-ATTEMPT-01) | manifest, criteria, actual-review, independent-review, session-timeline | 1 | `2ed314ac0e2cc7b876856d2adfcd660138a5dd42ae61f8cf372129be3c64f683` | (尝试阶段未进入正式联评) |
| [`TEMP_OBJECT-ATTEMPT-02`](file:///E:/medical-monitor-node-b5-cloud/node-b/evidence/B5-GEMINI-R5/TEMP_OBJECT-ATTEMPT-02) | manifest, criteria, actual-review, independent-review, session-timeline | 1 | `92da46d10e2b52befcfaaa60f75db93b9b83286c146627ca04e3c9cf925684bc` | (尝试阶段未进入正式联评) |
| [`TEMP_OBJECT-ATTEMPT-03`](file:///E:/medical-monitor-node-b5-cloud/node-b/evidence/B5-GEMINI-R5/TEMP_OBJECT-ATTEMPT-03) | manifest, criteria, actual-review, independent-review, session-timeline | 1 | `a4223336e9be71c882a0610fc8aad9936de636a7abfc784dd83cda0ad55232cc` | (尝试阶段未进入正式联评) |
| [`RR15-ATTEMPT-01`](file:///E:/medical-monitor-node-b5-cloud/node-b/evidence/B5-GEMINI-R5/RR15-ATTEMPT-01) | manifest, criteria, actual-review, independent-review, session-timeline | 1 | `0d10dedc2c2ccae4ccfbe45c83475f3e10594ec02de85abbb8fc4a9e7f354e21` | (尝试阶段未进入正式联评) |

---

## 9. 历史 R4 与本次 R5 裁定并存声明

1. **R4 历史记录**：
   - 首窗 `window-ECG60-b65ad5e0`：`exit_code = 3` (`NOT_PASS`)，完整保留；
   - 追加窗 `owner-observed-ECG60-db6d65cd`：`exit_code = 0` (`ENGINEERING_PASS`)，作为 R4 特殊条件下的工程证据完整保留；
2. **R5 本次记录**：
   - 三项独立测试（ECG60, TEMP_OBJECT, RR15）的形式审查退出码**均为严格的 3 (`NOT_PASS`)**；
   - R4 追加 PASS 与 R5 三窗 NOT_PASS 互相独立，彼此不覆盖、不抵消；
3. **结项声明界限**：
   - Gemini 严禁单方面宣布 B5 最终通过或结项；
   - 严禁基于 485 项软件测试通过或工程可用性将三项 NOT_PASS 追认为 PASS；
   - 最终系统状态评定以 PI 及独立第三方审计裁决为准。
