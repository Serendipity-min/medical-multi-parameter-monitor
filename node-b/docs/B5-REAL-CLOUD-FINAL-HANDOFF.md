# 最新交接｜2026-10-29，三路实板验收未通过

唯一综合结论与下一步见[B5-C-EGRESS-FINAL-CLOSEOUT.md](B5-C-EGRESS-FINAL-CLOSEOUT.md)。最后核验实装B40928/C46584；ECG因完整854B发送后SEND OK未确认而提前停止，TEMP/RR未执行。C47120是待批诊断候选，尚未安装，根因未确定。物理断电未确认；测试账户未撤销，不能称全部封存或阶段通过。以下内容仅保留历史。

---

# 最新交接状态｜温度已启用，B5三路最终验收未完成

当前真实部署为B40928B/C43036B，完整备份与先前部署均保留。本次B温度15秒接收PASS；最新ECG300秒原码连续74993点、Backend2893接受且拒收0、STOP420.093秒，但48条REPLAY及WSS时效失效使严格结论NOT_PASS。温度两次START分别止于AT及冷态TIME门，均未开始评价；RR新组合云窗NOT_RUN。

TIME失败后停止新增目标操作，物理断电未获完成回报，不能声称已封存。旧报告中B39948/C42552、未改应用等描述仅是历史。未恢复C24104、未回滚sector3、未撤销测试账号、不改正式云和算法。

具体证据、已排除路径、剩余不确定性及唯一收尾方案统一见[综合诊断与最小方案](B5-FINAL-ENGINEERING-ACCEPTANCE-REPORT.md)。下一步应保留B/接线，只解决C启动授时准入、出口调度及420秒串口收尾，再按对象批准一次候选安装与ECG/TEMP/RR分路复验；当前没有新的安装/START自动许可。

---

# B5-002阶段唯一交接｜gen5实板通过，最终评价未通过C出口完整性

## MPM-B5-FINAL最新裁定｜2026-10-28

本轮已实际写入gen5并经双全片/options核验通过，C全片SHA为`a5239d616523621593b5e76fd70212aa199e72603b85e359492d642448fff528`。测试云恢复及真实TLS/Broker/Backend/WSS准入通过；首个G3失败原件保留，PI另批有条件一次B Go及替代窗口，已采得45秒预热后的300秒评价。

最终`B5_E2E_ENGINEERING_NOT_PASS`：B600次观察均HR60有效、约249.99SPS且ADC/CAN无新增错误；C队列丢弃增加1251，ECG仅17651/74250点、RESP6789/14850点，HR125/295条。已收到子集无原码映射错值，Backend接受1194、拒收/丢弃0，WSS实收；完整性不足。原码有STOP，但终态诊断在约422.125秒才被处理，冻结监督退出1，不追补成功收据。详见唯一[最终工程评价与综合阻塞报告](B5-FINAL-ENGINEERING-ACCEPTANCE-REPORT.md)及[本轮证据](../evidence/B5-FINAL-20261028/result.json)。

按负责人当前不断电指示保持供电；未恢复C24104，未执行R-CFG/R-APP/R-CLOUD。测试unit仍受6h上限管理，账号未撤销；正式服务PID及配置SHA事后核验不变。算法、应用BIN及保护分支未改。以下为先前检查点，不能当最新状态。

## 前轮检查点｜2026-10-28

负责人新批准的一次180秒快速桥单包窗口已实际通过：新nonce、48B请求/回复，CIPSEND前至完整回复观察结束595ms，满足原1000ms完整门；SDK1519次，调用者/worker/监督器退出均0，socket/接收模式/SNTP停止状态清理及Close通过。没有复位、Go、烧录、sector3写入、MCU时间安装或B5START。Close后的运行状态未另取证，不借此关闭CPU问题。

gen5 Wi-Fi最小配置、gen5→gen4和gen5→原gen3回退包已在受限EFS离线封存，79项定向Python验证和3项C记录校验通过；实际写入与恢复均NOT_RUN。C仍为最后已知42552B应用＋gen4，测试云服务当前UNKNOWN，本轮未查询或重启。gen5安装、测试服务只读/必要恢复、HW准备、G3及每项回退保持分对象批准，所有新模板均禁用。详见[本轮综合诊断与下一轮准入](B5-G3R6-FAST-PASS-GEN5-G3-READINESS.md)、[分对象授权草案](B5-GEN5-AND-G3-OBJECT-AUTHORIZATION-DRAFT.md)及[真实结果](../evidence/B5-G3R6-FAST-01/result.json)。

以下按原文保留历史检查点，包括最早无回包、SNTP TIME失败、2578ms门失败；不能将其解释为最新状态或因新窗口PASS而覆盖失败原件。

## 历史状态｜2026-10-27

本轮已按负责人“允许ESP侧单个UDP/NTP取证并分析，模块未变，不重复识别/哈希”的许可完成。裁定`ESP_SINGLE_NTP_REQUEST_ACCEPTED_NO_REPLY_OBSERVED_SOCKET_CLOSED`；总NTP载荷尝试1、收到包0、socket关闭已确认，未发送B5START。详情见[单包分析报告](B5-ESP-UDP-NTP-ANALYSIS.md)及[原始执行摘要](../evidence/B5-ESP-UDP-NTP-01/result.json)。SEND OK仅证明ESP接受载荷，不等于服务端收包或授时通过。

第一条执行记录因主机只接受CIPDINFO:0、模块实返false提前停止（socket未开、载荷0、退出1）；修正等价布尔解析后完成尚未消费的同一单包，不重发数据，两个执行记录和原工具源码均保留。跨记录独占payload marker在首个载荷字节前消费；修正记录worker/监督实际退出均0。18项定向测试通过；离线控制器测试曾因替身缺少属性失败，已在任何实板执行之前修正，负例日志保留。

当前接收模式0，主动+IPD未出现；一次被动读取ERROR不能单独用于判无包。已离线审计发送后至关闭/最终查询的RX头覆盖，未记录字节0；发送后主观察2秒，约3.281秒关闭、3.718秒最终状态。原生UART_DR 221字节重建与计划一致，一次48B载荷，没有补造回复。C最小收尾在Flash运行、DISARMED且无Fault，SDK已正常关闭；严格按负责人要求没有UID、Flash数据、options显式读取和新镜像哈希复核，不能据此签新的全片完整性PASS。

本轮不设置模块时间、不启用SNTP/改网络配置，不改算法/固件/正式云；没有新G3 START、服务恢复或账号撤销。直接UDP尚未证实收到回包，不能唯一判为内置SNTP问题、路由器过滤或某一网络端故障；此前PC参考不是同时/同路径对照。下一项应为单独批准的同步AP/路由器侧抓包与相邻参考，当前单包授权已消费，不自动发第二个包。

当前保持J-Link在C、C J5、B断电、C USB_UART断开。历史ROM、冷启动、同窗双有效、绝对阻抗和故障恢复均保留原状态。142份原件/来源快照在归档时逐个通过EFS属性检查，公开仅安全摘要/哈希/测试日志。以下SNTP和测试服务状态是此前检查点，不代替下次实时查询。


本轮依据负责人“启用命令返回→配置读回→时间变化，然后继续上次失败进度”的新许可执行有界分阶段排查；没有消费新的G3 START许可。当前结论为`TIME_SYNC_ADMISSION_BLOCKED_G3_NOT_STARTED`。保持原C42552B（BIN SHA d5b9624b3da1129b4e045d3b2f669c00d2d93cb7379b15293ff143fe9f130683）、B39948B、sector3及算法阈值，未烧录、不改正式云。总览见[授时排查汇总](../evidence/B5-ESP-SNTP-01/investigation-summary.json)。

| 分阶段实际证据 | 本轮结果 | 严格边界 |
|---|---|---|
| 易失参数与测试Wi-Fi | SYSSTORE=0并查询确认；CWMODE/冻结sector3测试Wi-Fi一次连接及SLEEP=0均OK | 只用既有私有配置，未打印SSID/密码，不代表互联网UDP授时通过 |
| 默认SNTP启用/读回/时间变化 | CIPSNTPCFG=1,0返回OK，enabled=1；0/5/15/30秒读到1513/1518/1528/1543 | 仍非有效UTC；已复现设置成功但未获授时，不能把命令接受等同时间有效 |
| 模块端既有三主机DNS | 三条CIPDOMAIN均OK并返回IP；首个为RFC1918，另两个为公网分类 | 私网地址本身不是故障证明，也不证明UDP123可达 |
| 电脑侧单包参考 | 对模块实际DNS结果每个发1个48B NTP请求；首个超时，后两个收到匹配nonce/模式/stratum/时间和RTT的包 | 路径是电脑，不能冒充ESP Wi-Fi链路可达；只3包，无重试、无设备时间写入 |
| 临时优先既有第二服务器 | 设置及读回OK，模块仍只返回2526/2531/2541/2556 | 单纯更换优先目标未恢复有效UTC；未安装固件或永久更改配置 |
| 回放当前候选原命令 | 原CIPSNTPCFG=1,0重新恢复默认主机列表，与最初enabled读回逐字节相同 | 会覆盖临时选择，不能把易失预设当旧候选已自愈；随后SNTP已关闭并读回 |

三次C硬件会话（默认启用、DNS只读、单变量对照）均有独立字节白名单、180秒监督和一次`.used`，worker/监督实际退出均0；每窗均核对UID、完整1MiB Flash/options前后逐字节相同、Flash正常运行及DISARMED，未执行reset/halt/go。两次启用阶段正常关闭SNTP并读回确认；DNS阶段没有启用SNTP。UART字节实际231/94/225，均与各自冻结计划一致。完整Flash仍acb33fdd39ecb016ecd848ec25eee051635f56ef8138b577a8590d2734ad687e，options仍52d5979da03bd7be45e385920ec7d5901793bab3f6bc1daa0c1c1997f9e91687。源/工具SHA、原始回复及真实退出码分别见[SNTP](../evidence/B5-ESP-SNTP-01/result.json)、[DNS](../evidence/B5-ESP-NTP-DNS-01/result.json)、[电脑参考](../evidence/B5-NTP-PC-REFERENCE-01/result.json)、[单变量对照](../evidence/B5-ESP-NTP-SELECT-01/result.json)。

DNS原执行解析器未识别带引号的IP，原收据中的IP_parsed=false保留；只离线去掉引号并重解同一原始回复，三条均有合法IP，未因此重发查询。工具按阶段改动的原执行版本均保存在各自EFS源码档案；当前版本包含新增DNS与单变量流程，不能把最后源码SHA冒称全部窗口的执行SHA。默认阶段11项/共享16项定向验证、DNS13项、单变量15项及电脑参考4项通过；没有重跑旧Host/ARM/TLS/UI矩阵。

授时精确根因仍OPEN：本轮SNTP启用命令明确被接受，后续三个目标也均能DNS解析；仍不排除最初授时期间的DNS瞬态故障。问题待从ESP实际链路/回包或内置SNTP处理继续区分，尚不能唯一断言路由器封UDP、模块损坏或源码算法问题。负责人仅补充Wi-Fi来自“路由器”，UDP123策略UNKNOWN。下一项补证应为ESP侧一次原始UDP/NTP请求、匹配nonce的回复和socket关闭，不能用电脑NTP包给模块灌时间；该原始UDP工具/负例/精确scope尚未完成，本轮未发该包。没有充分证据支持改算法或盲改固件；新固件安装仍须独立批准。

G3另有服务驻留阻塞：北京时间17:10:17只读核查测试Backend/TLS仍active，正式服务PID及所有冻结配置SHA不变、18775监听、8884不监听；测试服务到17:15:45的6h上限只剩约327秒，低于G3冻结的625秒启用预算。本轮没有start/restart、ACL/HUP或正式云写入；账号/ACL未自动撤销，不能声称已清理。后续先重新核实到期状态，必要时按单独测试服务恢复权限处理，不能为赶窗口缩短300秒评价/420秒硬停。

新的G3继续许可已记录为条件授权但enabled=false、B5START_allowed=false、实际START=0：TIME_SYNC及TEST_SERVICE_BUDGET两门禁未过。没有为了“继续”而再次触发已知TIME失败或降低TLS校验。当前J-Link在C、C J5、B断电、C USB_UART断开，所有主机设备会话已关闭，SNTP关闭，C DISARMED；无须为未就绪云窗提前转接。原ROM、B5独立冷启动、同窗HR/RR、绝对阻抗及故障注入原状态保留。

本轮四阶段原件/源码快照共312份已逐个验证受限EFS；此计数是各阶段归档时点，Git只含安全摘要/哈希/非敏感测试日志。以下时间查询与G3-02为历史检查点，不覆盖本轮结果。


时间诊断已按新授权完成。首次入口C位于ROM（VTOR=0x1FFF0000，PC样本0x1FFF32F2/32EA/32EE），实际worker/监督退出1、SDK44次、UART写0，未开始两条查询；原件保留。负责人随后单独批准一次人工C RESET及一个新的180秒查询窗口，并回报“C已复位一次”；只在完成事实之后启用第二次会话，代理reset/halt/go始终0。新窗口不复用已消费许可，C在Flash运行及身份/完整Flash/options/DISARMED先通过后才发送固定查询。

第二窗口worker与监督退出0：`AT+CIPSNTPCFG?`收到37B，实报`+CIPSNTPCFG:0`与OK；`AT+SYSTIMESTAMP?`收到41B，实报`+SYSTIMESTAMP:404`与OK。两条各一次，USART3_DR实际34次字节写请求，没有启用SNTP、设置时间、设置Wi-Fi或B5START。当前SNTP关闭、epoch仅404秒，低于最低1792977536，所以当前无法通过有效UTC门禁。时间查询命令已获当前模块接受，不能再将其“不支持查询”当成既定原因。见[首次ROM回执](../evidence/B5-ESP-TIME-01/result.json)与[实际查询及离线重解](../evidence/B5-ESP-TIME-01/result-02.json)。

原执行解析器只接受含时区的CIPSNTPCFG回复，故最初收据把简短`+CIPSNTPCFG:0`保留为null，未伪造成已启用/已关闭。原始字节完整不变，随后只修改主机离线解释器并重解同一份数据，将SNTP正确识别为false；增加该真实格式回归测试后，时间查询12项、共享GMR16项通过，实板执行前为11+16项。执行源码SHA与离线解析修正源码SHA分别保存，不把修正后的源码冒称为当时执行版本，未再次发送查询。

证据边界：负责人已将B/C全部断电并重新只给C上电，易失SNTP配置和时间可能因此丢失。当前关闭/404不能倒推G3-02当时的CIPSNTPCFG设置返回或默认NTP/DNS可达性，授时精确根因继续OPEN。下一步需要另批一次有界的“启用返回→配置读回→时间变化”诊断，保存错误和真实回复后再定纠正措施；本次不执行、不重启云窗，也不人工填时间绕过SNTP/证书门禁。

第二窗SDK818次、34次UART写，完整1MiB Flash/options前后逐字节一致（全片仍acb33fdd39ecb016ecd848ec25eee051635f56ef8138b577a8590d2734ad687e，options仍52d5979da03bd7be45e385920ec7d5901793bab3f6bc1daa0c1c1997f9e91687），退出Flash正常、DISARMED，健康核验后SDK退出续跑策略启用，主机会话均关闭。C42552B固件、sector3/7/11、B39948B及算法阈值均未改；当前J-Link在C、C原J5、B断电、C USB_UART断开。84份准备/源码/原始数据文件已逐个验证EFS，Git只保存安全摘要、SHA与日志；历史失败、ROM及其他未验门禁保留。

G3-02物理停机已获负责人后续明确回报“已全部断电熄灭”；另存[停止完成事实](../evidence/B5-G3-02/physical-stop-confirmation.json)，不修改原始STOP未知回执。断电的精确时刻未知，仍不能补签420秒内完成物理停止，也没有捕获MCU STOP横幅。此次冷态转接不是独立冷启动/ROM根因实验。未启停测试或正式云服务，测试账号/ACL不自动撤销。

以下G3-02及AT R4为此前检查点，不覆盖上面的实际时间诊断结果。


G3-02已按负责人“AT已恢复，继续准备并执行新的G3上云窗口”重新独立授权并执行，原失败窗口没有复用。C新鲜只读PASS（全片/options一致、DISARMED），工具/环境/42552B与39948B部署未改；测试Backend/TLS在窗口前后均active、正式服务PID及配置SHA不变、8884未监听，没有云配置写入。负责人对整组冷态准备回复“COM6，正常刷新”，现场附件以该完成回复绑定，不能据此签独立冷启动或ROM根因通过。

本次只发送一次8B B5START，计划内C人工RESET一次由负责人完成；AT、GMR 2.3.0.0、WIFI、WIFI_AWAKE、SINGLE、PASSIVE通过。START后17.687秒出现`GW FAIL TIME`，未建立T0，300秒评价实际0秒；worker及监督器实际退出码均1，自动重试/恢复0。TLS/CA/SNI/MQTT及新鲜UDP SNTP取样没有在这次记录中完成，不能将观察器联网当作C发布成功。真实Broker观察消息0，Backend accepted/rejected/dropped均0，WSS保存753份仅证明观察链可用。见[新窗实际回执](../evidence/B5-G3-02/result.json)。

已离线核对sector3最低epoch为1792977536（2026-10-26 01:18:56 UTC），不是未来时间。`gateway_transport.c`中TIME门禁先发送CIPSNTPCFG（返回值被忽略），再至多15次查询SYSTIMESTAMP，只在解析到不低于最低epoch的值才放行。现日志未保存这组模块原始回复，故不能区分配置命令被拒、DNS/NTP不可达、时间未同步或回复解析问题；不能直接判ESP损坏，也不能绕过时间和TLS校验。下一步应单独冻结有界时间诊断，保存CIPSNTPCFG?/SYSTIMESTAMP?/CIPSNTPTIME?等实际回复后再决定纠正措施，不继续重发云窗。

B保存103份诊断，HR60有效103/103、RR无效103/103，无新增ADC bad_status/SPI/overflow/init/long-gap；这不是300秒评价通过。CAN预备期TEC最高123/REC1，START后保存观察TEC最高78/REC0，未保存到BOFF；B全记录expired增加13057，ECG发送点计数0，必须保留，不能签CAN或云传输PASS。正常DISARMED/无TIME阶段与真正传输异常需另行区分，不从本次TIME故障直接认定CAN电气根因。

失败后电脑串口/J-Link/观察会话已关闭，但B只读工人收到STOP后Close未启用退出续跑，关闭后的B状态UNKNOWN，未再连接确认；不以最后一次健康Flash采样声称关闭后状态。C `STOPPED`横幅未捕获，负责人对切电提示回复“排查原因，在决定是否停止”，物理停止UNKNOWN。Tarm+420截止北京时间16:09:03.661，结束主机进程不等于C业务停机；再次提示断电，未获得完成事实前不能填写停止通过。原始612份文件及原码/Flash/options保留受限EFS，公开仅摘要和SHA。未烧录、改sector3、改BIO_V2阈值、恢复固件或改正式云；CPU ROM、同窗双有效、阻抗标定等原状态保留。

以下R4 AT成功及G3-01失败为历史检查点，不覆盖G3-02结果。


最新R4已按负责人“重新插入模块后再测一次”的新许可执行并PASS，worker/监督/实际进程退出0。代理显式reset/halt/go、冷态转接及改线动作均0；不能据零显式reset断言绝无未观测硬件复位。用户仅报告重新插入和灯闪，重插时供电状态UNKNOWN，不补签冷启动。当前模块实读AT `2.3.0.0-dev`、SDK `v3.4-22-g967752e2`，另报告Bin `2.2.0`及目标标签`ESP8266_1MB`；目标标签不等于独立物理Flash容量测量，也不能确定购买新旧或唯一模块ID。AT一次收到10B OK，GMR一次收到189B OK，UART_DR写请求总12，未重试。见[R4实际回执](../evidence/B5-ESP-GMR-REAL-04/result.json)。

R4补齐了不读UART_DR、不改寄存器的路由观察：PB10/PB11为AF7，GPIOB与USART3时钟、USART3 NVIC使能和运行时基均符合预期；保存查询前后SR及NVIC/时基快照。完整1MiB Flash/options前后逐字节一致、DISARMED及正常Flash出口通过，sector3/7/11未变。照片P5路由看起来符合预期，但不是电气通断证明；重插后相同115200查询恢复只支持当前通路可用，不能唯一锁定此前插接/供电/启动状态中的某个原因。

当前AT版本已由UNKNOWN更新为上述实读版本；原R1 ROM、R2/R3零RX、原G3首次AT失败全部保留，不能覆盖。R4未发Wi-Fi/TLS/MQTT命令或B5START，G3的300秒评价仍未完成，CA/SNI/SNTP/TLS能力不因GMR通过自动升级。新G3窗口需独立准入/批准，不自动启动，旧ROM及双通道/冷启动/标定残余状态不变。当前SDK会话已关闭，沿用J-Link在C、C J5、B断电、C USB断开。

以下UNKNOWN及等待近照等均为此前检查点，不覆盖R4最新实测。

接收证据边界：A/B的0字节为C软件RX环增量，不等于物理ESP TX无信号。保存Flash的USART3向量与ELF强ISR已离线核对一致，但NVIC/USART_SR/GPIO实际状态未在该查询中保存，仍需与P5实物/供电EN共同补证；不得直接判两块模块损坏。见[接收证据范围](../evidence/B5-ESP-GMR-REAL-03/RX-evidence-scope.json)。

最新R3备用模块对照已完成并停止：负责人已确认冷态替换、DIP-8方向及一次正常C RESET，J-Link在C、C J5、B断电、C USB断开；保持P5/P7/115200/固定查询不变。备用B同样只有4字节AT写请求、新RX=0、新UART错误=0，GMR未发送，版本仍UNKNOWN；C身份、完整Flash/options和DISARMED核验一致。见[R3真实回执](../evidence/B5-ESP-GMR-REAL-03/result.json)。原A与备用B都不能据本次结果判定为旧/新或损坏；共同供电/EN/启动/实际串口路径/波特率仍待物理补证，不自动重复查询、改参数或刷模块。

当前所有SDK/串口会话均已结束，R1/R2/R3许可均消费。C保持原42552B及G2-B配置、现装备用B，B断电；G3没有重启。下一步优先取得C P5及P1/P2插座可读丝印的近照，核实共同路由/并接设备；没有额外测量或硬件窗口授权时不继续连接或写UART。

G3 R4已获批并真实执行一次：C复位由负责人仅按一次，完整B5START只发送一次；C约2.078秒后输出GW FAIL AT，联合worker/监督退出1，无T0、300秒正式评价0秒，许可消费，不自动重试或恢复。见[AT停止复核](B5-G3-01-AT-STOP-REVIEW.md)和[真实G3回执](../evidence/B5-G3-REAL-01/result.json)。B保存94份诊断均HR60有效/RR无效、250SPS且无新增ADC错误；云观察CONNECT/SUBACK、Backend健康/MQTT订阅和WSS正常，但记录期间START后Broker实收0、Backend接受增量0，不能签B到云通过。

负责人随后确认C P5路线正确，当前A模块为ESP-01S且灯不亮；尚不能据此判A损坏或AT版本旧。新增GMR查询未刷C/ESP固件：R1入口VTOR=1FFF0000、PC均在ROM，UART写0停止；原件和异常收尾多读的一份ROM快照保留。已修正ROM直接Close，14项新增离线测试通过。负责人另批一次C正常人工RESET后，R2确认C运行Flash、完整镜像/options符合，固定115200 AT写4字节但新RX=0、新UART错误0，未发GMR；收尾完整Flash/options逐字节未变、DISARMED不变。见[R1](../evidence/B5-ESP-GMR-REAL-01/result.json)及[R2](../evidence/B5-ESP-GMR-REAL-02/result.json)，当前AT版本仍UNKNOWN。

根据负责人新的换备用模块指令，已准备[R3单模块对照](AUTH-B5-ESP-GMR-001-R3.md)：A原件保留，备用记B，不先贴旧/新或坏/好标签；只更换模块，P5/波特率/固定查询逻辑不变。新的物理完成附件未齐前执行器保持禁用，不自动再跑原R1/R2/G3。最多一次正常人工C RESET属于本次对照启动准备，仍ROM立即停，不追查ROM根因。替换后AT成功也只能关联模块/插接状态，不能确定A唯一故障原因。

G3失败后的420秒固件STOP行未取得；负责人最初要求先分析，随后已为独立GMR准备确认全暗10秒冷断电，这仅是后续物理隔离证据，不补签G3到期自停。正式云配置、B/C应用、sector3/options、BIO阈值均未改；GMR新增权限仅UART_DR固定字节，不冒称全目标零写只读。历史ROM根因、独立冷启动、同窗HR/RR、阻抗绝对标定及故障注入状态原样保留。

以下为此前检查点；其中“G3未启动/待现场”不覆盖以上最新真实结果。

负责人已批准HW卡一次C只读及G3 R4进入许可，并明确ESP保持在板供电。HW实际首窗已PASS：一连接/关闭、1MiB Flash与16B options各一次，退出0；UID/保护匹配、PC采样均在Flash、VTOR=0x08000000、无HALT/Fault，DISARMED=0。完整Flash及options与G2-B后冻结原件逐字节一致，sector3/7/11未变。显式halt/go/reset/Flash写/AT/B5START均0，未重试；原件仍只存受限EFS，见[真实C准入回执](../evidence/B5-G3-HW-PREFLIGHT-01/result.json)。

当前等待负责人按已批准HW卡完成一次冷态转接、C USB_UART及B J5上电，并回报实际COM和源/电气附件。G3许可已取得，不再重复申请；执行器在现场齐全前保持禁用，B5START仍0。下方“尚待批准/待现场”的描述为此前软件准备检查点，不覆盖本段最新实际进展。独立测试服务本次尚未新鲜查询，不自动启动或恢复。

G2-A唯一42552B应用实际安装PASS；MEM-AP第二只读窗口PASS；G2-B R3首次真实sector3写入PASS，耗时110.641秒，完整Flash/options及DISARMED合格。写后全片SHA `acb33fdd39ecb016ecd848ec25eee051635f56ef8138b577a8590d2734ad687e`，候选BIN及sector3外所有字节未变。

负责人另批G1-RESUME R2后，独立Backend/TLS已实际恢复PASS，TLS CA/SNI、Backend健康和MQTT订阅通过；18775监听、8884未监听，正式服务PID与配置未变。仅两个测试unit各start1，无ACL/HUP/正式环境改写。北京时间11:15:45启动，原6h驻留上限预计17:15:45；测试账号/ACL仍在，未自动撤销。

G3联合取证工具现已完成软件准备，41项定向离线测试通过：真实B原码/过滤后CAN队列映射、Broker原始载荷、实际Backend聚合计数/WSS、单次START及独立420秒监督。完整300秒软件合成夹具逐点核对75000个ECG点和15000个RESP点；改坏波形值或QoS均拒绝。这不是实板或真实云窗验收。默认计划退出0，两个禁用许可CLI负例均按预期退出1，未消费授权。失败原件及历次退出码保留。

[HW准备卡](AUTH-B5-G3-HW-PREP-001-R1.md)、[G3 R4卡](AUTH-B5-G3-CLOUD-WINDOW-001-R4.md)与[现场附件](B5-G3-SITE-ATTACHMENT-R1.md)已冻结；工具、DLL、地址白名单、24个依赖源码及环境SHA见[绑定清单](../evidence/B5-G3-PREP/bindings.json)。实际COM、冷态转接、源/电气完成事实与一次新鲜C只读回执仍缺，私有授权均禁用。未来计划内C人工RESET仅在B/云端观察器就绪后一次，由G3 R4另批，不能现在提前按。

本次软件准备没有连接J-Link/串口或云端、没有发送AT/B5START、没有复位/烧录/改配置，BIO阈值与固件不变。G3 B5START=0，300秒实板云窗NOT_RUN；C最后实测DISARMED，不能冒称本轮重新读到。G1服务本轮未重新查询，17:15:45只是原驻留预计上限，启动前要实时健康和至少625秒预算，不能自行重启。ROM根因、独立冷启动、同窗双有效、阻抗标定和故障注入保留原状态。

最新详细交接见[B5-G2A-SITE-ADMISSION-HANDOFF](B5-G2A-SITE-ADMISSION-HANDOFF.md)，实板配置证据见 `../evidence/B5-G2B-SECTOR3-01/`，服务恢复见 `../evidence/B5-G1-RESUME-01/`。恢复R-CFG→R-APP及R-CLOUD仍各自另批且未执行。

---

## 以下为G0历史检查点

以下“本轮/当前/未授权”均指G0当时；最新进展以上方汇总和各期原件为准，历史不覆盖。

> 本文保留G0阶段结论。负责人后续单独授权的G1-A/HW0/G2-RO实际结果，现以[B5-G1-G2RO-ADMISSION-HANDOFF](B5-G1-G2RO-ADMISSION-HANDOFF.md)交接；本轮G2-A/G2-B/G3仍未授权。

本报告是B5-002唯一阶段交接，不替换历史B4/B5-001原始验收。**G0只读审查已完成；尚不能安装或启动云窗。** 审计详情、真实配置指纹和隔离方案见[B5-G0报告](B5-G0-CLOUD-READONLY-ADMISSION.md)。

## 冻结与已执行

开工远端/本地基线`baa08b850c9bd5e62ace7682a937b9c68423a0fa`，实现`c65fbedce7edf5d822c573ef5cdeb6471d1ae3d5`；本轮源码/文档变更只在`codex/node-b5-cloud-integration-20261026`，不改冻结B5实现。交付提交由本文件所属Git提交及后续远端取回回执定位，避免把自引用SHA写成不可实现的固定值。

唯一42552B BIN SHA `d5b9624b3da1129b4e045d3b2f669c00d2d93cb7379b15293ff143fe9f130683`；ELF SHA `3c726f61f76eadac4909826203ca84dee65521aec448ad477ddca0c3c58795d8`。B39948B/C24104B冻结原件及320份不可变归档复核一致，没有重建/烧录或重新跑现有Host/ARM、本地TLS模型链路、七页UI。

本轮实际动作：只读SSH进程/有效配置路径/源码/ACL/认证元数据/TLS证书；TLS握手无MQTT CONNECT；磁盘恢复布局与保护区比较；19项恢复校验和11项权限拒绝测试，退出0。两次工具前置失败退出1保留，随后成功回执退出0。G0无COM/J-Link/ESP操作、无MQTT发布、无云写入/reload/restart、无Security Gate。

## 真实差异及下一步

1. 8883及外部TLS1.2可达，证书有效；8884未监听。但B5账号/ACL不存在，Backend白名单无GW-B5-001，隔离测试入口未部署。正式服务均保留。
2. 实际Backend Hub缺少已审B5的会话代次隔离，不能仅加白名单。优先专用Backend＋loopback TLS/WSS＋SSH观察，不新增公网端口；公网WSS直达备选需另批独立测试域名/证书及443 SNI站点。
3. 当前C sector3的336B记录CRC有效、B5身份不匹配，不能直接启动或改宏绕过。应用跨sector0/1/2，旧24104B卡不能套用；配置sector3另卡提交，committed最后写，余16048B保留。
4. G0已按C24104历史全片重算离线包，但**FRESH_READBACK_REQUIRED**：须另批新scope的一次非侵入C双1MiB/双16Boptions与身份/配置读回，然后重新绑定包，不能把G0复制/内存重算当新鲜双读。
5. 默认回退目标是本次新鲜C24104＋原sector3。应用回退、配置回退、云专属资源撤销分别批准；恢复历史H3或恢复正式联网均不是默认许可。

[分卡索引](B5-G0-SPLIT-AUTHORIZATIONS.md)：G1云配置、G2-RO新鲜读回、G2-A应用、G2-B配置、G3单次420秒云窗及三个独立回滚对象，全部`enabled=false / owner_approved=false`。当前G2新读回scope/配置写入器仍缺离线验收绑定，卡片不代表执行工具已准入。负责人不批准下一阶段时保持现状。

## 分项裁定

| 门禁 | 当前裁定 | 补证 |
|---|---|---|
| G0 | **READONLY_REVIEW_COMPLETE / ADMISSION_BLOCKED** | 不代替后续许可 |
| B5_SOFTWARE_OFFLINE | **PASS，沿用已裁定** | 本轮不重跑 |
| C_INSTALL | **NOT_RUN** | 新鲜原件、三扇区安装独立批准和实读 |
| SECTOR3_TEST_CONFIG | **BLOCKED / NOT_RUN** | 测试凭据、完整sector3包、专用写入器、独立批准 |
| BROKER_ACL_AND_TEST_BACKEND | **BLOCKED** | 专用账号/ACL/服务/入口未部署；仅TLS子项通过 |
| 300S_E2E | **NOT_RUN / NOT_AUTHORIZED** | G1/G2通过后另批单次B5START；45秒预热＋300秒共同评价 |
| REAL_ROLLBACK | **NOT_RUN** | 新42552B和sector3各自实际恢复证据，不能借旧24104演练 |
| B4_ALGORITHM_REGRESSION | **既有ECG60及独立RR15各自PASS；B5联网负载实板NOT_RUN** | B未改阈值/寄存器，不以云传输代替生理有效性 |
| ROM_ROOT_CAUSE | **UNRESOLVED** | 保留历史原件；本轮不主动复位排查 |
| B4_INDEPENDENT_COLD_BOOT | **NOT_VALIDATED** | 观察/计数差异保留，不签新候选通过 |
| SIMULTANEOUS_HR_RR | **NOT_VALIDATED** | 不同模式/导联两窗不拼成同窗PASS |
| ABSOLUTE_CALIBRATION | **IMPEDANCE_AMPLITUDE_NOT_CALIBRATED_INSTRUMENT_REQUIRED** | 名义ECG参考/增益非绝对标定，ΔΩ/Z0/Zpp仍未知 |
| CONTROLLED_CAN_FAULT_RECOVERY | **NOT_RUN** | 需另批故障注入及恢复窗 |

完整工具/快照/测试/授权卡SHA见[冻结清单](../evidence/B5-G0/G0-bindings.json)。原件、负例与设备身份只存受限EFS，Git不含Flash/options/UID/凭据。正常推送及独立远端取回的实际结果在[交付回执](../evidence/B5-G0/git-delivery.json)记录。未启动三板集成、云端发布或保护分支合并；本轮结束，等待PI分别决定后续G1/G2/G3。
