# RR15 源端真值 A0：PI 审查包

**A0_OFFLINE_SOURCE_TRUTH_DESIGN = COMPLETE；SOURCE_UNKNOWN；A1_REQUEST_DISABLED / MEASUREMENT_NOT_READY。** 本轮已完成合同要求的事实审查、独立参考条件设计和三路径分流。没有独立端子参考数据，因此不确认ECG_PRESENT或ECG_ABSENT，也不改变ROOT_CAUSE_UNRESOLVED。

## 基线和本轮真实操作

独立分支 `codex/b5-rr15-source-truth-a0-20261030`；唯一父提交 `eda6e24a8eedcfe0b50416390022db0c187550af`。Git远端验收分支HEAD已核对为该SHA；合同原件以相同字节复制在 `contracts/`，用户明确请求与附件均只授权A0，没有现场范围扩展。

执行内容仅为：读取合同/两版既有说明书与历史资料；本地提取/渲染并目视手册重点页；核验两张旧照片SHA并重看；核验已验收24项manifest、12项受限回执/波形/原槽引用；复用既有因果结果及原波形，不再编译C、回放或重跑65+17。三个既有离线工具文件未改，运行次数0，源码SHA见 [source-review-provenance.json](../../evidence/CODEX-R6-RR15-SOURCE-TRUTH-A0-20261030/source-review-provenance.json)。

没有设备SDK/DLL/COM/SWD、探针枚举、板/模拟器上电、菜单操作、改线、RESET、B5START、Flash或云业务动作。只操作本机文档/受限文件及明确授权的Git仓库交付；原PDF、原照片、历史采集EFS没有改写。手册新渲染曾由文档工具生成在忽略的build目录，随后校验SHA并存入新EFS目录，只移除了本轮已确认复制成功的生成副本，未删除原始资料。

## 关键事实与结论

- 用户给定12页说明书P11写呼吸波形“心率范围：60 bpm”；既有21页V2.2 P20重复该文字，同时单列呼吸15、幅度1.5R、波形周期30、基线1K、RA–LL。不能把这些字段混成一个频率，也不能假定只有RESP而没有ECG。
- 两版已审菜单/呼吸文字没有明确“保持RESP同时关闭ECG”的定义。其实际能力为UNKNOWN，不能编造ECG OFF、HR=0或拿关机/开路/Lead-Off代替。
- 本机历史模式/菜单确认、当时端子加载、源版本、参考仪器性能和源端QRS都没有独立参考闭环。旧算法有效/无效、相关性和既有波形形态无法补成物理真值。
- 历史仅有电池万用表的自述，不等于今天仪器只有该型号，但没有足以证明合格隔离差分参考链的材料；没有安全接线、噪声/检出下限和同钟方案，所以A1不能启用。

完整事实矩阵：[RR15-SOURCE-TRUTH-FACT-MATRIX.md](RR15-SOURCE-TRUTH-FACT-MATRIX.md)。M12/M22 SHA分别为 `27fe9e4a37a761ab7df939bf49693942dbf3e5692f09e2e10311106053503cc8`、`8b264906747e76336e7a7221ab77b76e3697078f794b064e77081e7e56fc48aa`；PDF图像只是说明书示意，不是本台设备参考波形。

## A1 申请和待 PI 决定

[A1申请](RR15-REFERENCE-A1-REQUEST.disabled.md)及对应 [disabled JSON](RR15-REFERENCE-A1-REQUEST.disabled.json) 均无执行入口、无token/nonce/签署、允许现场动作空集。先提议A1-S源端独立参考，正控制60s→RESP待测180s→正控制60s，零重试；独立校准方法/预算还需冻结。A1-L加载B/同步CH2/CH1是另一份待批范围，不随A1-S自动批准。300秒是提议的参考数据时长，不是本轮许可，也不是420s正式联评。

参考设计指标（≥2kS/s、0.05–150Hz、≤1ms映射目标）都是待验证目标，不是已确认仪器能力；最小QRS检出幅度、共模/量程、RLD兼容、输入加载、隔离数据口和安全图仍待具体器材证据。只有DMM或普通接地示波器不满足设计；不要求现在接仪器、测阻或拍新上电照。

PI下一步应决定是否具备/可确认合格仪器和参考来源，并指定电气审查/人工停止负责人，再选择是否独立签署A1-S或A1-L。需要填全的未知项已集中在禁用申请中；本轮不通过发问诱导现场操作，不自动创建现场令牌。

## 算法和数据治理

分流及保护表见 [RR15-ALGORITHM-DESIGN-DECISION.md](RR15-ALGORITHM-DESIGN-DECISION.md)：有QRS则申请修订未来刺激；可靠无QRS且同期有效HR才申请模式无关质量门；未知则不调阈值/不正式重试。历史六事件没有同期外部参考，未来测一次不能追溯确认旧输入类别。

真实ECG60/90/120与两组低幅带噪ECG120保留逐数据集相对基线≤1pp退化及±2bpm约束；原94.4356%/94.4444%不抹去，也不复活上轮已撤回的“预登记95%”措辞。既有R5和ECG各02及合成留出都已被查看/回放，今后只作为非盲回归；新候选需新独立留出或如实报告非盲性质，不更名旧目录制造未知验证。

## 验证、SHA和退出码

本轮实测代码只有离线收集/交付一致性脚本（存新EFS并记录SHA），不新增/重写项目工具。PDF提取/原件核验、证据收集、照片SHA核验、最终静态交付检查的真实退出码分别列于 [A0-execution-ledger.json](../../evidence/CODEX-R6-RR15-SOURCE-TRUTH-A0-20261030/A0-execution-ledger.json)。65/17、C编译、算法回放、A1参考和420s复验均NOT_RUN；不能把文档校验exit0当作源端真值PASS。

可复算 [EVIDENCE-HASHES.json](EVIDENCE-HASHES.json) 覆盖本提交各公开文件（自身除外）；[unchanged-tools-and-baseline.json](../../evidence/CODEX-R6-RR15-SOURCE-TRUTH-A0-20261030/unchanged-tools-and-baseline.json) 核对工具/C/header/reviewer/既有采集摘要仍等于父提交。完整私有渲染、旧原件定位与本轮执行脚本在忽略的 `node-b/build/rr15-source-truth-a0-pointer.json` 指向的新EFS job；Git仅SHA/文字矩阵，无真实波形、照片或PDF原件。

状态保留：RR15因果交付有条件验收、ROOT_CAUSE_UNRESOLVED；算法补丁NOT_IMPLEMENTED且当前NOT_AUTHORIZED；R5/R6 RR15正式NOT_PASS/3；ECG60/TEMP工程PASS为既有范围；A1、Gate F、420s重试、烧录和B5结项均未授权/未满足。提交推送后停止，等待PI下一次独立决定。
