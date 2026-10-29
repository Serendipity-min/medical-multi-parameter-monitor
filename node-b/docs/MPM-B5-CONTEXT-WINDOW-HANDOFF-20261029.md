# MPM-B5｜上下文窗口交接合同（2026-10-29）

> 用途：将当前长会话移交给新窗口，保留接线、实装身份、真实结果、失败和授权边界。本文件是交接记录，不新增上电、连接、复位、Go、Flash、sector3、云服务或 B5START 权限。
>
> 当前结论：**C49132 同候选追加 ECG60 窗口通过 B→C→Broker→Backend→WSS 的300秒工程评价；首窗失败保留。独立物表 TEMP 和 RR15 云端窗口尚未完成，B5 三模式最终结项未完成。两板已由负责人确认全部断电。**

## 1. 接手位置与阅读顺序

| 项目 | 唯一当前基线 |
| --- | --- |
| 仓库 | `Serendipity-min/medical-multi-parameter-monitor` |
| 独立工作区 | `E:/medical-monitor-node-b5-cloud` |
| 实验分支 | `codex/node-b5-cloud-integration-20261026` |
| 本文件写入前 HEAD | `3944e21ee31f81a31c1c39666079f423cb2a1de0` |
| C49132 实现提交 | `29e6a773dcd65ccd7b63507188067baa6fe9f71e` |
| 原始项目目录 | `E:/多参数心电监护仪系统-样机开发`；不要因默认 cwd 在此就修改该处保护分支 |
| 当前日期/时区 | 2026-10-29，Asia/Shanghai |

先读工作区根 `AGENTS.md`，再读本文件及 [唯一业务交接报告](B5-C-REPAIR-R4-FINAL-HANDOFF.md) **顶部“最新实板交接：C49132的ECG60追加复验PASS，首窗失败保留”**。后者包含多轮历史快照，下方旧“当前”“待安装”“NOT_PASS”不能覆盖顶部最新状态。

接着阅读 [双窗对照](../evidence/B5-C-REPAIR-R4/TIME-INIT-R1/two-ECG-window-comparison.json)、[首窗联评](../evidence/B5-C-REPAIR-R4/TIME-INIT-R1/actual-C49132-ECG-review.json)、[追加窗联评](../evidence/B5-C-REPAIR-R4/TIME-INIT-R1/actual-C49132-owner-retest-ECG-review.json)。本轮已有独立远端取回及六份文件 SHA 核验，记录在忽略目录 `node-b/build/ECG-retest-final-remote-check.json`；新窗口先查本地 Git 状态，不必为接手重跑现场或既有软件矩阵。

冻结时 `candidate.json` 的 NOT_RUN 是采前快照；实际安装/验收以随后真实回执为准。审批卡文字和历史 PASS 都不是新一次许可。

## 2. 最后确认的物理状态

负责人在追加复验正常 STOP、串口/调试/采集会话关闭后明确回复“**全部断电熄灭**”：B/C J5关闭，C USB及 J-Link 电脑端 USB 已拔，板、ADS、两屏、ESP全暗。没有再上电、复位或读取目标。此次停机不是冷启动实验。

- JTAG 板端最后在 **B**；电脑端 USB 已断开。C 的 USB_UART 已断开，末次端口 **COM6**，不是旧 COM15。新枚举可能变化，不假设仍在线。
- CAN、独立参考地、BOOT、温度和导联按原接法保留；ESP-01S仍装C板，当前随板断电。
- 模拟器最后使用普通 ECG60/1.0mV、电池供电、充电USB断开。停机指令没有要求关闭 SKX，故**此刻模拟器自身是否仍开机未知**，不要补写。
- A段、INMP441、TTS/喇叭模块及人体均未接入。无其他目标会话占用是上轮结束事实，不是下一次现场的永久保证。

接手阶段只离线阅读，不自行恢复供电或启动服务。后续确需操作时，一次告知负责人完整步骤；不要反复询问已确认的 MCU/J-Link 型号、资料包或历史 SHA。

## 3. 实装固件、源码与恢复身份

### 3.1 Node-B：B40928B

已安装真实 GY-641V3 接收扩展；BIO_V2、ADC寄存器和阈值保持原值。

| 身份 | SHA256 |
| --- | --- |
| 40928B BIN | `a1cf57648ca3787de30c1ad7055634c278fbbde538bb0bc562961bd212182ed2` |
| 安装回执完整1MiB Flash | `ceebec5a91835aed3cb70c683fd8de5142e5ba59a2163a1968cec182018b48ae` |

BIN来源见 `node-b/evidence/B5-SEPARATE-CHANNELS-20261028/install-results.json`；私有全片/options由当前窗口绑定的 `B_install_receipt` 定位。B39948和旧25284等均为历史版本，不得再当作当前硬件部署候选。

### 3.2 Gateway-C：C49132B + gen5

| 身份 | 冻结值 |
| --- | --- |
| BIN字节数 | 49132 |
| BIN SHA256 | `72131dbb5ef6bc0e0d33e328925c685403bae928aea9447a81f8291c6ae5c1ab` |
| ELF SHA256 | `10051aa990cff78882d94870ad99509011f140439d01e76aa0e47f2bcfc44b0b` |
| 实际完整1MiB Flash | `9bba23b436f079183296fa98dcaeed047eb919ba8597d75a85bc144bc48417fd` |
| 91份真实编译输入清单SHA | `84ea9a8699c5915ec2b5846374c04cf4fd845d2b0a4b17287143a2aa4643639e` |

一次应用安装及独立只读实测 PASS，双完整Flash/options、身份/保护区、DISARMED、Close均通过。gen5 sector3未改变；未自动恢复C49068、C24104或原H3。

资源：48KiB应用区仅余 **20B**；`.bss=74180B`、`.data=92B`，保留栈8192B，最新实窗栈水位上界最大2700B。不能为加日志随意扩扇区或宣称全部未来栈路径安全。双ARM构建一致，相关真实AT组合89条步骤及实际121项工具测试通过；命中0项的筛选器未计通过数。

安装只涉及 sector0/1/2（0x08000000–0x0800BFFF）；sector3（0x0800C000–0x0800FFFF）、options、sector7（0x08060000–0x0807FFFF）、sector11（0x080E0000–0x080FFFFF）独立保护。应用候选尾部按精确包保留，不自行把余区全部填FF。C49132→C49068精确应用回退包已离线验证，**未实际执行**。原H3/C24104及各代完整恢复原件仍保留；不能拿“有备份”代替“本次恢复已演练”。

## 4. 接线总表：保留现状，不据此自动改线

A/B/C均为STM32F407ZGT6、1MiB同类开发板，**私有UID不同**。型号相同不能证明目标身份；安装前必须绑定正确板卡。C温度/ECG屏、ESP、CAN接头命名容易混淆，必须分板解释。

### 4.1 电源、调试、USB

| 部位 | 已知接法/限制 |
| --- | --- |
| B/C运行供电 | 各用原J5；历史适配器铭牌12V DC/1A、中心正。两板5V/12V输出不互并 |
| J-Link | 原板载JTAG标记接口接调试排线；不以J-Link给目标供电，VTref是电平参考。历史SDK通常SWD/1000kHz，以冻结工具为准 |
| C串口 | USB_UART/USB232（CH340），115200、8N1；**不要插USB_SLAVE** |
| BOOT | B0/BOOT0、B1/BOOT1最后报告接GND；静态跳帽/电压不能证明复位瞬间锁存 |
| 冷态转接 | 关闭两板J5、拔C USB和J-Link电脑USB，全暗10秒后才动整只排线；避免反供电/热转接 |

开发板J5是供电，**屏背J5是RS232/TTL选择**，两者不是同一对象。C串口连接不授权USB下载；J-Link所在板必须以实物事实和私有身份共同确定。

### 4.2 B CAN1 ↔ C CAN2，500kbps

| 部位 | 已完成接法 |
| --- | --- |
| B P6 | CAN_RX↔PA11、CAN_TX↔PA12；D-/D+未连接 |
| C P4 | CAN2_RX↔PB12、CAN2_TX↔PB13；**不是RX↔TX或PB12↔PB13** |
| 外部差分线 | B CAN1_H↔C CAN2_H，B CAN1_L↔C CAN2_L，H/L不交叉 |
| 参考地 | B明确GND↔C明确GND，独立一根；不借用RLD/模拟器导联 |
| 终端 | 两端各120Ω；历史断电并联实测60.8Ω，非今日重新测量 |
| A段 | 未来A CAN1↔C CAN1独立500kbps、两端120Ω；当前物理断开，不把两段H/L并联 |

板图为TJA1050/5V，B CAN1 U3、C CAN2 U2，参考两针座2=H/1=L，实物以丝印为准。逻辑PB12/PB13不能直接充当CAN H/L。业务Node-ID A=1、B=2、C=3，旧B的3/1Mbps/单PDO方案已过时。CAN2依赖CAN1共享时钟、过滤器分界14已软件验证，不重写驱动。

C PB12/PB13与I²S2/INMP441及板载音频资源冲突；当前未接INMP441/TTS且不启用音频，不推断板载WM8978已经电气隔离。

### 4.3 B ADS1292R、温度与模拟器

实际ADS模块丝印 **ADS1292_V2.0**，资料包目录V4.1不等于实板版本。实板只有J1/J2，J1空、J2接开发板5V/GND，曾确认模块灯亮；不要按另一张图反复寻找J3或移动不存在的跳帽。

| B引脚 | ADS信号 |
| --- | --- |
| PA0 | PW / PWDN-RESET |
| **PG15** | START，负责人已确认；不是历史PA1 |
| PA2 | CS |
| PA3 | DR/DRDY，EXTI3，负责人已确认 |
| PA5 / PA7 / PA6 | SCLK / DIN(MOSI) / DOUT(MISO) |
| 5V / GND | J2供电及公共参考 |

引脚表结合冻结源码/板图；START、DRDY及电源有负责人现场确认，不冒称全部导线新测通。ADC250SPS；CH1为阻抗呼吸、CH2为ECG。CH1SET/CH2SET=0x40，gain4；Vref2.42V仅名义值，gain6错误换算已修正，未修改寄存器/阈值。

**三合一导联的模块F与模拟器F不是同一个含义：**

| 导联 | 普通ECG接法（最后状态） | 独立RESP接法（后续须冷态批准切换） |
| --- | --- | --- |
| 红R | RA/R | RA/R |
| 黄L | LA/L | LL/F |
| 绿F（模块RLD） | RL/N | RL/N |
| 空置 | LL/F及胸导 | LA及胸导 |

不短接LL/RL，不把主动RLD接地，不接人体，不仅按IEC颜色猜映射。ECG和RESP分别成功的不同路径不能合成同窗双有效。

SKX-2000D+：最后普通ECG60bpm、1.0mV、电池、充电USB断开；独立RR历史设置15bpm/1.5R/波形周期30bpm/窒息0s。E3六窗曾用波形周期20bpm，与后来的30bpm不要混用；“波形周期”与呼吸率是不同菜单字段。未标定的1.5R不能写成1.5Ω或把ADC codes当Ω。

**GY-641V3：** VCC→B3v3、GND共地、RC→PC10、TD→PC11。当前驱动UART4 **9600、仅PC11接收**；PC10保持输入，不启用发送器、不写模块配置。曾15秒取得69个新有效帧，最新ECG云窗还观察到温度300条VALID。没有合格非人体参考源，数量是非人体物表工程值，不是已校准核心体温。

### 4.4 屏幕与C ESP：特别容易接错的路径

- 两块B屏为同类大彩屏，照片型号`DC80480DN050_1111_0C`；供电使用5V/GND，背J5丝印OFF=RS232、ON=TTL。不要未经许可焊J5或把RS232直接接MCU。
- B心率/呼吸屏DOUT→232RX、DIN→232TX，经板载SP3232；**P3原跳帽已取下，COM1_T→PA10、COM1_R→PA9；P7的PA9/RXD、PA10/TXD两帽均取下**。这是负责人实际接法，不凭T/R名字反向猜接。固件USART1 PA9TX/PA10RX，115200。
- 旧P3 COM1_T→PD2、COM1_R→PD6未接到候选输出，曾导致“无波形”；修路由后波形恢复。屏静止不等于CPU ROM。
- 温度屏历史DOUT→J4 R2IN、DIN→T2OUT、5V/GND；B P5曾报告PB11_RX↔COM2_T、PB10_TX↔COM2_R。此为历史观察路径，非本次新通断；不要为了云端温度输入自动改屏路由。
- **C P5**用于ESP：PB10_TX↔WB_RX/GBC_RX、PB11_RX↔WB_TX/GBC_TX，**不是COM2_R/T**。与B P5温度屏路径分板记录。
- C ESP-01S为最后复位/重插后恢复工作的模块，USART3 PB10/11、115200；最新AT报告2.3.0.0，未刷写ESP。曾有备用模块对照，不凭“新/旧”记忆判硬件好坏。
- B P7去帽不能复制到C；C USB_UART在真实窗口已正常使用。C P4是CAN2，P5是ESP，不混淆。

原始资料路径：`E:/stm32/stm32文件`；项目`doc/B/操作手册.pdf`、`doc/B/SKX2000D+说明书.pdf`、`doc/B/ADS1292R模块资料V4.1 - 副本`及`M系列串口屏开发包V3.2`。厂家算法示例只供参考，实际使用本项目BIO_V2，不替换已验收算法。

## 5. 项目进度与判定边界

| 专项 | 当前真实结果 |
| --- | --- |
| B0/B1、BIO_V2离线审查 | 历史PASS，不重做 |
| 独立ECG/HR | 60/90/120 BPM各两轮实物PASS |
| 独立RESP/RR | 12/18/24次分各两轮PASS；206025帧、稳态保存681/681有效 |
| B4正常CAN传输 | 独立ECG60及独立RR15经B CAN1→C CAN2通过冻结工程范围；非同时双有效 |
| B5-0～2 | Host/ARM、本地TLS、数据模型和七页UI等预检PASS，不重开发 |
| G1/G2 | 独立MOCK云测试、新鲜全片/options双备份、应用安装、MEM-AP SDK/DAP交叉及真实配置写入均已有PASS |
| 屏重启修复 | `SCREEN_RESET_MCU_RESET_FIX_PASS`；不等于CPU ROM根因关闭 |
| C49132 ECG60 | 首窗NOT_PASS；负责人独立追加复验 `B5_SEPARATE_ECG60_ENGINEERING_PASS` |
| C49132独立物表TEMP 300秒 | **NOT_RUN**，不能用ECG附带温度实收代替 |
| C49132独立RR15 300秒 | **NOT_RUN**，不能用旧B4 RR PASS代替上云验收 |
| B5三模式最终结项 | **NOT_COMPLETE**，不能签全体 `B5_E2E_ENGINEERING_PASS` |
| 三板并发/正式发布 | NOT_RUN，A段未接，未合并保护分支 |

当前温度扩展后，ECG窗TEMP为独立观察，不沿用最早B5草案“TEMP一律INVALID”覆盖真实模块数据；RR在ECG窗仍应真实INVALID。各profile以实际绑定criteria为准，不采后调整。

## 6. C49132两次实窗：为什么不能只留下PASS

同一固件、工具、名义源/导联、原判据。各窗45秒预热＋300秒共同评价＋15秒尾段，原420秒业务硬停，均为非人体MOCK。首窗失败后负责人明确新增一次采集授权；新token/目录/计数，未烧录或改阈值，未覆盖原件。

| 指标 | 首窗 | 负责人追加复验 |
| --- | --- | --- |
| TIME粗时间 | 端点1、第7次、12012ms成功 | 端点0、第3次、4012ms成功 |
| 新鲜NTP RTT/两时差 | 103ms / 104ms | 55ms / 127ms |
| B稳态HR | 493/600有效；107次NO_CYCLES/UNSTABLE | **601/601有效且均60** |
| Broker HR | 250 VALID、50 INVALID | **300/300 VALID60** |
| Broker RR | 297 INVALID，3条10次分VALID | **300/300 INVALID/null** |
| ECG源点 | 74439，有缺口 | **75012，原覆盖/连续性检查通过，映射错误0** |
| Broker实收/Backend接受（整窗） | 2785/2785，拒收丢弃0 | **2857/2857，拒收丢弃0** |
| 评价期WSS快照 | 2973 | **2972，所需重叠ECG批次751可见且一致** |
| C稳态发送/溢出/UART/MQTT错误增量 | 均0 | **均0** |
| 正式联评 | exit3，NOT_PASS | **exit0，failures=[]** |

追加窗B采样250.0350086SPS，ADC/SPI/长间隔、B CAN expiry/overflow/error/discontinuity和TEC/REC/BOFF增量0；C诊断60条、最大间隔5.094秒；最大JSON848B＜2048B。采集进程exit0不替代首窗联评exit3。

首窗HR失效已在B端、CAN/云之前出现。614个VALID ECG批次在WSS一致，130个INVALID批次按质量策略屏蔽；质量变化会丢弃未满的混合质量批次，C WAVE gaps为0。支持“输入/算法质量状态变化有贡献”，不能断言唯一是模拟器，也不能把全部缺口说成网络丢包。两窗说明间歇性质量风险仍在；工频占比重叠，不足以证明工频为唯一原因。负责人没有异常时点回报，不等于仪器证明源稳定。

### STOP残留必须保留

两窗源端精确420000ms业务STOP，phase7/CLOSED、pending0、unsynced0，主机观测420.047/420.063秒，满足原冻结STOP判据。但首窗STOP live24/cache27，末尾cache51/停止后overflow29；追加窗live24/cache28，末尾cache52/停止后overflow30。**不是队列清空，也不是整段零丢弃。** 此为停止后RAM队列语义遗留，不计入稳态零错误，也不隐去或临时改判据。

## 7. 已遇问题、已修路径与仍不能断言的原因

| 问题 | 已有证据/处置 | 禁止误判 |
| --- | --- | --- |
| ECG无效/RESP削顶、无周期、宽带干扰 | 审核RA–LA与RA–LL路径、按模式分别验收；当前阈值不变 | 线短不代表接触/源/参考地已排除；不能用未知真值算准确率 |
| 屏无波形/静止 | 修正P3/P7路径；调试器健康退出续跑恢复刷新 | 屏静止不证明算法丢失或CPU在ROM |
| 屏启动触发MCU复位 | 修正屏启动帧处理；实板屏断电重启恢复波形且不触发原MCU复位路径 | 此PASS不解决BOOT/ROM根因 |
| SDK预算6000耗尽/短读/退出HALT | 区分预算拒绝与原生DLL失败，修复read_failed锁存、API时序、Close预算/续跑；MEM-AP交叉PASS | 显式reset/halt/go为0不代表Connect/Close无隐式副作用 |
| 854B CIPSEND写完无SEND OK | 保存UNSYNCED及真实超时，禁止盲发AT恢复 | 完成UART写不等于ESP完成发送，更不等于云接收 |
| 1.5秒交付停顿、2.516秒观察间隔/REPLAY/STALE | 修5ms轮询内1000ms等待、QoS1剩余预算不足仍开QoS0、二进制被OK/ERROR误判；保FIFO/单在途严格PUBACK | 不能用直连TLS夹具代替真实ESP组合时序；不能扩大缓存/降低时效制造PASS |
| 诊断干扰及STOP缺证 | 低扰动有界日志、基线/末尾落盘/监督器收尾已回归 | 目前STOP后残留队列仍存在，不称排空 |
| 频繁TIME失败 | 方案A共享已有服务器选择与失败恢复；冷启动CFG禁用仅回`:0`无列表导致零查询路径已反例复现并在C49132修正 | 仍无路由/AP双向抓包，不能认定唯一是UDP123/NAT/DNS或模块故障 |
| 观察到新启动横幅 | 有一次负责人明确承认误按RESET，原件保留 | 不伪称软件随机复位 |
| J-Link/COM/电源操作偏差 | 曾连错B/C、COM15改COM6、忘开C、源模式与计划不符；按现场事实修正 | 不归咎所有失败为固件，不凭同型号绕身份校验 |

### 当前TIME实现（方案A，不是人为写时间）

ESP内置SNTP建立模块秒级时间；C主动48B NTP建立经nonce/协议/服务器关系校验的毫秒UTC，保留**1000ms新鲜性**。显式选用/读回既有至多3端点并统一轮换，15次查询/约30秒准备预算，不是每端点30秒，整体仍受60秒就绪门限制。明确禁用回复先易失启用并重读，仍无列表则拒绝。成功端点供新鲜请求复用，并检查两份UTC一致性。

一致性冻结式：ESP秒值e，查询起止tq0/tq1，参考接收tr；q=tq1−tq0≤2000ms，u=floor(RTT/2)+1ms，L=1000e+uint32(tr−tq1)，仅`L−u ≤ S ≤ L+1000+q+u`通过。保留5000ms PUBACK、2048B、CA/CN/SNI、MOCK及420秒门；不发SYSTIMESTAMP设置、不重写UTC、不关TLS证书校验。普通NTP nonce不是加密认证。ESP当前固件是否编译证书日期检查仍UNKNOWN，不能由CA命令OK证明。

主要代码：`gateway/storage/router.c`、`gateway/b5/network_main.c`、`gateway/mqtt/src/gateway_transport.c`、`mqtt_transport_adapter.c`、`platform.c`；不要用`gateway/dual_can/network_main.c`或GitHub旧B5覆盖温度扩展。

## 8. 搁置问题：独立登记，不因ECG云PASS关闭

| 项目 | 状态与最小剩余证据 |
| --- | --- |
| CPU ROM根因 | **CPU_ROM_ROOT_CAUSE_UNRESOLVED**；PI已决定先搁置，不主动再扩ROM调查 |
| 当前完整部署独立冷启动 | 未完成独立专项验证；历史某些无探针重启屏刷新不是当前全部固件独立冷启动闭环 |
| 同窗ECG+RESP双有效 | 未证明；当前SKX分别模式及分别接线成功不能合成同时有效，源能力不足需证据才能签BLOCKED |
| 阻抗绝对幅度 | **IMPEDANCE_AMPLITUDE_NOT_CALIBRATED_INSTRUMENT_REQUIRED**；只有电池万用表，无32kHz隔离阻抗条件；菜单R和ADC不能替代Ω标定 |
| 温度绝对准确度 | NOT_CALIBRATED，无非人体合格参考；只可签物表通信/有效性工程结果 |
| CAN故障注入/恢复 | 未完成独立故障矩阵；正常传输不替代断链/错误恢复验收 |
| 输入间歇质量 | 首窗失败/追加窗通过，物理唯一根因UNKNOWN，保留后续触发时补证 |
| STOP后队列 | 业务停止合格但RAM缓存及停止后overflow保留；新改动需另定范围 |

ROM确曾真实PC在`0x1FFF32F0`/VTOR`0x1FFF0000`，后来暂停核心真实PC`0x1FFF369E`、MSP`0x20001D50`，ROM代码为接口/GPIO探测，Flash/options完整。另一次`0x0800A3A0`是Flash HALT，不是ROM，更不是“芯片中算法消失”。候选机制：CH340自动下载Q1/D2影响NRST、Q3/R44影响BOOT0；J5供电下拔USB不等于隔离CH340。BOOT静态低不证明复位边沿低；没有示波器边沿证据，不能定因。应用静态审查未发现故意跳ROM，但不等于排除全部间接故障。

监控脚本历史还有运行态误分类、Close不续跑及POPUP_END重复创建导致跳过Close，已离线修正；最终监控修正版未据此取得完整实板闭环。不要为了重现而无限连接/复位或强设PC/MSP/VTOR。

## 9. 云端、私有原件与工具定位

云端独立命名空间 **GW-B5-001**，测试发布账户`b5-gateway`仅写`mpm/v1/GW-B5-001/#`、观察账户`b5-observer`只读对应空间。正式 **GW-C-001** 未被测试冒用。独立Backend/Hub/token/log及loopback TLS `127.0.0.1:18775`，经现有SSH别名转发观察。所有输入MOCK/synthetic，A OFFLINE，INVALID/STALE/会话代次保持真实。

最近隔离Backend/TLS就绪时正常，未再次启动；原六小时驻留记录截止 **北京时间2026-10-29 23:05:05**。这是既有记录，不是本文重新远端探测。新窗口可能已经到期，先按批准的只读范围核验；**账号/ACL不会随unit到期自动撤销，不能称整个环境已清理**。不得凭旧许可自动start、部署G1、HUP Broker、开放8884或改正式服务。若后续窗口包含人工等待，需按冻结工具核算足够新鲜云预算。

私有根：`E:/medical-monitor-node-b-precan-private/20261023`，保存EFS受限原始全片/options/UID、sector3、凭据、UART/帧/云端完整原码和授权消费。不得上传全片或打印秘密。仓库仅保留脱敏证据、应用BIN及哈希。

本机忽略的定位入口 **`node-b/build/b5-repair-r4-time-init-pointer.json`**：

- `binding/root/templates`定位精确安装/恢复包；`install_output`和`C_readonly_output`定位实测回执。
- `windows.ECG60`是**追加PASS窗**；`prior_windows`保留首个NOT_PASS。各authorization/bundle指向B/C身份、DLL/工具SHA、源附件、`.used`及云端观察包。
- `formal_review`、`field_manifest_sha256`、`physical_final`定位正式裁定、完整现场文件清单与最终断电事实。
- `B_install_receipt`、`B_temperature_receipt`在当前窗口授权文件内；不要整份打印该私有文件。
- `node-b/build/b5-repair-r4-time-bootstrap-pointer.json`、`b5-boot-watch-pointer.json`定位旧TIME/ROM证据。

忽略定位文件不保证出现在新克隆；缺失时从现有工作区/EFS与已追踪SHA恢复索引，不猜路径、不重新上板补做历史备份。原生失败、真实退出码、授权次数、脚本版本都保留，不能改写旧卡或删除`.used`。

## 10. 新窗口工作合同与建议顺序

1. **先只离线接手**：确认工作区/分支/HEAD/未提交文件，读本文件和唯一交接顶部、两窗实测JSON、AGENTS。不要再全量重读长历史，遇证据冲突才沿指针找原件。
2. 向PI简报：ECG60追加窗PASS，TEMP/RR独立300秒未完成，当前全断电、B40928/C49132/gen5保留；询问本次是否继续两项剩余对象，而非重新请求所有旧审批。
3. PI要继续时，优先复用**同一已安装C49132**，不要为上下文迁移重构算法/CAN/授时、重新烧录或重做已过矩阵。冻结新鲜现场/工具绑定、云只读/必要服务恢复与两个窗口各一次START的边界；旧TEMP/RR未消费不等于跨日仍自动有效。
4. TEMP：保留非人体物表定义、无绝对参考的限制；按当前温度profile核验源帧/校验/新鲜度、B→C→Broker→Backend→WSS和INVALID语义，冻结后各层保存原件，不临时降低门槛。
5. RR：另在批准冷态操作中将黄L由LA移LL，R→RA、F→RL不动，独立呼吸15/1.5R/波形周期30/窒息0；参数先核实、判据采前冻结。不得通电改线、短LL/RL、接人体或宣称同窗ECG也有效。
6. 各窗各自45秒预热/300秒评价/420秒硬停，独立token、唯一START、新DISARMED行确认；C实体RESET只在联合记录就绪后提示，避免聊天回报延迟反复消耗窗口。新鲜B/C核验按实际批准次数执行，不重复连接补齐“好看的”证据。
7. 正常窗结束后安全封存；R-CFG/R-APP/R-CLOUD是否执行由各自对象权限决定。**目前三种恢复执行次数均0**。不能默认恢复正式H3或自动撤销测试资源。
8. 最终更新唯一业务报告，分别填写ECG/TEMP/RR状态及残余风险；到三窗完成或真实硬件阻塞里程碑再集中commit/push/独立远端核验。本文交接文档不自动触发新push。

普通软件/解析器/预算问题在已批范围内自主最小修复及必要回归，STOP_TARGET不停止安全离线研究。ROM/HALT、未知状态、异常复位、身份/Flash漂移、电气异常或ESP UNSYNCED时停止危险目标动作，保存原件，不自动Reset/Go/重刷/补发START。恢复动作必须有明确对象/次数/时限，不用“已重启恢复”冒充根因解决。

不修改BIO_V2阈值、ADS/GY配置、真实UTC/来源、TLS校验、Backend时效及原验收门槛；不动P4/main/H3/A/B/P6/语音等保护分支、不合并/建PR/删历史、不启Security Gate、不新增正式云写入或三板联动。

## 11. 可直接粘贴给下一窗口的开场指令

> 请接手 `E:/medical-monitor-node-b5-cloud/node-b/docs/MPM-B5-CONTEXT-WINDOW-HANDOFF-20261029.md`。先读根AGENTS和唯一业务报告最新C49132顶部，再核对两窗实测JSON与本机忽略的time-init-pointer，不重跑已过测试。当前B40928/C49132/gen5保留，最后全部断电，JTAG板端最后在B；ECG60追加300秒云窗PASS，首窗NOT_PASS保留，独立TEMP/RR云窗未完成。先只离线确认进度和剩余工作，不自行上电、连接、复位、Go、烧录、写sector3、启云服务或发B5START。需要现场时一次提出两个剩余对象的有界安排，沿用既有实装，不重复开发算法/CAN/授时，不降低判据；ROM根因先搁置。所有私有原件只在受限EFS，不回显凭据/UID/端点。

本次上下文交接只新增本文件，未操作目标、云端或旧证据；是否将本文件纳入后续里程碑提交由负责人决定。
