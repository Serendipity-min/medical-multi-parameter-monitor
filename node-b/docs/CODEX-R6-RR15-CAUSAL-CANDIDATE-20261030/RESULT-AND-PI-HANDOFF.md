# R6 RR15 异常心率专项：离线裁定与 PI 交接

**ROOT_CAUSE_UNRESOLVED。** 已确认六个异常 HR 事件由原 BioV2 C 的峰/周期资格路径产生，非云端新增；仍不能从现有记录排除弱真实 QRS，或唯一确定工频、RESP耦合及其它噪声的物理来源。因此本轮没有修改算法、阈值或固件，没有制造一个“RR15模式禁HR”补丁。

工作基线为 `b9b17a7657f101e8901a24115da8538becc420d0`，独立分支 `codex/b5-r6-rr15-causal-candidate-20261030`。本交付为工具修复和因果证据候选，**没有可烧录的新固件**；提交SHA在提交推送后另行给出，避免自引用。原R5/R6 RR15正式NOT_PASS/3保持不变。

## 输入和采样完整性

| 数据 | 已核验输入 | 连续性/来源 |
|---|---|---|
| 当前R6 RR15 | 2939块、123870个两份一致原始帧；blocks SHA `e8cbb06f…` | seq缺口0、flags非零0、无无效status帧；IRQ ms步长4/5，cycles步长672018..672452 |
| 当前已通过ECG60 | 2943块、123616帧；blocks SHA `acea4fd1…` | seq缺口0、flags非零0；cycles步长671952..672408 |
| 历史ECG60/90/120各01/02 | 6份、共138607帧 | 从原running slots、每块hash/offset及已绑定暂停RAM重新导出，与历史CSV逐字节相同；01开发、02留出 |
| 独立R5 RR15留出 | 3561块、150074个两份一致帧；blocks SHA `0351f74c…` | 工况/回执/bundle链核验；旧失败标签已知，本次未以留出波形挑阈值 |

完整SHA见 [input-integrity-and-C-agreement.json](../../evidence/CODEX-R6-RR15-CAUSAL-CANDIDATE-20261030/input-integrity-and-C-agreement.json) 及 [existing-host-regressions.json](../../evidence/CODEX-R6-RR15-CAUSAL-CANDIDATE-20261030/existing-host-regressions.json)。窗口binary整体、index、每块offset/hash、双副本资格及启动epoch均核验；不把未获资格的边缘帧拼成缺口内插。

CH2=ECG、CH1=RESP，seq位于offset12、IRQ cycles位于16、IRQ ms位于20，flags位于9。flags是源采样异常标志，不是Lead-Off。原始status完整保留；没有从可变status位臆造“导联脱落”。原CAN槽与raw逐seq时戳一致，flags0，RESP due严格为seq%5==0且相邻due差5：RR有24770条、ECG有24719条，均无due缺口。这里确认250Hz/50Hz原链路的名义节奏与记录连续性，不是新硬件精度测量。

## 同算法 C 回放及六事件

算法C与B41012同次构建来源一致，原码/header不改。在EFS内编译纯host库，检查C的sizeof=120和全部30字段offsetof；额外只读C观察包装直接包含原文件并读取静态周期状态，**每个实际输入帧的120字节诊断与不加观察器的原库完全一致**。

| 事件 | 板端HR / 阳性诊断数 | 获资格的真实周期序列（ms） | 最后峰宽（ms） |
|---|---|---|---|
| 1 | 52 / 2 | 996,1269,1156 | 12 |
| 2 | 64 / 5 | 932,1113,856 | 12 |
| 3 | 82→73 / 6 | 736,841,684；随后加入820 | 20（82首次资格） |
| 4 | 38 / 2 | 1445,1596,1729 | 12 |
| 5 | 58 / 4 | 1053,888,1029 | 16 |
| 6 | 39 / 1 | 1521,1673,1328 | 20 |

相应中位数和原C的20%稳定窗口给出这些HR；没有用预期RR模式把输出改成0。`hr_last_cycle_ms`实际上是最后接受峰的绝对设备时间，不能当周期长度；本表来自C内intervals和逐峰时间差。完整峰宽、peak/gate比、seq、设备时间及更新证据见 [six-event-period-and-signal-evidence.json](../../evidence/CODEX-R6-RR15-CAUSAL-CANDIDATE-20261030/six-event-period-and-signal-evidence.json)。

原C与板端逐seq对齐：两窗600/600评价期HR/valid一致，RR六事件的20个阳性诊断均重现。全会话回放预热后RR为2821/112624个样本HR有效，8段episode；其中两段在原评价期外，**不能把8段说成原六事件不一致，也不能将2.50%的逐样本占比混作20/600的SWD占比**。

仍有模型未闭合：RR评价期1个非有效HR诊断的last_good/count不同，13个IRQ ms字段不一致；ECG有15个IRQ ms字段不一致；RMS最大差分别约0.60/0.86codes。记录是非原子SWD读，原getter/Tick的实际调用时刻未采集。每帧额外Tick+0/+1ms的RR阳性样本仍2821，+4ms为2819，这只是敏感性实验，不能伪称实机调度已复现。因为不改阈值，本轮不会把未解释细节藏在所谓“修复通过”中。

## 对真实QRS、工频与耦合的区分

六事件各保留前8秒/后4秒原始CH2、原C量化UI滤波输出及CH1 RESP波形，另有独立ECG60正例，共7套PNG/PDF、14个最终图文件，全部在EFS。候选峰竖线不是独立QRS标签。初图标题裁切已纠正并保留初图，最终使用两行标题；所有数值面板已核验，重绘不改变原始数组。

观察支持干扰，但不足以判物理根因：

- 六事件8秒原始CH2 RMS约345.6..359.2codes，峰绝对值/RMS约2.34..2.67；已通过ECG正例具有明显重复QRS形态。幅度和形态差异**不构成一个允许直接挑阈值的真值标签**。
- 用实际IRQ ms做50/100Hz联合最小二乘分解，可解释约67.2%..86.6%功率；按名义250Hz报告的FFT主峰约50.025Hz只是频率格点描述，不是精确市电频率测量。
- 剩余CH2与RESP的线性相关约0.318..0.530；50Hz幅度包络与RESP相关的符号/强度跨事件变化（约-0.490..+0.597）。这支持共享扰动或耦合假设，却不证明耦合方向、单一来源或没有弱QRS。
- 原C确实接受了一些12..20ms窄峰，再靠偶然稳定的三个间隔获得HR资格。但现有16组已知无QRS合成噪声没有复现误报，因此不能宣布一个普适质量门缺陷已被独立证实。

没有将去工频残差/FFT结果替代真实ADC回放，也没有把变换数据当成参考ECG。当前证据足以确定算法路径，未足以确定原始信号的唯一类别。

## 正反例、留出与真实退出码

预登记见 [PREREGISTRATION.md](PREREGISTRATION.md)，不改算法的开发决定在开启留出前单独封存：[DEVELOPMENT-DECISION-BEFORE-HOLDOUT.md](DEVELOPMENT-DECISION-BEFORE-HOLDOUT.md)。

| 验证 | 结果 / 真实进程退出码 |
|---|---|
| 工具定向单元测试（最后guard运行） | 17/17，0失败/错误，exit0；目标/DLL/网络调用0 |
| 原host算法/通道隔离/边界三套 | 27/27、28/28、10/10，共65项，三个exit0 |
| 新ECG60真实正例 | 回放45s预热后112368/112368样本HR60有效；exit0 |
| 历史ECG60/90/120，01开发+02留出 | 6/6数据集预热后正确率及有效覆盖100%；exit0 |
| 独立R5 RR15留出 | 2740/138828样本HR有效（1.9737%），问题仍在；表征执行exit0，不是反例通过 |
| 新合成QRS正例 | 24组含相位/随机seed留出；22组正确覆盖100%，两组低幅带噪ECG120为94.4356%/94.4444%，单列覆盖限制，不新增验收门槛 |
| 其它已知非QRS噪声 | 16组，含正弦1/8/25/50/100Hz、50Hz调幅/色噪声/RESP叠加、白噪声，均无有效HR；固定seed/相位留出，不参与调参 |

新增40组挑战应按上述真实覆盖及噪声结果报告；`corpus`进程exit0仅表示完成表征，不能写成“40项全部PASS”。预登记规定相对基线非回归/±2bpm，没有登记新的95%验收线；过程中把95%称为预登记目标的措辞已撤回，未改预登记文件、原始结果或算法。两组94.4%是描述性覆盖限制，不用新判据重判。详见 [corpus-and-holdout-results.json](../../evidence/CODEX-R6-RR15-CAUSAL-CANDIDATE-20261030/corpus-and-holdout-results.json)。

保留其它失败/纠正：单元测试首跑exit1是单副本合成夹具误降序号水位，修正夹具后通过；最初前后速率字典比较因Python整数key与JSON字符串key误报不等，规范化后相同；一次封存脚本将绝对路径交给git show，脚本exit1、git128，改为相对路径后封存exit0。没有重跑制造原失败；原工具记录/私有原件和语义区别见 [offline-boundary-and-exit-ledger.json](../../evidence/CODEX-R6-RR15-CAUSAL-CANDIDATE-20261030/offline-boundary-and-exit-ledger.json)。

## 本轮补丁前后与制品

只修复/补足离线回放工具：EFS入口及保留host制品、index/source/header哈希、IRQ/status/epoch/缺口统计、禁止频谱压缩缺样、uint32暖机、C offsetof、真实峰时间语义、逐seq诊断与C观察包装；新增专项分析/语料驱动和测试，未重新开发整套硬件工具链。

缺一帧的频谱反例：旧工具错误给出 `RAW_UNCALIBRATED`，新工具给出 `INSUFFICIENT_CONTIGUOUS_SOURCE`。同一真实输入、同一C的前后样本数、HR率值直方图、HR有效样本与episode数完全相同，当前RR仍2821个有效HR样本。**这是工具修复，没有宣称修好了异常HR**。见 [before-after-tool-counterexamples.json](../../evidence/CODEX-R6-RR15-CAUSAL-CANDIDATE-20261030/before-after-tool-counterexamples.json)。

| 制品 | SHA256 |
|---|---|
| 原算法C，前后均相同 | `3adca55cb1eb1fa3ed8e4148f837287d0454bcc2c08ae77a8f73deb1dac156a7` |
| 原header | `76198016006ab8de6126a7cb051aeb3ab296c5655152c74cf5565bd85aba0913` |
| 最终纯host库（不是MCU制品） | `fb9d85a6e5d83c5d54c00e825d9a92f43c18acb2da02eb995fa727ce8447c0ad` |
| 只读观察host库 | `a7df0d27fc557b2d99af2c0725dda0a80e8fe7fd5673690bbc52969100940bb4` |

编译器、ABI桥、不同构建的实际库SHA均见 [artifact-provenance.json](../../evidence/CODEX-R6-RR15-CAUSAL-CANDIDATE-20261030/artifact-provenance.json)，不宣称不同host构建二进制逐字节相同。原C/header、冻结reviewer/profile与旧criteria共12项原字节保持不变；未进行MCU构建、烧录或正式评测器重跑。

## 停止与后续 PI 决定

当前只按用户报告保持未上电，本轮没有接线/电源操作、目标SDK/COM连接、RESET、B5START、Flash或云业务操作。GitHub仓库fetch/push是本次明确要求的VCS交付，不包含服务器服务/凭据/ACL修改。不要为读本报告自行上电或改线。

建议PI先决定是否批准一个**有源端参考标签**的非人体区分试验：确认SKX在RESP15条件下是否仍实际输出ECG，并获得同接线CH2源端参考/干扰对照，预先冻结读数、接线、次数与停止责任；禁止短接、伪造Lead-Off或模式屏蔽。若以后获得可靠无QRS标签，才据独立正反例提出模式无关最小质量门；弱带噪ECG120覆盖限制需同时保留/验证。此建议不是当前实板许可。

私有波形与逐帧状态通过忽略的 `node-b/build/codex-RR15-causal-current-pointer.json` 定位到本次EFS job，`PI-PRIVATE-INDEX.md`含最终波形链接。Git仅统计、源码和哈希：[private-evidence-digest-index.json](../../evidence/CODEX-R6-RR15-CAUSAL-CANDIDATE-20261030/private-evidence-digest-index.json)。公开交付整体哈希见 [EVIDENCE-HASHES.json](EVIDENCE-HASHES.json)。推送后停止，等待PI是否授权后续实板复验。
