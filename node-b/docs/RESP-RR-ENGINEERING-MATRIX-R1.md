# RESP E3：12/18/24次分、各两轮的正式名义RR工程矩阵 R1

2026-10-23，Asia/Shanghai。**仅准备，当前仍30bpm；六格均未采集、未复位、未连接SDK。** 前置E2已由20→30原码周期3000→2000ms建立，既有单窗分析3保留。本矩阵只做NOMINAL_RATE_MATCH，不是阻抗或临床精度认证。CPU ROM/Flash机制按负责人要求继续待查。

## 六格顺序与互斥时间段

|独立格|名义呼吸率（次/分）|轮次|目标周期ms|当前状态|
|---|---:|---:|---:|---|
|12-r1|12|1|5000.000|未设置、未运行|
|12-r2|12|2|5000.000|未设置、未运行|
|18-r1|18|1|3333.333|未设置、未运行|
|18-r2|18|2|3333.333|未设置、未运行|
|24-r1|24|1|2500.000|未设置、未运行|
|24-r2|24|2|2500.000|未设置、未运行|

每格在同一连接内先完成身份/Flash/options、一次正常复位后的入口和初始化核验，再开始独立137秒槽采样。首条窗口诊断设备时间为锚点：**[0,45)秒预热、[45,135)秒评价、[135,137)秒尾裕量**。前置初始化等待不替代这45秒。预热、尾段、锚点前保留帧及所有失效原因均保存，不进入稳态RR分母；原码错误、ADC错误、近轨在整个窗口仍判失败。每格从新启动开始，不挑最后一次有效RR，也不因提前有效缩窗或因失效延窗。

每格137秒，六格槽窗口共822秒（13分42秒），前末完整Flash读、启动和分析另计。两轮为两个独立窗口，各有自己的预热/复位/尾段。按12-r1→12-r2→18-r1→18-r2→24-r1→24-r2执行；某格采集或分析非0立即停，不自动进入下一格，不以“第二轮”覆盖第一轮失败。换档须有负责人实际菜单确认，同档两轮沿用一次现场确认，无需反复询问；任何状态变化重新核对。

## 设置和电气边界

保持呼吸波形、波形周期20bpm、幅度1.5R、窒息0s，既有ECG60设置只作来源记录，实际CH2/HR另记。只由负责人改变“呼吸率”，两个bpm字段不能混用。12/18/24依V2.2手册可设，但本轮没有假定现场已经设成；若实际菜单无法设定，停止该档并记录，不擅自换20或借波形周期字段凑数。

同一B STM32F407ZGT6，J5供电、原BOOT/JTAG/5V共GND/START PG15/DRDY PA3；红R→RA、黄L→LL、绿F→RL，LA/胸导空置，原接线不动。SKX电池、充电USB断开，万用表两笔离开且OFF，无新增接地仪器，CAN/A/C/人体断开、导联无短路和异常。沿用既有源DC代表值2.5/16/-13.5mV（当次量程未知）及20/30实板记录，不伪造新测量或认为它已认证32kHz/隔离额定；无变化则不要求重复测导线电阻。F按模块设计接主动RLD，绝不能短接LL与RL、当GND或改驱动配置。

source_type=RESP_EXPLORATORY，dynamic_pair=MANUFACTURER_MANUAL_RA_LL；reference_rpm/Z0_ohm/delta_Zpp_ohm=null，1.5R只保存原文。nominal_rpm只有收到实际设档确认后填写，不能将菜单当校准真值；不报告准确率百分比。绿F端到端映射未做电测的历史边界保留，不重启负责人取消的通断/电阻项目。

## 采前冻结的工程判据

1. 全部原始槽块SHA、稳定槽导出、序号/设备时序/flags/尾RAM/诊断120B原件/身份/Flash/options/退出码先核验；缺口、重复冲突、CH1/CH2近轨、ADC初始化/SPI/状态/队列错误均失败，不补点。主机观测SPS须240–260。
2. 评价段原码须覆盖45秒起点后≤12ms到135秒终点前≤12ms。以不接收名义设置作为先验的冻结6–40搜索，时间域中位间隔、谱峰和自相关须相干；原码时间域RR与名义值差≤1次/分。保存每个周期、近轨情况、候选/接受计数。
3. 评价段至少45次实板保存诊断；首点≤46.5秒、末点≥133.5秒，相邻点严格递增且间隔≤2000ms。**所有这些保存观察均rpm_valid=1且rpm_reason=0**；各RR与名义值及独立原码时间域估计差均≤1次/分。该100%是保存观察有效率，不声称250SPS逐样本RR连续有效覆盖；非原子诊断来源照录。
4. 各档两轮全部通过，独立原码RR两轮差≤1次/分；六格使用不同源/profile/现场卡/真实采集回执/原码SHA。缺格、重复原件、重跑或只平均末值不能得到总通过。只有六格实物完成后才记E3_NOMINAL_RR_ENGINEERING_PASS。
5. CH2仅独立记录，不要求独立RESP下持续HR60有效；HOST冻结C回放和事件单列，不代替实板RR或改动固件/阈值。启动无效原因全部保留，既有20/30分析3不回改。

## 精确有限权限（每格，六张卡不可互换）

单探针/单操作者Codex /root，VTref3.0–3.6V、SWD1000kHz；Open≤1、显式Connect≤1、Close≤1。所有guard在Device前：SuppressGUI、禁固件升级、ForceAttachTarget1、InhibitConnectRetries1、SetRestartOnClose0、SetSkipDebugDeInit1、Flash/options禁缓存。SDK不是电源开关，不新增硬件连接。

每格reset≤1、halt≤1、go≤2，目标Flash/options/应用内存/PC/SP/VTOR/GPIO/SPI/BOOT/RCC写0。正常reset仅限前置阶段SetResetType0；复位实际暂停后读核心一次，SP20002F30、PC去Thumb位080001A0或000001A0，零地址别名64B等于候选Flash向量才go一次。等3秒，间隔0.5秒的两组运行/VTOR/PCSR/fault/初始化缓存及ADC/BIO推进检查通过才开始137秒。

目标50ms槽轮询≤2741块；每10块一组120B诊断/48B统计/12B初始化RREG缓存≤275组，准备再2组，各总≤277。窗口结束后halt一次，确认暂停读128KiB RAM取完整稳定尾段，末核Flash/options及身份一致，才go一次并确认关闭前运行。Close后状态未知，不重连调查；失败不补发go/reset、不烧录、不自动恢复。

受控SDK≤10000次，另Close≤1；正常reset≤5秒、halt≤3秒、普通/槽读≤5秒、完整Flash≤45秒、RAM≤15秒、Close≤5秒。独立监督360秒全会话硬限，仅终止不另连；新MatrixLink同为360秒且完整重新收窄白名单，避免继承旧240秒/4000次预算导致长窗在尾段失败。该时效变化在采前为137秒新协议设定，不追认或修改任何历史失败。

|只读地址/字节数|每格上限|
|---|---:|
|E000ED00/4、E0042000/4、1FFF7A10/12、1FFF7A22/2、40023C14/4、40023C0C/4|各2|
|08000000/1048576、1FFFC000/16|各2（前/末）|
|00000000/64|1，仅复位暂停别名阶段|
|E000EDF0/4|2800|
|E000ED08/4|5|
|E000ED28/4、E000ED2C/4|各2|
|E000101C/4|10（准备各5）|
|20001AE4/120、2000018C/48、200001BC/12|各277|
|20001F30/3072|2741|
|20000000/131072|1（暂停尾段）|
|SDK核心寄存器|1组；名称≤256、值≤21，确认暂停才读|

不读ROM向量、RCC/BOOT/GPIO开展机制调查，不改RLD/相位/增益/滤波/阈值，不接CAN/A/C/人体或改正式腾讯云。

## 冻结身份与执行包

BIN25284B SHA438a8120f6df06ce219cdc30c0e5b697ac0e993f98d5a80521b10361536ae3ae；整片Flash期望f713277a50a5ec8d8a93317f412d5ab1b754e5d619918e57e9efe9dceef24cbb、options期望52d5979da03bd7be45e385920ec7d5901793bab3f6bc1daa0c1c1997f9e91687。UID/OPTCR私有参考SHA6807dc3c928c11b5ba3d2185286f2a7e18bc526485d7ac84edace59728dc0323。均在当次前末核验，不拿历史SHA冒称新读取。

ABI锚点capture-resp-E1-05.json SHA36bd57065035e91b461b24110e55de9ef929b73d2e5bee5e656ee4931d05616d仅验证固件布局，不作本次源或权限。J-Link DLL固定E:/medical-monitor-node-b-field-private/field-r3/jlink-986a-portable/JLink_x64.dll，SHA632d0d78e72b8a55c65945a0c393a9f081082c725fff4ba3081b0a565fd58cff。BIO C源SHA3adca55cb1eb1fa3ed8e4148f837287d0454bcc2c08ae77a8f73deb1dac156a7。

私有准备目录E:/medical-monitor-node-b-field-private/field-r3/resp-003/e3-matrix-r1。每格profile已冻结；source-template的nominal_rpm和实际呼吸率文字为null，目标另记target_rpm，operator_ready/menu_confirmed=false，不可执行。收到实际设档和按卡执行指令后，新建source-ready-格.json、同档安全/负责人原话记录和manifest-ready-格.json（绑定真实文件/原话/本卡/profile/tools SHA）；准备模板原件不覆盖。首格外的清单还须绑定前格成功分析SHA。独占attempt-格.json在SDK前消耗，失败后不能换目录重试。

|格|profile SHA256|source-template SHA256（不是实际已设源）|
|---|---|---|
|12-r1|`41beaf18b4c17defe321d9051f82aed61981337ed0d2ae000a1ca4c3348040ab`|`3fd6808b725e724ffa7c0887900f5144a26949d8b9d2e462103f55267b9cf231`|
|12-r2|`104ff52f78e900533fba1e5038a9dad656c9a7313a5e703bf695c7b1891979e3`|`d2cb27517a50c31521cacc52127d9a8d3ecd21678e5e9bbcb2d3fea0a0b45801`|
|18-r1|`565ba5fb5659cab0fc4de0e4bb79b33fc692a2813b03ff4a81849a6b18dbd0c7`|`a93d66251319b9bfff6c27e9d5bb0a378c9a622f31d511b3067b53b1cf8f315a`|
|18-r2|`82773271031314c81db22ac8ff727b539ac72f70895bd52a85c6f23c919b0187`|`ea5a7d04c9fd21135b5a36f94a2721120c90e5aac434bd3e551be73391e736d6`|
|24-r1|`9acd646e551e42b1a6bc7e2e7747b6274d6b3eef0df75d44a976a48d5ec27ac1`|`6ccfb4e73b39ec95de7edfa4cfd3936bc1a1c5f013f668036850aa7379610b75`|
|24-r2|`1d00cea2dbe4c59b90e496515b5d394310b0ea2b78733f389847584adbc6282e`|`06f4650a2c03d200dba4a71729ffc59bad505372dd5e1d13b6afcecccb61ba31`|

单格命令由对应卡逐项给出：supervise_resp_matrix_b.py→resp_matrix_b.py。单格离线分析analyze_resp_matrix_b.py --capture ... --source-record source-ready-格.json --profile profile-格.json --out analysis-格；六格后纯离线--summaries六个analysis-summary-private.json汇总，不能顺带执行剩余格。

worker真实退出0=完整采集及稳定导出、1=停止、2=导出失败；监督0/1；单格分析0=全部采前判据通过、2=输入完整性失败、3=周期或稳态RR/覆盖不足、1=异常；矩阵0=六格通过、2=有完整性失败、3=工程不通过、1=缺格/重复/异常。每个原生退出码保留，分析失败不能由采集0或回放成功抵消。

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
- `node-b/tools/resp_matrix_b.py`：`55d933f19ccc8ffabaf5b92bbd77efef5d8940e8941b5338f7ab7d3a82a1b39d`
- `node-b/tools/analyze_resp_matrix_b.py`：`8208773ed890cc276d38144b99f023da68c7fb223d793acb6b76498244d746a5`
- `node-b/tools/supervise_resp_matrix_b.py`：`8286a91d01a5cbf87fb02b07165c77029f38eee895cbae524e317a8a573cee0a`
- `node-b/tests/test_resp_matrix_b.py`：`9ae45d58ec52a61d074726593dfc216572d2d992660ca8ae1a6012810241a0c3`
