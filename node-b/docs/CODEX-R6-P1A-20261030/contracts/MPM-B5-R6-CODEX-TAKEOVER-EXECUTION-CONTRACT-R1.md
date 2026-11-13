# MPM-B5｜R6 Codex 接管、工具复用审计与 P1-A 限定执行合同（R1.0）

> **合同编号**：`MPM-B5-R6-CODEX-TAKEOVER-P1A-R1`  
> **签发日期**：2026-10-30  
> **执行主体**：Codex（接替 Gemini/Antigravity）  
> **项目仓库**：`Serendipity-min/medical-multi-parameter-monitor`（PRIVATE）  
> **唯一已核验代码基线**：`patch/b5-r6-patch01-20261030@01864fb4c1ea35c9da38aa98b1e85790d2ed5415`  
> **目标工作目录**：仅在经 Codex 只读核验实际存在且与本仓库匹配时，使用 `E:\medical-monitor-node-b5-cloud`；不得从字符串路径推断当前文件/现场事实。  
> **本轮执行级别**：`P1-A / OFFLINE TOOL REVIEW / HOST-ONLY CANDIDATE PATCH`；**绝不包含 P1-B 通电只读验签**。  
> **上一份 PI 合同**：`MPM-B5-R6-P1-READONLY-GATE-CONTRACT-R1.md`，SHA256 `bea43ecb12057e7ec5395041d138a7be470612aa77a9bdacf754b942ca799668`（于 2026-10-30 本聊天中签发；**不保证存在于本地 Windows 项目目录或 GitHub**，须由负责人另行交付）。  
> **合同效力**：本合同替换执行主体并收紧 Codex 的离线工作范围；不撤销既有 R5 原件保护，也不扩大上一份合同对任何硬件或正式业务的权限。**交付给 Codex 执行离线范围**不等于 PI 已签署 Gate F、P1-B 或 P2 许可。

---

## 0. PI 立即裁定（先读，具有最高优先级）

### 0.1 工具策略：`REUSE_FIRST, AUDIT_BEFORE_USE`

- **选择复用 Gemini 的已有工具和 R6 41,012 字节候选**，不重新开发 G3、CANopen、MQTT、证据联评、SWD 工具链；原因是已有多轮阶段性数据、哈希、历史失败反例和回滚基线，重造会扩大差异面且无法自动继承通过证据。
- **复用不是默认信任**。Codex 需独立验证每个脚本的调用链、硬件副作用、目标硬件身份绑定、离线/现场模式隔离与证据哈希。凡已有工具绑定旧板、旧镜像、旧 scope，必须先 `FAIL_CLOSED`；不得因名字含 `readonly`、`R6` 或 `MOCK` 就执行。
- 可在**新独立分支**中提出/实现最小**主机端离线候选补丁**，仅限 G3 R6 分派、Mock/现场驱动硬隔离、拒止测试、构建器插入断言和审计证据工具；**不能修改采样算法、底层驱动、Gateway-C、云端生产配置或既有验收判据**。任何代码变动都只能标记 `CANDIDATE_OFFLINE`，不部署、不合并、不自动授权硬件。
- **现有 `b5_channel_review.py` 与三个 R5 `criteria.json` 必须保持字节不变**。若发现评测器缺陷，只写独立勘误及候选修复建议，不得在本合同内改判据或回填 PASS。

### 0.2 Codex 的第一问——`01864fb` 后是否还有进展／PI 合同？

**正式答复：有新的 PI 裁定合同；已核验的 GitHub 工作分支暂无新代码提交。**

1. 2026-10-30 经 GitHub 只读核对，`patch/b5-r6-patch01-20261030` 远端 HEAD 仍为 `01864fb4c1ea35c9da38aa98b1e85790d2ed5415`，比较结果 `identical / ahead 0 / behind 0`；仅对**这条工作分支**成立，不证明其他分支或任何本地未提交文件不存在。
2. 该提交后，PI 在 ChatGPT 中签发了上述 **`MPM-B5-R6-P1-READONLY-GATE-CONTRACT-R1.md`**：`P1-A=GO`，`P1-B=CONDITIONAL_NOT_ACTIVATED`，Gate F 未签署，B41012B 烧录和三组正式测试均 `NO-GO`。
3. Codex 本轮新增执行依据为**本合同**；旧合同与本合同须同时列在交付台账。合同存在于对话附件不代表存在于仓库。**不准自行伪造/补造文件路径，不准以过时交接快照替代 Git HEAD 或实物核查。**
4. 如 Codex 本机在开始时检测出新 commit、dirty working tree、stash/工作树变动或本地合同不一致，先保存差异的只读证据并进入 `BASELINE_CONFLICT_HALT`，不得 `reset --hard`、`clean -fdx`、覆盖或自动合并。无需因此要求负责人重述已经明确的 PI 裁定。

### 0.3 Codex 的第二问——R5 后当前实物状态？

**正式答复：截至本次合同签发，今天的现场实物状态是 `UNKNOWN`。**

| 物理事实 | 当前状态 | 后续取得证据的规范 |
|---|---|---|
| Node-B 供电是否断开 | `UNKNOWN` | 仅靠负责人当前目视/照片确认，禁用历史快照代替 |
| Gateway-C 供电是否断开 | `UNKNOWN` | 同上；ESP-01S 供电非隔离属于已知设计风险，当前是否实际有电仍未知 |
| C USB-UART 与电脑端是否连接 | `UNKNOWN` | 只记录物理位置；不打开 COM/读串口探测 |
| J-Link 电脑端是否连接 | `UNKNOWN` | 只记录线缆状态；不发起 SDK 连接 |
| SWD/JTAG 板端插在哪块板 | `UNKNOWN` | 只读照片/目视，不能热插拔、切换接头 |
| 黄 L 线在 LA 或 LL/F | `UNKNOWN` | 从当前接线照片确认；不移动导联来满足预设 |
| SKX2000D+ 当前是否开机 | `UNKNOWN` | 目视/既有照片，禁止触碰开关和菜单 |
| J3 跳帽、额外导联、RLD 与 CAN 接线 | `UNKNOWN`（当前现场态） | 与原理图、历史实测和当前实物分开记账，冲突即停止操作 |

**边界**：10 月 29 日“全部断电”记录是历史，不是今天的实物证明。未知项目不阻断本合同**完全离线**任务；但凡要开展任何通电、插拔、SWD/J-Link、COM 探测、运行模拟器或 Flash 读取，必须首先完成 P1-A 现场事实交接，并向 PI **一次性**提交逐板 P1-B 授权申请。未获新授权时保持 `HALT_BEFORE_CONNECT`，不得为了消除 UNKNOWN 自行触碰设备。

---

## 1. 冻结身份、实验事实和研究边界

| 对象 | 当前应引用的历史基线／状态 | 禁止误宣称 |
|---|---|---|
| Node-B 历史实装 | `B40928B`；BIN 40,928B；SHA256 `a1cf57648ca3787de30c1ad7055634c278fbbde538bb0bc562961bd212182ed2`；历史完整 Flash SHA256 `ceebec5a91835aed3cb70c683fd8de5142e5ba59a2163a1968cec182018b48ae` | 不可说今天已实读且确定未变 |
| Gateway-C 历史实装 | `C49132B`；BIN 49,132B；SHA256 `72131dbb5ef6bc0e0d33e328925c685403bae928aea9447a81f8291c6ae5c1ab`；历史完整 Flash SHA256 `9bba23b436f079183296fa98dcaeed047eb919ba8597d75a85bc144bc48417fd` | 不可说已通过 R6 只读验签 |
| Node-B R6 候选 | `B41012B`；BIN 41,012B；Git 原始 BIN SHA256 `1dbbf27177caa429f037ac72c43581a519e8ff70ac6224411c9c4ffe9529432d` | 未安装、未实板证明新 TEMP 时序合格 |
| R5 三个正式窗口 | ECG60、TEMP_OBJECT、RR15：全部 `exit_code=3 / NOT_PASS` | 不因文档修订、CPU Mock 或 R4 工程复验而追认 PASS |
| TEMP | R5 600 帧中 29 帧越界；最低 `-27ms`；正式规则 `[-10,2500]ms` 不变 | 不得放宽到 -35ms 或改写真实采样时间戳 |
| ECG | 8.375s C 诊断空档、6 条 REPLAY、6 项 C 过期计数、WSS 缺失判定 | 不得仅凭计数相等归因 Wi-Fi 或把不同集合混为一谈 |
| RR15 | 300s 评价中 12 帧 B HR 有效、6 条云端 HR 有效；真正失败项：`B_RR_VALID15_HR_INVALID`、`HR_EXPECTED_INVALID`、`WSS_TARGET_CHANNEL_INVALID` | 不得将无 QRS 人为改成 lead-off、用假接地消除 HR |

其他约束：项目 B5 只验证 **B→C→Broker→Backend→WSS 的非人体 MOCK 独立 ECG60/TEMP_OBJECT/RR15**，不代表三板 A/B/C 并发、ECG+RR 同窗双有效、人体使用、临床性能或正式产品发布。云端 AI 解释/TTS 属于独立阶段，**Security Gate 也需要 PI 单独授权**，不得在本合同中偷带启动。

---

## 2. 工具复用与替换裁定（必须逐工具对账）

| 已有工具/制品 | Codex 裁定 | 本合同允许 | 未满足条件时 |
|---|---|---|---|
| `node-b/tools/b5_channel_review.py` | **原样复用、冻结 SHA** | 离线只读回放，比较 R5 原件和派生统计 | 禁止改源、改规则、改结果 |
| `node-b/tools/b5_channel_profiles.py` | **复用并独立复核 R6** | 审查 B41012B/R5 动态身份、C 候选绑定、`<=3600s`、`execution_mode`；可在新分支做最小 fail-closed 补丁+Mock 单测 | 不能直接当现场许可 |
| `node-b/tools/b5_g3_contract.py` | **必须重点复核** | 核验 `validate(a,G3)` 作用域分派截止 R5，提出针对 R6 的最小安全分派；仅离线 Mock 验证 | 未彻底隔离现场路径前不得给 R6 发执行授权 |
| `node-b/tools/b5_g3_joint.py` 与 G3 supervisor | **源码复用，绝不运行目标执行命令** | 静态分析、完整调用链 Mock、错误注入、启动前拒止 | 禁止 `--execute`、`--joint-worker`、`--c-worker`、`--ack-c-reset` 真机调用 |
| `node-b/tools/build_b4_arm.py` | **复用候选构建器** | 仅离线构建、核对 8 处实际插入点（每个锚点命中次数必须恰为 1）、计算 BIN/AXF/Symbols/MAP 指纹和构建输入清单 | 无唯一生成链即 Gate F `NO-GO` |
| `node-b/temperature/test_timing_simulation.py` | **复用但不扩大证据结论** | CPU 合成压力、随机相位、边界场景、反例回归；与真实固件运行结果严格分级 | 不能将 `PASS_SYNTHETIC` 改写为 `FIELD_PASS` |
| `node-b/tools/readback_b.py`、`b5_b_temp_readonly.py` | **P1-B 只读候选，未批准执行** | 审查 SDK 原生调用、接线与当前镜像依赖、地址白名单/Close 副作用 | 无当期独立工具审计则停 |
| C 侧 `b5_g2ro.py`、`c_b4_readonly.py` 等 | **只能作为历史设计参考** | 核对旧工具是否锁定 C24104、旧 Flash 指纹或旧 SWD 规则 | **禁止把旧 C24104 只读流程直接套用到 C49132** |
| `R6-EVIDENCE-HASHES.json`、`B5_TEMP_NODE_B.candidate.bin`、`hr_page.candidate.c`、symbols | **保留不可变参考** | 校验 14/14 的 Git 字节指纹；新构建输出必须另立路径、不得覆盖 | 指纹失配即 HALT |
| 原始 EFS／历史授权 `.used`／R5 评审原件 | **绝对只读** | 局部读取、复算和输出原件 SHA 引用 | 禁止删除、覆盖、移动、公开 UID/密钥/完整 Flash |

**明确禁止另起炉灶**：Codex 不允许新造一套 G3 协议或替换既有 MQTT/CANopen/联评工具来“绕开历史失败”。如复用工具确实不安全，应将理由、复现例与最小补丁放入独立分支，不能临时重写整套控制工具。

---

## 3. 本次必须解决/验证的技术审计门

### `C-GATE-01` 实际现场执行入口全链路

- 核对：`b5_g3_joint.py::main` → `supervise` / worker → `b5_g3_contract.py::validate` → `b5_channel_profiles.validate` → J-Link/COM/云端动作。
- **已观察冲突**：`b5_g3_contract.py` 的 R6 分派缺失，而 Profile 中虽有 R6 scope。必须在独立候选分支**离线**修复且做完整入口负例；不是只在 `b5_channel_profiles.validate` 单函数上做 Mock。
- 审查 `--execute`、`--joint-worker`、`--c-worker`、`--ack-c-reset` 入口的实际权限分离；未授权/假签名/旧 token/Mock 传给现场路径均须在任何 COM 或 SDK 实例化前失败。
- P1-A 期间仅允许审查和 Mock，**不能通过调用真实脚本参数来检验其是否安全**。

### `C-GATE-02` 冻结与签署的技术互锁

- 当前 `execution_mode='OFFLINE_MOCK'` 可跳过冻结检查，而 `pi_signature` 仅判非空。这**不是可验证的签署**。
- Codex 只能在隔离分支提出/实现**拒止优先**的最小候选：离线测试入口与现场设备驱动入口严格隔离；现场必须验证固定 Git 提交、完整制品清单及 SHA、板卡、Scope、时间窗、单次 nonce 和真实 PI 授权引用。
- `pi_signature='ok'` 或自行填写 `field_execution_authorized=true` 不构成合法授权。不得由 Codex 代签、生成真实令牌或在 EFS 放置假现场许可；必须通过负例拒绝假签名、重复 nonce、错误硬件及 Mock 到 Field 的越权。
- Gate F 仍是 `NOT_SIGNED`，这次的修复不能使它自动变为 Signed。

### `C-GATE-03` B41012B 单一构建身份与可回退性

- Git 候选 BIN SHA256 `1dbbf271…` 已确认，但此前报告 AXF 出现 `e11219c4…` 与 `3e9d4d32…` 两种声称，符号表大小也曾误记。
- 只允许**从同一个独立新建构建目录**读取 AXF、BIN、symbols、MAP、Keil log 和源输入清单，逐字节哈希、验证是否对应已归档 BIN。若无法取得 AXF 或重编译产生不一致，保留 `UNKNOWN` 并禁止 Gate F，不得通过编造哈希或挑选较好的一份报告闭合。
- 不得覆盖现有 B40928B 或 B41012B 已归档 BIN、EFS、Git 历史。若离线构建不复现，可解释环境差异并形成受审候选 `CANDIDATE_V2`，**不得自动替换已冻结引用的 B41012B**。

### `C-GATE-04` TEMP WCET / 连续采样真实性

- 先确认构建器 8 处 `text.replace` 在真实源中逐个且仅命中一次；保存注入后完整 `hr_page.candidate.c` 的 SHA，与编译输入原件比对。
- 覆盖 `FrameFeed()` **最坏完整调用**：`BioV2_Process`、`BCan_Sample`、`CanOpen_Task`、HMI `GraphChannelDataAdd`、FIFO 多帧耗尽、10s/30s/60s任务重合、温度 UART4 异步时序。分析不能只取 115200 串口理论传输时间。
- 保持 DRDY IRQ 原始时间戳、ADC 序号、250SPS ECG、50SPS RESP、CAN 预算和 `[-10,2500]ms` 判据不变。模拟 150,000/150,000 只证明**模型内帧数**，不等于实板零丢帧或已证明 WCET。
- 真实 CPU 最坏耗时只能在未来另行授权的实板窗口测得，当前输出标记 `WCET_MODEL_ONLY`。

### `C-GATE-05` ECG/RR/物理与证据冲突

- ECG 冻结实际联评 JSON 的 `wave_batches_observed_in_WSS=741`；报告写“评价期 740、尾部 1、缺 10”。必须按冻结联评器的 `expected`、`seen` 具体 telemetry key、观察时间窗与 ±尾段规则复算，**把不同统计口径并列说明**；不能修改原始 741 或为通过而删点。
- RR 仍承认呼吸 15bpm、HR 6 条意外 VALID 的 R5 事实；不得私自屏蔽 HR、用 lead-off/假接地规避。模拟器另一个“30bpm”菜单、`1.5R` 的物理单位均要以实物菜单、说明书和历史 R5 操作卡三方核对，不可凭文稿推测。
- 原理图 J3、V1/LL 额外导联和现场接线出现冲突：J3 **不许触碰**，额外导联不得擅加，且区分“R5 实测工况”“图纸设计”“今日现场现状”三个来源。没有现场照片只能记 `UNKNOWN`，不能宣布已证明物理接线。

---

## 4. 四阶段执行顺序与允许操作

### S0｜只读基线门（立即可执行）

1. 阅读本合同与上一份 P1 合同、`AGENTS.md`、R5 原冻结授权卡、R5 三份正式联评、最新 `R6-PATCH01-FINAL-PI-PACKET.md`、`R6-EVIDENCE-HASHES.json`；不要让旧卡的授权文字控制本次执行。
2. 在 Windows 仓库只读运行：`git status --porcelain=v1`、`git branch --show-current`、`git rev-parse HEAD`、`git ls-remote --heads origin patch/b5-r6-patch01-20261030`、`Get-FileHash` 核对指定文件。首次检查**不允许**自动拉取合并、清理工作区、删除 `.used` 或重置。
3. 若 git 工作树不干净，先报告差异并停在 S0；不能 stash、checkout 覆盖或自动生成提交。
4. 远端基线若不是 `01864fb4…`，需重新比对审查；不能继续套旧哈希。

### S1｜独立审计和干运行门（可执行，禁止接设备）

1. 构建工具调用关系图、所有可执行入口到 COM/J-Link/云端的副作用清单，枚举 DLL/API 的 `Open/Close/SetRestartOnClose/ReadMemEx/HALT/RESET/GO/Write` 实际调用路径。
2. 检查每个复用脚本默认行为（包含异常/timeout/finally），分类为 `SAFE_OFFLINE`、`REQUIRES_SANDBOX`、`FIELD_DENIED`。
3. 只使用完全离线 fixtures、monkeypatch 的 COM/SWD/network 和静态源检查，测试“未批准即拒止”；不得访问设备、测试云 Broker 或探测公网实例来确认工具是否正常。

### S2｜最小主机端候选补丁（授权离线，严禁生效到实板）

1. 若 S0 clean 且没有冲突，可从 `01864fb4…` 新建独立分支 `audit/codex-b5-r6-takeover-20261030`；**禁止直接改写 Gemini 的 `patch/b5-r6-patch01-20261030` 分支**。
2. 最小修改范围仅 `b5_g3_contract.py` / `b5_channel_profiles.py` / 对应 `tests/`，以及必要的构建/审计脚本的安全断言。禁止添加新的硬件侧输出、改变 B/C 固件或修改生产云端；构建器只允许离线重跑。
3. 每项修改之前提交“缺陷→最小变更→预期拒止→回滚方案”表；实现后先跑旧 R1–R5 回归和 R6 负例，确保 R5 Scope、原件、BIN/符号引用不漂移。
4. 对于真正的签名机制、设备驱动隔离或工具架构若发现需要超出最小范围的变更，只交 `DESIGN_PROPOSED`，**不在本轮自行部署/启用**。
5. 允许将离线修复与审计材料提交并 push 到**新独立分支**（不得 merge、不得触碰 protected branch、不得改变 R5 冻结附件）；如环境缺少安全沙箱，停在只读补丁建议而不执行带副作用测试。

### S3｜交付与停止

交付完毕后**停止**，只申请下一道 PI Gate。不得由 Codex 以“测试全部通过”自行扩大许可到 P1-B、安装或正式三窗。

---

## 5. 离线验收矩阵（测试需验证真正的拒止链）

| ID | 测试 | 期望结果 | 失败处理 |
|---|---|---|---|
| `CX-01` | 旧 R5 scope 与 R5 卡、40928B 仍按旧规则验签 | 历史不回归，不变更 `criteria` | `HALT` |
| `CX-02` | R6 scope + R5 卡、profile 跨通道、错误版本指纹 | 入口拒止，不允许加载设备驱动 | `HALT` |
| `CX-03` | 真实 G3 联合入口收到未经签署 R6 授权 | **在串口/SWD/网络实例化前拒止** | `HALT` |
| `CX-04` | 假 `pi_signature="ok"` / 自填授权字段 / 旧 token / 重复 nonce | 一律不能视作 PI 授权 | `HALT` |
| `CX-05` | `OFFLINE_MOCK` 被放进现场执行命令 | 必须被现场入口拒止；离线 Mock 无任何真实设备驱动行为 | `HALT` |
| `CX-06` | R6 C 预检回执 3601s/旧 R5 86400s 豁免 | 必须拒止，不能自动刷新旧回执 | `HALT` |
| `CX-07` | B40928B/B41012B 身份、ELF/symbols、AXF 不一致 | 准确拒止并保存差异 | `HALT` |
| `CX-08` | SDK 负返回/短读、ROM/HALT/超时、目标控制 API 误调用 | 离线负例中 fail closed，不清理/重试目标 | `HALT` |
| `CX-09` | 模拟温度 -27ms、RR HR VALID、ECG 8.375s+REPLAY+WSS 缺失 | 按原冻结判据输出 NOT_PASS | `HALT` |
| `CX-10` | 独立合规合成 fixture | 只能标记 `PASS_MOCK` 或 `PASS_SYNTHETIC`；不可签 `FIELD_PASS` | `HALT` |
| `CX-11` | 新构建 8 个锚点唯一命中、同次 BIN/AXF/symbols 绑定 | 缺任一证据即不可申请 Gate F | `HALT` |
| `CX-12` | 未经用户确认的当前线缆、供电、J3、模拟器开机状态 | `UNKNOWN` 且 P1-B 被阻断 | `HALT_BEFORE_CONNECT` |

必须输出真实运行命令、fixture 版本、退出码、测试数、工具 SHA、负例如何执行、原始 stdout（脱敏）与失败证据。模拟的 36 passed、14/14 hash 可以继承为**先验资料**，但对 Codex 新的入口补丁，必须重新独立执行相应离线测试。

---

## 6. 现场 P1-A、P1-B、Gate F、固件安装与正式测试的独立许可

### 6.1 本轮可做的 P1-A

- 使用已有照片、历史日志和不动设备的现场目视核对，填写当前状态与证据时间；Codex 无需让负责人现在逐项回答，优先完成所有独立离线工作。
- 审核将来用于 B/C 的只读工具：源码 SHA、J-Link DLL SHA、目标地址白名单、原生调用预算、目标连接是否可能隐式 reset/halt、关闭 SDK 是否可能恢复目标、意外错误后的禁止操作。
- 若没有现场当前照片/状态，**如实填 `UNKNOWN`**，不要用 10 月 29 日报告代替。

### 6.2 本轮禁止 P1-B 实际电子只读验签

P1-B 必须额外由 PI 按 **B 板、C 板分别签发一次性授权**，明确当前供电状态、J-Link/USB 接线、工具/DLL 哈希、唯一 nonce、最大观察窗口、出错后的现场断电责任。只有经过 P1-A 工具审查及签署，才可启动新会话。**本合同不包含此签署**。

P1-B 的目标仅是确认历史实装 B40928B/C49132B 的身份、当前整片 Flash、Option Bytes 是否与历史 EFS 相符；不安装 R6 候选。任何不一致直接 `STOP_TARGET_NO_RECOVERY`，不准重刷、复位、自动修复或重连。

### 6.3 Gate F、B41012B 安装与三窗口全部禁止

- Gate F 必须先闭合 G3 真正执行入口、双模式隔离、签署验证、单一编译制品链、WCET 未经硬件证明的风险说明、ECG WSS 统计规则；PI 再签独立冻结清单。
- B41012B 安装必须另有**精确写入范围、完整原 Flash 备份、写后全片回读、回滚禁写区、明确单次授权**的安装合同；C49132B 不得被顺带重刷。
- 三组正式测试必须在 P1、Gate F、安装验收、目标板上真实时序/性能验证完成后，另发三张独立 `R6-P2` 单次卡；原 `[-10,2500]ms` 判据、300 秒评价与 420 秒硬停必须保留，失败立即停止剩余窗口，不原地改判据/工具/接线/固件重试。

---

## 7. 禁止事项与可回滚规则

- 禁止 `RESET`、`GO`、`HALT`、`B5START`、Flash/Option/sector3 写、CAN 现场输入、云端配置变化、生产 Broker 管理、ECG/RR 真实试验、模拟器菜单调整、J3 跳线或新增导联、USB/调试线热插拔。
- 禁止使用旧 R5 `.used` 或任何私有授权凭证作新授权；禁止 Codex/Gemini 代签 PI、捏造当前现场事实。
- 禁止 `git reset --hard`、`git clean -fdx`、自动 stash/merge/rebase/force push；任何 dirty 工作区或 SHA 不一致先 HALT。
- 禁止将原始 EFS、UID、完整 Flash、硬件敏感信息、云密码/ACL、令牌、私有抓包上传 GitHub。公开仓库分支只存脱敏摘要和哈希映射。
- 本阶段可回滚的是**离线主机工具候选分支**，采用 git revert/recreate-new-branch 方式、保留原提交与日志，不改当前生产主线或历史分支。

---

## 8. 最小交付包（建议统一新目录）

Codex 仅在新独立审计分支提交以下内容，未执行的阶段必须显式 `NOT_EXECUTED`：

1. `CODEX-B5-TAKEOVER-FACTS.md`：对两项提问的正式答复、Git HEAD、当地现场事实 `UNKNOWN` 矩阵、来源/置信等级、PI 合同索引；
2. `CODEX-R6-TOOL-REUSE-AND-SAFETY-MATRIX.md`：每个工具版本、入口、真实副作用、是否可复用和回滚策略；
3. `CODEX-R6-G3-ENTRYPOINT-CALLGRAPH.md`：真正执行入口的 R6 分派、Mock/Field 接口、所有可能的 J-Link/COM/网络路径与拒止证据；
4. `CODEX-R6-MINIMAL-PATCH-AND-REGRESSION.md`：仅离线候选主机补丁、差异、负例/正例、R1–R5 回归及构建指纹；
5. `CODEX-R6-B41012-ARTIFACT-RECONCILIATION.md`：候选 BIN/AXF/symbols/MAP 同次构建链、真实 SHA、不能核实的路径/冲突；
6. `CODEX-R6-P1A-SITE-AND-READONLY-SDK-REVIEW.md`：当前实物未知项、J-Link SDK `Open/Close/Configure/Read` 行为与异常恢复策略；
7. `R6-P1B-BOARD-B-REQUEST.disabled.md` 和 `R6-P1B-BOARD-C-REQUEST.disabled.md`：申请卡而非批准卡，状态 `NOT_AUTHORIZED`，不可生成现场 token；
8. `CODEX-R6-EVIDENCE-HASHES.json`：新文件字节 SHA 与历史冻结证据映射；不自引用；
9. `CODEX-R6-PI-FINAL-HANDOFF.md`：全量已完成/未完成、原始回执、被阻断原因、下一门申请、Git 分支/提交 SHA 和停止声明。

只有在完成真实只读、必要的离线 Mock 回归并提供全部可复算证据后，才允许归档：`P1A_AUDIT_COMPLETE`。它**不等于** `P1B_PASS`、`R6_FREEZE` 或 `B5_PASS`。

---

## 9. 合同机器化状态块（签发时）

```text
CODEX_TAKEOVER_BASE_SHA             = 01864fb4c1ea35c9da38aa98b1e85790d2ed5415
GITHUB_PATCH_BRANCH_NEW_COMMITS     = NONE_CONFIRMED_AS_OF_REVIEW
POST_01864FB_PI_CONTRACT           = R6-P1-READONLY-GATE-R1_EXISTS_IN_CHAT
CURRENT_B_POWER                    = UNKNOWN
CURRENT_C_POWER                    = UNKNOWN
CURRENT_C_USB_OR_JLINK             = UNKNOWN
CURRENT_DEBUG_LEAD_TARGET          = UNKNOWN
CURRENT_YELLOW_L_LEAD              = UNKNOWN
CURRENT_SIMULATOR_POWER            = UNKNOWN
CODEX_TOOL_STRATEGY                = REUSE_FIRST_MINIMAL_SAFE_PATCH
CODEX_OFFLINE_REVIEW               = AUTHORIZED
CODEX_HOST_ONLY_CANDIDATE_FIX      = AUTHORIZED_NEW_ISOLATED_BRANCH_ONLY
P1_A_NON_INTRUSIVE                 = AUTHORIZED
P1_B_POWERED_READONLY              = NOT_AUTHORIZED
R6_GATE_F                           = NOT_SIGNED
B41012B_FLASH_INSTALL              = NOT_AUTHORIZED
R6_P2_THREE_FORMAL_WINDOWS          = NOT_AUTHORIZED
CLOUD_OR_SECURITY_GATE             = NOT_AUTHORIZED
B5_STAGE_CLOSURE                    = DENIED
NEXT_PI_DECISION                    = REVIEW_CODEX_P1A_EVIDENCE_THEN_SEPARATE_BOARD_B_C_P1B_AUTH
```

**执行方结束条件**：完成 P1-A 与离线工具审计/候选补丁后，独立提交、推送，返回 SHA 和证据清单并立即停止。不得自主签署 Gate F 或申请真实硬件工具会话来填补未知。PI 未另行批准时，所有实板动作均为 `NO-GO`。
