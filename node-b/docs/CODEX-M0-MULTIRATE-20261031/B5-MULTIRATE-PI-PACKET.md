# M0 多速率与三板入场：PI 审查包

2026-10-31，Asia/Shanghai。**M0_OFFLINE_PLANNING_COMPLETE；M1/M2/TRIPLE_BOARD_FIELD = NOT_AUTHORIZED。** 用户本次“授权执行合同中的操作”按合同当前开放的离线范围执行，没有扩展为24场现场测试。基线为 `6669a855662f0655fc7d7b6fc4c9a45ee1ef13b0`，独立分支 `codex/b5-multirate-planning-20261031`；[合同原件副本](contracts/MPM-B5-R6-MULTIRATE-VALIDATION-AND-THREE-BOARD-ENTRY-CONTRACT-R1.md)保持相同字节。

## 交付与主要决定

- [唯一拟议矩阵](MULTIRATE-MATRIX.proposed.json)及[判据说明](MULTIRATE-PREREGISTRATION.md)：E60/E90/E120/R12/R15/R18/R24/R30，每格3次，独立run_id及拟议冷启动代次；共24次、每次45s预热+120s评价，记录时长合计66分钟。它不是现场会话/SDK/云租期预算。
- [24份默认禁用卡及准入差异](disabled-cards/README.md)：执行入口空、现场动作空、次数0、签署/信任根/nonce/有效期/当前现场证据均未建立。没有把旧卡、OFFLINE_MOCK或自填字段变成授权。
- [历史证据清算](HISTORICAL-EVIDENCE-RECONCILIATION.md)：B2 ECG六窗、E3 RR六格及当前R6三个独立窗口分别保留，不跨代合并通过率。旧E3使用周期20，新提案周期30；两者刺激不同。旧开发/留出集均是已知非盲回归。
- [厂家技术询问稿](SKX-MANUFACTURER-QUESTIONS.draft.md)：尚未发送、尚无回复；SKX_QRS_OUTPUT=UNKNOWN。没有厂商承诺或实测QRS结论。
- [三板入场计划](P7-TRI-ENTRY-PLAN.md)：C49132历史B-only范围与通用双CAN软件候选分开；A实装BIN、CAN2物理版本/终端及当期云资源仍UNKNOWN。当前B5宏主动禁用A，不能直接接A进入并发。
- [失败/停止/退出码表](FAILURE-STOP-EXIT-CODES.md)及[复用入口差异](TOOL-REUSE-AND-SCOPE-GAPS.md)：不改旧165s以外的固定时限或冻结正式评测器；新M1入口/评测器尚未实施，原生副作用仍开放。

## 本轮实做与验证

核对A0已验收manifest的13项文件；核对12份历史公开逐窗结果及对应私有分析摘要、源/profile/card/采集/判据/工具哈希链；复核R6 ECG60、TEMP及RR15的既有真实退出码。历史65+17算法/工具回归、旧12场实板矩阵和420s窗口均未重跑。复用原工具，只新增本交付文档/拟议JSON和摘要索引。

运行三个已有纯Host组件用例：普通双口资源策略、B-only隔离资源策略、真实bxCAN驱动的RAM寄存器替身ACK/FAIL/STOP检查。三次编译、三次运行均exit0，收集器exit0；仅是M0组件检查，不是完整T0集成或C49132精确宏/原构建验证。编译器版本、源码/脚本/日志SHA、真实argv/退出码见 [pure-host-component-checks.json](../../evidence/CODEX-M0-MULTIRATE-20261031/pure-host-component-checks.json)。没有加载SDK/DLL/COM或进行网络、硬件I/O。

保留排障原件：最初收集因12份旧分析文件无EFS属性而exit1；原件未改，所需摘要逐字节复制到本轮新EFS目录，SHA和新副本EFS属性核验后继续，修订收集exit0。旧文件仅能记为受限目录旧件，不能追称EFS加密已合规。三板源码初次严格磁盘/Git比对因三个文件CRLF/LF不同exit1，分别登记原字节SHA与规范化文本一致，未改源码。路径发现的非零返回另列，不能冒作算法失败或隐去。完整暂存空白检查exit2仅涉及合同原件五处Markdown行末双空格，保留原件字节；仅排除该原件副本后的其余交付检查exit0。

本轮 SDK/COM、上电/接线/SKX菜单、RESET/HALT/GO、B5START、Flash、云业务/配置/ACL/部署操作均0。只进行授权内Git读取/交付网络操作，不联系厂家，不下载依赖/固件，不合并分支、不运行Security Gate。

公开完整性清单：[EVIDENCE-HASHES.json](EVIDENCE-HASHES.json)；[执行账本](../../evidence/CODEX-M0-MULTIRATE-20261031/M0-execution-ledger.json)保留实际非零和最终退出码；[历史登记](../../evidence/CODEX-M0-MULTIRATE-20261031/historical-evidence-register.json)与[三板源索引](../../evidence/CODEX-M0-MULTIRATE-20261031/tri-interface-sources.json)给出原件/工具SHA。新执行脚本及摘要副本只在 `node-b/build/m0-multirate-pointer.json` 定位的新EFS job；原数据、UID、全片/options、凭据、图片不进入Git。

## 未关闭项与下一轮申请

1. 厂家针对本台型号/序列/固件的书面源定义尚无；参考仪器、安全差分、加载和时标验证未建立，SOURCE_UNKNOWN / ROOT_CAUSE_UNRESOLVED不变。不得据此调HR阈值或认定CH2无QRS。
2. M1尚缺B41012完整一致调试链、165s受限入口/独立评测器、SDK Open/Close原生风险处置、当日现场/冷态流程/责任人、单会话预算与可信一次性签署。禁用卡不能运行；需在新范围完成薄适配及Mock后才可另批现场。
3. A实际BIN未知；C49132历史B-only、应用区余量有限，当前完整源码与原构建91项输入字节对应尚未复证。三板需新集成方案、源/OD/PDO/工具冻结、内存/队列/公平性、供电/终端/CAN2/音频冲突审查和独立Flash/回退许可。
4. 旧隔离云租期/账户/ACL/当前部署未知，不能复用为M2/T3准入；P5/P6/P4整合、安全门、发布/24h soak各另授权。冷启动ROM、SDK副作用、绝对温度/电压/阻抗校准继续开放。

**建议下一轮先批准T0纯Host离线三板集成准备/回归**，具体提案见[P7计划](P7-TRI-ENTRY-PLAN.md)：无设备、无网络、无云进程、无下载、无Flash；先冻结候选与修正过时TEMP夹具，再运行一次有界双节点模拟。M1单板现场为另一独立申请，不能用“同意T0”同时启用。最终需要PI针对新M1卡逐块签署，M2及T1–T4仍未授权。

保留 `B5_LIMITED_PASS_PENDING_NEW_MATRIX`；R6 ECG60/TEMP工程exit0、RR15正式NOT_PASS/exit3，RR15_FULL/B5_FULL_3WINDOW_CLOSED不得宣称。提交推送、复核远端SHA后停止，等待PI决定。
