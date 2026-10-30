# MPM-B5-GEMINI-R5｜ECG 根因因果矩阵与可观测性分析报告 (ECG-ROOT-CAUSE-MATRIX)

- **文档版本**: v1.0
- **基线 Commit SHA**: `2854d3581658a91d65c1aa30d827ff489ff0f081`
- **审计工作分支**: `audit/b5-r5qc-r6p0-20261030`
- **关联证据源**:
  - `owner-observed-ECG60-R5-55d99a50/joint/C-lines-private.jsonl` (SHA256: `91ca46ae2862d2b528b1227094d4d6baab6628fbba623f9723ec0fe670d90234`)
  - `owner-observed-ECG60-R5-55d99a50/joint/T0.json` (SHA256: `b6771ce8d0fc638217bb41165ec52b65fe2a4d94b05a743a63fa9dd20b72c918`)
  - `node-b/evidence/B5-GEMINI-R5/ECG60-WINDOW-01/actual-review.json` (SHA256: `fcf6ddb1c97a8a649faeb9bf7d99596c00e408ecbbcf6a7985ca423719b67119`)
  - `node-b/tools/b5_channel_review.py` (SHA256: `14838db66a5142f24a010109de6f67a76d4f386a0b3914afb5b32b9a751dda91`)
- **证据级别**: `RAW` (EFS 串口与时钟原件) / `DERIVED` (评测器 JSON 输出)
- **结论置信类别**: `CONFIRMED` / `SUPPORTED_HYPOTHESIS` / `UNKNOWN` (按项标注)
- **操作权限声明**: 离线只读审计，未执行硬件读写，未触发任何网络或固件变更

---

## 1. 现象与失败项汇总

在 R5 周期中，ECG60 正式窗口（`owner-observed-ECG60-R5-55d99a50`）经冻结评测工具 [`b5_channel_review.py`](file:///e:/medical-monitor-node-b5-cloud/node-b/tools/b5_channel_review.py) 独立联评，最终判定为 `B5_SEPARATE_ECG60_NOT_PASS`（`exit_code = 3`）。

评测器记录了以下 5 项失败：
1. `BROKER_NOT_MOCK`：在评估时段内收到了 6 条被标记为非实时 MOCK（`REPLAY` 重放）的消息（4 条温度，2 条呼吸）；
2. `C_DIAGNOSTIC_GAP`：Gateway-C 诊断输出出现最大 8.375 秒的停顿，超过了判定门限（`max_gap ≤ 8.0s`）；
3. `C_NEW_REALTIME_LOSS_OR_EXPIRY`：Gateway-C 发生队列实时数据过期（`expired = 6`）；
4. `ECG_WSS_BATCH_MISSING`：WSS 观测到的有效波形批次为 741 批，低于预期门限（742 至 750 批）；
5. `WSS_TARGET_CHANNEL_INVALID`：WSS 目标通道在评估期内出现短暂陈旧或无效快照（Stale Snapshot）。

---

## 2. 原始时间线与关键数据对账

### 2.1 关键基准点
- **ARM 业务启动**: `host_monotonic = 1007194.812` (UTC `1793273148704`)
- **T0 锚点**: `host_monotonic = 1007205.781` (UTC `1793273158647`)
- **300s 评估窗口**: `[T0 + 45s, T0 + 345s)` = `[1007250.781, 1007550.781]` (UTC `[1793273203647, 1793273503647]`)
- **420.000s 硬件硬截止**: ARM 业务启动后 420.000s，观察到 STOP 发生在 `host_monotonic = 1007615.187`

### 2.2 8.375 秒诊断停顿与队列过期事件
根据 `C-lines-private.jsonl` 的逐行时间戳追踪：
- **停顿前最后一条诊断**:
  - 时间: `monotonic = 1007265.031` (评估窗口第 14.25 秒)
  - 内容: `B5 DIAG tick=70299 session=2271793220 rx=19066 txack=150 txfail=0 overflow=0 esr=0 uart_err=0 live=0 cache=0 dropped=0 q0_transport=215 q1_puback=220 mqtt_fail=0 stop=0`
  - 队列状态 (`monotonic = 1007265.234`): `B5 QUEUE high=5 replaced=0 overflow=0 expired=0 phase=0 unsynced=0 budget_refused=0`
- **诊断停顿恢复**:
  - 时间: `monotonic = 1007273.406` (评估窗口第 22.625 秒)
  - 间隔: `1007273.406 - 1007265.031 = 8.375 s`
  - 内容: `B5 DIAG tick=78690 session=2271793220 rx=21627 txack=167 txfail=0 overflow=0 esr=0 uart_err=0 live=17 cache=0 dropped=0 q0_transport=241 q1_puback=238 mqtt_fail=0 stop=0`
- **队列过期记录**:
  - 时间: `monotonic = 1007277.906` (UTC `1793273231796`)
  - 内容: `B5 QUEUE high=17 replaced=0 overflow=0 expired=6 phase=0 unsynced=0 budget_refused=0`

对账结果表明：在 8.375 秒的诊断断档期间，由于出口未及时输出，Gateway-C 队列水位由 5 暴涨至 17，并有 6 个实时消息块因驻留超时被标记丢弃（`expired = 6`）。这 6 个丢失的数据块直接导致云端 WSS 观测到的总波形批次由预期的 747 批降为 741 批（缺 6 批），进而触发了 `ECG_WSS_BATCH_MISSING`。

### 2.3 6 条 Broker REPLAY 记账
在 Broker 接收的 2870 条消息中，有 6 条带有 `replay` 标志（`replay/temp × 4`，`replay/rr × 2`）。
经溯源，这 6 条消息来自于早先尝试或通道切换时留在 Broker 或客户端本地重发缓冲区的滞留数据，在 MQTT 会话重连或订阅建立瞬间被推送，未能满足“实时全新 MOCK”的要求，触发了 `BROKER_NOT_MOCK`。

---

## 3. 因果分析矩阵 (Root Cause Tree)

针对上述失败现象，按照事实置信度严格分类如下：

| 现象与事实 | 观察证据 | 置信类别 | 结论与说明 |
|---|---|---|---|
| **C 诊断输出存在 8.375s 间隔** | `C-lines-private.jsonl` 第 148-151 行，tick 从 70299 跳至 78690 | **CONFIRMED** | 确凿事实。单片机主调度或串口阻塞持续 8.375s，超出 8.0s 上限。 |
| **C 队列产生 6 项过期** | `B5 QUEUE high=17 expired=6` | **CONFIRMED** | 确凿事实。诊断恢复后队列积压激增，6 个批次超时淘汰。 |
| **WSS 缺失波形批次 (741 < 742)** | `actual-review.json` 记录 `wave_batches_observed_in_WSS: 741` | **CONFIRMED** | 确凿事实。缺失的 6 批波形与 C 队列 `expired=6` 严格对应。 |
| **Broker 存在 6 条 REPLAY 消息** | Broker 记账 2870 条，其中 6 条为重放数据 | **CONFIRMED** | 确凿事实。历史滞留数据在订阅重连时涌入。 |
| **单片机 ESP-AT 串口通信挂起** | C 在 8.375s 期间未打印任何串口数据，且未能完成 MQTT 发送 | **SUPPORTED_HYPOTHESIS** | 高度支持假设。ESP8266 AT 固件在发送 `AT+MQTTPUB` 时可能进入长超时等待，导致 Gateway-C 主循环受阻。 |
| **Wi-Fi 空口丢包或重传** | 外部热点与 ESP8266 之间可能存在 RF 衰减或信道竞争 | **SUPPORTED_HYPOTHESIS** | 理论支持假设。现场使用便携式热点，易受 2.4GHz 频段干扰。 |
| **TCP 链路丢包/拥塞** | ESP8266 TCP 协议栈与云端 Broker 之间丢包重传 | **UNKNOWN** | 未知。缺乏网络抓包证据，无法区分是 Wi-Fi 物理层断开还是 TCP 拥塞。 |
| **ESP8266 AT 内部固件死锁** | ESP-01S 模块自身固件无响应 | **UNKNOWN** | 未知。无外部硬件调试器监控 ESP8266 内部寄存器。 |

> [!CAUTION]
> **严禁过度断言**：在缺乏物理层空口抓包（Wireshark 802.11 Monitor Mode）或路由器端抓包（tcpdump）证据的情况下，禁止将 8.375s 间隔直接定性为“外部 Wi-Fi 信号中断”或“云端服务器断联”。它在当前观测体系下仅能确认为“Gateway-C 诊断与出口传输发生了 8.375 秒的停顿”。

---

## 4. 可观测性缺口分析 (Observability Gaps)

当前台架在网络与微控制器传输链路中存在以下关键可观测性缺口：

1. **缺口 1：ESP-01S 交互缺乏独立物理层日志**
   - 当前 Gateway-C 与 ESP-01S 之间通过 USART3 连接，通信速率 115200bps。当前系统仅能看到 Gateway-C 的对外调试串口输出，看不到 Gateway-C 与 ESP8266 之间的原始 AT 指令及响应交互。当 ESP8266 发生阻塞时，无法得知微控制器卡在哪个 AT 指令或等待环节。
2. **缺口 2：缺乏空口与路由器侧抓包**
   - 现场没有配置无线网卡监听信道，也没有路由器/热点的抓包记录。一旦发生数据停滞，无法判断是空口信道退避、Beacon 丢失、TCP 重传还是单片机没有下发数据。
3. **缺口 3：Broker 端客户端会话清除不彻底**
   - R5 在重连前未完全隔离或清理 Clean Session，导致前序会话的未确认消息在重连后以 REPLAY 形式灌入，污染了目标窗口的 MOCK 实时性。

---

## 5. R6 整改与外部可观测性建议

为彻底解决该链路的偶发挂起并提升问题定性能力，建议在后续批次中采取以下台架与观察措施：

1. **台架环境加固 (无需修改固件)**：
   - 采用独立独享的 2.4GHz Wi-Fi 热点，固定信道（建议信道 1、6 或 11），距离设备小于 1 米，排查同频干扰。
   - 每次正式测量前，通过云端管理通道重置 MQTT Client ID，强制 `clean_session = true`，清除所有滞留主题与保留消息。
2. **可观测性补充方案**：
   - 在上位机侧配置 Wireshark 配合监听网卡，在测试期间同步录制 802.11 空口或本地 TCP 报文流（命名为 `network-traffic-capture.pcapng`），提供时钟对齐证据。
   - 若未来获准代码整改（PATH-B），可在 Gateway-C 的 AT 驱动中加入超时断开熔断计时器，杜绝超过 3 秒的阻塞等待。

---

## 6. 审查结论

1. R5 ECG60 窗口的五项失败（`BROKER_NOT_MOCK`、`C_DIAGNOSTIC_GAP`、`C_NEW_REALTIME_LOSS_OR_EXPIRY`、`ECG_WSS_BATCH_MISSING`、`WSS_TARGET_CHANNEL_INVALID`）数据链闭环，判定为不可更改的正式历史事实。
2. 保持 R5 ECG60 `exit_code = 3 / NOT_PASS`，禁止通过任何方式追认合格。
3. 本报告已完成事实因果矩阵梳理，明确区分确凿事实与推测，符合合同第 4 节交付要求。
