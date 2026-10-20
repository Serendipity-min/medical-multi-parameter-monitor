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
