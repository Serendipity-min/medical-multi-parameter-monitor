# MPM-B5｜RR15 根因专项 PI 验收裁定与源端真值验证执行合同 R1

> 合同编号：`MPM-B5-R6-RR15-SOURCE-TRUTH-PI-R1`
> 日期：2026-10-30
> 仓库：`Serendipity-min/medical-multi-parameter-monitor`（PRIVATE）
> **唯一审查代码提交**：`codex/b5-r6-rr15-causal-candidate-20261030@eda6e24a8eedcfe0b50416390022db0c187550af`
> 祖先：`audit/b5-r6-rr15-offline-causal-20261030@b9b17a7657f101e8901a24115da8538becc420d0`
> **当前授权**：`A0_OFFLINE_SOURCE_TRUTH_DESIGN = GO`；`A1_PHYSICAL_SOURCE_REFERENCE = NOT_AUTHORIZED`；`R6_RR15_FORMAL_420S_RETEST = NO_GO`
> **禁止将本合同解释为**：Gate F 签署、B41012B 固件更新授权、一次性硬件令牌、自动授权上电/接线/复位、生产系统发布。

## 1. PI 审查结论

### 1.1 接收事项

1. GitHub 提交 `eda6e24...` 与对应独立分支存在，变更仅为离线诊断工具、测试、证据和文档；未新增可烧录的算法固件。
2. `input-integrity-and-C-agreement.json` 记录 RR15 原始帧 123,870 条，ECG60 原始帧 123,616 条；在 600 条评价期 SWD 诊断中，原 C host 回放与实板 **HR 数值和 valid 状态 600/600 一致**。仍有 RR 1 条其它主状态差异、13 条 IRQ 时间字段差异，ECG 15 条 IRQ 时间字段差异；这些不能冒称整条 120B 现场诊断逐字节一致。
3. 六簇 HR 异常可以由原始 CH2 输入经过原版 `bio_v2.c` 的 `heartbeat` → `accept_cycle` → `publish` 解释，峰宽 12–20 ms，3 个或更多间隔满足约 ±20% 中位周期稳定性门；对应有效 HR 范围为 38–82 bpm。确认**算法产生输出的路径**，不确认非 QRS 输入的物理真值。
4. 50/100 Hz 分量对六段 8s CH2 原始信号解释约 67.2%–86.6% 功率；残差信号与 RESP 的线性相关约 0.318–0.530。该统计仅支持干扰或耦合假设；不证明因果方向，也不能排除小幅真实 QRS。
5. 既有 C 回归 27+28+10=65 项和新工具 17 项均有退出码 0 回执。真实 ECG60/90/120 的六组开发/留出样本以及当前 ECG60 正例，报告在指定 45s 预热后正确有效覆盖 100%；两组低幅带噪合成 ECG120 仅约 94.44%，属于必须保护的弱信号能力边界。16 个已知无 QRS 的合成负例均未检出有效 HR，但**这不构成实际 RR15 无 QRS 的证明**。
6. R5 RR15 的旧留出数据仍有 2740/138828 个逐样本 HR 有效状态（约 1.97%），当前 R6 RR15 的现场评价期仍为 20/600 个异常 HR 诊断和 10 条云端异常 HR，冻结联评状态继续为 `NOT_PASS / exit_code=3`。

### 1.2 不予接收事项

- `ROOT_CAUSE_CONFIRMED`：**拒绝**。输入源物理真值未建立。
- `RR15_ALGORITHM_FIXED`：**拒绝**。未提交新算法，也没有新的工程正反例修复结果。
- `R6_RR15_FORMAL_420S_RETEST`：**拒绝**。重复相同工况不能解释根因，零误报的单窗结果也可能具有偶然性。
- `R6_GATE_F`, `B5_STAGE_CLOSURE`, `SDK_RESIDUAL_RISK_CLOSED`：均未授权或尚未满足。

## 2. 本轮允许执行的 A0 离线工作（立即生效）

执行者：Codex；**REUSE_FIRST / MINIMAL_DIFF / FAIL_CLOSED**。从 `eda6e24...` 建立新独立分支，不能修改 Codex 既有审查分支、Gemini 分支、`main`、R5/R6 冻结正式联评、原始采集 EFS。只允许完成以下工作：

1. **源端菜单/接线证据审查**：对照现有 `SKX2000D+` 说明书（项目已识别 12 页、P5/P11）、已封存工况记录和历史照片，区分呼吸率、阻抗幅度 `1.5R`、波形周期 `30bpm`、ECG 模拟输出/关闭选项、参考阻抗 `1kΩ`。不得把 `30bpm` 自行解释为载波频率；不得从 `L→LL/F` 推断 CH2 必然无 QRS。
2. **源端参考真值条件矩阵**：写出何种独立证据才足以标签化 `ECG_PRESENT` / `ECG_ABSENT` / `SOURCE_UNKNOWN`。必须区分“模拟器用户界面设置”与“实际模拟器端子电信号”；历史算法 HR=0 不等于输入信号无 QRS。
3. **最小非人体硬件区分实验预注册**：仅形成供 PI 审核的、尚未启用的 A1 申请；说明真实仪器是否具备隔离差分、高输入阻抗及同钟参考，确认安全连接图、RLD 网络风险、已知独立参考性能、采集持续时间、时标同步方法、每个工况切换的冷态隔离步骤及异常处置。若缺少可安全建立参考的仪器，明确 `MEASUREMENT_NOT_READY`，不得建议以普通接地示波器直接探测 RLD/电极端。
4. **算法质量门设计审查**：不写“RR 模式屏蔽 HR”的补丁；仅提供一份以真实证据为条件的候选设计表（例如峰形、时间-频率证据、带内 QRS 特征、实际周期可信度），逐一列出易误拒的低幅 ECG120 样本和正例保持方案；不要对现有六簇拟合新阈值。若无可靠无 QRS 标签，保持 `ALGORITHM_PATCH_NOT_AUTHORIZED`。
5. **语料/留出治理**：标明当前 R5 RR15 与 ECG60/90/120 的开发与留出波形已被本轮查看，不能在未来调参后重新宣称“全盲留出”；下一算法候选需要新独立留出或按已公开数据的非盲性质报告。所有真实采样及图像留受限 EFS，不进入 Git。
6. **可信源与工具防线**：复用现有 `b5_rr15_causal_replay.py`、`b5_rr15_causal_analysis.py`、`run_rr15_causal_corpus.py`；对新报告实现 SHA/运行脚本一致性核验。若不需要改工具则不得为增加提交而重写工具。既有 65/17 回归不必重复全跑，除非修改其影响范围。

> A0 包不允许真实目标 SDK/DLL/COM/SWD/Flash，**不允许上电、不允许改变黄 L 线、不允许移动 J-Link、操作 SKX 菜单、不允许云端服务/ACL 改动**。如果必要信息不能由已有材料证明，只能登记 `UNKNOWN` 和所需后续授权，不得诱导执行者偷偷采样。

## 3. A1 实板源端参考实验：仅为提议，当前未授权

A1 **不是** 420 秒完整 B→C→云联评。即使 A0 完成，仍需 PI 针对操作前最新实际状态、仪器清单、接线/供电隔离、风险、次数、异常恢复责任签署新的一次性许可。

所提议的辨别目标是：在**预先固定且独立可验证的非人体源**下，判断 RR15 的模拟器端子是否持续携带真实 QRS 或与 QRS 混淆的同步成分。建议至少有可靠 ECG 正参考与 RESP15 待测配置；是否存在有效的“真正无 ECG 输出”控制，必须以说明书与实物能力为准，不得编造菜单或将 Lead-Off 当作无 QRS。采集必须可与原始 CH2/CH1 时基比较；若无可靠安全的外部参考源，就报告无法区分，**不要启用正式 RR15**。

严禁：人体接入；带电改线；RLD/模拟器电极随意接地、插入外部偏置或电阻；假电极、Lead-Off 掩盖；改变冻结联评标准；旧授权卡/旧 nonce 复用；未经授权的 C RESET、B5START 或 SDK 重连接。

## 4. A1 证据的条件分流与后续修复合同

| A1 独立真值 | 判定 | 允许的下一步（仍需单独批准） |
|---|---|---|
| `ECG_PRESENT_CONFIRMED` | 当前“RR15 不能出现 HR”的测试源前提可能不成立；算法输出真实心率不能当作已证伪 | 修订**新一版**测试刺激/隔离方案并预登记；保留历史 R5/R6 NOT_PASS，不追改标准；不屏蔽心率 |
| `ECG_ABSENT_CONFIRMED` 且六簇复现 | 形成已知无 QRS 的真实假阳性反例 | 允许提出一个**模式无关**最小算法质量门，在独立分支 CPU/Host 守恒验证；仍不自动批准烧录 |
| `SOURCE_UNKNOWN` / 参考冲突 | 不得将相关性解读为物理因果 | 暂停算法阈值优化及正式重试；补充参考条件或保持未决 |

未来独立的算法候选，必须遵守：原始 ADC/IRQ ms/seq、250SPS 与 50SPS 数据连续性及诊断 ABI 不漂移；冻结判据不改；真实 ECG60/90/120 均守住预登记的正确率/有效覆盖相对基线退化不超过 1pp 和 ±2bpm 的约束；对低幅带噪 ECG120 的已知约 94.44% 覆盖不能忽略，应逐数据集报告。若这些不能满足，不得以“RR 无误报”换取真实心率被大幅过滤。

## 5. 离线交付物与停止条件

Codex 在新的独立分支中交付：

- `RR15-SOURCE-TRUTH-FACT-MATRIX.md`：说明书、旧照片、菜单、接线证据、未知项及来源哈希；禁止填充猜测。
- `RR15-REFERENCE-A1-REQUEST.disabled.md`：**默认禁用**，明确仪器、安全/电气隔离、现场可验证标签、各工况、时长、异常停止责任、预算和不可复用次数。
- `RR15-ALGORITHM-DESIGN-DECISION.md`：三路径（真实 QRS、无 QRS、未知）下的算法/工况分流及低幅 ECG120 保护。
- `RR15-PI-PACKET.md` 和机器可复算 `EVIDENCE-HASHES.json`：本轮真实操作、工具 SHA、样本/参考证据的受限索引、退出码、未关闭项。

全部修改仅限新的 A0 分支。若无法提供经确认的物理参考仪器、安全接线和真值定义，应停止在 `A1_REQUEST_DISABLED`；不能因 A0 审计通过自动上电或发出新现场令牌。完成后推送交付分支，等待 PI 独立审核与 A1 决定；不合并主分支。

## 6. 正式状态块

```text
RR15_OFFLINE_CAUSAL_DELIVERY       = ACCEPTED_WITH_OPEN_PHYSICAL_CAUSE
RR15_ORIGINAL_C_REPLAY_HR_VALID    = OBSERVED_600_OF_600
RR15_ROOT_CAUSE                   = UNRESOLVED
RR15_ALGORITHM_PATCH              = NOT_IMPLEMENTED
RR15_LATEST_FORMAL_RESULT         = NOT_PASS_EXIT_3
ECG60_ENGINEERING                 = PASS_EXIT_0
TEMP_OBJECT_ENGINEERING           = PASS_EXIT_0
SOURCE_TRUTH_A0_OFFLINE_DESIGN     = AUTHORIZED
SOURCE_TRUTH_A1_LIVE_REFERENCE    = NOT_AUTHORIZED
RR15_NEW_420S_FORMAL_RETEST       = NOT_AUTHORIZED
R6_GATE_F                          = NOT_SIGNED
B5_STAGE_CLOSURE                  = DENIED
REAL_SDK_COM_FLASH_RESET_B5START  = 0_AUTHORIZED_BY_THIS_CONTRACT
```

**PI 核心裁定：不再重复没有新输入真值和没有新固件的正式 RR15 联评；先证实源端实际有没有 QRS，再选择物理工况整改或算法质量门整改。**
