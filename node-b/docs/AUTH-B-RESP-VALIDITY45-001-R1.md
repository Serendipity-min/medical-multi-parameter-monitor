# AUTH-B-RESP-VALIDITY45-001 R1｜一次45秒呼吸数据有效性卡

2026-10-22 Asia/Shanghai。负责人已明确要求在准备精确卡后重采**一次45秒**，且已确认设置完成、界面为呼吸波形。本卡依据本轮指令执行，不要求重复批准已明确的45秒任务，不复用已消耗的10秒卡。仅检查本窗CH1周期及实板RR有效性，不签E2速率跟踪、E3矩阵或绝对阻抗精度。CPU的ROM→Flash问题按要求暂列待查，不做关闭/重连比较或复位调查。

## 冻结现场与源

- 同一B板STM32F407ZGT6、J5/YL-1210供电ON、原BOOT/J-Link/模块接线不动；ADS1292_V2.0/J2板5V/commonGND，START PG15、DRDY PA3。
- R红→RA、L黄→LA、F绿主动RLD→RL，LL/胸导空置；CAN/A/C/人体断开，SKX电池且充电USB断开，无新增接地仪器，万用表两笔已移开OFF。沿用已确认不变事实，不重复测量或接线。
- 负责人本轮明确设置：ECG60、呼吸率15bpm、幅度1.5R、窒息0s；当前呼吸波形界面，波形周期维持此前20bpm。呼吸率和波形周期分别记录；不把20当RR，不把窒息0s擅解为已测得禁用。
- source_type=RESP_EXPLORATORY，mode=INDEPENDENT_RESPIRATION，nominal_rpm=15；reference_rpm、Z0_ohm、delta_Zpp_ohm均null，dynamic_pair=UNVERIFIED。ECG60是源设置报告，须另看CH2实际周期，不拿它当已测值。
- 电气依据为同一套ECG六窗及RESP短窗接法、浮地电池源/仪表、原名义限流支路和既有A/B端子直流报告值；量程偏离/粗量程零显示原件保留。本次只作有界非人体45秒，不声称高频/RLD通用兼容或实测限流电流。设置变化限于负责人已完成的源菜单，本工具不改源。

## 固件/身份和准确执行包

BIO_V2 BIN25284B SHA438a8120f6df06ce219cdc30c0e5b697ac0e993f98d5a80521b10361536ae3ae，完整Flash期望f713277a50a5ec8d8a93317f412d5ab1b754e5d619918e57e9efe9dceef24cbb，options期望52d5979da03bd7be45e385920ec7d5901793bab3f6bc1daa0c1c1997f9e91687。UID/OPTCR仅绑定私有身份参考SHA6807dc3c928c11b5ba3d2185286f2a7e18bc526485d7ac84edace59728dc0323，当次前/末重新核验。不改固件、BIO阈值、旧工具或ECG六窗原件。

| 项目 | 精确值 |
|---|---|
| 监督 / worker | node-b/tools/supervise_resp_validity_b.py → resp_validity_b.py |
| DLL | E:/medical-monitor-node-b-field-private/field-r3/jlink-986a-portable/JLink_x64.dll；SHA632d0d78e72b8a55c65945a0c393a9f081082c725fff4ba3081b0a565fd58cff |
| profile | E:/medical-monitor-node-b-field-private/field-r3/resp-003/capture-resp-validity45-01.json；SHA`38af99e0d18bf224ff0a39ea79edc749323fa2af731dc4c1664f06360bb2e637`，独立schema RESP_VALIDITY_CAPTURE_45S_1 |
| 实际源 | 同受限目录source-record-validity45-01.json；SHA`651b10156788927556daac69a02b88354eeea50ec862b937ca2861b71890ad5a`，schema RESP_VALIDITY_SOURCE_1 |
| manifest | 同目录validity45-01-manifest-private.json，Open前冻结本卡SHA/全部依赖/DLL/profile/源/本轮原话绑定及完整argv |
| 输出 | E:/medical-monitor-node-b-field-private/field-r3/resp-003/validity45-01，必须不存在；分析另存analysis-validity45-01 |

旧10秒profile只作为冻结固件/ABI静态身份锚点验证，不作为此次运行profile、时长或授权。所有旧绑定及失败保留原字节。单操作者Codex /root，单探针、VTref3.0–3.6V、SWD1000kHz，Open≤1、显式Connect≤1、Close≤1，无连接或窗口重试。

## 顺序与控制上限

Device选择前设置ForceAttachTarget1、禁升级/连接重试、SetRestartOnClose0、SetSkipDebugDeInit1、Flash/options禁缓存；不升级、不供电、不新建WorkRAM/间接读取或启用trace。命令仅冻结策略及Device=STM32F407ZG，明确拒绝SetResetType和Reset/WriteMem/WriteReg。

1. 同一连接核身份、完整Flash/options。读取当前DHCSR/VTOR及必要fault状态。若已在运行，直接核验；若本来已暂停，仅当真实R15落BIO_V2 Flash、VTOR08000000、CFSR/HFSR均0且仍暂停，才允许条件go一次。若ROM/未知PC/故障则STOP，不reset、不跳PC，不扩展CPU排查。
2. 两组准备快照间隔0.5秒，分别保存完整BIO/ADC/初始化缓存、VTOR/PCSR及运行状态，须候选PC/有效ABI/计数推进/缓存匹配/无ADC错误。运行态不调用SDK ReadReg取PC；PCSR无样本不写DWT强制采样。
3. 同一连接采**45秒**，目标50ms轮询，≤901个3072B槽块；每10块一组120B诊断/48B统计/12B缓存，共≤91组。原始版本、冲突、序号/设备时戳/flags及实际IO区间完整保存，不补点。
4. 窗末halt≤1、确认暂停后读取单次128KiB RAM，同份RAM取head/稳定尾段；完整Flash/options及身份末检通过才最后go一次。Close不自动go；关闭后状态不作独立保证。来源仍保持负责人已设置状态，不切菜单。

合计**reset=0、halt≤1、go≤2（最多1次条件续跑＋1次末尾恢复）、Flash/options/应用内存/GPIO/SPI配置写0**。SDK受控调用≤4000，另Close≤1，总≤4001。普通/槽读≤5秒、halt≤3秒、整片Flash≤45秒、RAM≤15秒，全会话硬上限240秒，独立监督超时只终止，不补发恢复命令。45秒只指槽采样窗口，前/末整片核验另计真实时长；本轮不做CPU问题归因或多次连接试验。

## 精确读取白名单

| 地址/长度 | 上限或用途 |
|---|---|
| E000ED00/4、E0042000/4、1FFF7A10/12、1FFF7A22/2、40023C14/4、40023C0C/4 | 前/末身份各一次 |
| 08000000/1048576、1FFFC000/16 | 前/末整片Flash/options各一次 |
| E000EDF0/4 | 初态/条件续跑核对、准备快照前后、逐槽及尾段/恢复，≤930次 |
| E000ED08/4 | 初态、条件续跑、准备两组VTOR，≤4次 |
| E000ED28/4、E000ED2C/4 | 条件续跑fault＋准备两组，各≤3次，只读不清除 |
| E000101C/4 | 准备两组PCSR，各5次、20ms间隔，共≤10次 |
| SDK核寄存器 | 仅已有S_HALT时≤1组，枚举≤256个名称，已枚举R0–R15/MSP/PSP/XPSR/CONTROL/PRIMASK至多21值；不运行态隐式暂停 |
| 20001AE4/120、2000018C/48、200001BC/12 | 准备各2组＋窗口各≤91组，共每种≤93次；缓存仅初始化回读，非新SPI |
| 20001F30/3072 | 45秒槽块≤901次 |
| 20000000/131072 | 窗末确认暂停后≤1次；head偏移140/已发布槽偏移1F30来自同一缓冲 |

不读BOOT/GPIO/RCC/ROM向量作深入排查，无源端仪器连接、LL/RL短接或RLD变更。

## 采前冻结的有效性分析

以首条窗口实板诊断设备时钟为锚：0–10秒预热，10–40秒评价，40–45秒尾裕量。所有帧仍保留；前置环形历史不混入结论。先复核每块原件SHA、完整诊断解码、确认尾段和进程退出，再判序号/flags/设备时序、CH1/CH2近轨、四类ADC错误、主机观察240–260SPS及30秒评价覆盖。

CH1周期独立用峰间隔中位数＋谱峰＋自相关估计，不输入名义15作先验；沿用冻结估计器一致性门。实板RR有效性须评价段≥5次保存观察、全部rpm_valid=1，并且每个有效RR与独立时间域估计相差≤1次/分。仅限保存观察，不冒称逐样本连续实板覆盖。名义15是否相符另列描述，不计算源精度；未知Z继续null。若相干周期20而非15，只能说与该实际信号相符，不能宣布源15通过。

冻结C源Host回放单列，并输出CH2实际尖峰周期，不预设测得ECG60。波形周期20字段不充当RR真值；窒息0s语义未独立证明，不强解为禁用。分析成功且本窗周期/RR有效exit0；输入完整性失败2；完整但未观察到相干周期或RR未有效3；分析异常1。状态细分，不能用末值覆盖失败。

采集worker0成功、1 STOP/前置拒绝、2导出失败，参数错误真实2；监督保存worker真码及自身0/1。身份/哈希/部分读/运行状态/ADC/缓存/近轨/超时/现场异常即STOP，原件和真实退出码保留，不重试、不改阈值、不擅自加幅或延长。此卡只一次45秒，不自动进入15→30或12/18/24矩阵。

## 工具SHA256

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
- `node-b/tools/resp_validity_b.py`：`233ba6149b62471fcb0f4967d9330b472591ca100ee70d494539d27b82a4dda4`
- `node-b/tools/analyze_resp_validity_b.py`：`8d34d7ab1f0a8afbbdbe4071c857340d1a66ab645ccdd5829a46f5de408932b9`
- `node-b/tools/supervise_resp_validity_b.py`：`6a5536a66fd1af53794799fa2c37cef8cf870264defec14abc14742dce4860ac`
