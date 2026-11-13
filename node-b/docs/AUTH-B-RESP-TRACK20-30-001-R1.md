# AUTH-B-RESP-TRACK20-30-001 R1｜固定波形周期20的呼吸30单窗及20→30对照

2026-10-23，Asia/Shanghai。负责人已明确当前只将呼吸率改为30、其余不变，并要求工具准备好即可采集。本卡绑定该指令，**只采一次新的30bpm/45秒窗口，不重采20基线**。为保持启动流程与基线相同，沿用上一窗已获准并执行的一次正常复位＋有限采集流程；在本卡重新明确reset≤1，不重用旧卡/旧输出或追加复位许可，不追查CPU根因。BIO_V2固件与阈值均不改。

## 固定现场、源及对照

同一B STM32F407ZGT6、原J5/BOOT/J2/5V共GND/START PG15/DRDY PA3/J-Link，红R→RA、黄L→LL、绿F→RL，LA及胸导空置。负责人报告接线和其余状态不变；沿用电池SKX/充电USB断开、表笔离开OFF、无新增接地仪器、CAN/A/C/人体断开。源端DC只引用既有代表值及量程未知的边界，不伪写本轮新电气测量。

呼吸波形，**呼吸率30bpm，波形周期20bpm，幅度1.5R，窒息0s**；此前ECG60设定只作来源描述，不视为本窗实测。source_type=RESP_EXPLORATORY，dynamic_pair=MANUFACTURER_MANUAL_RA_LL，nominal_rpm30；reference_rpm/Z0_ohm/delta_Zpp_ohm仍null，不把菜单当独立标定真值。两个bpm字段独立校验，Codex不切源、不改其他字段。

20基线使用已完成的rall20-recovery-01，原始数据不覆盖。其公开分析摘要SHA954a06da964f538e99f851ceff878974955882783f6ba84ea97537e6e4171406，实际源SHA4c01a79ace48ce1aa5e90932238994f2f268ff184a5bfe0402122b9036704f8f；原码周期中位3000ms、三方法20次/分，冻结RR有效性分析3保留。

## 精确执行包

| 项目 | 冻结值 |
|---|---|
| supervisor → worker | node-b/tools/supervise_resp_rall30_b.py → resp_rall30_b.py |
| 共用恢复/采样 | 已冻结recover_resp_rall20_b.restore/RecoveryRallLink及resp_rall20_b.collect，二者不修改 |
| 分析 / 对照 | analyze_resp_rall30_b.py / compare_resp_20_30_b.py，后者纯离线、不连接硬件 |
| DLL | E:/medical-monitor-node-b-field-private/field-r3/jlink-986a-portable/JLink_x64.dll；SHA632d0d78e72b8a55c65945a0c393a9f081082c725fff4ba3081b0a565fd58cff |
| 新source | 同resp-003私有目录source-record-rall30-01.json；SHA9f8b4359beef3625e8e3466ee87dcda494d5949afa672e4713fcce56b230a304 |
| 新profile | 同目录capture-resp-rall30-01.json；SHAef6c6f0fd68b1d468ce54021ff1643005968065c1846716364c2d384d0fc1f4e；独立RESP_RA_LL30_CAPTURE_45S_1 |
| scope | E2_MATCHED_20_TO_30_SINGLE_NORMAL_RESET_45S，不冒用20窗口profile/旧卡 |
| manifest | 同目录rall30-01-manifest-private.json，绑定本卡/25项工具/DLL/source/profile SHA、当前原话文字与文件SHA及完整argv |
| 输出 | 同目录rall30-01，分析analysis-rall30-01，均须不存在；对照另存分析目录period-tracking-20-30-private.json |

冻结BIN25284B SHA438a8120f6df06ce219cdc30c0e5b697ac0e993f98d5a80521b10361536ae3ae；完整Flash期望f713277a50a5ec8d8a93317f412d5ab1b754e5d619918e57e9efe9dceef24cbb、options期望52d5979da03bd7be45e385920ec7d5901793bab3f6bc1daa0c1c1997f9e91687。UID/OPTCR绑定私有身份参考SHA6807dc3c928c11b5ba3d2185286f2a7e18bc526485d7ac84edace59728dc0323，前/末实核。旧E1 profile仅作固件/ABI静态锚点，不作本次源或时间授权。

## 一次连接内的顺序和权限

单操作者Codex /root、单探针；VTref3.0–3.6V、SWD1000kHz，Open≤1、显式Connect≤1、Close≤1。Device选择前设置ForceAttachTarget1、禁连接重试/升级、SuppressGUI、SetRestartOnClose0、SetSkipDebugDeInit1和Flash/options禁缓存。不供电、升级、启trace、WorkRAM或间接读取。

1. 核身份及完整Flash/options，保存初态DHCSR/VTOR。初态不限ROM/Flash或暂停，不因状态已变误套上轮失败卡。
2. 仅在恢复阶段设置SetResetType=0并正常器件Reset≤1（≤5秒）。实际暂停后读取一组真实核心寄存器和地址0/64B别名。Flash向量SP=20002F30、入口080001A1；真实PC去Thumb位须080001A0或别名000001A0，MSP（或R13）20002F30，别名64B与Flash前64B一致才go一次。
3. 等3秒，取两组间隔0.5秒的准备快照。先检查运行态/VTOR08000000，再解码RAM；PCSR/fault/BIO与ADC计数推进/初始化缓存及无近轨/ADC错误均须通过。不写PC/SP/VTOR/BOOT/RCC来强行通过。
4. 同一连接采一次45秒，目标50ms轮询，槽块≤901、每10块一组120B诊断/48B统计/12B初始化缓存≤91组，全部原始块/冲突/版本/序号/时戳/flags/IO区间原样保留，不补帧。
5. 窗末halt≤1，确认暂停后单读128KiB RAM取稳定尾段；末核完整Flash/options/身份通过才go一次并确认关闭前运行。Close不自动go；失败不补发恢复、不重连。

**reset≤1、halt≤1、go≤2、Flash/options/应用内存/GPIO/SPI配置写0**。受控SDK≤4000次，另Close≤1。普通/槽读≤5秒、reset≤5秒、halt≤3秒、完整Flash≤45秒、RAM≤15秒，全会话240秒硬限；独立监督只终止，不另开连接或补发命令。45秒是槽采样窗，前/末全片核验另计真实时间。

## 精确只读白名单

| 地址/长度 | 上限 |
|---|---|
| E000ED00/4、E0042000/4、1FFF7A10/12、1FFF7A22/2、40023C14/4、40023C0C/4 | 前/末身份各一次 |
| 08000000/1048576、1FFFC000/16 | 前/末全片各一次 |
| 00000000/64 | 复位暂停后别名核对≤1，仅该阶段允许 |
| E000EDF0/4 | 初态/复位/核心读/准备/槽/尾/恢复≤940次 |
| E000ED08/4 | 初态及两组准备前置和快照≤5次 |
| E000ED28/4、E000ED2C/4 | 两组准备各≤2次，不清除 |
| E000101C/4 | 两组各5次、20ms间隔，≤10次 |
| SDK核心寄存器 | 确认复位暂停后≤1组，名称≤256、核心值≤21 |
| 20001AE4/120、2000018C/48、200001BC/12 | 准备2组＋窗口≤91组，各≤93次；缓存非新SPI回读 |
| 20001F30/3072 | ≤901次 |
| 20000000/131072 | 尾段暂停后≤1次 |

不读ROM向量/BOOT/GPIO/RCC开展根因调查，不改RLD/相位/增益/滤波或门限，不接源端仪器或新线缆。

## 采前冻结的两层判据

原码/诊断/退出/尾段/恢复/各SHA先核验，缺口/冲突/flags/时序/近轨/ADC错误及主机240–260SPS与设备覆盖先判完整性。首条窗口诊断锚定0–10秒预热、10–40秒评价、40–45秒尾裕量，与20基线相同；预热/新鲜周期不足导致的RR无效仍全部保留，不能从评价段中事后删掉。

单窗RR有效性沿用至少5次评价观察、全部rpm_valid1且与相干原码估计差≤1次/分；原码峰间隔/谱峰/自相关用固定6–40搜索，不以30作先验。CH2单列，不要求伴随HR60硬通过或把不稳定尖峰估计当实际HR。

**E2周期跟踪另判**：两档原件/算法相同且完整，原码均相干，源只有呼吸率20→30而波形周期20/1.5R/窒息0/接法等控制不变；中位周期比T30/T20应接近2/3，允许相对偏差≤10%，两档原码时间域估计各与名义设置相差≤1次/分。满足时仅记E2_RATE_TRACKING_SEEN，不认证绝对频率/ΔΩ/医疗精度或正式RR矩阵。当前对照不以两窗全段RR有效性通过为前提；它们的原分析退出码单列、不改写。

worker0/1/2、监督0/1语义不变；单窗分析0=原码相干且全评价RR有效、2=完整性失败、3=完整但周期或RR有效性不足、1=异常。对照另有真实退出码0=两档工程周期跟踪建立、2=完整性失败、3=未建立、1=异常，不能用对照0抹掉单窗3。E3未执行，CPU问题继续DEFERRED_BY_OWNER。

7项新离线检查与6项共用恢复检查通过，另在SDK前跑禁用清单真实CLI负例；软件通过不代替实物结果。任何身份/入口/运行/ADC/近轨/超时异常立即停，保留失败、原始数据与退出码；不重试、不再切源、不追加窗口，历史ECG六窗及20基线不覆盖。

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
- `node-b/tools/recover_resp_rall20_b.py`：`b57d75c52922b24cce0bc78ec53a636654cae53c7837ce597df904e72193b21d`
- `node-b/tools/supervise_recover_resp_rall20_b.py`：`dffbc700405780731d54e9a0a19f1070a13d1d16a0d7fc4432d98cf3c925c0c5`
- `node-b/tools/resp_rall30_b.py`：`fd05f6f2d1fabd68f2851c99e4135166023638f08c605dbba8c0926de9728b05`
- `node-b/tools/analyze_resp_rall30_b.py`：`645e3f1bb98ac82edcfd530e7c3cd1c0e24c077ce450aa24f85dec9fbe0c919f`
- `node-b/tools/supervise_resp_rall30_b.py`：`c2bd27b66c25a3c2b2bafde6bed7b02ab3a28ba87ead77596632195bc0272b4d`
- `node-b/tools/compare_resp_20_30_b.py`：`d1e2054cf76fd5ffe1392b606fc4470f7d3ecdd0bcaeef1ad1799fb2fd2b382a`
