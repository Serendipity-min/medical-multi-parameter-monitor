# AUTH-B-RESP-RA-LL20-RECOVERY-001 R1｜一次正常复位及有条件45秒窗口

2026-10-23，Asia/Shanghai。**PREPARED_AWAITING_EXPLICIT_RESET_AUTHORIZATION；未执行。** 前一[零复位卡](AUTH-B-RESP-RA-LL20-001-R1.md)已在ROM运行/诊断ABI失败处停止，其一次窗口权限不重用。负责人原采集指令不冒称含新复位许可；本卡只为恢复候选运行和取得数据，不追查进入ROM原因。

## 不变现场与范围

沿用负责人最新报告：呼吸波形、呼吸20bpm、幅度1.5R、波形周期20bpm、窒息0s，红R→RA、黄L→LL、绿F→RL、LA/胸导空；同一B上电/J-Link、原模块/BOOT/供电/START/DRDY不改，电池SKX且充电USB断开、表笔移开OFF、CAN/A/C/人体和新增接地仪器断开。源端直流代表读数及量程未知边界见[停止报告](RESP-RA-LL20-001-RESULTS-R1.md)，本卡不要求重测、不改菜单或线缆。批准时只绑定本卡的新复位/窗口许可和未报告变化的既有状态。

仅**一次正常器件复位**（SetResetType=0，JLINKARM_Reset≤1），不烧录。允许一次Open、显式Connect≤1、Close≤1；单探针/单操作者，VTref3.0–3.6V、SWD1000kHz，沿用先ForceAttachTarget/禁重试/禁升级/SetRestartOnClose0/SetSkipDebugDeInit1再Device的保护顺序。当前初态不限定必须暂停或ROM，避免状态已变却误用旧卡；无论当前在哪，本卡最多执行该一种正常复位一次，未满足真实入口即STOP。

## 精确包

| 项目 | 固定值 |
|---|---|
| supervisor → worker | node-b/tools/supervise_recover_resp_rall20_b.py → recover_resp_rall20_b.py |
| 共享采样/分析 | 冻结resp_rall20_b.py的collect及analyze_resp_rall20_b.py；原窗口入口不修改 |
| DLL | E:/medical-monitor-node-b-field-private/field-r3/jlink-986a-portable/JLink_x64.dll；SHA632d0d78e72b8a55c65945a0c393a9f081082c725fff4ba3081b0a565fd58cff |
| 新profile | 同resp-003私有目录capture-resp-rall20-recovery-01.json；SHA44c13ba74331421e2ab01b65b7eb80b2d5235eb5cdac8fbc44fb268504496e9a |
| 新source | 同目录source-record-rall20-recovery-01.json；SHA4c01a79ace48ce1aa5e90932238994f2f268ff184a5bfe0402122b9036704f8f |
| scope | 新source/profile均含ONE_NORMAL_RESET_BEFORE_NEW_45S，独立新文件，不重用失败卡授权 |
| manifest | 同目录rall20-recovery-01-manifest-private.json；当前enabled=false、owner_reset_authorized=false；获批后只绑定新增原话及其SHA，完整argv、本卡SHA和21项工具SHA |
| 输出 / 分析 | 同目录rall20-recovery-01 / analysis-rall20-recovery-01，均必须不存在，不覆盖失败rall20-01 |

source仍为RESP_EXPLORATORY，厂家手册RA–LL，nominal20非独立频率真值，Z0/ΔΩ/reference_rpm均null。新profile以原19项采集依赖校验其ABI；恢复manifest另绑定这19项及2项新增恢复/监督代码，共21项，不通过放宽旧验证器授予reset。

## 顺序与控制上限

1. 同一连接核UID/OPTCR/芯片/Flash长度和完整Flash/options，与既有身份参考及候选全片一致才进入恢复阶段。完整Flash期望f713277a50a5ec8d8a93317f412d5ab1b754e5d619918e57e9efe9dceef24cbb；options期望52d5979da03bd7be45e385920ec7d5901793bab3f6bc1daa0c1c1997f9e91687；私有身份参考SHA6807dc3c928c11b5ba3d2185286f2a7e18bc526485d7ac84edace59728dc0323。
2. 保存初态DHCSR/VTOR。只在此阶段允许SetResetType=0和一次JLINKARM_Reset（≤5秒）。须实际暂停，才读取一组真实R15/MSP等核心寄存器和地址0的64B别名；从已核完整Flash取向量，不新增不同长度的Flash读。
3. 要求Flash向量SP=20002F30、入口080001A1，真实R15去Thumb位后为080001A0或其别名000001A0，真实MSP（或R13）等于20002F30，地址0的64B与Flash前64B完全一致。不符即STOP，不写PC/SP/VTOR、BOOT、RCC或任何寄存器来强行通过。
4. 入口门通过才go一次，等3秒；两组准备间隔0.5秒。**先检查运行态/VTOR08000000，再解码RAM**，随后PCSR、fault、BIO/ADC计数推进、初始化缓存和无近轨/ADC错误均须通过；仍在ROM或其他异常停止，不重复Reset、不换ResetType。
5. 同一连接采一次45秒。槽/诊断/完整性/尾段及分析与上一张零复位卡相同：最多901槽、91组诊断，尾部halt≤1，确认后128KiB RAM，末核身份及完整Flash/options通过再go一次。Close不自动go，失败不补发恢复。

合计**reset≤1、halt≤1、go≤2、Flash/options/应用内存/GPIO/SPI写0**。SDK受控≤4000次另Close≤1；普通/槽读≤5秒、reset≤5秒、halt≤3秒、1MiB Flash≤45秒、128KiB RAM≤15秒，会话240秒硬限，超时监督只终止。只有Reset改变运行/复位状态，绝不宣称完全无目标状态变化。

## 精确只读白名单

| 地址/长度 | 上限 |
|---|---|
| E000ED00/4、E0042000/4、1FFF7A10/12、1FFF7A22/2、40023C14/4、40023C0C/4 | 前/末身份各一次 |
| 08000000/1048576、1FFFC000/16 | 前/末整片各一次 |
| 00000000/64 | 复位暂停后别名核对≤1，仅该阶段允许 |
| E000EDF0/4 | 初态/复位/核心读前后/准备/槽/尾/恢复≤940次 |
| E000ED08/4 | 初态及两组准备的前置和快照≤5次 |
| E000ED28/4、E000ED2C/4 | 两组准备各≤2次，不清除 |
| E000101C/4 | 两组各5次、20ms间隔，≤10次 |
| SDK核心寄存器 | 仅复位确认暂停后≤1组，名称枚举≤256、核心值≤21 |
| 20001AE4/120、2000018C/48、200001BC/12 | 准备2组＋窗口≤91组，各≤93次 |
| 20001F30/3072 | ≤901次 |
| 20000000/131072 | 尾部确认暂停后≤1次 |

不做关闭/重连对照，不读ROM向量、BOOT/GPIO/RCC深入调查。恢复脚本仅在验证后短阶段放开一次Reset及一次地址0/64读取，其他阶段拒绝；共享原采集入口仍reset=0。

## 分析、停止和原件

沿用采前冻结0–10秒预热、10–40秒评价、40–45秒尾裕量。独立原码周期估计不用20作先验；实板RR有效判据、名义匹配描述、未知Ω边界、源菜单与CH2实测分列不变。worker0/1/2、监督0/1、分析0/1/2/3语义沿用前卡；未进入窗口则无RR计算、分析退出码null，不以软件测试替实物。

卡只执行一次；任何身份/入口/栈/别名/运行/ADC/近轨/超时异常即停并保存全部原件，不重试、不重刷、不自动再开卡。恢复6项合成测试与禁用CLI负例先通过，批准前实际reset和新增硬件调用均0。

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
