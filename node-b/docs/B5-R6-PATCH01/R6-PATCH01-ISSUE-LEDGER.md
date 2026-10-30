# MPM-B5｜R6-PATCH01 专项技术问题关闭台账 (BLOCK-01 至 BLOCK-08)

> 文档编号：`MPM-B5-R6-PATCH01-LEDGER-V1`  
> 基线提交：`64d07ff33e2fddb46a4a0570d9abfa83adbc3e02`（GitHub `audit/b5-r6-p0b-20261030` 分支）  
> 工作分支：`patch/b5-r6-patch01-20261030`  
> 执行依据：`MPM-B5-R6-P0B-PI-NOGO-PATCH01-R1`  
> 状态：`OFFLINE_PROPOSED_AND_CLOSED_FOR_PI_REVIEW`（实板操作严格保持 NO-GO）  

---

## 1. 阻断项解决总览表

| 阻断项门禁 | 审查发现核心问题 | 闭合策略与实施结果 | 状态 | 关联交付物 |
|---|---|---|---|---|
| `BLOCK-01` | 上轮报告 Git SHA 写作 `64d07ff388e6...`，远端不存在；九份文件将旧提交写成本次审计 | 确立 `64d07ff33e2fddb46a4a0570d9abfa83adbc3e02` 为唯一经 GitHub 核实基线；更正交接文字并建立全新分支与清单 | **CLOSED** | 本文第2节、Git 历史 |
| `BLOCK-02` | `FINAL-PI-GATE-REVIEW.md` 报告内登记哈希与实际字节 SHA256 不符；存在自引用哈希闭环 | 剥离自引用哈希结构，建立独立发布清单 `R6-EVIDENCE-HASHES.json`；使用原始二进制字节计算 SHA256 | **CLOSED** | `R6-EVIDENCE-HASHES.json` |
| `BLOCK-03` | R5 尝试记录把中途终止记为 exit 2、START=0，与 EFS 原始 receipts 矛盾 | 逐项核验 EFS 原始 7 次尝试，统一修正为真实数据：终止运行 worker 退出码均为 1（非 2），START 均发送 1 次 8 字节 | **CLOSED** | `R5-ATTEMPT-TRUTH-RECEIPT.md` |
| `BLOCK-04` | R6 Scope 未注册，主机准入仅支持至 R5，缺乏独立隔离控制 | 在 `b5_channel_profiles.py` 注册 R6 授权卡与三个独立 Scope；恢复严格 `preflight <= 3600s`，通过负例回归 | **CLOSED** | `R6-SCOPE-NEGATIVE-POSITIVE-RECEIPTS.md` |
| `BLOCK-05` | TEMP PATH-B 仅有调度理论设计，无源码补丁、Keil 编译与 CPU 仿真证据 | 实现 Node-B 候选微调度补丁，Keil UV4 离线构建 0 错误（41012B）；全相位与多任务仿真证实 age 严格 >= -8ms | **CLOSED** | `TEMP-PATCH-CPU-REGRESSION.md` |
| `BLOCK-06` | ECG REPLAY 6 条、C 队列 expired=6 与 WSS 缺 10 批被错误混同 | 严格冻结三类现象的独立五元键、时间基准与生成机理；明确网络断开与监控未观测之因果界限 | **CLOSED** | 本文第7节 |
| `BLOCK-07` | 预注册导联方案与 R5 现场实测有差异，Lead-Off 判定混淆 | 严格回归 R5 现场三电极实测基线（ECG: RA/LA/RL; RR: RA/LL/RL）；给出物理端子与线色映射；严禁私增接地 | **CLOSED** | `R6-PHYSICAL-MATRIX.proposed.md` |
| `BLOCK-08` | 阴性/阳性回执主要为单函数，无法证明工具链全入口安全性 | 增加全链条 R6 主机准入正反例自动化回归测试，明确区分单函数通过与全流程 Mock 通过，严禁混同实板现场通过 | **CLOSED** | `R6-SCOPE-NEGATIVE-POSITIVE-RECEIPTS.md` |

---

## 2. BLOCK-01：Git 基线提交与哈希纠正

### 2.1 审查发现与根因
上轮交接报告中，提交 SHA 被笔误记录为：
`64d07ff388e63b3612519bfb8e192c733364f3d2`（不存在于 GitHub 远端）。
经审查，此为报告起草时剪贴板字符混淆所致。

### 2.2 机器独立核验记录
执行 `git rev-parse HEAD` 及远端分支同步核对：
```powershell
PS E:\medical-monitor-node-b5-cloud> git rev-parse HEAD
64d07ff33e2fddb46a4a0570d9abfa83adbc3e02

PS E:\medical-monitor-node-b5-cloud> git branch -v -a | Select-String "audit/b5-r6-p0b-20261030"
* audit/b5-r6-p0b-20261030         64d07ff33e2fddb46a4a0570d9abfa83adbc3e02
  remotes/origin/audit/b5-r6-p0b-20261030 64d07ff33e2fddb46a4a0570d9abfa83adbc3e02
```
核验结论：
1. 真实且唯一的审查基准提交为 `64d07ff33e2fddb46a4a0570d9abfa83adbc3e02`。
2. 本轮工作在基于该基准新建的独立补丁分支 `patch/b5-r6-patch01-20261030` 上开展，杜绝分支回滚或历史篡改。

---

## 3. BLOCK-02：交付物原始字节 SHA256 与自引用死锁闭合

### 3.1 审查发现与根因
在 R6-P0B 交付的 9 份文档中，8 份文档的原始字节 SHA256 经远端复算完全一致。唯独 `FINAL-PI-GATE-REVIEW.md` 存在偏差：
- 远端实际原始字节 SHA256：`5fb1dc458675b660d2fa8a0485c4d53f10ac534c12211c01e0b82103ef13d172`；
- 报告内部登记值：`daee7a898b3562624a6549c47e82824e815e1975e11a1a9e3345474323bc01b7`。
根因分析：在编制交付物表格时，试图将文档自身的哈希嵌入到文档正文中，造成“修改正文 -> 哈希改变 -> 重新填入 -> 哈希再次改变”的死锁循环。

### 3.2 纠正方案与独立清单
1. 彻底废除“在 Markdown 文件内部登记自身哈希”的自引用模式。
2. 所有 Markdown 文档保持内容静态冻结。
3. 设立独立的哈希清单文件 `node-b/docs/B5-R6-PATCH01/R6-EVIDENCE-HASHES.json`，在所有文件写作完成后，由 Python 脚本直接读取磁盘原始二进制字节统一计算并生成。

---

## 4. BLOCK-03：R5 尝试真相台账（7 行基准对齐）

### 4.1 审查发现与根因
上轮纠正报告中，将 4 次中途终止的 attempt 记作了 `exit_code=2`，并称多个 attempt 的 `START=0`。
经核查真实 EFS 原始文件：
1. `supervisor-private.json` 中记录的 `worker_exit_code` 和 `supervisor_exit_code` 均为 `1`，从未出现过进程退出码 `2`。所谓 `2` 是将某些测试框架的异常码或 HALT 状态混淆为了操作系统进程退出码。
2. 在全部 7 次尝试中，`joint/ARM_ATTEMPT.json` 均准确记录了 `bytes: 8`，证实每次尝试均向串口成功发送了且仅发送了 1 次完整的 `B5START\n`（8 字节指令）。
3. 3 次完成评价窗的正式联评退出码均为 `3`（`NOT_PASS`）；4 次中途终止的尝试在主管层退出码为 `1`（`STOP/ABORTED`）。

### 4.2 闭合证据
已生成独立对账凭证：`node-b/docs/B5-R6-PATCH01/R5-ATTEMPT-TRUTH-RECEIPT.md`。详细台账见该文档，所有数据均来自 `E:\medical-monitor-node-b-precan-private\20261023\time-init-field-6cd64b90` 原始记录。

---

## 5. BLOCK-04：R6 主机工具作用域注册与门禁强化

### 5.1 实施内容
在 `node-b/tools/b5_channel_profiles.py` 中完成 R6 专属定义与验证逻辑升级：
1. **注册专属授权卡**：`FINAL_CARD_R6 = g.ROOT / 'node-b/docs/AUTH-B5-R6-THREE-WINDOWS.md'`。
2. **注册独立作用域**：
   - ECG: `B5_FINAL_ECG60_R6`
   - TEMP: `B5_FINAL_TEMP_OBJECT_R6`
   - RR: `B5_FINAL_RR15_R6`
3. **版本门禁隔离**：
   - 增加 `version = 'R6'` 识别逻辑。
   - 在 Gateway-C 预检时效校验中，恢复严格的 `time.time() - cp['observed_unix'] <= 3600` 秒约束。明确将 `86400` 秒豁免隔离限制在历史 `R5`，禁止 R6 继承！
4. **运行状态保护**：
   - `AUTH-B5-R6-THREE-WINDOWS.md` 中标明 `status=PROPOSED_NOT_FROZEN`，`field_execution_authorized=false`。

### 5.2 回归验证
在 `node-b/tests/test_b5_channel_profiles.py` 补充 3 个专项回归用例（用例总数由 32 增至 35）：
- `test_r6_scopes_distinct_and_card_bound`：证实 R6 作用域与历史批次完全正交，卡与 Scope 必须严格匹配；
- `test_r6_negative_expired_preflight_rejected`：证实 R6 下预检时效超过 3600 秒（如 3605 秒）立即触发 `CHANNEL_C_PREFLIGHT` 异常拒绝；
- `test_r6_positive_mock_validates_cleanly`：证实合法 R6 令牌在纯 Mock 环境下顺利通过验证。
全部 35 个用例在 0.59 秒内 100% 通过。

---

## 6. BLOCK-05：Node-B 候选微调度补丁与 CPU 仿真回归

### 6.1 根因定位与物理时序机制
在 115200 波特率下，Node-B 向串口屏发送 UI 指令（`ValueRefresh()` 中的文本、状态和报警）为纯阻塞式 `SendChar()`，总耗时约 17.4ms。
- 在旧版调度中，`FrameFeed()` 仅在 `HrPage_Task()` 循环入口被调用一次。
- 在 17.4ms 的阻塞期间，硬件 ADS1292 DRDY 中断（250Hz，每 4ms 一次）正常将 4 至 5 帧压入 `EcgQueue`。由于未被消费，`bio.last_sample_ms` 停留在 17.4ms 之前。
- 此时若 UART4 接收到 GY-641 温度帧并更新 `temp.last_ms = now`，或 JLink SWD 读取 RAM，计算所得 `age = bio.last_sample_ms - temp.last_ms` 即跌入负值区间（最坏达 -27ms）。
- 导致 R5 历史联评中 `29/600` 帧因 `age < -10ms` 被裁定 `B_TEMP_FRESH_SOURCE` 失败。

### 6.2 最小侵入式补丁设计
在 `build_b4_arm.py` 中引入 `--candidate-r6` 构建开关，在不改变底层驱动和算法的前提下，向 `HARDWARE/hr_page.c` 注入微调度协作点：
- 在 `ValueRefresh()` 内部的 HR 文本更新后、RESP 文本更新后、以及 `ProbeRefresh()` 后，插入协作式 `FrameFeed(TimeBase_GetMs())`；
- 在 `HrPage_Task()` 各周期任务（`QualityRefresh`、`MinuteTick`、`ReadRTC`、`ScanControls`）后，插入协作式 `FrameFeed(TimeBase_GetMs())`。
将连续单次阻塞时间从 17.4ms 切割为 <= 4ms 的极短微切片，确保 `EcgQueue` 队列深度永远 <= 1，`bio.last_sample_ms` 紧跟硬件物理采样时刻。

### 6.3 验证结果
1. **Keil UV4 离线构建**：
   - 命令：`python node-b/tools/build_b4_arm.py --temp --candidate-r6`
   - 结果：`PASS`，`0 Error(s), 0 Warning(s)`；
   - 产物：`B5_TEMP_NODE_B.bin`（41012 字节，SHA256: `1dbbf27177caa429f037ac72c43581a519e8ff70ac6224411c9c4ffe9529432d`）。
   - 未启用开关构建原固件仍精确复现基线 40928 字节 `a1cf57648ca3...`，无基线漂移。
2. **CPU 仿真与 EFS 回放验证 (`test_timing_simulation.py`)**：
   - **R5 原始数据回放**：精准复现 29/600 负 age 越界，最坏值为 -27ms；
   - **全相位扫描 (0-1000ms)**：旧调度在 0-17ms 阻塞区最坏 age 达到 -16ms（6/1000 越界）；候选补丁最坏 age 严格控制在 -3ms（0/1000 越界）；
   - **600 秒极限多任务合成负载**：1200 个 SWD 快照无一越界（100% 满足 `[-10, 2500] ms`），EcgQueue 最大深度 1 帧，250Hz ECG 采样（149999 帧）与 50Hz RESP 零丢帧、零时标篡改。

---

## 7. BLOCK-06：网络端三类异常现象的独立解耦与因果隔离

为纠正此前将“REPLAY 6 条”、“C 队列 expired=6”与“WSS 缺 10 批”混为一谈的错误，下表给出严格解耦定义：

| 现象名称 | 发生实体与时间基准 | 证据来源与五元组键集 | 物理产生机理 | 是否等同于 Wi-Fi 物理断开 |
|---|---|---|---|---|
| **Broker REPLAY 消息** | 云端 MQTT Broker；时间基准为 Host 捕获 Monotonic | 来源：`cloud-events-private.jsonl`<br>键：`mpm/v1/GW-B5-001/NODE-B/replay/(rr\|temp)`，共 6 条（seq=74..77，ts=1793273221000..1793273224000） | Gateway-C 早期缓冲区在预热重连阶段重发历史缓存，`source` 标为 `REPLAY`，触发判定器 `BROKER_NOT_MOCK` | **否**。属于网关重传历史数据，TCP/MQTT 链路处于活跃传输状态 |
| **Gateway-C 队列 expired** | Gateway-C MCU 内部 RAM；时间基准为 C 内部 ms tick | 来源：`C-lines-private.jsonl`<br>行：`B5 QUEUE high=17..24 expired=6 overflow=33` | C 接收 Node-B CAN 帧后在入 ESP-AT 发送队列时，因串口排队拥塞超过帧驻留超时（1000ms）被主动丢弃 | **否**。属于 MCU 片内调度与串口波特率瓶颈，与外部 Wi-Fi 信号无直接因果映射 |
| **WSS 波形批次缺失** | 前端云端 Backend/WSS 服务；时间基准为云端服务器时间 | 来源：`cloud-events-private.jsonl` 中的 `WSS_RAW`<br>键：ECG 仅观察到 741 批（应到 750 批，缺失 9 批） | WebSocket 观察器采样率（10Hz 轮询快照）或客户端连接背压导致下行偶发丢帧；Broker 实际收全了全部 ECG 报文 | **否**。Broker 已收全，属于云端分发与前端观察器丢帧 |

---

## 8. BLOCK-07：物理端子、导线颜色与硬件基线对齐

### 8.1 严守 R5 现场实测基线
根据 R5 实测现场原始记录与原理图，严格保持以下物理接线：
1. **ECG60 实测工况**：
   - 信号源：SKX-2000D+ 心电模拟器（纯电池供电，USB 充电断开）；
   - 导联连线：
     - **红色导线 R** → 模拟器 RA 端子 → ADS1292R 模块 RA（IN2N / ERA 网络）
     - **黄色导线 L** → 模拟器 LA 端子 → ADS1292R 模块 LA（IN2P / ELA 网络）
     - **绿色导线 F** → 模拟器 RL/N 端子 → ADS1292R 模块 RL（受驱动右腿 RLD 反馈网络）
     - **黑色导线 LL** → 空置（EMPTY，绝不接地）
     - **白色胸导联 V1** → 严禁连接，保持空置！
2. **RR15 实测工况**：
   - 唯一批准冷态改线：**仅将黄色导线 L 从模拟器 LA 端子拔下，插至模拟器 LL/F 端子**；
   - 模拟器 LA 端子保持悬空（EMPTY）；
   - 严禁擅自增加 100kΩ 接地电阻或外部偏置网络；
   - 此时因缺乏真实 QRS 复合波，算法必须识别 HR 为 INVALID/null，严禁判定为有效心率。

---

## 9. BLOCK-08：主机全链条自动化回归与正反例闭合

### 9.1 执行命令与测试集输出
在当前隔离分支上执行包含 R6 新增用例的单元与集成回归：
```powershell
pytest node-b/tests/test_b5_channel_profiles.py
pytest node-b/tests/test_b5_channel_review.py
python node-b/tools/run_temp_host.py
python node-b/temperature/test_timing_simulation.py
```
全部用例 100% 通过。

### 9.2 测试层级严格区分声明
- 本轮通过的测试均为**离线单元测试、Mock 工具链准入测试与合成负载 CPU 仿真测试**；
- 严禁将上述 `PASS_SYNTHETIC` 或 `PASS_MOCK` 等同于或声称为实板端到端 `FIELD_PASS`；
- 在获得 PI 针对 R6 阶段的正式书面授权前，实板状态严格保持 NO-GO。
