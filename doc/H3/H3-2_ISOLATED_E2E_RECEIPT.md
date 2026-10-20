# H3-2 隔离链路回执（进行中，尚未准出）

截至 2026-10-20，结论为 **FAIL / 正式发布暂停**。主机监听退出码0仅表示完成取证，不能解释为硬件链路验收通过。

真实路径为 Node-A 物理CANopen → C中断静态队列 → Adapter/Router → ESP8266 AT 2.3.0.0 / SNTP / TLS → 独立8884 Broker → 独立Backend → WSS。来源按操作者批准的非个人测试源标记MOCK/synthetic，未回放R3真人记录，未验证生理测量准确度。Node-B未接入，观测中未出现在线。

| 原始观测入口 | 实际时长 | 关键结果 |
|---|---:|---|
| cloud/evidence/h3/observations/e2e-20261019T132109Z/result.json | 600.076s | MQTT1191、WSS5949；匹配数值未发现不一致；连续有效窗口仅39.548s，退出1 |
| cloud/evidence/h3/observations/e2e-20261019T134417Z/result.json | 900.091s | 等待A期间无有效输入，退出1；不能当作活跃验收 |
| gateway/physical_can/evidence/h3/uart-20261020T010558Z-result.json | 329.219s | FIFO/软件队列/UART/主机日志丢失0；发布失败5，Router累计丢失177 |
| cloud/evidence/h3/observations/e2e-20261020T010618Z/result.json | 900.007s | MQTT1828；数值匹配错误0；最长有效174.875s，退出1 |
| gateway/physical_can/evidence/h3/uart-20261020T011626Z-result.json | 1200.000s | FIFO/软件队列/UART/主机日志丢失0；发布失败18，Router累计丢失423；包含一次已明确记录的隔离Broker重启注入，不是正常稳定网络窗口 |

首次联网镜像缺少应用自身VTOR初始化，已修复；C原应用sector0–2实际回写并读回核验通过。后续UTC小数映射已修正，保留原新鲜度/发送频率；修正后的现场检查中Backend拒收累计658未继续增加。不能把旧失败记录删除或清零后改写成通过。

串口跨夜中断后，恢复工具最初错误地把下载线DTR置False，保持了C复位；已按本机reset_active_high/boot0_active_low极性修正，并在现场A断电条件下复用原成功握手时序。恢复时只核对Flash并写312B预留SRAM，不擦写Flash。RAM配置不具备断电持久性，不能声称C已具备正常持久生产配置。

当前诊断确认存在5000ms发布总预算失败；必须记录实际QoS与在途编号，才能区分QoS0发送和QoS1确认。独立Broker诊断仅输出指定测试客户端的编号、QoS、报文长度、UTC与PUBACK发送事件；原始日志、地址、Topic和载荷不落盘。正式Broker未修改/重启。

另一次0.222s MQTT/WSS观察因并发会话争用共享状态临时文件失败（原结果保留）。工具已改为各会话独立原子状态文件，并发回归通过；工具失败不能替代硬件FAIL归因。

最新候选源码4209876ed659408d7bd8ca22a804d93e76bdee35，镜像39120B，SHA256 6aecb5ea4d03d9f57a051b8701c49bffb8e01d3e5b6dd622e1b3f0f51e50d6cc，仅应用sector0–2。sector7/11与选项字节逐次核对，未改动。正在进行失败报文与Broker回执配对，尚未宣布修复或H3-2 PASS。

当前已通过：两种ARM构建；IRQ目标42项P5普通Host；Backend/AI/受限下载观测105项普通测试。没有执行正式Security Gate或安全扫描，没有PR，没有修改P4/main。原Web/Nginx/AI正式服务未切换，H3-3所需现场发布窗口尚未申请。

## 2026-10-20 AP位置调整与时钟归因补充

`ap-adjustment-normal-window.json` 中319.000s实际活跃窗口，PPG PDO增加15302、QoS1确认增加672，FIFO/软件队列/Router/UART/主机日志新增丢失及发布失败均0。此前失败5、Router丢失97原样保留。该结果仅证明这一段板端传输计数通过，**不是完整E2E PASS**。休眠查询原本已经为0；不能声称关闭休眠修复了问题。调整AP后最近查询从-74dBm改善到-64dBm，关联改善不等于证明所有无线故障根因。

逐包配对发现MQTT报文1618在C返回发送成功后未抵达隔离Broker；相邻1617/1619均实际收到并确认。该失败不能归为Broker漏发PUBACK。新600s观察仍退出1，匹配数值差异0，但Backend拒收增加432；独立319s窗口的报文采集时间最高超前服务器约5.6秒。断网复测中B始终OFFLINE、无效值隐藏正确，但110s内未观察到有效恢复，原退出1保留。

C原系统文件明确使用16MHz内部HSI；诊断每5000固件毫秒约间隔4945真实毫秒，长时累计漂移与上述未来时间一致。板卡原理图第4页Y2标8MHz，文件SHA256 `7737115dc272d6daff1f3bb08b7c8c23c10415c10bca57c3d72979adf53b46b2`。依据ST RM0090的HSI/HSE时钟说明，新增仅独立IRQ目标的外部8MHz晶体启动，不使用PLL，不改采样频率、TTL、5000ms发布预算或PUBACK匹配。起振/切换超时停止，不静默退回HSI继续发布可信时间。原P4/旧轮询目标系统文件保持不变。

新候选40040B，SHA256 `00fb5dab92202c89c3a108eb78f3506afe2d978d728d410cceff4718a146d8a6`，text39944/data88/bss123040。两种ARM、协议Host、网络排队顺序Host、时钟失败关闭/500kbps分频Host、IRQ P5 42项均退出0；Python功能107项退出0。一次测试编排误填不存在的测试路径退出4，原日志保留，修正路径后107项通过。原始退出码见 `gateway/physical_can/evidence/h3/hse-regression/`。晶体候选尚待真机复测，正式站仍未切换。

## 同路由器对照与新鲜SNTP候选（03:13 UTC补充）

HSE候选已实际烧录并核验，sector7/11和选项字节未变。诊断中位间隔恢复为5.000秒，600s E2E观测的Backend拒收2209→2209，证明本轮新增未来时间拒收已消除。该窗口仍有6次发布失败、Router丢失90；6个失败报文编号均未在隔离Broker中成为完整PUBLISH，不可归因为Broker漏发PUBACK。仅TCP头元数据的180s观察保留于 `hse-tcp-header-observation.json`，无地址和载荷；关闭连接后的FIN重传不能单独证明路由器丢包。

操作者先提供另一网络，实际可见信道36/5GHz，ESP8266不兼容；失败记录保留，未重刷Flash。随后指定的2.4GHz网络经受限配置比对，确认与最初网络相同，不能声称完成了换路由器对照。只读及RAM恢复回执分别保留。为做同网对照，本机通过本任务独占的手动Wi-Fi配置连接至相同SSID/信道5；凭据只在仓库外及OS保存，待对照结束恢复原配置。独立8884新增 `h3-net-probe` 角色仅允许 `h3/net-probe/#`，不进入监护模型，结束后撤销该角色。

实际300s对照：PC TLS1.2 QoS1确认507/QoS0发送160、最大PUBACK1203ms；服务器回环确认630/QoS0发送298、最大31.258ms，均退出0且无重连。PC同步等待导致实际发送速率低于服务器对照，不能解释为两者严格同负载。C恢复原网络后约1300s观测的发布失败/FIFO/软件队列/Router/UART/主机丢失均0，QoS1确认2723、QoS0发送851。此时传输故障未复现，**不能据此宣称路由器故障已证明或所有间歇失败已根治**。

同一C窗口仍有约2–3秒时间偏旧，标量2秒发布间隔叠加后触发既有5秒STALE边界。服务器chrony校时正常，系统对上游偏差约0.15ms、root dispersion约20ms；PC与服务器交叉核对未显示秒级差异。当前隔离程序仅确认模块RTC年份有效便接受时间，未证明本次获取了新SNTP样本。因此新增显式 `--fresh-sntp` 候选：从模块配置读取目标，以UDP实际请求/回复取得毫秒SNTP时间，核对originate、模式、LI、stratum、epoch、往返预算，再进入原SSL/MQTT流程。不改监护TTL、发送频率、PUBACK及5000ms预算。

新候选40928B，SHA256 `35d91a1e8db7762af06ef39b289ee871e20ac10cd74046ac988fbf9d9c00ebe4`，仅sector0–2。SNTP策略Host、原P5 42项、fresh-SNTP P5 44项、两种fresh-SNTP ARM及Python107项通过。首次fresh P5揭示短读未累积（退出1），修复后原日志和通过记录均保留。该候选尚待硬件验证，正式发布仍暂停；正式候选Nginx仅准备并做语法检查，未切换任何原入口。

参考：[ST RM0090](https://www.st.com/resource/en/reference_manual/dm00031020-stm32f405-415-stm32f407-417-stm32f427-437-and-stm32f429-439-advanced-arm-based-32-bit-mcus-stmicroelectronics.pdf)、[ESP8266规格](https://documentation.espressif.com/0a-esp8266ex_datasheet_cn.html)、[ESP-AT 2.3 TCP/IP命令](https://docs.espressif.com/projects/esp-at/en/release-v2.3.0.0_esp8266/AT_Command_Set/TCP-IP_AT_Commands.html)。


## 03:39 UTC：新鲜SNTP实板结果与停源记录

C候选源码 `71eb0948b3e54cbf049f4e23c7c2462a9b3953f9` / 镜像SHA `35d91a1e8db7762af06ef39b289ee871e20ac10cd74046ac988fbf9d9c00ebe4` 已实板下载并逐字节读回、保护区及选项字节核验通过。下载回执整体退出1来自后续Host状态文件PermissionError，不能误写成Flash读回失败；原回执/日志保留。Host原子替换增加有界重试，经模拟短暂占用与持续失败回归验证；持续失败仍显式抛出，不触碰设备计数。03:26 UTC仅被动重开串口继续监听，没有复位、RAM注入或Flash写入；前后观测之间存在Host记录空窗，不能拼成无间断日志。

真实UDP SNTP初期多次拒绝样本，最终取得RTT61ms、估计半程不确定性30ms的新鲜回复，随后进入TLS/MQTT。600.086s云端观测：MQTT1513、Backend新增时间拒收0、队列丢失0、匹配数值差异0、Node-B未在线。PPG/PR/SpO2消息年龄中位数约306/504/383ms，原2–3秒偏旧问题在本次样本中已消除。原严格“三流同时持续VALID300s”指标最长76.294s，退出1保留。另增加显式active-ppg评估，仍保留原三流指标及退出码，不改生产TTL/质量/发送频率；空波形、过期、未来包、错误来源、B非OFFLINE均不通过。360.015s补充观测PPG最长127.880s，仍退出1，无效值隐藏/缺席B正确。

停波与C接收PDO同步：例如5秒PPG PDO从约250降为40，PUBACK持续增加且发布失败/Router丢失为0。现场随后确认已取下探头；该窗口按停源测试保留，不能冒充连续有源300秒。现场已重新接回本轮声明的非个人测试源并开始新的420秒观测。没有把原INVALID/STALE改为VALID。临床测量准确度未验证，非个人来源始终MOCK/synthetic，网关自身LIVE；未进入正式发布。

新一轮真实浏览器隔离检查5项通过，新增1次实际豆包调用，截图隐去问答正文和体征值。凭据仅在服务器和临时进程内存，后续用量以持久流水汇总。原正式Backend/Broker/AI/Nginx未切换。


## 03:48 UTC：重新接回探头后的活跃窗口通过

现场重新接回已声明的非个人测试源后，420.080s MQTT/WSS观测退出0：连续新鲜PPG348.261s，MQTT1226、匹配数值差异0、无效值可见0、B非OFFLINE0、Backend拒收2209→2209。有效SpO2/PR均在内存逐层匹配；真实传感器质量使标量间歇INVALID，原“三流全部连续VALID”辅助指标87.687s/退出1原样保留。合同要求实际活跃负载300s及质量语义准确，没有要求修改源质量或要求连续血压；因此新增显式active-ppg门禁与原辅助指标分别交付，未更改生产时效和质量判定。

同一新鲜PPG区间内的板端精确300.000s（03:37:41–03:42:41 UTC）独立回执 `fresh-sntp-active-300s.json`：FIFO/软件队列/Router/UART/主机日志新增丢失0，TX失败/发布失败0，实际PPG PDO持续接收，TIME持续发出。具体累计起止值及增量保留，不把QoS0 SEND OK等同于PUBACK或上屏。端到端逐层结果另见 `e2e-probe-restored-observer-console.json`。

实际D命令断网30秒后的180.058s观测退出0：STALE→OFFLINE→ONLINE，故障后新鲜PPG恢复；B始终OFFLINE、不可用网关下VALID0、无效标量/波形暴露0、历史补传冒充当前0。网关首次STALE在观测30.534s，恢复新PPG在54.842s；不是从D发出开始计算的恢复耗时。断网导致32槽历史缓存累计溢出53条，按预期故障窗口计入Router丢失，未清零，不能用此故障窗口替代正常窗口零丢失证明。

一次离线AI检查因测试session_id格式不符返回422（未调用豆包）；修正为32位十六进制时网络已恢复，因此200/NOT_CALLED仅作为恢复后当前事实检查，不冒称捕获了离线分支。更早的实际离线AI验证仍保留。新浏览器调用后流水为历史3次3578 Token＋H3新增7次3918 Token，共10次7496 Token；H3七次均VALIDATED，费用仍仅有操作者免费/体验说明，未推断实际费用为0。

NIBP本轮没有获得新的有效血压输入，保持INVALID；本轮未声称验证临床准确度或有效血压90秒过期真机路径。原Node-A应用未改/未烧录，C当前仍RAM配置，保护sector7/11与选项字节未变。正式发布尚未获本合同要求的最终现场窗口确认，原站未切换。
