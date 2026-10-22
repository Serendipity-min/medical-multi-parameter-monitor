# MPM-B-ALG-002 唯一阶段交接

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
