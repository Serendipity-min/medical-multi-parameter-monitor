# R4当前综合交接：TIME路径修复，方案A已补一致性检查

## 最新实板交接：C49132的ECG60追加复验PASS，首窗失败保留

2026-10-29。本阶段已按批准完成C49132一次安装及独立只读，真实完整Flash匹配`9bba23b436f079183296fa98dcaeed047eb919ba8597d75a85bc144bc48417fd`，双全片/options、DISARMED、保护区及Close通过；sector3、B40928、算法阈值、ADS/GY配置与CAN接线未改。源码实现提交`29e6a773dcd65ccd7b63507188067baa6fe9f71e`，BIN/ELF和91份编译输入仍按TIME-INIT-R1冻结；未安装额外字节或自动回退旧镜像。

首个C49132窗完整采集，但ECG/HR质量不满足原判据，正式联评exit3、NOT_PASS。负责人随后**明确新增一次采集许可并表示现场观察模拟器**；使用全新授权/token/目录，绑定前次授权和失败联评SHA，同一固件、工具、源名义设置与判据，仅追加B只读一次、C人工RESET一次、B5START一次，没有烧录/复位B/Go。沿用仍在一小时有效期内的C独立核验；没有冒称复验时重新读取C完整Flash。

两窗均为普通ECG60/1mV、RA–LA–RL、电池无充电USB、非人体MOCK，45秒预热＋300秒评价＋15秒尾段、420秒业务硬停。C唯一复位均在联合记录就绪后由负责人完成，以新DISARMED行确认并各发START一次；首窗未覆盖或重写。原始B帧/C串口/Broker/Backend观察/WSS、API时序、授权消费和SHA全部保存受限EFS。安装器及独立C核验、两窗采集/监督器/B工人/云观察exit均0；**采集exit0与首窗联评exit3分开记录**。

| 项目 | C49132首窗 | 负责人追加复验 |
| --- | --- | --- |
| TIME | 第二端点，第7次查询、12012ms；新鲜RTT103ms、时间差104ms | 首端点，第3次查询、4012ms；新鲜RTT55ms、时间差127ms |
| B稳态观察HR有效 | 493/600；107次NO_CYCLES/UNSTABLE | **601/601均60 BPM、有效** |
| Broker评价期HR | 250 VALID、50 INVALID | **300 VALID均60 BPM** |
| Broker评价期RR | 297 INVALID、3条10次/分VALID，不合ECG窗预期 | **300 INVALID、值null** |
| ECG源点及映射 | 74439点，有序列缺口；已匹配批次无数值错误 | **75012点、无覆盖/连续性失败，逐点映射错误0** |
| Broker实收/Backend接受（整窗观测） | 2785/2785；拒收/丢弃0 | **2857/2857；拒收/丢弃0** |
| 评价期WSS快照 | 2973 | **2972** |
| C稳态发送/溢出/UART/丢弃/MQTT错误增量 | 均0 | **均0** |
| 正式联评 | `B5_SEPARATE_ECG60_NOT_PASS`，exit3 | **`B5_SEPARATE_ECG60_ENGINEERING_PASS`，exit0、失败项空** |

### 判定与根因边界

两窗都通过了方案A的模块时间、新鲜NTP及原一致性区间，随后TLS/MQTT和共同T0成功；**本次没有再次触发TIME拒绝**。这是本阶段两个实际窗口的结果，不声称所有未来网络条件下永不失败。

首窗B质量无效在CAN/上云之前已经出现。130个Broker ECG批次带INVALID；614个VALID ECG批次均在WSS找到且值一致，INVALID按既有规则屏蔽。C的WAVE记录gaps始终0，质量切换时quality_resets和partial_discarded增长；代码本来会清理不同质量状态之间的未满批次，解释可达的波形缺口路径，不把它说成网络凭空丢包。B的ADC坏状态、SPI、队列、长间隔、CAN错误/过期/断续增量均0。

追加复验完整通过原判据：B约250.035 SPS、HR601/601有效，C诊断60条、最大间隔5.094秒；WSS全部所需波形及标量一致，原MOCK/INVALID/STALE/OFFLINE语义、2048B限制、严格PUBACK及会话约束均未放宽，最大MQTT JSON848B。温度同时有300条VALID传输观察，**不能替代未执行的独立TEMP物表验收**；RR15正式窗亦未运行。

负责人本窗未发送异常时点报告；这不等于独立测量证明模拟器输出稳定。同一名义条件下首窗不稳、追加窗通过，说明需要保留间歇质量风险；**模拟器输出、导联接触、供电/参考地或其他输入扰动的唯一物理原因仍UNKNOWN**。工频占比在首窗有效/无效观察中重叠，不能单凭该指标断言唯一根因，不改BIO阈值制造有效值。

### STOP、恢复与封存

两窗C源端业务均精确420000ms停止，phase7/CLOSED、pending=0、unsynced=0；主机观察STOP分别420.047s和420.063s，尾段/自然STALE或OFFLINE及客户端关闭通过。追加窗原STOP中live24/cache28，随后RAM cache52、停止后队列overflow30；首窗对应cache51/overflow29也保留。**这是停止边界的残留队列行为，不计成稳态零错误，更不隐去或宣称队列排空。** 按原冻结STOP判据本窗通过，残留队列语义另列遗留，不为关闭它追加新固件。

本窗记录的C栈水位上界最大2700B，未超8192B保留栈；不作为所有中断嵌套/未来运行的总栈证明。B/C末态均由负责人再次确认全部断电熄灭，C USB及J-Link电脑USB断开，未复位/重新上电；停机不当作新的冷启动实验。

当前保留B40928/C49132及gen5，R-APP/R-CFG/R-CLOUD实际执行0，未恢复C49068/C24104/H3。隔离Backend/TLS在本次就绪核验时正常，未再次start；账号未撤销，沿用原六小时RuntimeMax，不声称整个测试环境已清理。正式配置、ACL、Broker、保护分支和Security Gate均未改动。

证据：[首窗正式联评](../evidence/B5-C-REPAIR-R4/TIME-INIT-R1/actual-C49132-ECG-review.json)、[追加窗正式联评](../evidence/B5-C-REPAIR-R4/TIME-INIT-R1/actual-C49132-owner-retest-ECG-review.json)、[同字节/同判据双窗对照](../evidence/B5-C-REPAIR-R4/TIME-INIT-R1/two-ECG-window-comparison.json)。仅签发本次**ECG60独立工程窗PASS**；B5三模式最终结项、独立冷启动、CPU ROM根因、同窗ECG/RR、绝对标定及CAN故障注入保持未完成/原状态。下文为历史时间快照，以本节为当前交接状态。

## 最新ECG复测：C49068已安装，TIME冷启动缺口复现并修正待审批

2026-10-29，负责人决定暂缓ROM根因调查，先测方案A时间门禁及ECG60的B→C→云。负责人完成新全暗10秒、C先上电5秒接J-Link、一次C人工RESET；在正常Flash、私有身份、保护、DISARMED及新鲜双全片/options全部合格后，**C49068实际安装一次PASS**。完整Flash实测`75db57c038c021b40f36fa1ee627f410d26061e18e0f59a8465c73af0216bc25`，正常Halt/Reset/Go各1、下载1，写后双全片/options、sector3及应用区外精确核验、Close均通过。随后独立C只读PASS；B40928、算法、传感器、CAN及gen5不变，没有烧录任何中间候选。

隔离测试Backend/TLS确因原RuntimeMax到期停止；配置/权限/端口、ACL及正式PID/服务合格后，各start一次，TLS/订阅/WSS就绪，驻留预算大于625秒。正式服务和配置未变，Broker HUP/ACL写/8884开放均0；测试账户未撤销，服务仍按六小时驻留，不称已清理。

负责人完成冷态回接，确认COM6、B屏刷新、ECG60/1mV、电池无充电USB、RA–LA–RL与非人体隔离状态；B只读/250SPS准备通过。记录就绪后负责人仅C RESET一次，工具按新DISARMED行发送**E-TB唯一START一次**。AT/GMR2.3.0.0/Wi-Fi/休眠关闭/单连接/被动接收通过，但TIME为`queries=0 elapsed=6 valid=0 epoch=0 tried=0`，C在START后2951ms STOP，reason3/phase0、unsynced/pending/live/cache均0；随后提示关闭未确认。**未到新鲜NTP、TLS/MQTT、共同T0或300秒评价，当前ECG上云仍NOT_PASS，不能判断本次传输正常。**

联合/监督器exit1=G3_C_NETWORK_STEP_FAILED；B exit1为G3_STOP_REQUESTED主机取消，关闭前Flash运行核验及Close续跑均true，不是B原生读取失败。云观察exit0、清理完成；背景/保留消息不冒充本窗设备交付。所有原件、工具及现场附件保留EFS；当前负责人已明确回报**全部断电熄灭**。本次无ROM/HALT复现，没有借恢复动作排查ROM。

### 这次提前TIME的归因与最小修正

已核对历史ESP真实原件：含回显37B，去回显后21B，内容为`+CIPSNTPCFG:0`、空行及OK，不含服务器列表；多次历史查询有同一SHA。本次末尾AT事件也记录21B，但本窗未保存ESP UART回复原文，故不能宣称字节级证实本次回复与历史原件完全相同。

软件缺口已在真实transport/coreMQTT/adapter/platform/UART-MMIO组合中复现：原C49068先要求读到服务器列表，之后才启用SNTP；未启用状态只返回`:0`时，初始化在任何时间查询和服务器尝试之前退出。原组合夹具始终回带列表的配置，遗漏此冷启动状态。反例使用上述真实禁用回复格式，断言time_queries=0、TLS打开0、UDP请求0；这解释可达的软件提前拒绝路径，**不证明公网NTP/AP/NAT问题已经排除**。

最小修正仅在明确的`:0`行时易失启用一次并重新读回列表，之后继续既有显式完整列表选源与轮换。启用最多多一次（合计≤4），不增加手工NTP重发或START；共享15次查询/30秒准备、60秒就绪、两类时间校验及一致性区间、1000ms新鲜性、TLS/严格PUBACK/2048B/420秒均不变。启用后仍无列表或命令错误照常拒绝。官方[ESP8266 ESP-AT v2.3命令说明](https://docs.espressif.com/projects/esp-at/en/release-v2.3.0.0_esp8266/AT_Command_Set/TCP-IP_AT_Commands.html#at-cipsntpcfg-query-set-the-time-zone-and-the-sntp-server)用于核对启用/查询语义；禁用时省略列表的具体格式依据本机历史原件，不冒称文档逐字规定。

89条真实AT组合构建/既有停顿/STOP回归步骤均exit0，含新增禁用启动正例和启用后仍空列表负例；相关4套Python实际121项测试通过。一个不存在的独立devices筛选器命中0项，明确不计为测试通过证据。两次ARM BIN/ELF完全一致；未重复算法六窗、本地TLS/UI或基础CAN验收。

### 唯一后继候选：C49132，仅离线冻结

- BIN SHA：`72131dbb5ef6bc0e0d33e328925c685403bae928aea9447a81f8291c6ae5c1ab`；ELF：`10051aa990cff78882d94870ad99509011f140439d01e76aa0e47f2bcfc44b0b`。
- 91份真实编译输入清单SHA：`84ea9a8699c5915ec2b5846374c04cf4fd845d2b0a4b17287143a2aa4643639e`；生产输入仅gateway_transport.c改变。
- 48KiB应用区余20B；bss74180B/data92B，最大静态单帧1096B不等于总调用栈证明。C49068启动期记录stack_used_upper2212B，不转作新C49132或300秒运行证据。
- **预期，尚未实测**after全片：`9bba23b436f079183296fa98dcaeed047eb919ba8597d75a85bc144bc48417fd`。当前C49068→C49132的精确sector0/1/2安装/回退包已离线逐字节重建，sector3/options/sector7/11不变；备妥不等于恢复演练。

新[初始化补包](AUTH-B5-C-REPAIR-R4-TIME-INIT-SUPPLEMENT.md)只准备I-TI/RO-TI/L-TI与独立ECG60 E-TI，模板全部disabled/owner_approved=false；新烧录和新START均0，等待新字节/窗口的一次对象批准。TEMP/RR新窗未启用。实际回执、反例、89项日志SHA、工具绑定、资源及候选见[TIME-INIT-R1](../evidence/B5-C-REPAIR-R4/TIME-INIT-R1/actual-C49068-install-and-ECG.json)。CPU ROM仍UNRESOLVED并暂缓，同窗ECG/RR、绝对标定、CAN故障注入均不补签PASS。下文为历史时间快照，以本节为当前状态。

## 最新启动监控：观察到复位后Flash，ROM根因仍UNRESOLVED

2026-10-29，负责人完成“C先上电5秒、再接J-Link电脑USB”，随后批准多轮有界启动调查。JTAG板端始终接C，不能称为调试器电气隔离的冷启动。B断电，C J5、USB_UART断开，ESP在板；本阶段零Flash/sector3/UART/START、零软件Reset/Halt/显式Go。健康Flash退出采用已批准的SDK Close续跑策略，**该策略有运行控制语义，不等于完全无副作用的只读连接**。C49068仍未安装，C49048/B40928及gen5不变。

结果和原生回执索引见[启动监控证据](../evidence/B5-C-REPAIR-R4/TIME-BOOTSTRAP-R2/C-BOOT-WATCH-20261029.json)。原件、每次执行源码、授权/.used、API时序、原生回调、样本和退出码均保存受限EFS；没有覆盖此前ROM或TIME失败。各会话只核对私有身份、64B Flash向量和16B options，**没有重复完整Flash读取，也不冒充新鲜全片PASS**。

| 阶段 | 实际证据与限制 |
| --- | --- |
| SDK兼容修复 | 首次OpenEx后可选EnableRemarks被本机DLL拒绝，尚未Device/Connect/读CPU；删除可选增强命令，保留原生日志。不是CPU启动失败。 |
| 健康挂接 | 一次60秒观察553样本，Flash、应用计时推进，3264 SDK调用、Close完成且续跑；未消费人工复位。其后15秒弹窗窗184样本仍Flash，负责人确认看到了但未按键，不能记为复位通过。 |
| 复位边沿 | 原样本捕获DHCSR=0x02010001、VTOR/PCSR/计时暂为0；下一轮捕获其后VTOR=0x08000000、应用PC、计时23ms。两轮工具分别因零向量过渡和沿用复位期间alias=0而过早判UNKNOWN，不是已证实进入ROM。修复仅在受邀复位后允许最多2秒只读零向量过渡，显式Flash VTOR不依赖该alias；ROM/HALT/Fault仍停止。 |
| 真实Flash HALT | 下一次挂接首次DHCSR=0x00030003，已暂停核心真实PC=0x0800A3A0、VTOR=0x08000000。按部署49048B ELF及SHA离线定位为__ssputs_r；未调用Go/复位恢复。它是应用暂停，与历史PC=0x1FFF369E的ROM停止分开。 |
| 负责人单次复位后关闭对照 | 单独批准并回报C实体RESET一次。首次15秒138样本Flash，853 SDK、Close续跑完成；再次挂接后15秒138样本仍Flash、计时继续，支持该次健康Close后正常运行。第二次收尾因重复创建POPUP_END抛FileExistsError，**显式Close和最终回执缺失、worker/supervisor均exit1**；不能签整组PASS或称退出后运行已确认。 |

监控新增代码已通过36项相关离线测试（exit0）。最后一项修复使POPUP_END幂等且放在必须执行的Close之后，避免主机标记错误跳过资源释放；此修正版尚未实板复验。早期各版源码与失败均保留，不用最新测试覆盖历史退出事实。

**归因边界：** 已证实监控存在两处状态误判及一处收尾错误；误判UNKNOWN→Close不续跑→下次见Flash HALT构成时间关联，且Close续跑后的一次再挂接保持运行。但没有每条Device/Connect/Close之前的独立CPU证据，不能指定某一API为唯一HALT原因，更不能将其等同为历史进入ROM的根因。BOOT0/NRST边沿仍未测量，CH340自动下载支路仍为待证假设，不把运行GPIO/万用表静态值当作锁存。

**当前末态：** 最后一次样本及关闭前检查为Flash运行；主机第二会话异常退出后设备状态UNKNOWN，没有追加连接、Go、复位、上电或烧录。下一组需冻结新的有限次数并取得对应主动恢复许可；不能重用已消费的两连接包。CPU_ROM_ROOT_CAUSE_UNRESOLVED及三窗NOT_PASS保留。下文为此前历史记录，涉及“当前”的旧文字以本节为准。

## 最新ROM专项：读取已完成，根因仍未关闭

负责人另行授权利用当前现场只读取证及排查可能原因。新增两个有限只读会话，每次120秒监督、最多300次SDK调用：第一会话120次，保存完整1MiB Flash/16B options、30KiB ROM、128KiB RAM及外设/别名快照；第二会话254次，只补已暂停CPU的真实核心寄存器，没有重复全片读取。均真实exit0、Close完成，显式Halt/Reset/Go/Flash/sector3/UART写0；Close不续跑。原件只在受限EFS。

**当前最新状态为HALT在ROM，C49068仍未烧录。** 第一新增会话的首次DHCSR读为0x00030003，DWT_PCSR均FFFFFFFF，因此没有拿它冒充真实PC。第二会话仅在确认已HALT后读取真实R15=0x1FFF369E、MSP=0x20001D50、LR=0x1FFF14E1；CFSR/HFSR0、DFSR1、DEMCR01000000。之前安装入场时的非HALT与现在HALT属于不同时间快照；没有调用前独立CPU证据，不能宣称已定位某一条SDK API为唯一触发。DFSR和RCC_CSR均可能保留历史标志，不当作本次事件计数或时间戳。

新鲜完整Flash和options现在已核实仍精确匹配C49048原件；ROM SHA为`ca1ae7213d01ce43f1f30d4e2751e2aec68cef16f7be62f856210104f583fc02`。0地址64B等于Flash向量、不同于ROM：Flash初始SP=0x20020000/入口0x08009681，ROM为0x20001D80/0x1FFF3DA1。MEMRMP读0时SYSCFG时钟未开，不能拿该值冒充复位BOOT锁存；别名比较只描述当前实际映射。PB2/BOOT1当前为低，专用BOOT0复位边沿没有捕获。

本机ROM反汇编和RAM结构一致：真实PC处于GPIO输入探测循环，检查PA10等引脚，符合bootloader接口自动探测；不是B5网络/算法正在执行。ROM栈位置也与本机ROM向量一致。反汇编最初因工具不支持长路径失败，原失败保留；只在同一受限EFS根内复制ROM到短路径后离线解码成功，没有新设备连接。

| 候选机制 | 支持证据 | 尚未证明的部分 |
| --- | --- | --- |
| BOOT0/NRST自动下载支路瞬态 | 本机板图第3页：CH340由板上+5V供电，Q1/D2影响RESET，Q3/R44接BOOT0；第4页BOOT0跳帽经R55=10k，Q3支路R44=1k。USB拔下不等于CH340控制支路电气隔离 | 未捕获复位边沿；不能由电阻网络理论直接认定其本次拉高，也不能用当前Flash别名反推曾经的BOOT锁存 |
| 调试挂接/退出的暂停副作用 | 之前运行ROM，新增只读窗口首次读时已HALT；每窗有一次Connect但显式Halt0。DFSR1与调试请求相符，Close策略0会保留停止状态 | 没有每次Connect/Close前独立状态，DFSR又是粘滞位，仍不能唯一归因到Connect、Close或某条读API |
| 应用故意跳ROM/软件复位 | 37个实装C49048编译C输入逐一核SHA审查，没有NVIC_SystemReset/ROM跳转路径；实际BIN没有本机ROM入口字面量，AIRCR写命中仅为NVIC优先级配置 | 静态检查不能排除全部间接控制流损坏；不能把“未发现故意跳转”写成绝对不可能 |

现有MCP和B5联合采集源码均已在open前设置DTR/RTS=False，本轮只核对源码，未打开串口。串口程序顺序风险已缓解，但板载电路上电瞬态及J-Link内部动作未因此关闭。按[SEGGER文档](https://kb.segger.com/J-Link_Command_Strings)，ForceAttachTarget跳过目标初始化，SetRestartOnClose=1相当于退出Go，SetSkipDebugDeInit跳过调试反初始化；这些命令被接受，不等于已证明零硬件副作用。

裁定保持`CPU_ROM_ROOT_CAUSE_UNRESOLVED`，**未宣称解决ROM**。本次读取已排除Flash被擦除/身份错误，并确认真实停留代码；要闭环，最小剩余补证是“无调试器独立启动→挂接前后”受控对照，并记录或隔离BOOT0/NRST自动下载支路。现有万用表不能捕捉复位边沿；若做电气隔离、正常复位/有条件Go或接入边沿仪器，需另行限定主动动作。本轮没有用重刷、强设PC/MSP/VTOR或擅自Go掩盖现场。

证据、两次实际SDK计数、原件清单SHA及可能原因见[ROM只读审计](../evidence/B5-C-REPAIR-R4/TIME-BOOTSTRAP-R2/ROM-cause-readonly-audit.json)。以下是此前各阶段的时间顺序记录，以本节为最新状态。

**最终现场更新：负责人完成本次全暗10秒冷态转接后，首次新会话在ROM入场门停止；负责人随后明确回报已人工复位一次并要求复查，新独立token会话仍在ROM。两次均身份匹配，VTOR=0x1FFF0000，第二次PC采样0x1FFF36C8/36BC/36B2，DHCSR=0x01010001（未显示HALT），CFSR/HFSR=0。每次44 SDK调用，agent Halt/Reset/Go/Flash写均0，Close完成。没有新鲜完整Flash/options通过，不能把上次全片身份冒作本次实时读回。C49068未安装，新START0；这不是TIME修复复测结果。**

当前物理状态按最新完成事实：C J5供电、J-Link在C、B断电、C USB_UART断开；ESP仍在板供电，自主联网UNKNOWN。停止目标操作，不追加复位/Go或重刷。原先“仍供电、USB在C/J-Link在B”和等待转接的文字仅为下文较早过程记录，已由此更新。两份原件、动作计数和SHA见[ROM入场停止](../evidence/B5-C-REPAIR-R4/TIME-BOOTSTRAP-R2/actual-ROM-entry-stop.json)。

2026-10-29。**实装B40928/C49048，gen5不变；最近E-D在TIME停止，三窗仍NOT_PASS，TEMP/RR未运行。负责人明确仍供电，USB在C/J-Link在B；没有把旧全暗事实代作当前断电证据。方案A说明后，负责人新批准“修复完毕之后允许烧录”，但本次冷态转接完成事实尚未收到；目前没有新增连接、AT、Flash/sector3、复位或START。**

## 最近实板原件

C49048安装和独立C只读真实PASS，全片`81b1808f9936b02f115cef99a47059417eec99eb80dff4ca4cf1f103392588d7`；双全片/options、保护区、DISARMED及Close通过。中断前C只读和隔离云核验子进程其实均已完成；核对原进程/回执后继续，没有重复连接或重试。原件和本批910份现场文件SHA清单仅EFS。

E-D的计划C RESET/START各1。AT、Wi-Fi和SNTP命令接受，但**15次查询/28005ms/末次epoch122/valid0**；新鲜NTP、TLS、MQTT、T0、预热和评价均未开始。C STOP为tick32468、armed_at542、reason3、phase0，UNSYNCED/pending/live/cache均0。joint exit1为G3_C_NETWORK_STEP_FAILED；B exit1为主机G3_STOP_REQUESTED取消，close_resume和关闭后运行核验均true，不是B原生读取故障。云观察exit0、清理完成、测试发布0；旧背景消息不冒充本窗测量。TEMP/RR START均0。

详见[实际安装、只读和TIME回执](../evidence/B5-C-REPAIR-R4/TIME-BOOTSTRAP-R2/actual-C49048-install-RO-and-TIME.json)。C STOP/主机Close不证明ESP已断电或自主SNTP已停止。

## 归因和方案A

已证实的软件缺口：旧代码裸启用SNTP后，粗时间失败就提前退出，**位于其后的新鲜NTP安全轮换不可达**。历史真实选择回执`B5-ESP-NTP-SELECT-01/result.json`还记录`exact_G3_preserves_selected_primary=false`。那次选择本身仍没有有效UTC，不能说备用端点已被真实证明始终可达。C48988成功窗与最近C49048的transport相同，后者新增诊断空档尚未执行，不能将TIME归因于诊断出口调度。

默认首端点不可用、备用可用的合成输入，封存C49048真实transport/platform/UART组合仍在28067ms失败，反例已复现。**当前网络底层原因仍UNKNOWN**：没有本次AP/路由/公网双向包证据，不能认定DNS、UDP123、NAT、服务器或模块SNTP的具体故障，也不能从epoch122单独断言CPU/ESP复位。

修复采用负责人建议的方案A：

1. ESP内置SNTP建立模块系统时间，C主动48B新鲜NTP建立毫秒UTC；不发送SYSTIMESTAMP设置命令，不用PC/编译时间替代。
2. 读回并缓存至多3个现有端点；选择时携带完整列表，只轮换优先顺序，逐项核验启用、UTC时区及全部端点，新鲜NTP沿用成功端点。没有添加新地址，未将全部端点标为已验证可达。
3. 共享最多15次查询、2秒绝对时隙及总≤30秒SNTP准备预算，不是每端点30秒；预算不足不开始新AT。原60秒共同就绪仍覆盖TLS/MQTT，未就绪不评价。成功后保留完整列表及次序，不额外启用SNTP恢复默认，避免无价值的再授时触发。
4. 事前冻结两份UTC的一致性区间：ESP回复e、查询起止tq0/tq1、新鲜参考接收时刻tr，q=tq1-tq0≤2000ms、u=floor(rtt/2)+1ms、L=1000e+uint32(tr-tq1)。仅`L-u ≤ S ≤ L+1000+q+u`通过；按实际q/rtt，最大上偏3501ms、下偏501ms。成功打印TIME_MATCH实际差值和q；失配reason10拒绝TLS。整数模块读数不继承旧fraction。
5. nonce/完整48B/LI/mode/stratum/服务器时间关系、1000ms新鲜包、CA/CN/SNI、5000ms严格PUBACK、2048B、MOCK、原UTC/时效和420秒门均保留。nonce匹配不是加密认证，普通UDP授时不证明能防主动伪造。

[官方v2.3 CIPSNTPCFG](https://docs.espressif.com/projects/esp-at/en/release-v2.3.0.0_esp8266/AT_Command_Set/TCP-IP_AT_Commands.html#at-cipsntpcfg-query-set-the-time-zone-and-the-sntp-server)支持显式列表和读回；[SYSTIMESTAMP](https://docs.espressif.com/projects/esp-at/en/release-v2.3.0.0_esp8266/AT_Command_Set/Basic_AT_Commands.html#at-systimestamp-query-set-local-time-stamp)分别支持读、设模块时间。**当前ESP二进制实际TLS证书日期检查构建选项UNKNOWN**；不以AT版本或CA配置OK代替该证据，未刷写ESP。

## 软件结果和唯一新候选

真实组合链新增主端点失败/备用可用、配置读回错、停用ERROR、三端全坏、坏nonce、慢命令预算、ESP旧/未来10天但仍高于下界、3501/501ms边界及超界1ms、uptime回绕。受控备用场景6次查询/10191ms通过两类校验；三端全坏15次/≤30秒失败，旧/未来时间拒绝TLS。这里只证明软件处理这些输入正确，未证明当前真实网络已经恢复。

真实egress/coreMQTT/adapter/platform/UART、1.5/2.516秒停顿、FIFO/严格PUBACK/二进制解析/STOP及178项相关Python工具用例通过。低扰动诊断旧空档回放60/60条、最大5610/5937ms、温度300/遗漏0。隔离TLS旧EFS回放不冒充物理ESP或300秒实板PASS；失败构建和夹具修正原件均保留，不重复算法六窗/UI矩阵。

唯一新候选C49068B，BIN `b663e82b16c16d1d252ca38e0ceec5b172495a30f893e50c370e200a4777dead`，ELF `f6dbbb9a93327752ecdb844fd547812ca02f9be8cf630966871b0a5bbfb72b38`，双实际ARM构建一致，48KiB剩84B。ARM断言保留全部条件、文件/函数/行号及原fatal/IRQ停机路径，只省略handler本就不用的表达式文本，未关闭断言或修改vendor coreMQTT。

**预期，尚未实板完成**after全片`75db57c038c021b40f36fa1ee627f410d26061e18e0f59a8465c73af0216bc25`。精确包从实际C49048出发，候选长度后的旧应用尾部按原件保留；sector3/options/sector7/11和应用区外不变。回退仅新候选→C49048，离线逐字节重建通过，默认禁用，不回H3。中间48904B未安装草稿已被替代，原件EFS保留；草稿曾误按FF尾部算after，离线精确包核验发现并更正，错稿/禁用模板保留，没有据此写设备。

源码/工具/恢复包身份及RAM/栈见[TIME-BOOTSTRAP-R2冻结](../evidence/B5-C-REPAIR-R4/TIME-BOOTSTRAP-R2/candidate.json)和[资源](../evidence/B5-C-REPAIR-R4/TIME-BOOTSTRAP-R2/resources.json)。新运行水位NOT_RUN，静态单帧不当作总栈证明。

## 当前执行边界

[综合补包](AUTH-B5-C-REPAIR-R4-TIME-BOOTSTRAP-SUPPLEMENT.md)分开I/RO/L/E/T/R。负责人已允许修好后安装，私有事务仍需冻结当次现场完成事实；未收到冷态转接回报，不将J-Link在B当作C目标。每窗同候选、独立一次START、45秒预热＋300秒评价＋15秒尾段、420秒硬停，保留全部原数量/时效/INVALID和五层原件要求。失败不自动重发、复位、Go、恢复。

原测试云驻留截至北京时间2026-10-29 15:07；目前未重新远端核验，不冒称仍在线或已清理。L仅在两个原独立unit确实到期且配置/PID/权限/端口一致时各启动一次；正式云、ACL/Broker不改，测试账号未撤销。

CPU ROM、独立冷启动、同窗ECG/RR、绝对阻抗/温度标定及CAN故障注入维持独立遗留。旧C48988真实ECG300秒数据保留，其诊断不足NOT_PASS也不改写。

---

## 以下为本次前历史快照，其中“当前”仅指对应旧阶段

# 历史：真实ECG300秒完成，诊断证据不足；C49048待一次增补

2026-10-29。**当前实装B40928/C48988，gen5及全部算法/接线保持原状。负责人已确认全部断电熄灭。C49048仅离线冻结、尚未安装，新增Flash和START对象均禁用。三模式总判定NOT_PASS；TEMP/RR未运行，不把ECG通信数据通过冒充三窗结项。**

## 本次真实安装、云窗与停止

- TIME/CLOSE补包的C48988安装及独立C只读PASS。实际完整Flash `9799f39c731ce0dd33eba00749f945db1255a887939f88a924b6908405392873`；双全片/options，sector3和sector7/11及其他范围不变，DISARMED/Close通过，正常Halt/Reset/Go各1，实际下载1次。未回退C48888/C46584/H3。
- 先前身份比较不匹配的会话零Halt/下载/复位/Go，失败原件独立保留。旧工具未在拒绝前保存实际身份字节，因此不能独立认定那次读到B的UID。经负责人冷态纠正后，新会话C身份完全匹配才安装。安装器现先保存私有身份及差异字段再严格拒绝，未放宽检查；对应负例通过。
- 本次L真实核验正式PID/配置/ACL一致，两个原测试unit仍active，实际start=0、正式云写入=0、8884未开放；测试TLS/CONNECT/SUBACK/Backend/WSS就绪。测试账号仍存在，不能称环境已清理；原RuntimeMax驻留结束也不等于撤销账号。
- ECG窗START=1、计划C人工RESET=1；粗时间4次查询/6006ms有效，新鲜NTP RTT57ms、不确定度28ms，TLS和MQTT通过，建立共同T0后按45秒预热、300秒评价和15秒尾段完整保存。
- 源端业务恰420000ms停止；主机观察到STOP偏移420.063秒，reason=1、phase=CLOSED(7)、UNSYNCED=0、QoS1 pending=0。B、联合记录、云观察及监督器exit均0，Close续跑核验通过；这些是采集完整证据，不自动等于工程PASS。

## ECG真实数据及未通过项

| 检查 | 本窗结果 |
| --- | --- |
| B稳态保存 | 600条，HR全部60且有效；估算250.040 SPS，ADC错误/长间隔/削顶新增0 |
| ECG源点及五层映射 | 75012点、映射错误0，751个波形批在WSS观察到 |
| HR云端 | 300条、全部VALID且60 |
| Broker / Backend | 2838 / 2838，重复0、拒绝0、丢弃0 |
| WSS正式评价 | 2974份；同会话、值、来源及INVALID语义通过对应原审查 |
| 最大MQTT JSON | 849B，未越2048B限制 |
| C已保存累计错误 | txfail/overflow/uart_err/dropped/mqtt_fail均未新增，CAN ESR=0 |
| C主诊断 | **19条，低于58；最大间隔18.375秒，高于8秒** |
| 队列取证 | **数量不足58**；不能用稀疏的0计数冒充完整取证 |
| 真实RAM/调度记录 | C48988 stack_used_upper=2748，service gap最大23ms、console最大24ms、RX高水位25；只属于该实装候选 |

总判定为 `B5_SEPARATE_ECG60_NOT_PASS`，离线综合review exit=3；失败原因 `CHANNEL_C_DIAGNOSTICS / C_DIAGNOSTIC_GAP / C_EGRESS_QUEUE_EVIDENCE`。原review因主诊断不足抛异常的exit=1、工具和原件也保存。主机review仅改为保留这一失败并继续产出剩余指标，58条、8秒及队列58条门槛未变。

温度模块在本窗真实收到1372个新帧、UART/校验新增错误0，但未做专用温度窗口，不能签TEMP云验收PASS。RR专窗也未消费START。原码、全片、身份和配置仅EFS；公共脱敏计数及原件SHA见 [实装及ECG结果](../evidence/B5-C-REPAIR-R4/TIME-CLOSE-R1/actual-install-and-ECG60-result.json)。

## 已复现的取证调度原因与最小修复

旧`network_main.c`把主诊断、队列及其他细项串在23阶段轮转中，只有QoS1/deferred为空且AT同步的业务空档才能前进，不能保证主诊断每5秒出现。另一个独立时序问题是温度入口用“距上次打印满1秒”限速，等待时间累积后追踪队列落后；本窗末尾`temp_trace_lost=82`，这不是已证明的CAN或MQTT温度数据丢失，却会破坏后续温度源点取证。

新候选只改变上述一个编译输入：

1. 主诊断与队列按固定5秒时隙优先，各空档最多输出一行；错过的旧时隙跳过，不生成伪历史记录。
2. 温度入口按原8项队列中的待记录项逐行清退，不再叠加漂移的一秒打印门；不扩大队列、不清零历史丢失计数。
3. 保持避开在途QoS1、deferred、AT不同步及控制台重入，其他细项继续分阶段输出。不改传输、UTC、TLS、FIFO、严格PUBACK、算法、配置或原验收标准。

编译真实`network_main.c`，使用本窗851个已观察输出空档回放，旧源复现19条主诊断/18条队列及入口积压；新源得到60/60条、最大间隔5610/5937ms、合成温度300条/遗漏0。该夹具保留相对时序，温度生产者是明确的每秒一项合成输入，不冒充实际温度原码或新候选实板结果。正常、计数回绕、2.516秒阻塞也通过。

69项真实AT/coreMQTT/adapter/platform/UART组合与诊断用例、136项相关Python工具回归、ARM双构建一致性通过。本地隔离TLS旧EFS回放Broker=Backend=2816、拒绝/丢弃0，WSS2298份加速快照、温度入口408/遗漏0、队列高水位18，本地资源已关闭；这些不替代真实300秒及WSS≥2900验收。

## 唯一待批新C49048及精确回退

- BIN `dedca0f4b0de6fb5d00e8e339020f982093e0e4509732a71c77e9c2edf2032bd`。
- ELF `1842e111adac0e421a68e37f076abf79c308819c59b3e56d6b2aeb67ac37e52e`。
- 91输入源码清单 `4a5d8d4b640138f0d782bf85e20d3360743330aaf3e5e05c771932021f83e749`；与实装C48988相比，仅`network_main.c`变化。
- **预期、尚未实板完成**的新全片 `81b1808f9936b02f115cef99a47059417eec99eb80dff4ca4cf1f103392588d7`。
- 安装包manifest `14a759504d12e7b827d9b464be504c9ed6d14ebcb57afe1b6a9a802a393c3866`；绑定 `c2e28aefab0a8256006c8fb6f80b7704fbe80da89ce9e1d4ea6d4d28485be40d`。
- 应用余104B，data92/BSS73976，堆24576、栈保留8192、额外间隔24232，最大单函数静态帧1096。新C49048运行栈水位NOT_RUN，不套用旧C48988的2748。
- 安装/恢复严格绑定实装C48988完整原件，sector0/1/2内写；离线重组精确回退通过，sector3/options/sector7/11保持原件。恢复默认禁用，未经对象批准不执行。

所有冻结身份、资源和回归见 [DIAGNOSTICS-R1](../evidence/B5-C-REPAIR-R4/DIAGNOSTICS-R1/candidate.json)。新候选模板中的未执行/未验收末态与当前旧候选断电事实分开，当前现场事实另列`current-site-and-actual-state.json`。

## 下一次唯一确认点与遗留项

[诊断调度综合补包](AUTH-B5-C-REPAIR-R4-DIAGNOSTICS-SUPPLEMENT.md)一次申请：新C49048应用安装一次≤180秒、独立C只读一次、原隔离云就绪、同一新候选ECG60/非人体物表TEMP/RR15各一次300秒和420秒硬停，ESP在板供电例外；sector3不写。原C48988的安装与ECG START已消费，依据PI R4第7节，不能重用旧许可写新字节或重发ECG START。正常门禁通过后不逐小步骤重新批准。

当前保持实板断电，无后续连接、AT、Flash或START；未恢复旧应用、未写配置、未改正式云。CPU ROM根因、独立冷启动、同窗ECG/RR、阻抗/温度绝对标定及CAN故障注入继续原风险状态。只有同一候选三窗和安全末态全部符合，才可签三模式工程结项。

---

## 以下为此前TIME/CLOSE离线冻结及历史现场快照，已由上文更新

# R4当前综合状态：TIME / 主动关闭修复待批

2026-10-29现场进展：**B40928/C48888为实际部署；新48988B为离线冻结候选，尚未安装。ECG两次START均未进入300秒，TEMP/RR未运行；三模式仍NOT_PASS。负责人已回报“全部断电”。** 以下更新为当前交接，后附S2冻结时历史快照。

## 实板已完成与失败归因

- I安装及独立C只读均PASS：实际全片 `6d3eee3ed63f6256ff34b415cd3edc04cfdebcd37eec108dba833105bda2dcb8`；新鲜双全片/options，Halt/正常Reset/Go各1，sector3/7/11/options和应用区外字节不变，DISARMED/正常运行及Close通过。未恢复C46584/H3/C24104。
- L真实只读和TLS/CONNECT/SUBACK/WSS就绪通过；原两个独立unit仍active，无需start，启动次数0；正式PID、配置/ACL均匹配，8884未开放。账号未撤销，不称环境已清理。
- E1：SNTP_ENABLE成功，15次查询15075ms仍无满足门槛UTC，TIME失败。未新鲜NTP/TLS/MQTT，未T0。
- E2：负责人额外批准同48888B复验一次。粗TIME此次1次/6ms有效，故第一次TIME结果未在复验中重复，不能据两次计算偶发率或认定永久故障。随后48B NTP写48、SEND OK已确认，但1000ms内无网络回复；其原因仍UNKNOWN。
- E2关闭UDP时，合法主动CIPCLOSE的中间CLOSED被本轮通用URC分支误判为意外关闭，UNSYNCED后阻断安全端点轮换。**这是Codex本轮解析修改的回归，已在实际platform/AT组合链复现，不归咎硬件。** 这也不证明它造成了此前854B故障，或解释了UDP本身为何零回复。
- 两次均无B测量MQTT发布、无T0/300秒；TEMP/RR各0次。两份观察器末尾均完整落盘、健康查询/断开原因及STOP保存。B退出码1为G3_STOP_REQUESTED主机取消，均核验正常Flash运行后Close并启用续跑，不能写成B原生故障。
- 失败被动尾段实测约5秒，包含一笔串口read完成余量；没有跨原440秒被动上界。新主机代码将read超时收窄到剩余尾段并记入API时序，保留既有445秒监督上界。

## 已完成的最小后续修复

仅两个编译输入改变：`platform.c` 为CIPCLOSE记录预期关闭上下文，只有此命令的CLOSED可继续等OK；没有OK仍失败，发送阶段意外CLOSED/ready/busy仍UNSYNCED。`gateway_transport.c` 保持15次查询，改为绝对2秒时隙的≤约30秒粗授时准备并记录末次epoch，原60秒共同就绪不变。

新真实组合用例先用实装48888源码复现预期CLOSED误判、以及“合成19秒才就绪却在15次快速查询后先失败”。修正源验证：CLOSED→OK通过/CLOSED无OK失败；实际fresh_sntp零回复→安全关闭→新nonce轮换→严格样本验证通过；合成19秒就绪在20173ms通过，计数回绕也通过；持续无时间在28067ms失败。**19秒是合成输入，不是本次ESP实际同步时刻。** FIFO/全部流压力、1.5/2.516秒停顿、二进制解析、发送准入、PUBACK和420秒门回归仍通过。

本地隔离TLS旧EFS回放重新通过：Broker=Backend=2816，拒收/丢弃0，WSS2416份加速快照、无新增错误STALE，源值/序列/UTC一致；不是实板300秒或WSS≥2900通过。本地自建资源已关闭。

## 唯一待批候选48988B

- BIN `7bf11c191c785cc8529be8b26fb83ce429d330a8238175f44add53384c8b4daa`。
- ELF `be4c0e937be6fc75c44cf146bae9569763fac6f7d08ed42b721e40adc48b8f9d`。
- 源清单 `7116cf2c6f84641830d21e7164efe440b4125762fe93b42c06b77b0a17171db2`；双构建BIN/ELF一致。
- **预期**新全片 `9799f39c731ce0dd33eba00749f945db1255a887939f88a924b6908405392873`，不是已完成实板结果。
- 安装包manifest `d1624533b1ebb984e114023989313d97b42736dc96fb5887fc94a733636990fa`；绑定 `a62f031a9f8be53b4bad403e5ae7baea0b487ce8c78d61f2803c44d905505076`。
- 应用剩164B；data92/BSS73976，堆24576、栈保留8192、额外间隔24232；最大单函数静态帧1096，不冒充总栈证明。旧48888启动短窗观测stack upper2240，新48988实板水位NOT_RUN。
- 精确安装/回退以**实际I读回的C48888**为before，离线逐字节恢复该全片已核验；sector3/options/保护区不变，不套用C46584或H3恢复。

证据和工具绑定：`node-b/evidence/B5-C-REPAIR-R4/TIME-CLOSE-R1/`；当前全片、UID、配置及原码仅EFS。新包尚未启用。

## 唯一综合增补确认点

见 [TIME/CLOSE综合增补](AUTH-B5-C-REPAIR-R4-TIME-CLOSE-SUPPLEMENT.md)：I-TC一次应用安装/独立只读/L就绪；随后同48988候选E/T/R各一次45秒预热＋300秒评价＋15秒尾段，420秒硬停，ESP在板例外，其余原判据不变。原I及两次E的token已消费，**不能把旧许可重用于不同字节的Flash和第三次START**；依据PI R4第7节一次集中申请新增对象，之后正常流程不逐步再批。

当前安全末态为负责人报告全部断电，无后续目标连接或AT操作。CPU ROM、同窗ECG/RR、阻抗/温度绝对标定、CAN故障注入继续原样登记。等待本次确定字节增补批准后才冷态转接C。

---

## 以下为首版48888候选S2冻结时快照

# B5 C修复R4唯一交接

2026-10-29，S0–S2候选冻结里程碑。**软件准出PASS；新候选尚未安装，三窗未执行，B5三模式结论NOT_PASS。** 实板批准与完成事实分开记账，后续仍在本报告更新。

执行起点：`codex/node-b5-cloud-integration-20261026@6835d8646e7b52464a6ad2188b88b916241068be`；开工fetch核对远端一致，原工作区干净。未修改B、算法、ADS/GY配置、CANopen、coreMQTT、gen5、保护分支或正式云环境。

## S0：实装、失败与源码归因

- B40928部署不变；C最后读回仍46584B，全片 `707d88987431cb4cdf4580d8f627ba58eea4980429d95fc6dcde6ceb8718ca4a`。47120B仅未安装的R3诊断候选。
- C46584的91份真实构建输入全部按归档SHA核对。与6835d86 Git字节比较有16处差异，其中13处仅CRLF/LF归一化；实际内容差异是 `esp_io_metrics.h`、`gateway_transport.c`、`platform.c` 三处R3诊断扩展。不能把换行差异说成CAN协议变更。
- 历史ECG在START后53.919秒STOP，T0为16.375秒，仅预热37.544秒，**300秒评价未开始**；TEMP/RR未运行。
- 854B包全部写出，但SEND OK未确认、UNSYNCED、仍有pending。最后4091ms不是5000ms原生超时的证明。该包的QoS/stream/seq、pending ID/起始年龄、传入预算、提示/数据/终态原时刻缺失，继续UNKNOWN。
- Broker原件264条与Backend增量267的覆盖不齐：不能推断丢3条，也不能宣称267条全部逐层匹配。原观察线程未完成最终回执，最后保存云原件约在START后48.75秒，早于C STOP约5秒；原件和未知状态均保留。

证据：`S0-failure-mechanism.json`、`historical-failure-original-reference.json`、`source-alignment.json`、`source-line-ending-audit.json`，均在本报告对应的 `node-b/evidence/B5-C-REPAIR-R4/`。私有原始UART、B采样、全片/options、配置、UID、观察回执仅保留EFS。

## F1–F6处置

| 发现 | 改动与验证 | 边界 |
| --- | --- | --- |
| F1 短轮询进入秒级AT等待 | 接收拆为持久available/data命令发送与回复推进；1/5/50/200/1000ms切片保留唯一owner、部分命令及解析上下文，不重发查询。命令本身仍有1000ms截止。 | 不是把AT超时一律降为5ms；未知/超时仍UNSYNCED。 |
| F2 剩余PUBACK预算不足仍发送 | Router出队前准入，序列化后再以真实包长核对；覆盖8N1线时、提示/终态预算和接收余量。不准入返回DEFERRED，无发送/ACK/REPLAY/丢弃；序列化期间预算变化时，原准备帧保留至后续准入。ACK接收先推进。 | 5000ms从原起点计算；reserve是准入保护，不是ESP成功时延保证。 |
| F3 二进制终态误判 | 同一解析器先验证长度头，精确消费二进制后才接受末尾OK；NUL/OK/ERROR/FAIL/>/URC字节不触发控制状态。非法长度/头模式拒绝，CLOSED/ready/busy单独分类。 | SEND OK仍不等于Broker收包；未知边界不CIPCLOSE。 |
| F4 日志侵入 | 周期长串诊断移出service/发送/PUBACK关键阶段；主循环空闲每次至多一行。RAM保留事务上下文、最近4个阶段、服务间隔/console耗时/RX高水位，停止后再输出。 | 现场原失败是否由日志导致仍未证实；新C运行水位尚未测量。 |
| F5 组合覆盖缺口 | 新增真实egress/coreMQTT/adapter/platform/UART-MMIO组合链，覆盖ACK等待、QoS0、keepalive、慢AT、854B/2048B、停顿与STOP。 | 本地TLS回放作为独立层，绝不冒充ESP收发验证。 |
| F6 TIME/观察器 | 检查SNTP启用返回，记录15次查询实际elapsed而不承诺固定等待19秒；保留安全端点轮换。观察器在CONNECT/SUBACK及真实WSS鉴权快照之后冻结基线；失败后限时被动收尾，健康查询和客户端关闭有总限，完整排空回调与落盘，挂起标UNKNOWN。 | 新鲜NTP1000ms、共同就绪60秒、PUBACK5000ms、2048B、420秒及TLS验证不变。未主动连接云端或发送新START。 |

## 反例与离线证据

调用真实C46584 `platform.c` 的MMIO反例：5ms请求耗258ms；含OK的70B回复读到46B就提前成功、含ERROR读到49B即错误失败。50ms预算发送854B时，实际写出48个串口字节，其中数据仅32B，留下不完整事务。以上是合成时钟复现，不是对现场854B事务的反推。

修正版：5ms返回≤5ms，含OK/ERROR/ready/>/NUL的回复完整消费；854B/50ms事前拒绝，UART写0。真实组合链通过：正常/回绕、ACK正确/错误/缺失/迟到/重复、ACK在QoS0期间到达、在途年龄900/4500/4950/4999ms、保活不误用5ms发送预算、已知接收owner有界结束后关闭、854B及2048B定长发送、SEND FAIL/静默/CLOSED/ready/busy及命令/提示/数据/SEND OK各阶段停止。

组合300秒压力使用全部B流，注入1500/1500/2516ms终态交付停顿：实时高水位15/24、QoS0 1066笔、严格QoS1确认1032笔，源龄峰值2260ms，新增覆盖/溢出/过期/历史/丢弃均0。原容量对照仍保留：旧16/64路径9条历史替代、HR最大8516ms；单扩容量对照也能通过部分场景，不能把收益全归为异步调度。

本地隔离TLS回放：历史遥测2654条，加新受控5秒状态夹具，Broker=Backend=2816，拒收/丢弃0，WSS2053份加速快照，无新增错误STALE；原源值/序列/UTC一致，温度入口408条、trace丢失0，实时高水位18。**2053不是实板要求的2900份，也不是300秒现场PASS。** 本地自建资源已关闭，正式云操作0。

安装/状态/三profile/映射/STOP/联合监督/观察收尾定向Python回归128项通过；真实退出和每个日志SHA见 `tool-regression.json`。既有原始失败未回写，开发中失败目录保留在忽略build；没有重跑算法六窗或UI矩阵。

复现入口（仓库根目录，现有工具链，不访问设备）：

```powershell
python -X utf8 node-b/tools/run_b5_repair_r4.py
python -X utf8 node-b/tools/run_b5_egress_final.py
python -X utf8 node-b/tools/run_b5_egress_tls.py
python -X utf8 gateway/dual_can/build_arm.py --b5 --egress-final
```

## 唯一R4字节资产和资源

| 项 | 冻结值 |
| --- | --- |
| C BIN | 48888B；`a4531973a377884039ceb5f2ec1187bb9a1c2ac79b091d24457f089c5890dfcf` |
| ELF | `bbe6ef833609fc0a3866d94f793494f3184d8ad4555ea0d17e88b228a308b3e7` |
| 91份源码/头规范化路径清单SHA | `4e549afe8c55f8a87506f722b710d62de3380fbfdc9513207905dc2b52ff099e` |
| 符号 | `92c4d3ba2e68c8c0b4d5593ace46c6ebdb0506c51a2a15e4d9aa595d37dff1bf` |
| 预期安装后全片（非实板结果） | `6d3eee3ed63f6256ff34b415cd3edc04cfdebcd37eec108dba833105bda2dcb8` |
| 包manifest | `af1ca4e31407299b4bdc7fbd0efcb8566717072476c7480da5394c33b16d08bb` |
| 应用绑定 | `80076ecc23ee5984cb7d4dd17c86c070afd59e9bed7615be15e958cd60dd4b41` |
| 原options | `52d5979da03bd7be45e385920ec7d5901793bab3f6bc1daa0c1c1997f9e91687` |
| 新四状态地址 | `0x20001E6A`至`0x20001E6D`（mqtt_connected/network_open/stopped/armed） |

源码实现提交：`fe164b0e2e58e21e52aa48d0e3454044f21d9098`（构建输入逐字节另按上述清单封存）。

两次ARM构建BIN/ELF完全一致；MAP、编译参数、GNU14.2、实际宏、符号、原始日志和所有编译输入按SHA归档EFS。应用止于sector2内，剩264B，不能再随意加诊断或越界。`.data=92B`、普通`.bss=73972B`，另有24576B堆和8192B保留栈，堆顶到保留栈下还有24232B间隔。最大已编译单函数静态帧1096B，**不是传递调用总栈证明**；新候选实板stack high-water为NOT_RUN，须在现场记录RAM行。IRQ、网络与采集不使用新动态分配。

精确回退离线拼接已验证：只恢复sector0/1/2即可逐字节恢复C46584全片；新BIN之外采用旧原件，sector3/7/11和options不变。备份/离线拼接不等于实际恢复演练。原C43036/C46456/C46584/R3候选和历史失败均保留。

## S3批量包与当前准入

唯一现场包：[AUTH-B5-C-REPAIR-R4-BATCH.md](AUTH-B5-C-REPAIR-R4-BATCH.md)。I安装、I-RO、L测试服务、E/T/R各自独立scope/token/目录，恢复对象默认禁用。7份私有模板全部 `enabled=false/owner_approved=false`；安装回执、独立只读、现场事实和云驻留是待补真实门禁，未伪填PASS。工具绑定与模板SHA见 `object-bindings.json`。

负责人最新要求离线结束后进入实板，且明确J-Link在B、USB在C、两板已供电、接法不变。按R4合同，现一次申请对上述**确定字节候选及I/L/E/T/R包**的现场确认；随后集中冷态转接C，I/I-RO/L通过后回接B并连续推进三窗。ESP在板供电非隔离例外须纳入本批确认，不反复索取已有型号/历史SHA。

每窗45秒预热＋300秒评价＋15秒尾段，≤60秒T0、420秒源硬停；ECG≥74250点/HR58–62有效≥295、TEMP≥295且原2500ms/2ms映射、RR≥14850点/RR14–16有效≥295、WSS≥2900。retain/Will和计数范围单独核账，不关闭非目标流。一个已START窗口失败不自动消耗下一对象；目标危险停止，离线研究继续。

目前实际R4安装0、新实板连接0、B5START0、测试服务启动0、Flash/sector3写0、正式云改动0；ECG本轮历史NOT_PASS、TEMP/RR未执行。当前不能签三路E2E或B→C阶段关闭。

## 末态与遗留

- 物理末态：负责人报告两板供电，**全暗未确认**；本软件阶段未连接或改变设备。下一操作必须是获批包内的安全停机/冷态准备。
- 云端末态：本阶段未新鲜查询；独立unit可能到期，账号/ACL未撤销。不能称环境已清理，L只允许严格匹配到期条件后各start≤1。
- CPU ROM根因UNRESOLVED；当前候选独立冷启动、同窗ECG/RR、绝对阻抗/温度标定、CAN故障注入及长时可靠性均未补签PASS。
- 原始854B现场唯一根因仍未锁定；本轮已实证并修复可达代码缺陷，最终收益等待同一候选三窗实板验证，不用软件回放代替。

S2交付只向原独立B5分支正常提交/推送/独立远端回读。无保护分支合并、PR、标签移动或Security Gate。远端回读完成信息随本次交付记录，现场阶段继续更新本文件，不另造多个“最终”报告。
