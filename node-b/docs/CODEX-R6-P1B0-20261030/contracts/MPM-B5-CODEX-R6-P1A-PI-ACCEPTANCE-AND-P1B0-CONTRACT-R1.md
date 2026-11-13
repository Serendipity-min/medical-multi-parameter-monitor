# MPM-B5｜Codex R6 P1-A PI 验收裁定与 P1-B0 离线准入收尾合同（R1）

> **合同编号**：`MPM-B5-CODEX-R6-P1A-PI-P1B0-R1`  
> **签发日期**：2026-10-30  
> **执行者**：Codex（不是 Gemini）  
> **仓库**：`Serendipity-min/medical-multi-parameter-monitor`（PRIVATE）  
> **本次审查冻结对象**：`audit/codex-b5-r6-takeover-20261030@9f5a6641fec2bcdb575f5f9ff549b8e9b0223820`  
> **起始祖先**：`patch/b5-r6-patch01-20261030@01864fb4c1ea35c9da38aa98b1e85790d2ed5415`  
> **本合同唯一新增许可**：`P1-B0_OFFLINE_ENTRY_AND_ADMISSION_DESIGN`。**未授予 P1-B 实板上电/SWD/J-Link，未授予烧录、RESET、B5START、正式三窗口。**

## 1. PI 验收裁定（证据分层）

### 1.1 本轮可接收事项

1. GitHub 已独立核实提交 `9f5a6641fec2bcdb575f5f9ff549b8e9b0223820` 及其独立分支；相对 `01864fb4...` 增加一个审计提交，不需要回滚 Gemini 分支、改写 main 或重做 R5 历史。
2. `mock-regression-02.json` 记录 **151 个离线测试、退出码 0、失败 0、错误 0、跳过 0**。这是 **PASS_MOCK**，不是目标板运行验收。本合同不要求重复同一套测试来赚取新的 PASS。
3. `r5-replay-03.json` 记录 ECG60、TEMP_OBJECT、RR15 三项历史正式回放均维持 `NOT_PASS / exit_code=3`，失败集合完全一致。R5 历史记录不可改判。
4. `CODEX-R6-EVIDENCE-HASHES.json` 包含 54 项索引；PI 核实了 GitHub **54/54 路径存在、大小一致**，并对八项高风险文件重新计算 **8/8 SHA256 一致**。54 项全量哈希匹配是 Codex 自身的运行回执结论；本裁定不将其冒称为 PI 全量独立复算。
5. B41012B 独立编译回执包含单次构建的 BIN、AXF、symbols、MAP、实际编译源码和工具指纹；BIN SHA `1dbbf27177caa429f037ac72c43581a519e8ff70ac6224411c9c4ffe9529432d` 与旧归档候选一致。**AXF 的原始哈希不同**，本轮比较报告支持差异位于非加载 `.comment` 元数据，但后续正式冻结必须从**同一次构建**选择一套真实制品链，不能任意拼接。
6. G3 主机入口已在离线候选中识别 R6 Scope，同时默认 `FIELD` 对 R6 一律拒止。未建立可信的 PI 验签机制，**不得宣称现场授权机制已完成**。
7. WSS 历史严格采用冻结评测器集合：`expected=751`、`seen=741`、`missing=10`；评价期原集合命中为 739，尾部允许窗口新增两项，另一个评价期已见批次非 expected。不要再采用 `750-740+1` 的混算口径。

### 1.2 当前状态

```text
P1A_DELIVERY                  = ACCEPTED_WITH_OPEN_RISKS
P1A_OFFLINE_AUDIT             = CLOSED
P1A_151_TESTS                 = PASS_MOCK_RECEIPT_EXIT_0
R5_ECG60_FORMAL               = NOT_PASS / EXIT_3
R5_TEMP_OBJECT_FORMAL         = NOT_PASS / EXIT_3
R5_RR15_FORMAL                = NOT_PASS / EXIT_3
R6_FIELD_G3                   = FAIL_CLOSED
P1B_BOARD_B                   = NOT_AUTHORIZED
P1B_BOARD_C                   = NOT_AUTHORIZED
R6_GATE_F                     = NOT_SIGNED
B41012B_FLASH_INSTALL         = NOT_AUTHORIZED
R6_P2_THREE_FORMAL_WINDOWS    = NOT_AUTHORIZED
B5_STAGE_CLOSURE              = DENIED
NEXT_ACTION                   = P1B0_OFFLINE_ENTRY_AND_ADMISSION_DESIGN
```

## 2. 权限表：本合同不等于实板执行卡

| 行为 | 本合同决定 |
|---|---|
| 阅读、审计、复用已有 G3 BLink/CLink、J-Link SDK 源码 | **GO：静态与离线** |
| 新建独立审计分支，设计/实现**默认禁用**的 P1-B 专用薄入口 | **GO：仅离线候选** |
| 负例、假 SDK、异常注入、模拟授权/假签名/重复 nonce 测试 | **GO：隔离 CPU/Mock** |
| 查阅已有现场照片/资料，记录负责人自述的当前状态 | **GO：只读资料，不能当作当日硬件实测** |
| 加载真实 J-Link DLL、枚举探针、打开 COM、连接目标板 | **NO-GO** |
| 上电、拔插、换板、冷态转接 J-Link、改导联、测阻、动 J3 | **NO-GO** |
| RESET/HALT/GO、写 RAM/Flash/Option Bytes、执行 B5START、AT、MQTT 云操作 | **NO-GO** |
| 新建有效现场 token、签署 Gate F、启用 B/C disabled 申请 | **NO-GO** |
| B41012B 烧录、正式 TEMP/RR/ECG 测试、并入 main | **NO-GO** |

**执行原则**：沿用 Codex `9f5a664...` 的审计结果；不从零重写工具、不打开冻结 `b5_channel_review.py` 和 R5 criteria 的修改权限；最小差异、可回滚、证据保留。所有被动证据读取与代码修改必须在与旧分支隔离的新分支进行。项目私有凭据/UID/原始整片 Flash/Option Bytes 不上传公开日志。

## 3. P1-B0 的唯一技术目标：一套专用只读入口，两个独立单板方案

### 3.1 入口分离

Codex 可在新分支建立例如 `node-b/tools/b5_codex_p1b_readonly.py` 的**候选**工具与 `node-b/tests/test_codex_p1b_gate.py`。名称可以微调，但不允许复用 `b5_g3_joint --execute`、`--c-check`、旧 G2RO 或 `readback_b.acquire` 作为 P1-B 真正执行入口；后者含与本阶段权限不符的任务/CPU 控制路径。

要求：

- 无参数 / `--plan`：**只输出 `enabled=false`、scope、工具 SHA、目标板与读白名单，不加载 DLL、不实例化 SDK、不枚举/探测**。
- 现场执行子命令：在本轮候选版本 **无条件 `P1B_FIELD_NOT_AUTHORIZED`**，且在创建任何 marker、child、COM 或 SDK 对象之前拒止；不要为了阳性测试加入临时绕过字段。
- Mock 入口必须由测试进程传入不可从申请 JSON 自选的 `execution_context=OFFLINE_MOCK`，使用假 SDK，不获得生产路径调用权。
- B 与 C 必须有不同 scope、独立身份引用、只读白名单、输出目录、有效期、nonce 和回执；共用底层纯只读代码可以，不能共用现场 token。
- 现场执行逻辑未来需要父进程与 worker 的同一授权 SHA/nonce/board/scope 绑定；父原子消耗一次 nonce，worker 校验内容，不得只检查 `.used` 文件存在。

### 3.2 身份冻结（历史实际实装，不是候选）

| 板卡 | 历史预期 BIN | 历史预期完整 Flash SHA256 |
|---|---|---|
| Node-B | **B40928B**，40928 字节，BIN `a1cf57648ca3787de30c1ad7055634c278fbbde538bb0bc562961bd212182ed2` | `ceebec5a91835aed3cb70c683fd8de5142e5ba59a2163a1968cec182018b48ae` |
| Gateway-C | **C49132B**，49132 字节，BIN `72131dbb5ef6bc0e0d33e328925c685403bae928aea9447a81f8291c6ae5c1ab` | `9bba23b436f079183296fa98dcaeed047eb919ba8597d75a85bc144bc48417fd` |

UID、Options、sector3、DISARMED flags 等敏感身份用已有受限 EFS 回执和实际地址绑定进行对照；**不能猜测地址，不能上传敏感字节**。当前板卡是否仍有此身份：`NOT_VERIFIED`。严禁把 B41012B 当作已实装。

### 3.3 候选读操作与预算，只供离线审查

- 每板最多 **1 个**新会话、`retries=0`；候选总体预算 `<=90s`，单次 1 MiB 全片读取计划上限 `<=45s`、其他单调用 `<=5s`，**这些均为待审目标，不能因 Mock 通过就声明现场达标**。Codex 应对照历史真实 SDK 耗时检验可行性，超预算则保留 `NOT_READY`，不增加重试次数。
- 候选白名单：完整 Flash `0x08000000` 读取 `1,048,576` 字节 **1 次**；options `0x1FFFC000` 读取 **16 字节 1 次**；身份/容量/状态仅既有已验证精确地址及长度。C 的 DISARMED flags 地址由 C49132 身份绑定取值；不能直接复制旧 C24104 常量。
- 硬禁止：`JLINKARM_Reset/Halt/Go`、target-memory writes、DRW 写、配置寄存器写、Flash unlock/erase/program、ROM 恢复、读 UART 数据寄存器、任何网络/业务流量。`SetRestartOnClose` 等 SDK **策略调用必须逐项解释副作用**，不准视作自动安全。
- 全部 SDK 原生调用返回值须记录真实数字；区分负错误、正短读、部分数据、超时；任何异常只可 `STOP_TARGET_NO_RECOVERY`，不再读取/补读、不自动重连/复位/GO。

## 4. SDK 的隐式 CPU 控制与 Close：必须正面处理的风险

已核验的静态风险：

1. `OpenEx/Device/Connect` 可能产生 SDK 内部 CPU 状态变化。没有显式 RESET/HALT/GO 调用，不代表目标一定未被暂停或重启。
2. `SetRestartOnClose=1` 和 `Close` 可能恢复运行；直接调用底层 DLL 的 `Close` 可能绕过上层日志与超时保护。
3. 旧 `b5_b_temp_readonly` 的部分错误/取消路径会跳过 Close。不能把进程被 `taskkill` 视作目标恢复。
4. `readback_b.acquire` 含真正 Halt/Go，**不得**作为本阶段零控制只读基础。

本合同要求 Codex 在离线 Mock 中覆盖：`OpenEx` 负返回、Connect 隐式状态假设、Device 改写环境、单次 Close 出错/超时、设置关闭策略失败、SIGTERM/异常处理、正短读、临时掉线及 `taskkill` 路径。每条路径必须输出**是否尝试 Close、是否完成 Close、最后已知目标状态、是否需要 PI 指定断电**，不得以 `verified_running=true` 伪造现场实际状态。

如无法从 SDK 原生文档、既有原生回执和已获准的离线分析确定副作用边界，结果必须是 **`SDK_RESIDUAL_RISK_UNRESOLVED / P1B_NO_GO`**。可以提出有证据的替代只读工具比较，但不能自行下载并使用新的调试器驱动。任何目标上的实证测试必须由未来独立授权明确覆盖。

## 5. 可信 PI 授权与一次性 nonce

本阶段仅设计和 Mock 测试；**不得自行生成可现场接受的 PI 私钥、签署文件或有效 nonce**。

- 建议外部信任根使用 PI 自主管理、仓库外保存私钥的非对称签名，候选验证程序只内置预审公钥/指纹，且须先获 PI 确认；不要用仓库内可编辑的 `pi_signature: "ok"`、布尔 `owner_approved`、可自填 `field_execution_authorized=true` 当作权限。
- 未来待签对象必须至少绑定：完整 repo commit/tree、工具源码 SHA/DLL SHA、B/C 唯一板卡、身份引用、只读地址/次数、预算、scope、nonce、授权起止 UTC、当日供电/接线前提、允许的 SDK Connect/Close 风险和具体异常人工责任。
- 离线回归要覆盖：伪造签名、错误公钥、修改作用域、错误板卡、过期/未来生效、重复 nonce、跨板重放、修改工具哈希、错绑地址、未确认 Close 风险等的拒止；同时有纯 Mock 合规阳性夹具。
- 信任根与签名格式未获 PI 签署前，正式执行入口保持禁用，不要求用户提前做无法验证的“签名”动作。

## 6. 今日现场事实：先前报告是负责人自述，不是连接实测

`CODEX-R6-P1A-SITE-AND-READONLY-SDK-REVIEW.md` 登记：负责人报告 **C 的 USB 在 C、J-Link 板端在 B、设备未上电、黄 L 在 LL/F、SKX 在呼吸模式**。这些事实仅对该次报告时间有效，电脑端插头状态、是否由 USB/J-Link 反向供电、VTref、实际针脚/方向、SKX 当前具体菜单、状态灯仍 `UNKNOWN`。

本合同只允许以**已有照片、已有读数或负责人自愿提供的非侵入式现场目视记录**补齐证据；不允许 Codex 要求为填表而上电、拔插、转接、测阻、查询设备、移动黄 L 或调整模拟器。在下一次物理许可签署当刻，仍应重新确认现场状态，不得永久继承今天的口头状态。

## 7. 最小修改与成果验收（一次提交，禁止反复补测）

### 7.1 代码范围

可以修改/新增：独立 **P1-B0** 薄入口及相应隔离测试，最多局部复用经过核验的 BLink/CLink **只读方法**。确需重构的底层 API 必须先列明旧行为、最小变化、拒止证据、回滚；不得修改旧 R5 正式联评器、criteria、历史现场卡、Flash 更新器、核心采样固件、云端逻辑，也不得改变旧 G3 的 R1–R5 行为。SDK 真实导入和执行仍禁用。

### 7.2 必须交付的四类成果

1. **入口和门禁表**：记录所有子命令/路径何时加载 DLL、触及 target、消费 nonce、创建 worker、何时拒止；确保本轮无任何真实硬件入口，正反例全覆盖。
2. **SDK/Close 风险矩阵**：每条正常/故障路径的接口、原生返回、潜在目标状态、保全/人工断电责任、未证实残余；附必要的模拟故障日志。
3. **逐板申请修订**：原两张 `R6-P1B-BOARD-{B,C}-REQUEST.disabled.md` 保持原样（不可启用），以新文件补充完整权限/地址/预算/现场条件和可签署模板；默认 `enabled=false`、`token=NOT_CREATED`。
4. **PI 单页裁决包**：新分支 SHA、变更文件/哈希、CPU 回归真实退出码（包括失败原件）、可复用工具、未闭合技术点、B/C 各自 `READY_FOR_PI_REVIEW` 或 `HALT`；不得写 `P1B_PASS`。

### 7.3 停止门与交付方式

- 在新独立分支工作，建议 `audit/codex-b5-r6-p1b0-20261030`；父提交必须固定 `9f5a6641fec2bcdb575f5f9ff549b8e9b0223820`。禁止强推、覆盖旧审计分支、合并 main、自动建或合并 PR。
- **一次汇总候选**：离线测试可按需要运行，但不得将失败转换为伪 PASS；一次性综合修复后输出一个最终审查包，不反复要求 PI 根据某一小错误开展正式实板测试。
- 错误或证据不足：保留原始回执，状态 `HALT / NOT_READY`；**不得**修改验收标准、补签字段或自行开放现场接口。
- 推送后由 Codex 停止；只有 PI 在后续独立消息中明确核准**具体板卡**的 P1-B 才能真正连接。B 和 C 分开批准、分开 nonce、分开时间窗、分开停止回执。

## 8. 未来门控顺序（本合同均未授权执行）

`P1-B0 OFFLINE REVIEW → PI REVIEW → P1-B BOARD-B single read-only session → PI REVIEW → P1-B BOARD-C single read-only session → PI REVIEW → R6 Gate F 候选制品/工具/判据冻结签署 → 独立 B41012B install/rollback authorization → 实装回读与候选身份二次冻结 → R6-P2 independent formal windows`。

如果任一 P1-B 测试因 SDK 原生调用或目标状态不明失败，必须停止该板和后续板的授权推进，不自动重试。不因单板只读通过而认定候选固件、ECG/TEMP/RR 或云链路通过。设备仅用于非人体样机工程验证；医疗精度和系统发布不在本阶段授权范围。

## 9. 唯一合法收尾状态模板

```text
CODEX_P1A_ACCEPTANCE          = ACCEPTED_WITH_OPEN_RISKS
P1B0_OFFLINE_CANDIDATE        = COMPLETE_OR_HALT_WITH_EVIDENCE
P1B0_NATIVE_TARGET_CALLS      = 0
P1B_BOARD_B                   = NOT_AUTHORIZED
P1B_BOARD_C                   = NOT_AUTHORIZED
TRUSTED_PI_FIELD_SIGNATURE    = DESIGN_ONLY_OR_NOT_READY
SDK_CONNECT_CLOSE_RISK        = DOCUMENTED_NOT_FIELD_PROVEN
R6_GATE_F                     = NOT_SIGNED
B41012B_INSTALL               = NOT_AUTHORIZED
R6_FORMAL_THREE_WINDOWS       = NOT_AUTHORIZED
R5_FORMAL_ALL_THREE           = NOT_PASS_EXIT_3_PRESERVED
B5_STAGE_CLOSURE              = DENIED
NEXT_ACTION                   = STOP_WAIT_PI
```

---

**签发裁定**：`P1A_ACCEPT / P1B0_OFFLINE_GO / P1B_BOARD_B_NO_GO / P1B_BOARD_C_NO_GO / R6_FORMAL_NO_GO`。本合同**仅授权离线候选工具与 PI 准备工作**，任何目标连接操作均须另行单板授权。
