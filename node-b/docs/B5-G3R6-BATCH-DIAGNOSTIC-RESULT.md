# G3R6 有界现场诊断综合结果

2026-10-28（负责人工作日）。基线`e497f3257a8aef4a23287fc6ef268447e3eb01cb`，独立B5分支。本报告统一记录准备、实测、离线归因和下一权限；不另外签发复位/烧录/云窗卡。

## 结论

**最新裁定：NORMAL_FLASH_EXIT_COMPARISON_PASS_AFTER_OWNER_RESET；ROM根因仍UNRESOLVED。** 第一连接曾因ROM按条件停止，原始失败完整保留。负责人随后明确回报“已复位，继续执行”，代理使用同批剩余第2/3连接完成正常Flash退出/重连对照，无额外复位或显式Go。工具源码不变，沿用已通过125项离线回归；没有重复旧软件矩阵。

| 项目 | 本批实际结果 |
|---|---|
| 批量批准 | 最多3次连接，每次120秒；全部条件成立才允许显式Go一次 |
| 负责人起始状态 | J-Link在C、C已上电；B断电且无J-Link/USB；本批无需上电B或转接 |
| 实际连接/SDK调用 | 全批3/3；第1次51、第2/3次各92；余0次 |
| 原生负返回/短读 | 各窗均0 / 0；不是SDK预算耗尽或真实读取失败 |
| 代理显式Go/Reset/Halt | 0 / 0 / 0；负责人手动C RESET另计1次 |
| 退出续跑策略 | 第1次未启用，第2/3次各健康应用一次；Close均返回。第3次入口独立验证第2次退出后任务推进，第3次Close后无第4次观察 |
| AT/UART、Flash/options/sector3写入、B5START、云操作 | 全部0 |
| 新鲜UID/应用/配置/options读取 | 第1次ROM门停止；第2/3次身份、64B应用头、336B配置、16B options与私有参考相符；未重读整片或完整应用，不能扩大成完整镜像PASS |
| 历史CPU问题 | HALT与ROM唯一根因仍UNRESOLVED；B4_CAN_PASS保留，B5_CLOUD_BLOCKED |

C保持供电、J-Link留C；代理没有断电、重新上电、按键或改线。B没有操作。续窗入口/出口均实读应用DISARMED；不能由此推断ESP自主联网状态或第三次Close后的即时状态。

## 人工复位后的续窗证据

负责人完成一次C人工RESET后，冻结续窗附件及新的到期时间，继续引用原批同一EFS目录、Go消费文件和已用第1次连接，未清零计数。原ROM回执、原授权及原`.used`不覆盖。详细数据见[continuation-01.json](../evidence/B5-G3R6-BATCH-01/continuation-01.json)。

| 项目 | 第2次连接 | 第3次连接 |
|---|---|---|
| 入口状态/VTOR | RUNNING_FLASH / `0x08000000` | RUNNING_FLASH / `0x08000000` |
| DHCSR / 入口DWT采样 | `0x01010001` / `0x080063DE` | `0x01010001` / `0x080063DC` |
| 入口→出口uptime（ms） | 65926→66086 | 66969→67128 |
| DISARMED | 前/后均true | 前/后均true |
| SDK/显式Go/worker退出 | 92 / 0 / 0 | 92 / 0 / 0 |
| Close | 健康检查通过、退出续跑策略生效、调用返回 | 同左；其后未追加观察 |

第3次入口相较第2次出口，任务计数推进883ms，支持这次Close后应用继续运行；各窗内部计数也推进，受检状态没有HALT/ROM/Fault或新复位迹象。正常分支仅在主机假链路上验证事前预算拒绝，不写UART/RAM、不改变真实调用预算。

这证明“负责人复位后应用恢复＋本次正常退出/重连对照通过”，不能证明为何第1次进入ROM，也不能证明未来不会再现。最后一次Close没有独立第4次观察，连接额度已耗尽，未追加取证。

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
- 第一连接因ROM未进入正常分支。负责人手动复位后，第2/3次零UART连接已完成主机假链路预算拒绝与正常退出对照；第3次入口证明第2次Close后任务推进。第3次Close后无独立观察，历史ROM根因不因此关闭。
- 最小复用上轮已测原生返回/异常/Close记录逻辑，通过实例级READ_SCOPE/NATIVE_SCOPE支持本包；旧工具默认白名单不扩大。125项必要Host/Mock回归退出0，[回执](../evidence/B5-G3R6-BATCH-01/tests.json)。不重跑旧ARM/UI/算法六窗，不加载真实DLL做离线测试。

## 第一连接停止时的权限边界与后续更新

第一连接停止时曾余2次连接，不能因此反复连接ROM或对ROM执行Go。该时点未获人工Reset许可；后续仅在负责人明确回报已完成一次RESET并要求继续后，才消费剩余两次连接。现在3次额度均已用完，Go未消费也不自动提供新连接或其他权限。

新增人工复位来自负责人，而非代理自动操作。代理没有把这一恢复动作当作根因关闭；也没有因任务恢复就继续AT/Wi-Fi/SNTP/UDP、配置gen5、服务恢复、真实B5START或任何回滚。

下一工程门是正确2.4GHz易失Wi-Fi与SNTP的完整启用→时间变化→关闭读回，再做独立新鲜公网NTP证据。可集中审批一份有固定字节、目的端、次数、时限及物理停止办法的批量网络包，避免逐步重复确认。本次仅完成SWD诊断，不使用旧网络授权或旧B5START；Flash/sector3及云端对象仍须分别批准。

本轮先本地归档与离线归因后，按真正ROM阻塞里程碑集中提交一次，不因中间单个错误推送。来源/工具冻结清单见[bindings.json](../evidence/B5-G3R6-BATCH-01/bindings.json)；远端交付真实回执另存build/EFS，不提前签发。
