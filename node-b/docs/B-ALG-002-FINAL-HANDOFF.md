# MPM-B-ALG-002 唯一阶段交接

最新：按负责人固定ECG60/呼吸15/1.5R/窒息0、波形周期20不变，完成一次45秒。采集/监督0、分析3；实际ECG60互证，但30秒评价中38次RR观察全部无效，RESP_PATH_NOT_OBSERVED。CPU问题暂列待查，未发reset/烧录命令。详见[45秒有效性实板结果](RESP-VALIDITY45-001-RESULTS-R1.md)。下方描述按历史阶段保留。

当前最终状态：新零复位卡获批并完成一次10秒；采集/监督0、分析3，RESP_PATH_NOT_OBSERVED，CH1有小幅变化但周期未解出。halt1/go1、未发reset或烧录命令。详见[本次实板结果](RESP-E1-03-RESULTS.md)。E2/E3未执行；本轮各卡已消耗，下方等待/准备文字为各阶段历史，不再作为当前状态。

最新追加：一次复位卡获明确同意，但入口已变为运行态/VTOR08000000，按原卡STOP；实际reset/halt/go均0，未采集、未重试。[新零复位10秒卡](AUTH-B-RESP-PILOT-002-R1.md)及测试已备，单独等待新窗口确认；详见[运行状态审查追加记录](RESP-RUNTIME-STATE-REVIEW-R1.md)。

最新启动只读核验：两次连接均实际PC=1FFF32F0、VTOR=1FFF0000、CPU暂停，Flash/options匹配。当前停在系统ROM，尚未证明最初进入原因；未发reset/go/halt，未继续采集。详见[启动与J-Link流程核验](RESP-RUNTIME-STATE-REVIEW-R1.md)。[一次复位及有条件10秒新卡](AUTH-B-RUNTIME-RECOVERY-RESP-001-R1.md)已备，等待新增复位权限；以下E1失败/E0描述保留为历史。

RESP-003最新执行：R3卡唯一会话在首组诊断触发RESP_DIAG_ABI，worker/监督均exit1，未完成10秒；halt/go/reset/写Flash均0，未重试。E1未签通过，E2/E3未执行。下方E0等待描述为历史快照；当前以[RESP报告](RESP-EXPLORATORY-REPORT.md)及[失败回执](../evidence/B-RESP-003/e1-failure-receipt-01.json)为准，R3一次权限已消耗。

RESP-003最新：负责人已明确允许厂家ΔΩ/动态端子未知条件下的有限非人体探索。E0独立源/profile/采集/120B解析/RR离线计算和13项测试已完成；E1准确R2卡已备，当前仅HOLD_FOR_SAFE_FIELD_GATE_AND_ACTUAL_MENU，未读板/改线/采集。[本轮报告](RESP-EXPLORATORY-REPORT.md)与[R2卡](AUTH-B-RESP-PILOT-001-R2.md)覆盖以下旧R1的探索准入判断，旧ECG结果和正文保留。

## R3当前裁定（覆盖下方历史阶段状态）

2026-10-22 Asia/Shanghai：**B2_ECG_HR_ENGINEERING_RATE_PASS_FOR_TESTED_SETUP**。独立工作区与唯一写分支不变；合同固件源码/阈值不变。身份/双备份、候选安装/整片校验、链路及未接源负例已完成。负责人逐档确认普通60/90/120；六个正式窗口全部满足冻结工程速率判据。当前完成6/6，结论仅限本次组合的名义速率一致性，不代表医学准确度、幅值标定或B3通过。详见[BIO_V2六窗实板结果](B-ALG-002-ECG-MATRIX-RESULTS.md)。

本轮RESP准备已完成只读资料审阅：[RESP核验R1](B-ALG-002-RESP-READINESS-R1.md)确认模块需要RA–LA；SKX说明书未指定动态阻抗端子对或R/ΔΩ定义。已交付[一次性缺项清单](B-ALG-002-RESP-INFORMATION-CHECKLIST-R1.md)、[单次10秒精确卡草案](AUTH-B-RESP-PILOT-001-R1.md)和禁用离线计划。状态DRAFT_NOT_APPROVABLE_SOURCE_AND_TOOL_GATES；已有ECG工具尚不支持RESP源门禁/正式RR评价。本轮未连接或读取硬件、未改线/切源菜单、未采集/烧录，当前源仍为上轮负责人确认的普通ECG120。此准备不签B3，也不申请现在批准带未知项的卡。

负责人已明确授权“连接模拟源、采集、排查”，并说明被其他测试覆盖后“重新烧录下载即可”。每个硬件窗口调用前展示精确卡，依据已有继续执行授权实施必要步骤；不将初始软件准备权限本身冒称硬件许可。J-Link当前接B的JTAG且仅调试；负责人已确认正常，不再重复索要型号/排线。

当前供电为J5/YL-1210 12V1A中心正极，开关已开，B0/B1均GND。模块ADS1292_V2.0、灯亮、J1空置、J2接开发板5V共GND；START→PG15/DRDY→PA3负责人确认。负责人只见J1/J2，不根据图中J3假定实物CLKSEL。ECG-PILOT前CAN/模拟器/人体均未接；之后负责人确认电池普通60、USB断开、R红RA/L黄LA/F绿RL/N、LL/F空置，B供电并接回J-Link，CAN/人体仍断开；本轮负责人确认源菜单切至普通120、电池供电且USB断开，接线保持。当前源类别为ENGINEERING_NONHUMAN/ORDINARY_ECG120，不冒用旧OPEN_UNKNOWN或其他档位状态。

| 窗口 | R3实际结果 |
|---|---|
| READBACK-001 R2 | VTref3300mV、DEV_ID413、M4、1024KiB、RDP0；Flash1MiB/options16B分别独立双读一致，恢复副本封存；显式h1/go1/reset0/写0 |
| INSTALL-001 R1 | 仅sector0/1共32768B恢复合同BIN，尾部7484B保留；整片逐字节预期一致，其他扇区/options未变；h1/reset1/go1 |
| PRECHECK R1 / FAULT / REPROBE | NOT_RUNNING及ROM暂停PC1FFF32EC、VTOR1FFF0000、CFSR/HFSR0，原快照保留 |
| BOOT-001 R1 | 一次正常器件复位，实际PC080001A0/MSP20002F30符合Flash向量才go；BIO_V2初始化，但当时5秒IRQ/帧0，记录FAIL不改算法 |
| ADC-PATH R1/R2 | 会话间暂停独立保存；无fault的Flash应用条件go1；MCU PG15高、PA3/EXTI3正确、ADC ready1，但仍曾0帧 |
| START-PULSE R1/R2 | R1写前停止；R2条件go后已129IRQ/129帧，按卡跳过脉冲；两轮GPIO写均0，不宣称脉冲修复 |
| PRECHECK-001 R2 | 约4.985秒captured260→1506，249.94985SPS；BIO计数推进，init/spi/bad_status/overflow0；未知输入不评准确率 |
| CAPTURE-OPEN-001 R1 | 10.016秒/126个真实槽块；稳定原码2609帧，连续序号内缺口0、重复冲突0、起始pending8保留；h1/go2、尾段暂停/恢复均确认、起止Flash/options不变。CH2近轨0、观察HR无效；CH1开路近轨100%，不代替已知ECG或RESP验收 |
| ECG-PILOT-001 R1 | 负责人确认接好普通60后采10.032秒，稳定2598帧/缺口0/近轨0；后段实板HR60有效，源冻结C回放末60。pending26保留，不以该短窗签正式PASS |
| ECG-MATRIX-001 R1：60 | 两窗各92秒；30秒预热后完整60秒评价，稳态原码14994/14995帧、实板观察76/75条全部有效HR60，回放全部60，主机约249.93/249.91SPS，两窗通过 |
| ECG-MATRIX-001 R1：90 | 两窗各92秒；稳态各14996帧、实板各76条全部有效HR90，回放评价段全部90，主机约249.92/249.95SPS。全窗稳定原码23093/23096帧，序号内缺口0/重复冲突0/CH2近轨0，ADC四类错误0；起始pending25/26保留且不补点。尾段暂停/恢复及起止Flash/options校验通过，各h1/go2/reset0/写Flash0，两窗通过 |
| ECG-MATRIX-001 R1：120 | 两窗各92秒；稳态各14997帧、实板各76条全部有效HR120，回放评价段全部120，主机约249.97/249.94SPS。全窗稳定原码23105/23108帧，内部缺口/重复冲突/CH2近轨及ADC四类错误均0；起始pending各26保留。尾段暂停/恢复与起止Flash/options校验通过，各h1/go2/reset0/写Flash0，两窗通过；未执行RESP |

90首窗第一条诊断HR无效；相对该诊断时刻2.389秒后首次观察到有效90，随后正式评价段全部合格。这只是本窗诊断的观察偏移，没有源菜单操作的同步时戳，不报精确变速延迟。120首窗首条诊断亦无效，相对该诊断2.388秒后首次观察到有效120；同样不是同步源切换响应时间。分析结果见field-r3/ecg90-two-window-analysis.json、ecg120-two-window-analysis.json、ecg-six-window-analysis.json及逐窗摘要；实板结果和Host回放分别记录。

多次发现下一会话已暂停，尚未区分连接/关闭等调试行为，不归因算法。已依SEGGER说明添加SetSkipDebugDeInit=1保留固件使用的DWT；仅证明策略解析/调用成功，不声称已消除全部会话间暂停。回执RUNNING指Close前实际观察，不是Close后独立观测。

固定BIN SHA `438a8120f6df06ce219cdc30c0e5b697ac0e993f98d5a80521b10361536ae3ae`；当次原完整Flash双读SHA `69d9efb0ce0a9228138ea3cc21adbb09c09a15a8b6dbf0d9a1d1ff861a32fc2a`；安装后完整Flash SHA `f713277a50a5ec8d8a93317f412d5ab1b754e5d619918e57e9efe9dceef24cbb`。BIN外字节保留，不拿BIN hash冒充整片hash。UID/序号/Flash/options/回滚镜像/RAM/原码/现场图片/DLL日志只存ACL受限 `E:/medical-monitor-node-b-field-private/field-r3`，失败只增不删。

工具为官方签名9.86a纯归档提取的JLink_x64.dll，SHA632d0d78e72b8a55c65945a0c393a9f081082c725fff4ba3081b0a565fd58cff；未运行安装器、改驱动或升级探针。MSI管理提取曾被自动审批拒绝，改用纯归档提取，没有换壳重试被拒安装操作。旧5.12/7.22b策略不足未在板上试错。连接保护、单探针/VTref、每调用及全会话独立监督均留证。

原offline profile仍保留未授权、UID为空语义；02用于两个10秒窗口，SHA9d17280c…及当时源码副本保留；正式92秒改用03，SHA `4e298cf97e55ea8c7d01aa9509b54ef682256fcad6c9ba30cca835ec1cde1a7f`，只是时长/工具绑定更新，不改固件。专用入口固定diag20001AE4/120、slots20001F30/3072、stats2000018C/48、启动RREG缓存200001BC/12，确认暂停后同一128KiB RAM取head/末127已发布槽；3:2冲突不投票、不补点/跨启动拼接。analyze_capture_b.py已用冻结C源输出明确标REPLAY的filtered/候选/接受事件，回放初态在首个保留帧重置，不冒称完整板内历史或逐位相同ARM执行。

既有21项工具/采集/正式判据unittest通过，全部脱机；本轮工具及判据未改，不因新增实物数据重复软件回归或用其替代实物结果。既有ARM0错误0警告/31项ABI/9项profile/27项旧采集工具证据保留。初次解码28I+4f误设由测试在硬件前发现，按120B ABI修为26I+4f；首轮Windows心跳unlink共享冲突在Open前停止，改只追加事件流并有并发负例。相关失败不抹除。

算法固定自研BIO_V2，CH2 ECG→HR、CH1阻抗RESP→RR；不换心电衍生呼吸旧目录。F绿→RLD、R红→ERA、L黄→ELA为设计映射，本次RL/N工程试接已有真实ECG输入，不外推所有负载兼容，也不伪造通断测量。MATRIX卡规定的60/90/120各30秒预热+60秒稳态×2已全部完成；六窗、未接源13次HR无效负例及原件完整性均核验通过，提出本次组合B2工程速率通过。卡内六次会话已用完，不据此增加硬件窗口或进入RESP。无同步逐拍参考不报漏检/敏感性，无I导联1mV保证不做幅值标定。CH1接源后不再顶轨，但RESP仍BLOCKED_ELECTRODE_PAIR_AND_REFERENCE，不拿普通ECG附带呼吸显示作动态阻抗真值。

历史8412帧未知输入不算准确率，37169帧仍NOT_RUN_EXACT_SHA_NOT_FOUND。H3/P4/main/B/B2/P6/A、正式云及CAN参数不变，无三板连接/PR/合并/tag/强推/扫描。当前机器证据为 `../evidence/B-ALG-002/field-r3/field-summary.json`、测试/SHA清单；最终提交、远端逐字节取回和保护refs比较写仓库外DELIVERY-RECEIPT。

## 以下为R1/R2历史阶段记录（当时结论，不作为当前许可或缺项）

2026-10-22，Asia/Shanghai。裁定：**B2_0_SOFTWARE_PREPARED_FIELD_BLOCKED**。

本轮完成独立工作区、Git/GitHub及候选身份复核、图纸/说明书/厂商演示审阅、离线profile与负例、备份恢复计划及精确授权卡草案。实物映射、RLD兼容、今日板上身份/完整备份、真实采集后端尚未完成；不签发B2-0实物全PASS，也不签发ECG/HR或RESP/RR PASS。

## 身份与权限

- 唯一写分支 `codex/node-b-bio-v2-field-20261022`，工作区 `E:/medical-monitor-node-b-field`。
- 精确起点 `c0617b9fc0ee1f1c6b2f3c4ece90b36db7a78740`；开工远端HEAD与之相同。
- 负责人最新更正：**J-Link当前连接B板**；CAN未接，SKX已到手，板为STM32F407。更早“未接/接C”回报不再作为当前事实，改正历史保留。
- 本轮未启动J-Link、SWD、ROM、串口或实物采集；未发供电、reset/halt/go、Flash写擦、导联连接或源启动指令。已连接J-Link不代表读取获准。
- 不改固件、旧采集器、H3/P4/main/B/B2/P6/A、云服务、CAN参数或受限历史原件；未建PR/合并/tag/强推，未启动安全扫描。

交付提交SHA由Git及仓库外DELIVERY-RECEIPT.json记录，避免本报告自引用。保护refs开工和结束快照留证，唯一写入者为Codex /root。

## 本轮真实软件验证

| 检查 | 实际结果 | 证据 |
|---|---|---|
| 新工作区ARM重建 | 0 errors、0 warnings，无旧算法符号 | arm-receipt.json、arm-build.log |
| 候选BIN | 25284B，与合同SHA438a8120…完全一致 | arm-receipt.json |
| 新ELF / symbols | cba20bfb… / a556fa4a…，与B1调试产物分别登记 | arm-receipt.json |
| ARM/Host布局及旧profile负例 | 31个常量一致，旧profile精确拒绝新BIN | abi-receipt.json |
| 新增门禁 | 9个unittest通过，含参数化身份/ABI/尾段负例 | field-profile-tests-final.log |
| 既有采集工具 | 27个unittest通过，全部为离线/模拟客户端 | acquisition-tests.log |
| 原资料包身份 | 266文件，0失败 | preparation-receipt.json |

门禁包括真实候选错误副本、工具漂移、UID/Flash/ABI不符、地址越界、落在RAM内的旧布局、活动RAM跨代/撕裂、3:2序列多版本冲突及未确认尾段/恢复。仅为脱机验证，不是设备现场验收或准确率。首轮7项日志保留，追加2个用例后的9项日志另存。

profile.offline.json SHA256 `d402780dc16781cfc9f8e3de4211b3d7514c5de73f3bcc2007ca4c1f782413a5`，状态OFFLINE_PREPARED_NOT_AUTHORIZED。其设备UID/Flash/options为null，不含真实设备身份。field_profile.py与既有槽重建器SHA均绑定；真实BIO_V2采集器尚未实现，不得交给旧acq.py运行。

原ARM日志及原合同副本逐字节保存。仓库既有属性保留Node-B原字节，默认格式检查将CRLF计为空白；显式CRLF检查后仅剩原合同第3行及原编译日志第33行尾随空白。新写文件检查0，未改属性或规范化原件。首次格式辅助程序误用GBK解析Git输出而失败，改为字节捕获后完成；各情况记录format-check.json。固件源码与起点完全相同。

## 实物阻塞与下一步顺序

| 门 | 状态与缺口 |
|---|---|
| 今日硬件/源 | STM32F407、SKX到手及J-Link接B为负责人口述；完整型号/照片/供电/附件/跳帽未知 |
| 导联 | 图纸ERA/ELA对应RA/LA；第三路RLD主动输出。手中F线实际去向、RLD负载兼容、隔离未核 |
| 当前Flash及完整备份 | NOT_RUN，未获读板授权；不冒用历史原件 |
| 采集适配 | BLOCKED_CAPTURE_ADAPTER：旧工具写死旧stats地址，漏新诊断区；BIO_V2无逐拍实板事件日志 |
| B2 ECG/HR | NOT_RUN / BLOCKED_FIELD_AUTH_AND_INPUT；先60/90/120 BPM，预热/窗口/阈值采前冻结 |
| B3 RESP/RR | NOT_RUN；ECG通过前不进入，电极对和动态ΔΩ真值仍阻塞 |
| B4修复 | NOT_STARTED；没有合格输入下的算法失败证据，不改阈值 |

模拟器附件中的F=LL是通用端子约定；厂商旧照片的第三路实际接RL，不能推定手中F线应接LL。拟接线只在实际电路通断及RLD兼容通过后纳入授权卡。算法固定为自研BIO_V2，CH2 ECG→HR，CH1阻抗RESP→RR；不切换到“用心电算呼吸”目录，也不把B保护分支旧代码冒充新候选。当前板内运行版本仍NOT_OBSERVED。

下一轮先补照片/现状、完善采集适配软件审查。`AUTH-B-ECG-00`为解决“先获读板权限才能得到当前备份SHA”的分窗提案，尚未批准；待现场事实及精确读取动作冻结后再提交。完成身份/双读备份后，另补全 `AUTH-B-ECG-01`，明确写板、源、导联、采集及恢复边界。两卡不互代，RESP仍需独立卡。当前不向负责人申请空白或带未知项的硬件许可。

历史8412帧未知输入及失败原件保持，未重复算准确率；37169帧仍NOT_RUN_EXACT_SHA_NOT_FOUND，不制造替代文件。软件测试与实物验收分别列示。

## 交付入口

- [基线、引脚、SKX及算法审阅](B-ALG-002-B2-0-AUDIT.md)
- [现场授权卡草案及缺项](B-ALG-002-AUTHORIZATION-CARDS.md)
- [当前板完整备份与精确恢复计划](B-ALG-002-BACKUP-AND-RECOVERY.md)
- [采集profile、数据表及工具缺口](../acquisition/field-biov2/README.md)
- [原合同逐字节副本](contracts/MPM-B-ALG-002-R1.0.md)
- 机器证据 `../evidence/B-ALG-002/`，受限目录 `E:/medical-monitor-node-b-field-private`。

本阶段停止于B2-0软件准备和具名现场阻塞，下一步优先ECG→HR，之后动态阻抗RESP→RR；不以任何脱机PASS替代实板结论。

## R2现场照片与首次只读卡补充

负责人补充同款模块/导联确认及两张现场照片：F绿、R红、L黄；照片中的STM32F407ZGT6为B，当前未通电，模块已连且无人接入；无其他调试程序或自动下载，只有Codex执行。BOOT名称/J5和J-Link供电功能、KTAG实际接口仍须据丝印/照片核定，不静默更正负责人口述。原R1观察保留，现状以R2为准。

资料级设计映射更新为F→模块RLD、R→ERA、L→ELA；未做通断或兼容性实测。[R2接线复核](B-ALG-002-CONNECTOR-REVIEW-R2.md)说明推理依据及颜色差异。

新增 [精确身份/备份卡](AUTH-B-READBACK-001-R1.md)，明确F407身份/options地址、1MiB独立双读、条件halt/go次数、单路供电和超时/停止，替代ECG-00泛化提案。[一次性现场清单](B-ALG-002-FIELD-INFORMATION-CHECKLIST.md)将纯备份必需资料与后续ECG/RESP资料分开。

旧J-Link V5.12的失败自动复位重试和close自动恢复尚无受控证据，列为Codex软件准备门；没有为核实工具而启动已接B的探针。状态仍PREPARED_PENDING_FIELD_AND_TOOL_GATES，不向负责人申请带未知项的执行批准。本轮仅改文档/证据，未改代码、未读写或供电任何硬件，也未产生当前Flash备份。
