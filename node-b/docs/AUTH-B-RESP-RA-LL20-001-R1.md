# AUTH-B-RESP-RA-LL20-001 R1｜RA–LL呼吸20的一次45秒采集卡

2026-10-23，Asia/Shanghai。负责人已报告R2参数/电压、新接法和B上电/J-Link接回，并明确要求一次采集计算；本卡在SDK打开前提交并绑定该原话，不再次请求同一采集许可。仅一次45秒，失败即停不重试。旧15/RA–LA卡、工具、profile、ECG六窗和失败原件不修改。本卡不追查CPU ROM→Flash原因，不复位、不烧录。

## 本次现场及电气依据

- 同一B STM32F407ZGT6、J5上电，原BOOT/J2/5V共GND/START PG15/DRDY PA3不改。负责人已完成**红R→RA、黄L→LL、绿F→RL，LA/胸导空置**；线缆网络沿用既有设计解释，不冒称新测通断。V2.2手册第20页明确RESP用RA–LL，手册SHA8b264906747e76336e7a7221ab77b76e3697078f794b064e77081e7e56fc48aa。
- 负责人本次报告呼吸率20bpm、幅度1.5R、波形周期20bpm、窒息0s；沿用呼吸波形页面与此前ECG60设定，ECG60须由CH2另看实际周期。两个20分别保存，不把波形周期当RR真值；窒息0s只作原始显示。
- R2三对原话“2.5mv,16mv-13.5mv”，按顺序解释RA−RL=+2.5mV、LL−RL=+16mV、RA−LL=−13.5mV；该负号解释使差分关系一致，但不是新增独立测量。绝对值最大16mV，小于保守0.20V停止界限。**实际量程及逐对20V粗读未复报，记未知，不补造双档读数。**
- 按“按R2完成”及既有不变范围沿用SKX电池/充电USB断开、无新增接地仪器、表笔移开OFF、CAN/A/C/人体断开；不冒称每项在本条均独立口述。依据同一非人体浮地源、上述端子直流报告、厂家指定电极对及模块名义39k×2/RLD100k支路，允许一次有界探索；不认证电流、32kHz/RLD兼容或绝对阻抗。
- 负责人在中间审阅前已完成接线/上电，作为负责人报告的状态转换偏离保留；Codex不追认自己控制了冷接过程。本次新指令授权从当前状态开始，Codex不再改线、切源或开关电源。

source_type=RESP_EXPLORATORY，schema RESP_RA_LL20_SOURCE_1，stage RESP_RA_LL20_SINGLE_WINDOW；dynamic_pair=MANUFACTURER_MANUAL_RA_LL仅表手册规定，Z0_ohm/delta_Zpp_ohm/reference_rpm均null，不当成实测阻抗或独立校准频率。

## 精确执行包与一次性输出

| 项目 | 冻结值 |
|---|---|
| supervisor → worker | node-b/tools/supervise_resp_rall20_b.py → resp_rall20_b.py |
| analyzer | node-b/tools/analyze_resp_rall20_b.py；冻结BIO_V2 C源Host回放与实板观察分列 |
| DLL | E:/medical-monitor-node-b-field-private/field-r3/jlink-986a-portable/JLink_x64.dll；SHA632d0d78e72b8a55c65945a0c393a9f081082c725fff4ba3081b0a565fd58cff |
| source | E:/medical-monitor-node-b-field-private/field-r3/resp-003/source-record-rall20-01.json；SHAe7e9c9317e7fd4d0b8c2855ac741caabd324678fadba676b4ed1b5ae8c6369db |
| profile | 同目录capture-resp-rall20-01.json；SHA39b1c9efe4fcb27618ddc7707604b1bc44a739810528a1c85a57673c0126972c；schema RESP_RA_LL20_CAPTURE_45S_1 |
| manifest | 同目录rall20-01-manifest-private.json；绑定本卡SHA、19项工具SHA、DLL、profile/source、安全记录与负责人本轮原话文件SHA和文字，保留完整argv |
| 输出 | 同目录rall20-01，必须不存在；分析另存analysis-rall20-01，不能覆盖旧输出 |

旧capture-resp-E1-05.json只验证冻结BIN/ABI/身份锚点，不作为本次时长/接法/profile或源授权。候选BIN25284B SHA438a8120f6df06ce219cdc30c0e5b697ac0e993f98d5a80521b10361536ae3ae；整片Flash期望f713277a50a5ec8d8a93317f412d5ab1b754e5d619918e57e9efe9dceef24cbb，options期望52d5979da03bd7be45e385920ec7d5901793bab3f6bc1daa0c1c1997f9e91687。UID/OPTCR绑定私有身份参考SHA6807dc3c928c11b5ba3d2185286f2a7e18bc526485d7ac84edace59728dc0323，当次前/末重新核验。

## 连接、采样和退出边界

单操作者Codex /root、单探针；VTref3.0–3.6V、SWD1000kHz、Open≤1、显式Connect≤1、Close≤1，不重连。Device选择前设置ForceAttachTarget1、InhibitConnectRetries1、DisableAutoUpdateFW1、SuppressGUI1、SetRestartOnClose0、SetSkipDebugDeInit1，Flash/options禁缓存。不升级探针、不供电、不启trace、WorkRAM或间接读取；拒绝Reset、SetResetType、WriteMem/WriteReg等写命令。

1. 同一连接前核身份、完整1MiB Flash/options。若运行态直接核准备快照；若本来暂停，只有真实R15在BIO_V2 Flash、VTOR08000000、CFSR/HFSR均0且仍暂停，才允许条件go一次。ROM/故障/未知入口即STOP，不复位、不跳PC，不扩展CPU调查。
2. 两组准备快照相隔0.5秒，保存120B BIO、48B ADC、12B初始化缓存和VTOR/PCSR。必须ABI/缓存匹配、计数推进、无ADC错误/近轨。运行态不以ReadReg隐式暂停；PCSR无样本不写DWT强制采样。
3. 采**一次45秒**，目标50ms轮询，≤901个3072B槽块；每10块一组诊断/统计/缓存，≤91组。保存全部原始块、真实版本/序号/设备时戳/flags、IO区间和冲突，不补点。错误即STOP，不靠多采一轮掩盖。
4. 窗末halt≤1，确认暂停后单读128KiB RAM，从同份RAM取head和稳定尾段；末核完整Flash/options/身份通过才go一次并确认关闭前运行。Close不自动go，关闭后状态不作独立保证；失败不在finally补发go/reset。

合计reset=0、halt≤1、go≤2（最多1次条件续跑＋1次末尾恢复），Flash/options/应用内存/GPIO/SPI配置写0。受控SDK≤4000次，另Close≤1。普通/槽读≤5秒、halt≤3秒、整片Flash≤45秒、RAM≤15秒，全会话硬时限240秒；独立监督只在超时终止进程，不另开连接或补发恢复命令。45秒指槽采样窗口，前/末整片核验另计真实时长。

## 只读地址与次数白名单

| 地址/长度 | 上限或用途 |
|---|---|
| E000ED00/4、E0042000/4、1FFF7A10/12、1FFF7A22/2、40023C14/4、40023C0C/4 | 前/末身份各一次 |
| 08000000/1048576、1FFFC000/16 | 前/末完整Flash/options各一次 |
| E000EDF0/4 | 初态/准备/槽/尾段/恢复，≤930次 |
| E000ED08/4 | 初态/条件续跑/两组准备，≤4次 |
| E000ED28/4、E000ED2C/4 | 条件续跑及两组准备，各≤3次；不清除 |
| E000101C/4 | 两组准备各5次、20ms间隔，≤10次 |
| SDK核寄存器 | 仅已有S_HALT时≤1组，枚举≤256名称、已枚举核心值≤21；不运行态隐式暂停 |
| 20001AE4/120、2000018C/48、200001BC/12 | 各2组准备＋窗口≤91组，共各≤93次；缓存不是新SPI回读 |
| 20001F30/3072 | 槽块≤901次 |
| 20000000/131072 | 窗末确认暂停后≤1次；head/稳定槽从同份缓冲切片 |

不读BOOT/GPIO/RCC/ROM向量深入排查，不新接源端仪器或导联。

## 采前冻结的分析与真实退出码

首条窗口诊断设备时钟锚定0–10秒预热、10–40秒评价、40–45秒尾裕量；原码全保留，前置环形历史不混入评价。先核块SHA、尾段/恢复、真实进程退出、序号/flags/时序/削顶/ADC错误/主机240–260SPS和评价覆盖，再判断周期。

独立CH1估计沿用冻结峰间隔中位数、谱峰、自相关交叉核对，不以20作搜索先验；本窗实板RR有效性要求≥5次评价观察、全部rpm_valid=1且有效RR与相干原码时间域估计相差≤1。名义20是否相符另列描述；约3秒仅为名义周期预期，不是输入真值。CH2另描述实际周期，不将ECG60自动当实测。RR有效仅限保存观察，不冒称逐样本连续覆盖、E2跟踪、E3矩阵或医疗精度。

worker0成功、1前置/执行STOP、2导出失败；监督保存worker真码及自身0/1。分析0=本窗原码周期相干且RR有效，2=输入完整性失败，3=完整但周期未建立或RR无效，1=分析异常。保留所有部分原件和失败，不重试、不改变预热/评价段或阈值。新增8项与原7项离线检查通过，不能替代本次实物结果；执行前另跑禁用清单真实CLI负例，确认不打开SDK。

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
- `node-b/tools/resp_rall20_b.py`：`8478070d4a4b4c3d468c50a5f0259ce546aa986e95b08182767d74bf9200fa53`
- `node-b/tools/analyze_resp_rall20_b.py`：`030daff2c8e07249392ee9d2e7a12f873ad9cc3a5652b506d71b7db65da67697`
- `node-b/tools/supervise_resp_rall20_b.py`：`131cf822a27eff0b68d47a5de47bcb1920a369583270be12b9559d0601592ecb`
