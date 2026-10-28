# G3R6 有界现场诊断综合结果

2026-10-28（负责人工作日）。基线`e497f3257a8aef4a23287fc6ef268447e3eb01cb`，独立B5分支。本报告统一记录准备、实测、离线归因和下一权限；不另外签发复位/烧录/云窗卡。

## 结论

**BLOCKED_ROM。** 第一连接即观察到目标在系统ROM运行，按本批批准的停止条件结束，未以Go或复位恢复，也未消费其余两次连接。离线工具125项相关回归通过；现场未通过正常退出/重连对照，不将它们混成PASS。

| 项目 | 本批实际结果 |
|---|---|
| 批量批准 | 最多3次连接，每次120秒；全部条件成立才允许显式Go一次 |
| 负责人起始状态 | J-Link在C、C已上电；B断电且无J-Link/USB；本批无需上电B或转接 |
| 实际连接/SDK调用 | 1 / 51；未自动追加后续连接 |
| 原生负返回/短读 | 0 / 0；不是SDK预算耗尽或真实读取失败 |
| 显式Go/Reset/Halt | 0 / 0 / 0 |
| 退出续跑策略 | 未申请/未启用；Close实际返回，退出后状态未再连接观察 |
| AT/UART、Flash/options/sector3写入、B5START、云操作 | 全部0 |
| 新鲜UID/应用/配置/options读取 | ROM门即停止，未继续；不能签今日身份/完整镜像PASS |
| 历史CPU问题 | HALT与ROM唯一根因仍UNRESOLVED；B4_CAN_PASS保留，B5_CLOUD_BLOCKED |

C保持负责人已经上电的现场；代理没有断电、重新上电、按键或改线。B没有操作。不把“SDK已关闭”当物理断电、ESP已停止或应用DISARMED证明。

## 原始状态与解释

安全摘要及原件SHA见[result.json](../evidence/B5-G3R6-BATCH-01/result.json)，全部原始API/回调/心跳/退出码在既有受限EFS本批新目录，不含公开凭据或UID。

| 状态 | 本次实读 |
|---|---|
| DHCSR，前/后 | `0x01010001` / `0x01010001` |
| VTOR | `0x1FFF0000` |
| 三次DWT PC采样 | 均`0x1FFF32EE` |
| CFSR / HFSR | 0 / 0 |
| DFSR / DEMCR | `0x00000001` / `0x01000000` |
| RCC_CSR / MEMRMP | `0x0E000000` / 0 |
| FP_CTRL / 6个比较器 | `0x260` / 全0 |
| Flash CR / SR | `0x80000000` / 0 |

本次DHCSR的S_HALT未置位，VTOR与三个DWT采样一致指向系统ROM，说明观测时正在ROM执行。DWT是运行采样，未暂停读取真实PC/MSP；不会用它冒充真实核心寄存器，也不会为了补寄存器而主动Halt。

DFSR=1是粘滞的HALTED线索，不能据此推翻当前S_HALT=0，也不能给出发生时间。DEMCR中跟踪位和本次设置的SkipDebugDeInit有关联语境，但没有因果证明。当前MEMRMP=0不代表复位时BOOT锁存；RCC_CSR的复位标志也是历史粘滞值，没有清零/复位时序对照，不能反推此次ROM由某次电源、引脚或SDK操作触发。RAM中的应用uptime/DISARMED在ROM态不作应用语义解释，不能说应用已经武装或联网。

## 与上一次6000预算/HALT的关系

上次后续窗口是DHCSR=`0x00030003`、VTOR在Flash、DWT全F，属于已观测Debug HALT。本次是非HALT的ROM执行，且51次调用均无负返回/短读，离1400次调用限额很远；没有进入命令、清理或退出续跑业务。**本次不能归为相同预算失败，也不能据此推翻已经证明的旧预算误锁存缺陷。**

实际日志记录保护策略在Device/Connect之前设置：RestartOnClose=0、InhibitConnectRetries=1、ForceAttachTarget=1及SkipDebugDeInit；随后Device选择、IsConnected、一次Connect，再取得第一组运行态。没有Reset/Halt/Go调用，Close发生在ROM停止判定之后。因此**本次事务末尾的Close不可能是此前已读到ROM的直接触发事件**；仍不能排除历史Close、上电BOOT锁存、之前调试器介入或本次连接内部行为。没有“连接前”的CPU连续证据，不能宣布ROM在连接前已经存在，也不能宣布是Connect造成。

离线复查C候选的`gateway/b5/network_main.c`、复用平台初始化以及已知复位/ROM跳转字面路径：应用启动会设置Flash VTOR，受审主流程要求完整B5START才联网；本批未发现可直接解释此处ROM停留的显式软件跳转。静态未发现不是硬件根因排除证明，未更改固件。历史B板在相邻ROM地址运行的记录仅作同类现象参考，不把B/C判成同一机制。

## 工具与验证

- 新批量工具默认禁用，独立地址/API白名单，无UART写、原始DAP写、Flash写、Halt或Reset入口。每会话120秒独立监督；会话及唯一Go都有独占消费文件，子进程入口不能重用已消费连接。
- 真实核心寄存器API仅在已经HALT时开放。可选Go要求真实应用PC、合法SRAM/MSP/Thumb线程态、Fault/Lockup/ROM排除、无异常捕获或活动断点、应用与完整sector3/options私有参考相符、复核期间调试/复位线索稳定；缺一即零Go。本次ROM门优先，未进入该分支。
- 正常分支计划两次零UART连接；只在主机假链路上注入预算拒绝，再健康退出，由下一连接检查uptime推进。本次未进入正常分支，不能签Close退出验证通过。
- 最小复用上轮已测原生返回/异常/Close记录逻辑，通过实例级READ_SCOPE/NATIVE_SCOPE支持本包；旧工具默认白名单不扩大。125项必要Host/Mock回归退出0，[回执](../evidence/B5-G3R6-BATCH-01/tests.json)。不重跑旧ARM/UI/算法六窗，不加载真实DLL做离线测试。

## 剩余权限与最少下一步

本批余2次连接、显式Go许可尚未消费，**不表示可以反复连接ROM或对ROM执行Go**。当前STOP_TARGET已生效，离线研究继续；本次未获得人工Reset许可。

若负责人决定继续恢复应用，最少新增对象是**一次C正常人工RESET**：保持J-Link在C、B断电、其他供电/USB/CAN/BOOT/ESP不变；完成事实确认后，才可在剩余连接额度内重新检查状态。若再次ROM/未知，停止，不追加Reset或Go。此处仅建议，未执行，也不把“复位后恢复”作为根因关闭。

若新状态是正常Flash，再完成剩余两次只读退出对照；若是HALT，只有本包全部条件满足才可使用尚未消费的一次Go。任何工具修正保留原始授权、已消费计数和原件，不换包清零次数。AT/Wi-Fi/SNTP/UDP、配置gen5、服务恢复、真实B5START及各恢复对象均未由本批获得新权限。

本轮先本地归档与离线归因后，按真正ROM阻塞里程碑集中提交一次，不因中间单个错误推送。来源/工具冻结清单见[bindings.json](../evidence/B5-G3R6-BATCH-01/bindings.json)；远端交付真实回执另存build/EFS，不提前签发。
