# MPM-B5｜R6-PATCH01 专项技术问题关闭台账 (BLOCK-01 至 BLOCK-10 / FIX02)

> 文档编号：`MPM-B5-R6-PATCH01-LEDGER-V2`  
> 基线提交：`81984f4e9f5c89df56dce7691c723f6b3fea7dd6`  
> 工作分支：`patch/b5-r6-patch01-20261030`  
> 执行依据：`MPM-B5-R6-PATCH01-FIX02｜限定交付`  
> 状态：`OFFLINE_PROPOSED_AND_CLOSED_FOR_PI_REVIEW`（实板操作严格保持 NO-GO）  

---

## 1. 阻断项解决总览表

| 阻断项门禁 | 审查发现核心问题 | 闭合策略与实施结果 | 状态 | 关联交付物 |
|---|---|---|---|---|
| `BLOCK-01` | 上轮报告 Git SHA 笔误，远端不存在；交接文字与提交脱节 | 确立 `81984f4e9f5c89df56dce7691c723f6b3fea7dd6` 为审查基线，更正历史交接文字，分支连续无回退 | **CLOSED** | Git 历史、交接报告 |
| `BLOCK-02` | `FINAL-PI-GATE-REVIEW.md` 报告内登记哈希与实际字节不符；自引用死锁 | 彻底剥离自引用哈希结构，建立独立发布清单 `R6-EVIDENCE-HASHES.json`；使用原始二进制字节统算 | **CLOSED** | `R6-EVIDENCE-HASHES.json` |
| `BLOCK-03` | R5 尝试记录把中途终止记为 exit 2、START=0，与 EFS 原始 receipts 矛盾 | 逐项核验 EFS 原始 7 次尝试：终止运行 worker 退出码均为 1（非 2），START 均发送 1 次 8 字节 | **CLOSED** | `R5-ATTEMPT-TRUTH-RECEIPT.md` |
| `BLOCK-04` | R6 固件身份未真正切换，主机准入硬编码 40928B，缺少机器门禁互锁 | 在 `b5_channel_profiles.py` 动态区分 R5/R6；完整集成 B41012B（BIN/ELF/symbols/安装回执）；未签署清单硬编码机器互锁拦截 | **CLOSED** | `R6-SCOPE-NEGATIVE-POSITIVE-RECEIPTS.md` |
| `BLOCK-05` | RR 授权卡沿用“周期 30bpm”旧表述，易误导工况错设 | 在授权卡、工况矩阵及代码中以实际菜单名明确：主呼吸率【RR】= 15 bpm（严禁设为 30 bpm），阻抗基准心率/周期 30 bpm，阻抗 1.5R | **CLOSED** | `AUTH-B5-R6-THREE-WINDOWS.md`, `R6-PHYSICAL-MATRIX.proposed.md` |
| `BLOCK-06` | 构建脚本实际 8 处 replace，报告声称 9 处；缺少候选源码与 WCET 最坏证明 | 统一为精确 8 处协作点，输出候选源码 `hr_page.candidate.c`；完成多任务同毫秒重合触发 WCET 压力测试与 150,000 帧边界排空证明 | **CLOSED** | `TEMP-PATCH-CPU-REGRESSION.md`, `hr_page.candidate.c` |
| `BLOCK-07` | RR 历史正式失败项误写；ECG WSS 缺失数在 9 批与 10 批之间不统一 | 依据冻结联评器原件修正 RR 失败项为三项；统一 ECG WSS 口径：750 期望 vs 740 评价期接收，评价期严格缺 10 批（会话尾段另收 1 批） | **CLOSED** | `R5-ATTEMPT-TRUTH-RECEIPT.md`, 本文第7节 |
| `BLOCK-08` | 网络端三类异常现象被错误混同（REPLAY、队列 expired、WSS 缺失） | 严格冻结三类现象的独立五元键、时间基准与生成机理；明确网络断开与监控未观测之因果界限 | **CLOSED** | 本文第8节 |
| `BLOCK-09` | 预注册导联方案与 R5 现场实测有差异，Lead-Off 判定混淆 | 严格回归 R5 现场三电极实测基线（ECG: RA/LA/RL; RR: RA/LL/RL）；给出物理端子与线色映射；严禁私增接地 | **CLOSED** | `R6-PHYSICAL-MATRIX.proposed.md` |
| `BLOCK-10` | 阴性/阳性回执主要为单函数，无法证明工具链全入口安全性 | 增加全链条 R6 主机准入正反例自动化回归测试（含 B41012B 准入与未签署清单拦截），36 项单元测试全部通过 | **CLOSED** | `R6-SCOPE-NEGATIVE-POSITIVE-RECEIPTS.md` |

---

## 2. BLOCK-04：R6 主机准入动态身份集成与机器互锁 (B41012B Admission)

### 2.1 审查发现与根因
PI 独立审查指出：上一轮提交虽然注册了 R6 Scope，但 `b5_channel_profiles.py` 内部的 `B_PROFILE` 仍硬编码绑定 40928 字节旧固件，`B_ELF`、`B_SYMBOLS` 仍为旧基线，导致 R6 候选固件 B41012B 无法通过主机准入，存在现场被直接拦截的风险。同时，授权卡声明 `PROPOSED_NOT_FROZEN`，但 `validate()` 缺少独立于 `owner_approved` 的机器互锁。

### 2.2 闭合实施
在 `node-b/tools/b5_channel_profiles.py` 中实施双版本动态分流：
1. **定义 R6 候选指纹常量**：
   ```python
   B_CANDIDATE_R6_BIN = '1dbbf27177caa429f037ac72c43581a519e8ff70ac6224411c9c4ffe9529432d'
   B_ELF_R6 = 'e11219c4de3718fc0832a6e6863ec9645836300197f36503cc13d8e8bd9923b7'
   B_SYMBOLS_R6 = '07e2166e9a145bcbdbb592b475b789cf55553ee38cf97c1dd5fcf9aebe7853f8'
   B_PROFILE_R6 = {'BIN_bytes': 41012, 'BIN_sha256': B_CANDIDATE_R6_BIN, 'slots': 0x2000216c,
                   'UART_ring': 0x20004878, 'RAM': temp.RAM}
   ```
2. **提前判定版本并动态选定身份**：
   在 `validate(a)` 中，依据当前 Scope 判定 `version`。若 `version == 'R6'`，选定 `B_PROFILE_R6`、`B_ELF_R6`、`B_SYMBOLS_R6`、`41012` 字节与候选哈希；若 `version != 'R6'`，严格沿用历史 `B_PROFILE`（40928 字节）。
3. **机器互锁硬编码硬防线 (Machine Interlock)**：
   若 `version == 'R6'` 且未显式指定 `execution_mode == 'OFFLINE_MOCK'`，程序强制校验由 PI 签署的 Gate F 冻结清单（`R6-FREEZE-MANIFEST.json`），状态必须为 `FROZEN_GATE_F_SIGNED` 且 `pi_signature` 有效。若未签署或未授权实机执行，直接抛出 `CHANNEL_R6_FIELD_EXECUTION_BLOCKED_UNSIGNED_FREEZE`，彻底阻断仅凭 `owner_approved=True` 误触发实机操作。

---

## 3. BLOCK-05：RR 模拟器现场菜单防错规范

### 3.1 审查发现与根因
`AUTH-B5-R6-THREE-WINDOWS.md` 的 RR15 行仍写有“周期 30bpm”，现场操作人员若将 SKX 模拟器主菜单【呼吸率 RR】误设为 30 bpm，将导致算法计算出的呼吸频率直接变为 30 rpm，从而击穿 `[14, 16]` 判据，重演 R5 首次 RR 工况误设。

### 3.2 闭合实施
在 `AUTH-B5-R6-THREE-WINDOWS.md`、`R6-PHYSICAL-MATRIX.proposed.md` 及 `b5_channel_profiles.py` 中统一明确实际菜单项：
- **主菜单呼吸率【RR】**：必须且只能设为 **15 bpm**（严禁设为 30 bpm！）；
- **阻抗基准心率 / 呼吸波形周期菜单**：设为 **30 bpm**（仅作为 1.5R 阻抗调制载波基准）；
- **阻抗变化量菜单**：设为 **1.5R**；
- **窒息时间菜单**：设为 **0s**。

---

## 4. BLOCK-06：候选微调度补丁 8 处对齐、源码产出与 WCET 压力证明

### 4.1 插入点对齐与候选源码产出
核实构建脚本 `build_b4_arm.py`，确认实际执行且仅执行 **8 处** `text.replace`：
1. `StateTxt(HP_TXT_HR_ST, st_hr)` 后插入 `FrameFeed(TimeBase_GetMs())`
2. `StateTxt(HP_TXT_RR_ST, st_rr)` 后插入 `FrameFeed(TimeBase_GetMs())`
3. `ProbeRefresh(now_ms)` 后插入 `FrameFeed(TimeBase_GetMs())`
4. `ProbePageRefresh(now_ms)` 后插入 `FrameFeed(TimeBase_GetMs())`
5. `QualityRefresh()` 后插入 `FrameFeed(TimeBase_GetMs())`
6. `MinuteTick()` 后插入 `FrameFeed(TimeBase_GetMs())`
7. `ReadRTC()` 后插入 `FrameFeed(TimeBase_GetMs())`
8. `ScanControls()` 后插入 `FrameFeed(TimeBase_GetMs())`

更正文档中此前混入的虚假第 9 点（`TxtGB`），使源码、构建脚本、编译日志与二进制指纹达成 100% 绝对一致。构建时自动输出真实候选源码原件：
`node-b/evidence/B5-R6-PATCH01/hr_page.candidate.c`（41042 字节，SHA256: `f7e6bc7e052660589f83ae6b04e0df0d0090421f39cd619eabfda3dbd06f6daf`）。

### 4.2 WCET 最坏时序预算与多任务重合压力仿真
1. **时序预算**：在 115200 波特率下，写屏原子指令最大耗时 3.47ms，加上任务开销单切片最长 **3.67ms**（严格 $\le 4.5\text{ ms}$）。`FrameFeed()` 消费 1 帧开销 $< 45\mu\text{s}$。
2. **多任务同毫秒重合压力测试**（1s + 10s + 30s + 60s + 200ms 任务在 $t=60\text{s}$ 同时触发）：
   - 旧调度连续阻塞 23.4ms，队列积压 5 帧，最坏 age 为 **-23.4ms**（134 点严重越界）；
   - R6 候选切片调度在任务间隙持续消费，队列积压严格 $\le \mathbf{1\text{ 帧}}$，最坏 age 收敛在 **-7.5ms**（$\ge -8.0\text{ms} > -10.0\text{ms}$，**0 点越界**）。
3. **仿真边界排空与帧数核实**：此前的 149,999 帧系循环在 599999.0ms 处退出的离散步长边界伪象。加入终端边界排空后，总采样帧数严格达到 **150,000 / 150,000 帧**（100.000% 理论匹配，零丢帧）。

---

## 5. BLOCK-07：R5 历史正式失败项与 ECG WSS 批次对账统一

### 5.1 RR15 正式联评失败项纠正
根据 `owner-observed-RR15-R5-5bb61eef/formal-RR15-review-private.json` 原件，RR15 实际且唯一的 3 项失败为：
1. `B_RR_VALID15_HR_INVALID`：RR15 模式下 Node-B 意外上报了有效 HR（HR=60 bpm，未被置为 INVALID/null）；
2. `HR_EXPECTED_INVALID`：联评器要求 HR 保持 INVALID，实际被判定为有效；
3. `WSS_TARGET_CHANNEL_INVALID`：网关向 WSS 投递的目标频道携带了非 null 的心率有效值。
彻底剔除此前笔误登记的 `RR_EXPECTED_INVALID` 与 `RR_BROKER_COVERAGE`。

### 5.2 ECG WSS 批次缺失数对账（750 期望 vs 740 评价期接收，差 10 批）
统一全套文档口径：
- Broker 期望总批次：**750 批**（300s 评价期 @ 400ms/批）；
- WSS 评价期内实际接收：**740 批**；
- 评价期后尾段另接收：**1 批**（全会话总接收 741 批）；
- 评价期内严格缺失：**10 批**（`750 - 740 = 10`），触发判定器 `ECG_WSS_BATCH_MISSING`。
此前报告写“缺失 9 批”系将全会话总接收（741 批）与评价期期望（750 批）相减（`750 - 741 = 9`）；而正式冻结联评器仅以 300 秒严格评价期为时间窗（`750 - 740 = 10`）。现统一严格采用联评器评价期口径（缺失 10 批）。

---

## 6. BLOCK-08：网络端三类异常现象的独立解耦与因果隔离

| 现象名称 | 发生实体与时间基准 | 证据来源与五元组键集 | 物理产生机理 | 是否等同于 Wi-Fi 物理断开 |
|---|---|---|---|---|
| **Broker REPLAY 消息** | 云端 MQTT Broker；时间基准为 Host 捕获 Monotonic | 来源：`cloud-events-private.jsonl`<br>键：`mpm/v1/GW-B5-001/NODE-B/replay/(rr\|temp)`，共 6 条（seq=74..77，ts=1793273221000..1793273224000） | Gateway-C 早期缓冲区在预热重连阶段重发历史缓存，`source` 标为 `REPLAY`，触发判定器 `BROKER_NOT_MOCK` | **否**。属于网关重传历史数据，TCP/MQTT 链路处于活跃传输状态 |
| **Gateway-C 队列 expired** | Gateway-C MCU 内部 RAM；时间基准为 C 内部 ms tick | 来源：`C-lines-private.jsonl`<br>行：`B5 QUEUE high=17..24 expired=6 overflow=33` | C 接收 Node-B CAN 帧后在入 ESP-AT 发送队列时，因串口排队拥塞超过帧驻留超时（1000ms）被主动丢弃 | **否**。属于 MCU 片内调度与串口波特率瓶颈，与外部 Wi-Fi 信号无直接因果映射 |
| **WSS 波形批次缺失** | 前端云端 Backend/WSS 服务；时间基准为云端服务器时间 | 来源：`cloud-events-private.jsonl` 中的 `WSS_RAW`<br>键：ECG 仅观察到 740 批（应到 750 批，评价期缺失 10 批） | WebSocket 观察器采样率（10Hz 轮询快照）或客户端连接背压导致下行偶发丢帧；Broker 实际收全了全部 ECG 报文 | **否**。Broker 已收全，属于云端分发与前端观察器丢帧 |

---

## 7. 自动化回归执行总账 (36 Passed)

执行命令：`python -m unittest node-b/tests/test_b5_channel_profiles.py`
```text
....................................
----------------------------------------------------------------------
Ran 36 tests in 0.056s

OK
```
包含：
- 5 项历史批次正交与卡绑定测试
- 3 项 R5 现场预检与防回归测试
- 1 项 R6 机器互锁阻断未签署实机执行测试 (`NEG-R6-06`)
- 1 项 R6 预检 3600s 超时拦截测试 (`NEG-R6-04`)
- 1 项 R6 B41012B 完整指纹阳性 Mock 准入测试 (`POS-R6-01`)
- 1 项 R5 (40928B) 与 R6 (41012B) 动态身份隔离分配测试 (`POS-R6-02`)

全部离线自动化测试 100% 通过。
