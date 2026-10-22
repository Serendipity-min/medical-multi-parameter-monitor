# AUTH-B-RUNTIME-RECOVERY-RESP-001 R1｜一次正常复位及有条件10秒RESP卡

2026-10-22 Asia/Shanghai。**状态：PREPARED_PENDING_EXPLICIT_RESET_APPROVAL。尚未复位或采集。** 本卡基于刚完成的启动只读核验：两次连接的实际PC均1FFF32F0、VTOR均1FFF0000、S_HALT=1，完整Flash/options匹配冻结候选；当前在系统ROM暂停，不能从该PC直接go。用户本轮只读核验的权限不自动扩展为复位，本卡等待仅针对“一次正常复位+检查通过后一次10秒”的明确同意。禁止固件烧录、写PC/SP或阈值调整。

## 不变现场与身份

同一STM32F407ZGT6、J5/YL-1210供电ON、BOOT B0/B1原GND位置、原J-Link接口；ADS1292_V2.0/J2板5V/commonGND/START PG15/DRDY PA3。R红→RA、L黄→LA、F绿主动RLD→RL，LL/胸导空置，CAN/A/C/人体断开。SKX独立呼吸波形15bpm/1.5R、电池/断USB，万用表已移开OFF，无新接线、供电或源菜单操作；不再重复索要这些已确认事实。窒息项未知不改，Z0_ohm和delta_Zpp_ohm保持null。原电气A/B读数和适用范围沿用，不证明32kHz通用兼容。

私有身份参考SHA`6807dc3c928c11b5ba3d2185286f2a7e18bc526485d7ac84edace59728dc0323`，每次重读UID/OPTCR绑定。BIO_V2 BIN25284B SHA`438a8120f6df06ce219cdc30c0e5b697ac0e993f98d5a80521b10361536ae3ae`，整片Flash SHA`f713277a50a5ec8d8a93317f412d5ab1b754e5d619918e57e9efe9dceef24cbb`，options SHA`52d5979da03bd7be45e385920ec7d5901793bab3f6bc1daa0c1c1997f9e91687`。

## 唯一入口与固定执行包

- 监督`node-b/tools/supervise_resp_recovery_b.py`，worker`recover_resp_runtime_b.py`；无自动重试。
- DLL `E:/medical-monitor-node-b-field-private/field-r3/jlink-986a-portable/JLink_x64.dll`，SHA`632d0d78e72b8a55c65945a0c393a9f081082c725fff4ba3081b0a565fd58cff`；单探针、VTref3.0–3.6V、SWD1000kHz。
- 独立RESP profile04：`E:/medical-monitor-node-b-field-private/field-r3/resp-003/capture-resp-E1-04.json`，SHA`36bd57065035e91b461b24110e55de9ef929b73d2e5bee5e656ee4931d05616d`；原01–03保留。04的基础采集绑定和03相同，新增恢复层另由本卡manifest冻结，不冒称旧R3已授权reset。
- 实际不变源02：`E:/medical-monitor-node-b-field-private/field-r3/resp-003/source-record-E1-ready-02.json`，SHA`94cb595ac0668d8d452a40e598e7483e3d304cf3c89161b565b3fbfb9c39d8c5`；原01保留。实际菜单原文字样15bpm，不伪写rbpm；复位许可由独立owner approval record约束。
- 输出固定`E:/medical-monitor-node-b-field-private/field-r3/resp-003/e1-02`，必须不存在；旧e1-01失败不得覆盖。
- 执行清单`resp-003/recovery-E1-02-manifest-private.json`当前enabled=false、owner_reset_authorized=false。收到明确同意后独占保存原话、将审批原件SHA与完整argv/本卡SHA/工具SHA冻结到清单，工具在构造SDK前校验；当前disabled计划不能执行。已冻结的disabled版本另存，不抹去等待状态。

## 执行顺序及不可越过的门

1. 单连接Open≤1，Device选择前保护策略与只读核验卡一致：禁升级/自动重试、ForceAttachTarget1、禁Flash/options缓存、SetRestartOnClose0、SetSkipDebugDeInit1。先核本次身份/整片Flash/options。必须再次实际确认ROM暂停、VTOR1FFF0000、R15处于1FFF0000–1FFF77FF；状态变化则停止，不机械复位。
2. 仅发一次`SetResetType = 0`及一次`JLINKARM_Reset`（正常器件复位，≤5秒）。必须仍暂停；实际R15必须080001A0或Flash别名000001A0、MSP=20002F30，向量须与冻结Flash头一致（入口向量080001A1），别名向量等于本次Flash头。任何不符停在原件记录，不写PC/SP、不go、不再reset。
3. 入口通过后go至多一次，等待3秒；两组前检间隔0.5秒，保存系统/PCSR/完整120B BIO/48B ADC/12B初始化缓存。须VTOR08000000、无CFSR/HFSR、无halt/lockup/新增reset、BIO ABI正确、样本与ADC计数前进、无四类ADC错、缓存匹配；否则STOP，不发START脉冲、SPI命令或改变模块电源。前检诊断独立子目录，不混入正式10秒窗口。
4. 前检通过，在**同一已打开连接**调用冻结RESP采集器的10秒collect，无中间Close/Open。重新核身份/Flash/options后，最多201槽块、21组诊断；末尾halt≤1，确认后读单次128KiB RAM，同份RAM取head/稳定尾段；结束Flash/options/身份通过才最后go≤1。然后Close≤1，保留SDK日志和真实退出码。只有成功尾段/恢复和进程退出0才离线分析。

**合计reset≤1（只在窗口前）、halt≤1、go≤2、目标应用内存/Flash/options/GPIO/SPI配置写0，额外供电/接线/源菜单操作0。** 复位会重置MCU外设/时基并重新执行既有固件初始化，这是本卡新增、必须明确同意的状态改变，不能称为全程只读。固件自身既有初始化行为与调试器目标写入次数分列；不修改固件来规避门禁。单会话受控SDK≤4000、另Close≤1；Open≤1、显式Connect≤1，无恢复重试。

## 读取地址、时间和停止范围

读取白名单为下列精确地址/长度之并集；不接受其他读取或SDK写入函数：

- 身份 E000ED00/4、E0042000/4、1FFF7A10/12、1FFF7A22/2、40023C14/4、40023C0C/4：恢复前、采集前、采集末各一次；ROM前检与重置入口的核寄存器只在实际已暂停时读，SDK枚举≤256项、每组所列核心寄存器≤21项，共≤2组。
- 整片08000000/1048576及options1FFFC000/16：恢复前、采集前和采集末各一次，最多各3次；00000000/64：复位入口别名核验一次；Flash向量从本次整片缓冲切片。不读取未知地址的向量。
- 运行前检系统快照各2组：E000ED04/4、E000ED08/4、E000ED24/4、E000ED28/4、E000ED2C/4、E000ED30/4、E000EDFC/4、E0001000/4、E0001004/4、40013800/4、40023874/4、40023844/4、40020410/4；PCSR E000101C/4每组5次、20ms间隔，共≤10次，0/FFFFFFFF只记无样本，不写DWT或trace启用。
- DHCSR E000EDF0/4：恢复前/入口/前检、各槽块与末尾暂停/恢复核验，≤250次；初态粘滞reset读值保留，复位后第一条检查建立基准，采集阶段出现reset即停。
- BIO 20001AE4/120、ADC 2000018C/48、缓存200001BC/12：恢复前检各2组，窗口至多21组，共每种≤23次；初始化缓存不冒称实时SPI回读。
- 槽20001F30/3072：仅新10秒窗口≤201块；RAM20000000/131072：仅窗末确认暂停后1次。
- 除原卡固定调试策略外仅新增SetResetType0和JLINKARM_Reset1次；不开放任意ExecCommand、Reset重试、WriteReg或WriteMem。

单普通/槽读≤5秒、Reset≤5秒、halt≤3秒、单次完整Flash≤45秒、RAM≤15秒；全会话硬上限240秒，独立监督只终止、不代发go/reset。10秒是运行采样窗口，不含前置复位/3秒初始化/整片核验。每阶段真实总时长留证，不截短日志。任何身份/哈希/入口/ABI/ADC/缓存/原码近轨/窗口状态错误或现场异常即停，失败Close不自动恢复；源保持独立呼吸15，不切其他档。

## 分析、结果与退出

采集0成功、1 STOP/前置拒绝、2导出失败；参数错误argparse真实2。监督保留worker真实返回码及自身0/1。分析沿用冻结analyze_resp_b.py，先核尾段/退出/全部原件哈希，再分别输出实板诊断、冻结C Host回放、独立CH1时间域/谱峰/自相关；分析0相干变化、2完整性失败、3未见可信周期、1分析异常。10秒不签RR正式有效率或绝对欧姆精度。

此次仅E1再次有界观察。若未见可信周期记RESP_PATH_NOT_OBSERVED；不自动进入15→30或12/18/24，不调整BIO_V2阈值，不接LL、A/C/CAN/人体，不改云环境及保护分支。历史失败和ECG六窗保留原字节。Close后状态仍未独立观测，不以关闭前RUNNING冒充后态。

## 冻结工具SHA256

- `node-b/tools/capture_resp_b.py`：`6989a819a5f26c91074bf2cfdd769313fa543aa85e58c01d5198bd0670e309ae`
- `node-b/tools/resp_exploratory.py`：`2b6a176b3568403fc8ba2e8ede92f537833d654112603a0b221e00e775762d77`
- `node-b/tools/analyze_resp_b.py`：`225e5ef46b8f450c3b4372d3fc102491c8f2e64ee8a5f9fd87a12074018e3360`
- `node-b/tools/supervise_resp_b.py`：`5019350e361f6ab999dc0fe9a09808b304228235d8c11b3abcf4e5e86f6f8a4d`
- `node-b/tools/capture_b.py`：`7c45589bff1099e20354b8dbe7db9bb2e32095bf67a904b9358cf4f4996800fa`
- `node-b/tools/readback_b.py`：`a095665739454398e359accca3cf67e885de1fa51bff756b7f6b5192b0c00116`
- `node-b/tools/precheck_b.py`：`3c490ecc99154aa857b0f2f9767951b5e6587844269983670a6ea53684ce4a81`
- `node-b/tools/adc_path_b.py`：`a80c1ed4ccddb8f0f569c3753c2659b78e01bb3c6b4f0b49bcaf3aa27a152d12`
- `node-b/tools/boot_check_b.py`：`0c854ade1cc99807badbdbc8a9f0a5eb7dd24d6447f617356fcd2bcd42f100c0`
- `node-b/tools/fault_snapshot_b.py`：`96d0976b2dd18d5c9a982c4d8b8afe9f2822f0120bbe06ef4c48cb4461bc49a3`
- `node-b/tools/field_profile.py`：`2cc386655e425d7f1ee57a8de956026cadd1057a27b2429ffa0f75a4bb1d9857`
- `node-b/acquisition/工具/stable_slot_export.py`：`7be6c02292e04894aa12b6eece5a439db49137517b2032ece31dd2c9e3825ae2`
- `node-b/tools/runtime_state_b.py`：`39554d2292b50a604c2b28c7aaa31b442a348e2ab65a77f281ae0b56b3b8ad46`
- `node-b/tools/supervise_runtime_state_b.py`：`98587c514f8987e76851b87465259a0b3242cb4b222c2289c1b6de5b0f580b22`
- `node-b/tools/recover_resp_runtime_b.py`：`0020bfc6f54bcddfbbaa8576801cab0e53f898a362249415082f95a51ea3b31b`
- `node-b/tools/supervise_resp_recovery_b.py`：`5f28aa9d627621d46f0df497eb460ac83b4ddb7c0cbcd21c2d35fdf9ebf5f4a9`
