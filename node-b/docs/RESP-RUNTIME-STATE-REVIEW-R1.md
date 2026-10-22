# 启动/运行状态及J-Link流程核验 R1

2026-10-22 Asia/Shanghai。[准确只读卡](AUTH-B-RUNTIME-STATE-001-R1.md)已按负责人本轮继续排查指令执行，仅两次预先列明的连接，halt/go/reset和目标应用数据/配置写均0。读取返回完整；发现异常状态后未恢复、未采集。worker真实exit3（完整读取但运行门不通过）、监督exit1，会话61.812秒。失败不是异常退出码被改写为0。

## 当次直接证据

| 项目 | 第一次连接 | 第二次连接 |
|---|---|---|
| 已暂停条件下实际R15 | 0x1FFF32F0 | 0x1FFF32F0 |
| MSP | 0x20001940 | 0x20001940 |
| 三组VTOR | 均0x1FFF0000 | 均0x1FFF0000 |
| 三组DHCSR | 均0x00030003，已暂停 | 均0x00030003，已暂停 |
| CFSR/HFSR | 均0 | 均0 |
| 完整Flash/options | 匹配冻结候选 | 匹配冻结候选 |
| 0地址向量别名 | 等于本次Flash头，不等于ROM头 | 等于本次Flash头，不等于ROM头 |
| 120B BIO | ABI不符，未解释为有效诊断 | ABI不符，未解释为有效诊断 |
| SDK受控调用 / Close | 244 / 1 | 244 / 1 |

当前处理器确实停在系统ROM，而不是在正常运行BIO_V2。候选存在于Flash不等于候选在运行；当前RAM不能按其符号地址强行解释为有效ADC和RR。此发现与原E1的ABI失败相符，但原E1没有PC/VTOR当次读值，不能倒填原E1的PC或精确状态变化时刻。尚未证明最初进入ROM的原因，不能归咎于负责人移动板子、改BOOT/接线或模拟器；负责人明确未操作开发板，目标操作均由Codex执行。

## 工具及连接/关闭审查

原RESP工具在目标显示运行时，只检查DHCSR运行位，不记录实际执行PC和VTOR；且旧u32读取没有保存返回值。这是Codex工具的诊断取证不足，已在独立新工具补齐，旧工具/已执行profile不改。新工具明确禁止halt/go/reset/WriteMem/WriteReg；所有标量系统读取保存原u32，核寄存器仅在实际S_HALT成立后读取，兼容R15/PC括号别名，原SDK名称也保存。

运行中计划使用只读DWT_PCSR取地址样本；此次CPU已暂停，PCSR全FFFFFFFF，只记不可用，未将它解释为真实PC，也未写DWT强制启用。精确R15来自已暂停条件下的SDK寄存器读取。DWT/CYCCNT/TRCENA原状态保留。

本次把ForceAttachTarget、禁自动重试/升级、SetRestartOnClose0、SetSkipDebugDeInit1及Flash/options禁缓存放在Device选择之前；Device可能执行连接，不让保护设置落后于潜在连接。Open前与Open后均记录接受结果，SDK日志及函数白名单受控。SEGGER文档说明这些策略的意图：[连接/关闭命令](https://kb.segger.com/J-Link_Command_Strings)；PCSR只读来源为[ARM Cortex-M4 r0p1 TRM](https://www.keil.com/dd/docs/datashts/arm/cortex_m4/r0p1/ddi0439c_cortex_m4_r0p1_trm.pdf)。这不等于已独立证明SDK完全无副作用。

第一轮关闭前和第二轮重连后均已在相同ROM暂停位置，未观察到新的位置变化。因此没有证据将本轮第一次Close单独定为进入ROM的动作；同样不能因此排除更早的连接/关闭行为。第二轮包含重新连接影响，关闭后的无连接时段没有独立观测，不作“Close后持续运行”的保证。两轮完整Flash/options一致也不能排除调试控制状态改变。

本次SYSCFG外设时钟未开，MEMRMP读值0不单独作为BOOT归因；实际别名向量匹配Flash是独立读取证据。GPIOB/PB2当前电平不是上电BOOT1锁存值，专用BOOT0也没有由此测得；不要求盲改跳帽。

## 继续采集之前

当前运行门为RUNTIME_HOLD，直接go会从ROM位置续跑，禁止这样凑采集。已准备[一次正常复位及有条件10秒卡](AUTH-B-RUNTIME-RECOVERY-RESP-001-R1.md)和专用工具：只准正常器件复位一次，不烧录、不写PC/SP；真实Flash入口/栈和初始化/ADC推进通过后，同一连接内采一次10秒，避免在恢复和采集之间再次Close/Open。失败停，不打START、不重试、不调阈值。

新卡包含reset≤1、halt≤1、go≤2，明显超出用户本轮“只读核验”，故执行计划明确disabled并单独询问新增复位权限；原接线/源模式/电气边界沿用，不重复索要现场事实。本报告形成时尚未获批/发出reset，新的10秒及E2/E3均未执行。后续状态以追加的真实执行记录为准。

7项只读工具离线测试、5项恢复门禁测试均exit0；两种disabled/未批准清单真实CLI均worker1/监督1，在SDK构造之前拒绝。合成测试不替代本次实板状态或呼吸验收。机器摘要见[本次状态证据](../evidence/B-RESP-003/runtime-state-01-summary.json)；UID、完整RAM、原始SDK日志及现场原话只保存在受限目录。

## 获批后的前置停止及新卡

负责人随后明确回复“同意按卡复位一次并有条件采集”，原话/卡SHA独占封存；复位卡获批后执行了一次连接。**在任何reset/halt/go之前**，新连接实际读得DHCSR=0x01010001（未暂停）、VTOR=0x08000000；已不符合获批卡要求的ROM暂停前提。按卡立即停止，worker/监督均exit1，SDK受控调用34，reset/halt/go/Flash写均0，未进入完整Flash前检或采集窗口。不把“已批准一次复位”写成“已经复位”，也不隐瞒前置失败。

这进一步说明会话之间状态发生变化；当前可确认的直接事实是向量表已指Flash、CPU在运行，不能因此声称BIO初始化和ADC已经恢复，因为尚未读到有效诊断或PC样本。变化发生原因仍未知，不能唯一归因于Close、连接、用户操作或恢复命令。恢复命令实际没有发出。

因原卡明确失败后不重试，已冻结该次失败，不重跑。另备[零复位新窗口卡](AUTH-B-RESP-PILOT-002-R1.md)，先在同一连接核VTOR/PCSR/BIO及计数推进，全部成立才新采10秒，reset0、halt≤1/go≤1；3项离线测试及未批准清单真实CLI拒绝通过。新卡当前单独等待负责人确认新窗口，原接线与电气事实不重复索要。见[本次前置停止证据](../evidence/B-RESP-003/e1-02-preflight-stop-summary.json)。

## 最终追加：新零复位窗口已经获批并完成

负责人明确回复“同意新的零复位10秒窗口”。新卡前检确认VTOR/PC/BIO及计数推进，通过后同一连接完成10秒，worker/监督0，未发reset命令、halt1/go1。分析exit3，RESP_PATH_NOT_OBSERVED。详见[最终实板结果](RESP-E1-03-RESULTS.md)。本文较早等待描述为冻结阶段记录；各次失败保留，不将后续采集成功倒写为已查明ROM状态变化根因。
