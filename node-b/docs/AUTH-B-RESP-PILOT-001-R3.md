# AUTH-B-RESP-PILOT-001 R3｜RESP-003单次10秒探索卡

2026-10-22 Asia/Shanghai。本卡按负责人明确调用的MPM-B-RESP-003制定，替代R1中“必须先取得厂家ΔΩ/电极对证明才可探索”的科学准入条件。**允许未知幅度为null、实际动态电极对UNVERIFIED；不放宽电气核对、现场确认或操作次数。** 本卡依据已报告的A/B组DC粗筛和实际呼吸15bpm/1.5R菜单修订。仅在独立呼吸页面接受原文字样bpm，不伪写rbpm。当前状态`HOLD_FOR_FINAL_READY_CONFIRMATION`，尚未启动探针。

## 当前事实和仍待完成的两项

负责人确认原三线/模块未变、电池供电且无异常；A组SKX端子200mV档代表值依次2.3/0.7/1.7mV，原20V卡的量程偏离已保留。B组在独立呼吸15bpm、1.5R下，20V档三对均报告为0；这是粗量程显示，不是精确0V。窒息项未找到，保持未知且不操作。两组报告值均低于0.20V停止界限，仅支持有限非人体10秒探索，不证明高频/RLD通用兼容。最后须确认万用表已移开且OFF，原电气边界及源菜单保持。

1. **电气门**：同一已通过ECG的接法、浮地电池源/表、图纸限流支路及A/B两组报告值共同作为本次有限非人体试采依据；单次代表值/量程偏离如实保留，不签通用电气兼容或32kHz通过。最后须确认万用表两笔均移开、表OFF，USB/其他接地仪器/CAN/A/C/人体断开，原导联无互碰，无发热/复位/供电异常。事实不符或有异常即不启动；额外测量/变线另卡。
2. **源菜单门**：已收到实际“呼吸波形/15bpm/1.5R”，独立呼吸上下文中的bpm仅解释为名义呼吸次数/分，原字保留。窒息项未找到，状态UNVERIFIED_NOT_CHANGED，不要求继续寻找、猜测禁用或设0；短窗中是否出现变化只作观察，不能把未知窒息设置当算法失败。最后就绪回复确认上述模式保持并可执行本卡一次10秒后，生成独占ready源和manifest；不把旧pending模板改为真记录。

当前负责人已报告独立呼吸波形15bpm/1.5R。A/B电压及实际量程的原始回复分开封存；本卡不要求再测、寻找窒息项、重新接线或切档。最后就绪确认前不打开探针。厂家ΔΩ缺失不作为探索阻断。

## 固定硬件、固件和数据身份

- B：STM32F407ZGT6，既有DEV_ID413、M4、1MiB、RDP0。真实UID/OPTCR只绑定私有原身份参考，SHA256 `6807dc3c928c11b5ba3d2185286f2a7e18bc526485d7ac84edace59728dc0323`；下一次连接仍需重新核验身份和Flash，历史记录不能冒充当次读取。
- J5/YL-1210 12V1A中心正极，BOOT B0/B1 GND；J-Link接B原JTAG接口，仅调试。ADS1292_V2.0、J1空、J2板5V/common GND、START PG15、DRDY PA3。保持原接线/跳帽/供电，不复位，不外加元件；不把F绿接LL，不短接LL/RL或任何电源地。
- BIO_V2 BIN25284B SHA `438a8120f6df06ce219cdc30c0e5b697ac0e993f98d5a80521b10361536ae3ae`；完整Flash期望 `f713277a50a5ec8d8a93317f412d5ab1b754e5d619918e57e9efe9dceef24cbb`，options SHA `52d5979da03bd7be45e385920ec7d5901793bab3f6bc1daa0c1c1997f9e91687`。原整片双备份/恢复副本SHA69d9efb0…保留；源码及阈值不改。
- 独立profile为受限`field-r3/resp-003/capture-resp-E1-03.json`，SHA `36bd57065035e91b461b24110e55de9ef929b73d2e5bee5e656ee4931d05616d`；schema `BIO_V2_RESP_EXPLORATORY_CAPTURE_1`，仅E1/10秒，绑定全部新旧共用工具、完整ABI和真实板参考。01/02已被03替代并保留，旧ECG profile会被明确拒绝。
- RESP源类型`RESP_EXPLORATORY`，独立模式15/1.5R；`Z0_ohm=null`、`delta_Zpp_ohm=null`、`dynamic_pair=UNVERIFIED`、`impedance_calibration=NOT_CALIBRATED`。模板SHA `6d8a7d79229d059f8048442668db4b49b1c505b45218319e8ad70568289827e5`尚未就绪，不允许调用；ready记录须含实际菜单文字、本人回复、安全记录路径和SHA，本卡/全部工具/profile/source的执行manifest在Open前独占落盘。

## 唯一软件窗口与准确入口

只允许Codex /root单操作者在本轮确认后执行一次，不允许重试。入口`node-b/tools/supervise_resp_b.py`，子进程`capture_resp_b.py`。参数固定为：

| 参数 | 值 |
|---|---|
| seconds | 10 |
| profile | `E:/medical-monitor-node-b-field-private/field-r3/resp-003/capture-resp-E1-03.json` |
| source-record | 当前仅有`source-record-E1-pending.json`，明确禁用；实际就绪后使用独占新文件`source-record-E1-ready-01.json`及其精确SHA |
| DLL | `E:/medical-monitor-node-b-field-private/field-r3/jlink-986a-portable/JLink_x64.dll`，SHA632d0d78e72b8a55c65945a0c393a9f081082c725fff4ba3081b0a565fd58cff |
| card | `node-b/docs/AUTH-B-RESP-PILOT-001-R3.md`；最终字节SHA在外部E1-launch-plan和公开E0回执冻结，不在卡内自引用 |
| out | `E:/medical-monitor-node-b-field-private/field-r3/resp-003/e1-01`，必须不存在 |

`E1-launch-plan-private.json`保存完整argv及卡/profile/源SHA；目前enabled=false，pending源不能作为ready执行。实际ready包必须先补齐电气/菜单事实，仍以本卡固定15/1.5R、10秒为准，不能借此换30、提高3.0R或延长时长。旧ECG监督器/采集器不用于RESP。

连接沿用官方SDK9.86a，单探针、VTref3.0–3.6V、SWD1000kHz，禁止升级、连接重试、自动reset、Close自动go，保留DWT。SDK函数白名单及固定调试策略见新工具，最多4000次受控SDK调用，另允许Close至多1次（总4001）。不允许Reset、目标内存写、任意ExecCommand或未知地址读取。

## 读取白名单及控制次数

| 数据 | 精确地址/字节 | 次数或时机 |
|---|---|---|
| CPUID/器件/UID/容量 | E000ED00/4、E0042000/4、1FFF7A10/12、1FFF7A22/2 | 起/止各一次身份核验 |
| Flash SR/OPTCR | 40023C0C/4、40023C14/4 | 起/止各一次，只读 |
| Flash/options | 08000000/1048576、1FFFC000/16 | 起/止各一次，核上述SHA |
| DHCSR | E000EDF0/4 | 初态、逐块及暂停/恢复检查，包含在4000预算内 |
| fault状态 | E000ED28/4、E000ED2C/4 | 仅初态已暂停需要条件续跑时；读取不清除 |
| 核寄存器 | 原SDK枚举，最多256项名称；仅读R13/R15/MSP/XPSR | 仅暂停初态PC核对，无改PC或寄存器写 |
| 槽块 | 20001F30/3072 | 连续10秒目标50ms轮询，最多201块；实际区间/哈希留证 |
| 完整BIO诊断/ADC统计/初始化RREG缓存 | 20001AE4/120、2000018C/48、200001BC/12 | 每10块一组，最多21组，原件及完整解析即时落盘 |
| 完整RAM尾段 | 20000000/131072 | 窗末确认halt后一次；同一RAM取head偏移140、末127已发布槽偏移1F30 |

先核当次身份、Flash/options及profile；初态若暂停，仅PC在`[08000000,080062C4)`且CFSR/HFSR为0才go一次。运行窗结束halt至多一次，确认暂停前后读取同一RAM，身份/Flash/options末检均通过才最后go至多一次。总halt≤1、go≤2、reset0、Flash/options/GPIO/SPI配置写0，无START脉冲或新SPI RREG。末态只报告SDK Close前实际所见，不宣称Close后独立观测；源保持获批采集初态的独立呼吸15，软件不自动切回其他模式。

单普通/槽块调用≤5秒，halt≤3秒，单次整片Flash≤45秒，RAM≤15秒，全会话硬上限240秒。10秒为轮询运行时间界限，最后一次受限读/诊断可能跨过边界，记录真实总时长及设备时间，不截短日志假装恰好10.000秒。STOP、超时、身份/哈希/ABI/配置缓存不符、部分读、ADC错误、观测原码近轨或运行状态变化即停；监督只终止，不在错误路径补发reset/go或恢复重试。现场过压/过流/发热/复位/异常地连接亦立即停，并按已批准的电气停止方案处置，卡外供电/接线动作不由软件代发。

## 分析和退出

保留全部槽版本、起始pending、冲突和确认尾段，原码不补点、不投票洗白；首次诊断之前的环形历史保留但不混入本次源状态周期估计。120B全部30字段（包括有符号raw/filtered、rpm/valid/reason及候选/接受/末周期/新鲜间隔/RMS/干扰比例）分别保存。

离线入口`analyze_resp_b.py`分开给出实板诊断、冻结C源Host回放和独立CH1原码估计（中位周期+谱峰+自相关），不把菜单数字输入估计器，不计算欧姆。10秒不要求rpm_valid为真、不签L3；无规律变化记RESP_PATH_NOT_OBSERVED，不下结论“模拟器不支持”或“算法错误”。不得以软件合成测试替代L1/L2实板证据。

采集子进程成功0、采集STOP/前置拒绝1、导出失败2，参数非法由argparse真实退出2；监督另存worker真实返回码和自身0/1。分析完整且观察到相干变化0、输入完整性失败2、未观察到相干变化3、分析异常1，均保留原件/日志。E1结束后停下分析，E2 15→30和E3 12/18/24不在本卡内；不得自动重试、改阈值、接LL、禁RLD或改寄存器。
