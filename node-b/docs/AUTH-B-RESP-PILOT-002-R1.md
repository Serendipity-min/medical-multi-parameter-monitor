# AUTH-B-RESP-PILOT-002 R1｜运行态核验后零复位单次10秒卡

2026-10-22 Asia/Shanghai。状态PREPARED_PENDING_NEW_WINDOW_APPROVAL。原RUNTIME恢复R1尝试在Open后读得DHCSR=01010001、VTOR=08000000，已不符合获批的ROM暂停前提，故按原卡停止；实际reset/halt/go均0、未采窗口，worker/监督均1。该失败和只读两轮原件保留，不重跑原卡。本卡是**新的一次窗口**，单独等待确认，不冒用“失败不重试”的原授权。

## 固定边界与执行包

沿用负责人已确认未移动/操作开发板、原三线R红→RA/L黄→LA/F绿RLD→RL、LL/胸导空置、J5供电ON、ADS1292_V2.0/板5V/commonGND/START PG15/DRDY PA3、原J-Link；SKX独立呼吸波形15bpm/1.5R、电池/断USB，万用表已移开OFF，CAN/A/C/人体断开，无改线/供电/源菜单动作。窒息未知不改、Z0/ΔΩ=null。该卡不要求重新测量或接线。

当次身份仍绑定私有参考SHA6807dc3c928c11b5ba3d2185286f2a7e18bc526485d7ac84edace59728dc0323；完整Flash期望f713277a50a5ec8d8a93317f412d5ab1b754e5d619918e57e9efe9dceef24cbb、options期望52d5979da03bd7be45e385920ec7d5901793bab3f6bc1daa0c1c1997f9e91687。BIO_V2 BIN25284B SHA438a8120f6df06ce219cdc30c0e5b697ac0e993f98d5a80521b10361536ae3ae，不改源码/阈值。

- 入口supervise_resp_checked_b.py→capture_resp_checked_b.py，同一连接前检与采集，无中间Close/Open。
- 官方9.86a DLL：E:/medical-monitor-node-b-field-private/field-r3/jlink-986a-portable/JLink_x64.dll，SHA632d0d78e72b8a55c65945a0c393a9f081082c725fff4ba3081b0a565fd58cff；单探针、VTref3.0–3.6V、SWD1000kHz。
- 独立profile05：E:/medical-monitor-node-b-field-private/field-r3/resp-003/capture-resp-E1-05.json，SHA`36bd57065035e91b461b24110e55de9ef929b73d2e5bee5e656ee4931d05616d`；实际源03：同目录source-record-E1-ready-03.json，SHA`1a14ca86ebf3c8d1f2169639a53d2e8ba4f1d2dc64d14a296eb5cd3ccac83550`。原01–04及历史源均保留；新包装层由manifest额外冻结。
- 输出固定E:/medical-monitor-node-b-field-private/field-r3/resp-003/e1-03，必须不存在。manifest为同目录checked-E1-03-manifest-private.json，当前enabled=false/owner_capture_authorized=false；同意后独占保存原话及SHA再激活，Open前核卡/工具/profile/source/DLL/审批原件全部SHA。

## 有限动作与准入顺序

Open≤1、显式Connect≤1、Close≤1；Device前禁自动升级/重试、ForceAttachTarget1、SetRestartOnClose0、SetSkipDebugDeInit1及Flash/options禁缓存。**reset=0、halt≤1（仅成功窗口尾段）、go≤1（仅最终恢复）、应用内存/Flash/options/GPIO/SPI配置写0**，无自动恢复或失败重试。运行态不读SDK核寄存器，不隐式暂停获取PC；直接禁止Reset、SetResetType和任意写API。

先核身份，初态已暂停/lockup立即STOP，不go。第一组系统/PCSR/BIO快照后读取整片Flash/options，间隔0.5秒保存第二组。两组必须VTOR08000000、观测到候选Flash范围PCSR、无fault/halt/lockup/新增reset、BIO ABI有效且样本前进、ADC无四类错误、初始化缓存匹配。PCSR不可用也不能冒称拿到了PC；本卡保守停止，不写DWT强制取样。

前检通过才在同一连接进入冻结RESP collect：重新核身份/Flash/options，单次10秒，≤201块3072B槽、≤21组诊断。末尾halt≤1、确认后读单次128KiB RAM、同份RAM取稳定尾段；末身份/Flash/options均通过才go≤1，Close≤1。前检诊断单列子目录，不混入窗口诊断或周期估计。

## 精确读取白名单

| 地址/长度 | 最多次数/用途 |
|---|---|
| E000ED00/4、E0042000/4、1FFF7A10/12、1FFF7A22/2、40023C14/4、40023C0C/4 | 身份，前检/采集前/末各1次 |
| 08000000/1048576、1FFFC000/16 | 前检/采集前/末各1次，整片/options哈希 |
| E000EDF0/4 | 初态、快照前后、各槽与尾段/恢复，≤240次，原u32留证 |
| E000ED04/4、E000ED08/4、E000ED24/4、E000ED28/4、E000ED2C/4、E000ED30/4、E000EDFC/4、E0001000/4、E0001004/4、40013800/4、40023874/4、40023844/4、40020410/4 | 前检两组，各地址≤2次；不写寄存器，MEMRMP时钟关闭时不单独判BOOT |
| E000101C/4 | PCSR每组5次、20ms间隔，共≤10次；运行地址采样，不冒称精确暂停R15 |
| 20001AE4/120、2000018C/48、200001BC/12 | 前检2组+窗口≤21组，共每种≤23次，缓存不冒称实时SPI |
| 20001F30/3072 | 新10秒窗口≤201块 |
| 20000000/131072 | 窗末确认暂停后1次 |

程序复用冻结读取类，但本次流程不会访问其未用向量白名单地址，也不会调用核寄存器枚举/ReadReg。受控SDK≤4000、另Close≤1，全会话≤240秒，普通/槽读≤5秒、整片Flash≤45秒、RAM≤15秒、halt≤3秒。10秒不含前检/Flash总耗时，记录真实时长；独立监督超时仅终止，不另开连接补救。

## 停止及结论

任一状态/身份/哈希/ABI/缓存/ADC/原码近轨/部分读/超时/现场异常立即停，失败不reset/go、不重试。采集0成功、1 STOP/前置拒绝、2导出失败，参数错误真实2，监督另存worker真实码及自身0/1。只在成功尾段/恢复及进程全0后，沿用analyze_resp_b.py离线分析；估计不接收菜单作为先验，分析0相干、2完整性失败、3未见可信周期、1分析异常。

只做本次E1新窗口，不自动进入15→30/E3，不宣称绝对阻抗或临床精度。原ECG六窗、失败及备份全部保留，不改变保护分支或云。Close后状态不作独立保证；若再次状态改变，保留原件并停止，先继续查调试会话问题，不凑窗口。

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
- `node-b/tools/capture_resp_checked_b.py`：`48b3f4bafc411f66adc4a92fa3d5522c47f96db286ce62de9201b6477bc1525c`
- `node-b/tools/supervise_resp_checked_b.py`：`7f6602ba50820e04b172623ccf66d09edd37d5cbf9373204427e649cf6b71087`
