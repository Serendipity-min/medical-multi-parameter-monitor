# MPM-B5-GEMINI-R5｜RR 工况勘误与心率异常偶发分析报告 (RR-HR-ARTIFACT-ANALYSIS)

- **文档版本**: v1.0
- **基线 Commit SHA**: `2854d3581658a91d65c1aa30d827ff489ff0f081`
- **审计工作分支**: `audit/b5-r5qc-r6p0-20261030`
- **关联证据源**:
  - `owner-observed-RR15-R5-5bb61eef/joint/B/diagnostics-private.jsonl` (SHA256: `7d0ba6293fbf3c8b4e7fe84666d6d459fe1334c2ee9ef90656a88b8159d33a69`)
  - `owner-observed-RR15-R5-5bb61eef/joint/cloud-events-private.jsonl` (SHA256: `64a27fe3b3a6a9be87a02b374d9e03ea2ba6452be425ca4e50ae8080f4f9f2e3`)
  - `owner-observed-RR15-R5-5bb61eef/joint/T0.json` (SHA256: `3dfc7857216a6a24564c7e47dfa935bebbec92bb3b71f9cf770cf41f874bc0fa`)
  - `node-b/evidence/B5-GEMINI-R5/RR15-WINDOW-01/actual-review.json` (SHA256: `331ad8bfde924043b355fa05c21f8a846f33cf23b2e59e354cb1ae360a7e58a2`)
  - `node-b/firmware/HARDWARE/bio_v2.c` (行 215, 241)
- **证据级别**: `RAW` (EFS 原始诊断与云端事件) / `DERIVED` (联评器输出)
- **结论置信类别**: `CONFIRMED` / `SUPPORTED_HYPOTHESIS` / `UNKNOWN`
- **操作权限声明**: 离线只读审计，未执行硬件读写，未修改判定门限或硬屏蔽心率输出

---

## 1. 现象与失败项汇总

在 R5 周期 RR15 正式评估窗口（`owner-observed-RR15-R5-5bb61eef`）中，冻结联评工具 [`b5_channel_review.py`](file:///e:/medical-monitor-node-b5-cloud/node-b/tools/b5_channel_review.py) 判定结果为 `B5_SEPARATE_RR15_NOT_PASS`（`exit_code = 3`）。

评测器记录了以下 3 项失败：
1. `B_RR_VALID15_HR_INVALID`：Node-B 内部诊断报告在 300 秒呼吸专用评估期内检测到了有效的心率（`hr_valid = 1`）；
2. `HR_EXPECTED_INVALID`：云端 MQTT 标量流在评估期内出现了有效心率数值（按判据要求在纯呼吸测试中 HR 必须全程保持 `INVALID/null`）；
3. `WSS_TARGET_CHANNEL_INVALID`：WSS 云端前端快照在上述时段捕获到了有效心率，违背了专一通道约束。

---

## 2. 模拟仪工况与授权卡文稿勘误

在现场执行与审计对账过程中，发现存在以下工况说明冲突：

### 2.1 授权卡文字笔误 (`QC-RR-CARD`)
在旧版授权卡 `AUTH-B5-GEMINI-R5-THREE-WINDOWS.md` 第 21 行中，对 RR15 的工况描述误写为：
> “SKX-2000D+ 呼吸模拟，周期 30bpm”

然而在 `criteria.json`、系统设计合同以及评测工具中，该模式的验收标准严格锁定为：
- 呼吸率目标区间: `14 <= rpm <= 16`（标称 **15 bpm**）；
- 心率目标: **必须完全处于 INVALID 状态**。

### 2.2 现场执行影响
在 R5 的首次尝试（`RR15-ATTEMPT-01`）中，测试人员按照卡面文字误将 SKX-2000D+ 模拟仪设置为 30 bpm，导致 Node-B 计算得到的呼吸率稳定在 30 bpm，无法进入 `14~16 bpm` 的就绪前置门，最终因 `COMMON_READY_DEADLINE` 超时安全熔断。
在后续正式窗口（`RR15-WINDOW-01`）中，现场人员将模拟仪修正为标称的 **15 bpm**，但卡面文字未曾正式勘误。

**审计裁定**：正式将此笔误记入勘误附录，R6 唯一合法预注册工况为：
- 仪器：SKX-2000D+ 模拟仪；
- 模式：纯呼吸模式；
- 设置参数：**呼吸率 15 bpm**，心率关闭（Lead Off / Flatline）；
- 导联接线：RA、LA、LL、RL 四导联标准阻抗呼吸连接。

---

## 3. 异常心率时间线与数据还原对账

通过对只读 EFS 中 `B/diagnostics-private.jsonl`（Node-B 2Hz 诊断）与 `cloud-events-private.jsonl`（云端 1Hz 标量）的关联分析，精确还原了全部异常数据的发生时间与数值。

### 3.1 关键时钟基准
- **T0 锚点**: `host_monotonic = 1059664.953` (UTC `1793325618580`)
- **300s 评估窗口**: `[1059709.953, 1060009.953]` (UTC `[1793325663580, 1793325963580]`)

### 3.2 异常数据逐帧与逐秒映射表

在整个 300 秒（600 帧诊断）评估窗口中，有 588 帧诊断正确报告 `hr = 0, hr_valid = 0`。剩余 **12 帧诊断**（对应云端 **6 条标量消息**）异常出现了非零心率。这 12 帧呈现为 3 次极为短暂的“突发脉冲”（每次脉冲恰好持续 2.0 秒，即 4 帧诊断 / 2 条云端标量）：

| 突发事件 | 评估窗口偏移 | Node-B 诊断索引 | 诊断时间戳 (monotonic) | Node-B 诊断值 (`hr`) | 云端标量 seq | 云端标量时间 (UTC) | 云端标量值 (`HR`) |
|---|---|---|---|---|---|---|---|
| **脉冲 1** | 第 127.3 ~ 128.8 秒 | 164<br>165<br>166<br>167 | 1059792.265<br>1059792.781<br>1059793.281<br>1059793.796 | `hr=73, valid=1`<br>`hr=73, valid=1`<br>`hr=73, valid=1`<br>`hr=73, valid=1` | 139<br>140 | 1793325745000<br>1793325746000 | `73.0 bpm (VALID)`<br>`73.0 bpm (VALID)` |
| **脉冲 2** | 第 131.8 ~ 133.4 秒 | 173<br>174<br>175<br>176 | 1059796.828<br>1059797.343<br>1059797.859<br>1059798.359 | `hr=115, valid=1`<br>`hr=115, valid=1`<br>`hr=115, valid=1`<br>`hr=115, valid=1` | 144<br>145 | 1793325750000<br>1793325751000 | `115.0 bpm (VALID)`<br>`115.0 bpm (VALID)` |
| **脉冲 3** | 第 155.9 ~ 157.3 秒 | 221<br>222<br>223<br>224 | 1059820.859<br>1059821.375<br>1059821.875<br>1059822.234 | `hr=64, valid=1`<br>`hr=64, valid=1`<br>`hr=64, valid=1`<br>`hr=64, valid=1` | 168<br>169 | 1793325774000<br>1793325775000 | `64.0 bpm (VALID)`<br>`64.0 bpm (VALID)` |

*(注：在评估窗口外，热身段第 31 秒有 1 条 `HR = 44.0`，尾部收尾段有 2 条 `HR = 60.0`，均属于非评估期)*

---

## 4. 根因分析：阻抗呼吸调制与心电 QRS 耦合机制

对上述现象的成因进行置信度分级：

| 现象与成因分析 | 置信类别 | 证据与推理依据 |
|---|---|---|
| **Node-B 输出了 12 帧有效 HR，云端输出了 6 条有效 HR** | **CONFIRMED** | 原始数据确凿记录，数值分别为 73、115、64 bpm，时长累计 6 秒。 |
| **三次异常脉冲均持续恰好 2 秒** | **CONFIRMED** | 固件算法中，心率周期过期时间常数为 2 秒（`expire(&heart.periods, now)`）。一旦误触发两次 R 波，有效标志位将保持 2 秒后自然超时归零。 |
| **呼吸阻抗载波/边缘泄漏耦合入心电通道** | **SUPPORTED_HYPOTHESIS** | SKX-2000D+ 模拟呼吸时在 RA-LL 导联注入 32kHz 交流阻抗调制信号。当呼吸波形发生峰谷反转或模拟仪继电器/电位器切换时，产生微小的陡峭电压毛刺，耦合进心电前置差分放大器。 |
| **QRS 检测算法灵敏度误触发** | **SUPPORTED_HYPOTHESIS** | 在心电信号几乎为零（平线）时，自适应滤波器的增益会自动放大，使得呼吸调制的陡峭边缘跨过了差分阈值，被误判为 R 波候选点。 |
| **外部接线屏蔽不良或悬空天线效应** | **UNKNOWN** | 现场导联线是否具备独立编织屏蔽层、屏蔽层是否在 RL 侧单端接地，缺乏实物显微与阻抗测试记录。 |

> [!IMPORTANT]
> **严禁违规捷径**：
> 1. 严禁在固件中加入针对 RR 模式的 `HR = 0` 硬屏蔽代码（作弊屏蔽）；
> 2. 严禁修改 criteria.json 放宽或特赦这 6 秒的心率有效；
> 3. 严禁在未经 PI 正式批准前擅自私接 100kΩ 接地电阻或更改电极网络。

---

## 5. R6 整改方案与验证建议

为在 R6 批次彻底消除呼吸对心电检测的虚假触发，提出以下合规整改路径：

### 5.1 台架与接线物理隔离 (PATH-A 推荐)
- **导联屏蔽层检查**：确保使用的 5 导联心电电缆具备完整的同轴屏蔽层，将右腿驱动（RL）可靠连接至模拟仪的地参考点；
- **模拟仪输出幅度核实**：将 SKX-2000D+ 的呼吸阻抗变化量（$\Delta R$）设定为标准人体典型值（建议 1.0 $\Omega$），避免设置过大调制深度引起前端过载；
- **导联线走线规范**：保持导联线平直，避免与电源适配器或 USB 数据线平行缠绕，减少感应共模噪声。

### 5.2 软件鲁棒性整改 (PATH-B 备选，需单独授权)
- 若经物理台架加固后仍存在偶发边缘毛刺，可在后续代码整改合同中，优化 [`bio_v2.c`](file:///e:/medical-monitor-node-b5-cloud/node-b/firmware/HARDWARE/bio_v2.c) 的 R 波幅度绝对门限：在输入信号幅值低于 50 $\mu\text{V}$ 时禁止心率状态置为有效（防止平线噪底自激）。

---

## 6. 审查结论

1. 确认 R5 RR15 评估窗口内存在的 12 帧诊断（6 条云端标量）异常心率系真实物理采集事实，导致三项失败标签（`B_RR_VALID15_HR_INVALID`、`HR_EXPECTED_INVALID`、`WSS_TARGET_CHANNEL_INVALID`）。
2. 保持 R5 RR15 `exit_code = 3 / NOT_PASS`，禁止通过报告篡改或特赦撤销失败。
3. 授权卡上的“30bpm”笔误正式予以勘误，R6 统一固定为 15 bpm。
