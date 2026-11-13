> 当前R4修复与后续实板交接统一见 [B5-C-REPAIR-R4-FINAL-HANDOFF.md](B5-C-REPAIR-R4-FINAL-HANDOFF.md)。以下保留本报告历史结论和原件，不作为新R4安装或PASS证据。

# B5最终综合阻塞报告与唯一下一步｜2026-10-29

**当前结论：NOT_PASS，尚未完成三个300秒实板窗口。** 软件离线测试通过不能替代本次验收。最后已读回部署是B40928/C46584（全片707d…ca4a）；C47120只是尚未安装、尚未获批的诊断候选。ECG这次在预热结束前失败，TEMP/RR的本轮START均未消费。当前物理断电未得到完成确认，不能声称设备已安全封存。

本节优先于下文保留的R1软件冻结快照；本文件是本阶段唯一综合报告，原件及原授权对象不覆盖。

## 实际完成与失败时间线

| 事务 | 真实结果 |
|---|---|
| C43036→C46456 | 一次受批sector0/1/2安装PASS，写后双全片/options匹配，正常Flash及DISARMED；独立只读PASS |
| C46456首窗 | START1，约18秒粗TIME失败，无MQTT/评价；不据此判断永久NTP故障 |
| 负责人续批的一次复验 | 新鲜NTP53ms/不确定度26ms通过，之后出现新启动横幅；负责人明确报告误触RESET，故记为人工中断，不归因CPU或软件自动复位 |
| C46456再窗 | 粗时间通过，新鲜NTP received=0/rtt=1009ms严格拒绝；发现本补丁fail-fast截断了原端点轮换的回归 |
| C46456→C46584 | 纠正上述回归后受批安装一次PASS；正常Halt/Reset/Go各1，写后双全片/options和独立只读PASS，gen5/所有尾部不变 |
| 跨夜续包 | 原两测试unit确为6小时timeout、PID0、Restart=no；正式PID/配置/ACL未变。PI另批后各start1，严格TLS/Backend就绪；C再次新鲜只读PASS，不重烧 |
| 2026-10-29准备1 | C未上电导致无COM6，SerialException，START0/B连接0；负责人纠正C上电后CH340 COM6正常，原件保留 |
| 准备2 | MQTT观察连接断开，START0；B未见ROM/HALT，取消退出前核验Flash运行、close_resume=true。只读90秒观察复验通过、4组以上PINGREQ/PINGRESP；不能据此确定原瞬断根因 |
| C46584实际ECG窗 | START1，新鲜NTP69ms/不确定度34ms、CA/证书名/SNI/TLS及五层就绪通过；在C业务53.919秒时UNSYNCED并停止，**未开始正式评价** |
| TEMP/RR | 本轮NOT_RUN；没有为补齐数量盲发其他START，也未切换RR源或导联 |

本轮两笔实际C安装均保留当前原件、新鲜双读、真实返回、独立关闭回执及恢复包。没有写sector3、改B固件/阈值/ADS/GY配置/CAN、修改正式云、合并保护分支或运行Security Gate。跨夜云服务恢复仅两个已存在的独立测试unit，各start一次，无ACL/HUP/正式服务操作。

## 当前能确定的原因

### TIME并非每次必现；新鲜UDP失败与粗TIME分开

粗TIME失败指15次模块时间查询未得到符合minimum_epoch的UTC，发生在新鲜nonce UDP/TLS之前。旧代码未保存启用命令和每次查询原始回复，无法反推是0时间、ERROR还是解析拒绝。随后实物完整NTP53ms、69ms均通过，证明不是每次必现；不能以两次观察推断长期故障概率或永久根因。

R1的fail-fast确实截断了原`fresh_sntp()`失败后由外层重新进入、轮换既有端点的机会，这是已确认的软件回归。已部署R2只恢复“48B完整发出、零回复、UDP已关闭、AT同步”时最多两次启动前轮换，新nonce、原端点、1000ms/60秒/420秒不变；粗TIME、部分包、错误nonce、关闭失败和UNSYNCED仍停止。实际69ms窗口没有消耗该失败额度。

### 当前唯一实板主阻塞：C发送终态缺失，机制尚未确定

最新源STOP为`tick=54500, armed_at=581, reason=2, phase=UNSYNCED(6), required=854, written=854, pending=1, live=24, cache=7`，业务经过53919ms。共同就绪在START后16.375秒，因此只完成约37.544秒预热，距离45秒预热门仍差约7.456秒，300秒评价没有开始。

最后发送耗时4091ms，C已写完854B但未确认SEND OK。不能把“UART写完”当ESP接受或Broker收到；也不能将此值直接命名为原生5000ms超时。源码允许QoS1待确认时QoS0使用剩余PUBACK预算，但旧日志没有逐包传入预算、pending age和AT回复特征，当前无法区分预算影响、ESP/TCP迟滞、连接关闭/忙/模块重启或终态解析问题。没有证据支持“B算法丢失”“UART/CAN错误”或“增大缓存就能解决”。

此前已记录SEND OK最大257ms、MQTT发送最大364ms、匹配PUBACK最大274ms；这些只是成功样本的最大值，不能作为失败包的耗时保证。故障前live高水位6，未见UART/CAN错误；故障时live24/cache7，停止后将未发live转入历史，cache31。`dropped=0`不能据此宣称没有时效失败或全程实时完整。

本次C没有在UNSYNCED后盲发CIPCLOSE，B取消退出前确认仍正常Flash运行。C业务停止不证明ESP已离开数据/连接状态；负责人未回报全部断电，ESP自主网络状态和最终物理安全末态仍UNKNOWN。后续目标操作必须先完成受批停机与冷态准备。

### 观察器还有独立证据缺口

保存的Broker观察原件为264条；Backend受理计数从3到270，增量267，拒收/丢弃0。多出的3条没有完整观察原件，可能包含Broker Will等状态，**不能直接称为C丢了3条，也不能宣称267条均已逐层同会话核验**。Broker原配置为`connection_messages=false`、无逐连接/逐包信息，未擅自改正式日志配置来补造历史。

原MQTT断开回调先锁存失败再退出，队列末尾原因码可能未落盘；已修正最终队列保存和主动/被动断开区分。最新失败中云端观察在START后48.75秒后不再新增，缺最终cloud回执，线程末态为`UNKNOWN_SUPERVISOR_MUST_END_PROCESS`。这与C终态缺失时间相邻，但不足以确认同一个网络原因。

已将健康检查从后台线程的多阶段等待改为单次总时限（常规3秒、最终1秒），保留严格TLS/HTTP200/Content-Length界；WSS关闭1秒、SSH等待有界，清理开始即存checkpoint、最后队列/断开码及最终完成分别保存。原设备420秒及主机总限没有扩大。真实隔离测试健康检查0.937秒通过、自有隧道关闭；4项截止/关闭回归及58项联合工具测试通过。当前未发现存活的本测试18775转发SSH进程，但不追认失败会话曾正常关闭。

短窗里Broker观察到HR37条（4条启动期INVALID、33条VALID且均60）、RR37条均INVALID、非人体TEMP37条均VALID/22.89–23.07°C；这支持短时语义独立传递，不是任何300秒通过，也不是温度绝对精度。

## 已完成的最小补证方案（未执行新实板）

1. 当前先由负责人完成全板断电确认。以后只按独立新对象冷态转C、fresh双全片/options、正常Flash/DISARMED后安装，ROM/HALT/漂移不强行恢复。
2. 使用唯一R3诊断候选，只新增失败时数字证据：等待原因、回复长度、CLOSED/ready/busy观察标志、实际预算/耗时/写数、QoS/stream/seq/pending age。不输出敏感原始载荷，不改变成功发送路径、判定、缓冲或TLS/时间门。
3. 先只开启一个新的ECG60窗口，仍45秒预热＋300秒评价/420秒硬停；以失败seq和五层原件区分“实际已到Broker但终态未确认”与“尚未交付/模块连接异常”，同时取得有界观察器收尾。失败不补发，不先命名根因。
4. ECG完整通过且各独立对象获批后，才顺序进入非人体物表TEMP和RR15，各一个START；原数量/时效/INVALID判据不变。不能用目前短窗或旧算法/基础CAN通过替代。

具体批量建议、精确对象和禁用模板见[待批R3方案](AUTH-B5-C-EGRESS-DIAGNOSTIC-001-R3.md)。没有新增实板安装、START或恢复许可，全部新模板默认拒绝，未复用已消费token。R3不是已确认根因修复，更不提供“下次必过”的承诺。

| 最后核验部署/唯一待批产物 | 精确SHA256 |
|---|---|
| B40928 BIN / 全片 | `a1cf57648ca3787de30c1ad7055634c278fbbde538bb0bc562961bd212182ed2` / `ceebec5a91835aed3cb70c683fd8de5142e5ba59a2163a1968cec182018b48ae` |
| 实装C46584 BIN / 全片 | `d01d08c23de3fbdc6639609136cacc6c0da0eda1fc4489bad8273829a2200e7a` / `707d88987431cb4cdf4580d8f627ba58eea4980429d95fc6dcde6ceb8718ca4a` |
| 待批C47120 BIN | `edd2bb8db2632993bf4fae5d577c1aa967e943884f2ebdc8b40d52710b08db88` |
| 待批C47120 ELF / 源码清单 | `32909b34625f965c785fa59b8cf9b48d1ad14bcdcc1bb47660c07bad1463938b` / `504b86effe2ea6d08fedc86c300b02d258e84ab97735cb4b306b05d3b6db27ba` |
| 待批预期全片（非实板结果） | `ffd814e16f6cc947fbf336c73abccfd3fcd7aa19e804dd1dbb54900a7c0e8a77` |
| 待批包manifest | `bde330d3b8d84d4b7c49ba73e6f135a684bd1833358cfe52097695e6b80565f3` |

R3两次ARM BIN/ELF一致，47120<49152B；`.data`88B、`.bss`73636B、heap24576B/stack8192B预留、额外RAM24576B、最大单函数静态帧968B。新R3实板栈水位NOT_RUN；实装R2短窗观测上界2488B，不代替新候选/全窗验证。R3的真实platform MMIO测试覆盖静默、CLOSED、ready、busy、SEND FAIL和原部分写/STOP场景，仍严格区分未知边界、已知失败与成功。

R3→C46584回退资产已按旧双份原件离线重建精确一致，sector3/options及全部尾部不变；实际恢复NOT_RUN。C43036/46456/46584及更早H3、gen5恢复资产全部保留，完整镜像和UID/私有配置仅EFS。C46584源码在诊断编辑后另按全部91个构建SHA归档，其中三处从已验SHA旧源/精确逆向诊断补丁恢复；不把事后未校验源码当成部署来源。

两个独立测试unit按另批各启动一次，最近只读正常；测试账户/ACL未撤销，不能称整个环境已清理。正式云端没有写操作。物理停机仍未确认；历史CPU ROM根因、独立冷启动、同窗HR/RR、阻抗/温度绝对精度及CAN故障注入继续独立未完成。`B5_THREE_MODE_NONHUMAN_E2E_ENGINEERING_PASS`、`B_TO_C_ENGINEERING_STAGE_CLOSED`均**不得签发**。

本轮真实原件SHA、交易与失败账、软件/ARM/负例回执见`../evidence/B5-C-EGRESS-FINAL-R1/`、`R2/`、`R3/`。以下是先前软件冻结时点的历史快照，不代表最新部署或实板结论。

---

# R1软件冻结快照｜2026-10-28（历史）

本合同的软件修复及离线验收 **PASS**，唯一新C候选为 **46456B**，尚未安装。三个新实板窗口均 **NOT_RUN**，验收裁定均为 **NOT_PASS（尚未执行）**；不能签发 `B5_THREE_MODE_NONHUMAN_E2E_ENGINEERING_PASS` 或 `B_TO_C_ENGINEERING_STAGE_CLOSED`。

本轮没有连接实板、复位、Go、发送AT、烧录、写sector3、发B5START或操作真实云服务。物理断电仍为 **NOT_CONFIRMED**，不把主机进程结束当作设备停机。最后已核验部署仍是B40928/C43036；这不是今天重新读取的实时身份。

## 来源与历史事实

工作区为 `E:/medical-monitor-node-b5-cloud`，唯一分支 `codex/node-b5-cloud-integration-20261026`。软件修复前逐文件核对C43036构建记录的83个源文件/头文件SHA，零漂移；从这些本地源码重新构建得到与已部署43036B完全相同的BIN和ELF。远端 `25e5863d948b5140764341572f97e769650db0bb` 仅作旧参考，没有拿它覆盖温度扩展。

初次基线归档因Windows路径分隔符筛选错误复制了0个源文件，已纠正；83个文件全部以原构建SHA逐字节确认后归档，包括两份经过精确逆向补丁还原、SHA完全匹配的文件。不能把首次空目录当作有效归档。来源与精确补丁见 `../evidence/B5-C-EGRESS-FINAL-R1/baseline-audit.json`、`compiled-source-sha256.json` 和 `C43036-to-candidate.diff`。

既有EFS原件保持不变：最新实际ECG评价有74993个连续ECG点、14999个RESP源点，Broker/Backend各2893条，Backend拒收/丢弃0；2845条MOCK、48条REPLAY，保存的WSS中72个快照ECG/HR不全有效、19个Node-B STALE，故原实板结果仍NOT_PASS。原Hub按保存服务时钟回放复现72个无效和18个节点失效，边界差1个不能替换原19个。温度首窗AT失败、冷态补窗TIME失败，RR新组合尚未执行，原始回执均保留。

已核实最大Broker观察间隔2.516秒，以及约100秒附近两次约1.5秒停顿。原记录没有逐包enqueue、提示符、数据、SEND OK、PUBACK时间，相关细分阶段为 **UNKNOWN**。这些观察间隔不能写成单次原生AT耗时，也不足以认定PUBACK是全部实板停顿的唯一根因。

## 最小C修复

1. `router.c/.h`：确认C43036已有B五路流FIFO，未误套旧单槽实现。新增状态优先、标量/波形有界轮转，保留原seq/session/UTC及真实REPLAY语义；记录生成、出队、历史化、覆盖、过期和高水位。将原live16/history64重新分配为24/56，总共仍80个MpFrame，未倍增缓存。队列驻留按入队单调tick计算，源年龄另计。
2. `egress.h`、`gateway_transport.c/.h`：固件和TLS回放共用实际发送推进函数。最多一个QoS1在途，只有匹配当前packet ID的PUBACK才能确认；等待期间可推进QoS0波形。错、迟、重复、前会话ACK均不能释放新消息，原5000ms超时不变。
3. `platform.c`：发送返回实际字节数，区分COMMAND/PROMPT/DATA/SEND OK及UNSYNCED。开启事务前检查原5秒事务及2秒收尾预算；部分命令/载荷或未知边界不盲发CIPCLOSE，清空RX也不能清除UNSYNCED。`mqtt_transport_adapter.c`审查后保持不变，继续完整向量发送、精确短写及2048B限制。
4. `network_main.c`、SysTick：最后8秒停止开启新事务，给原事务和关闭留预算；业务锁存仍是420000ms，没有延长。SysTick只记录源tick/原因/状态，主循环完成关闭与输出；初始化/网络失败有界退出，不继续盲重试。观察器保存同一串口块的全部原字节，不再因先见WRITE_SEND_FAIL而丢掉后续STOP。未来最终窗口同时要求原主机观察门及独立MCU源STOP证据。
5. 诊断只用有界计数、直方图及周期摘要。九阶段覆盖命令、提示符、数据、SEND OK、JSON、MQTT发送、PUBACK、队列驻留和源年龄；分位数是直方图上界，不冒称精确原生分位。另有8项温度入口追踪环，按源seq/报告UTC另记C入口UTC，溢出有lost计数。没有逐ECG点串口日志。

B40928、GY-641V3配置/解析、ECG/RESP算法阈值、ADS寄存器、CAN协议与接线、gen5均保持本合同前的部署设计。Git本次包含此前尚未提交的温度扩展源码及历史回执，不能因此宣称本合同又改动了B。TLS CA/SNI、可信时间、1000ms新鲜NTP门、60秒联网门、QoS1 PUBACK、MOCK及2048B均未降低。

## 离线验证与边界

| 验证 | 实际结果与限制 |
|---|---|
| C43036精确源码重建 | BIN/ELF与原部署记录均相同，退出0 |
| 原容量控制 | 相邻1500/1500ms及2516ms停顿，旧16/64出现9条历史/回放，HR最大年龄8516ms；未发生丢弃 |
| 仅容量控制 | 旧调度改24/56，在本组有限模型中也无历史回放；HR最大3271ms，状态3518/3599ms。不能声称容量对照必失败，或异步是唯一解释 |
| 完整修复压力 | 同样三次停顿及300秒生产模型，live最高24；ECG749批、RESP299批、HR/TEMP各299；无新增覆盖/历史/过期/丢弃，状态最大3152/3283ms |
| QoS及AT负例 | 真实coreMQTT推进QoS0不清除QoS1；原5秒ACK边界，错/缺/部分/重复/旧ACK、短写、断链与重连等退出0；真实platform.c的MMIO测试覆盖四个发送停止阶段，DATA实写3/需12，不盲关闭；6000ms不足5秒事务+2秒关闭时UART零写 |
| 实际入口420秒 | 正常、在途、tick回绕均锁存420000ms；溢出提前失败、联网失败立即锁存而不重试；各退出0 |
| Python工具 | 安装21、窗口26、复核6、STOP4、温度入口5、联合58、串口确认6，共126项通过，真实退出码均0 |
| ARM | 新候选两次构建BIN/ELF完全一致；CAN1/CAN2/USART3向量核对通过，未引入应用Flash写函数，退出0 |

压力模型中115200串行化、15ms AT固定成本、40ms ACK及受控序列化成本是明确的测试夹具参数，不是实板测得的分段耗时。真实过载负例仍明确产生历史/丢弃，不被包装成实时PASS。原有算法六窗和基础CAN没有重复验收。

本地端到端使用真实coreMQTT v2.3.1、独立严格TLS Mosquitto、实际Backend/Hub及WSS；发布推进代码与候选共用。取真实原码对应的2654条遥测，另以受控5秒周期产生状态，合计Broker收到2816、Backend接受2816/拒收0/丢弃0；2019个加速WSS快照无非预期STALE，源值/UTC/session/seq一致，温度入口408项/lost0，live最高18，JSON最高841B。已有最坏值JSON1492B/整包1534B边界保持。TLS回放注入1500/1500/2516ms停顿，Host另覆盖相邻停顿。

该回放是**软件反事实对照**：旧158条状态保留在历史审计里，新受控状态不是补造旧丢包；未观测到的旧C入队时刻仍UNKNOWN。2019个加速快照不替代实板300秒及≥2900快照判据，PC TLS不替代ESP实物TLS。期间失败的模型/测试日志保留；较早本地TLS失败版本尚无finally原始载荷归档，不能宣称那些失败运行的每个Broker/WSS原字节均已保存。历史硬件原件不受影响，最终工具已在finally保存后续原始证据。所有本地自建进程/连接已关闭。

历史408个有效温度报告中，旧时间关联规则只能对应329条UART帧，另79条相同值出现在旧报告锚点后1060–1522ms；这表明旧报告UTC不足以精确锚定测量时刻，不证明79次传感器错误。新C入口追踪用于未来逐条关联，仍要求2500ms新鲜度及原2ms相位界；缺项/失配/lost非零失败，不放宽旧门、不补写旧PASS。没有绝对温度参考，任何通过仅是非人体物表数据链路。

## 唯一候选、源码和资源

| 对象 | SHA256 / 大小 |
|---|---|
| 新C BIN | `1771ee61bde1fda9543ff7d056311d1602719d842552ce09dd7dece4aa19937e`，46456B |
| 新C ELF | `e618de6a266f3527fb2089b698a1c54d5f47c2b3be9444bc5a19f389bcbf3807` |
| 符号表 | `ab7e41ae2881c7bc507661d4b191200db1c7ce2117e0642ed5541c304fc96090` |
| 编译源码清单 | `951a26bad3c05d3eed2150ad198470ef8c7ad8363a9bb9b8dd857df955c26f6c` |
| C43036原BIN | `28af9628f428403cc479293adf748e57b68c82a8444458a5ca8de43f311f36d4` |
| C43036原全片 | `3369c5de14c2f81b37a2ca3a684ac80c65a2b50c63aba9e3ee892a074bb84fbd` |
| 新预期全片（非实板结果） | `b9e7518ec2af1b780534a97e769054630e19b6a4600800a6db2dea98b8f675ea` |
| options不变 | `52d5979da03bd7be45e385920ec7d5901793bab3f6bc1daa0c1c1997f9e91687` |
| 安装/恢复包清单 | `fca23d45a29cb0725599a4675c9c1266e39d39f74976550f8ac1bacf6ec4f607` |
| 私有应用绑定 | `67ddb7a9f444fab70f40e8473bdaadae5ac0c9771fc4281bb8c54718c8a6092b` |

构建入口 `python gateway/dual_can/build_arm.py --b5 --egress-final`。实际编译器、参数、83文件及新增头文件SHA见归档receipt和公共源码清单；源码交付提交为包含本报告的B5提交，以清单绑定编译内容，避免把报告自引用SHA当作二进制来源。中间45988/46440等仅是保留的开发产物，不是部署候选。

实际ELF `.data`88B、`.bss`73612B，预留heap24576B/stack8192B，除此之外SRAM余量24600B；最大单函数静态栈帧960B，router35312B。静态帧不是调用链峰值。候选包含栈水位观测，但**实板栈高水位NOT_RUN**，必须在后续授权窗口实测。BIN小于49152B，安装仍限sector0/1/2，不触sector3。

## 恢复资产与待批对象

受限EFS中保存唯一BIN/ELF、83文件基线、原C43036双份全片及options、49152B安装/恢复段、全片预期和私有身份绑定。离线拼接验证新全片及精确回退C43036通过；≥0x0800C000、sector3/7/11及options不变。这里只复用已封存双份记录生成资产，不冒称今天重新读取。**实际恢复演练NOT_RUN**，备份成功不等于恢复通过；不自动回退H3/C24104或原正式联网。

安装/回退卡：[AUTH-B5-C-EGRESS-FINAL-APP-001-R1.md](AUTH-B5-C-EGRESS-FINAL-APP-001-R1.md)。独立UPDATE/RESTORE scope均默认禁用，实际执行前须新鲜双1MiB/options、私有身份、正常Flash运行/DISARMED和具体电气事实全部匹配。一次sector012安装≤180秒，正常Halt/Reset/Go各≤1；ROM/HALT/漂移即STOP_TARGET，不自动恢复。ESP在板例外须本对象明确批准。

三个窗口卡：[AUTH-B5-C-EGRESS-FINAL-THREE-WINDOWS-001-R1.md](AUTH-B5-C-EGRESS-FINAL-THREE-WINDOWS-001-R1.md)。`B5_FINAL_ECG60_R1`、`B5_FINAL_TEMP_OBJECT_R1`、`B5_FINAL_RR15_R1`分别独立token、目录、次数和START≤1；当前均disabled/owner_approved=false、允许START数0。模板负例确认在目标操作前拒绝。真实安装/独立只读及新现场附件未落实，不能解锁窗口。

三窗各保留45秒预热、300秒共同评价、15秒尾段、420秒硬停、60秒共同就绪、1000ms可信授时、原数量及时效判据。ECG60/HR58–62且RR无效；物表TEMP≥295条有效且逐层对应真实UART；RR15在RA–LL–RL下RR14–16有效、无QRS时HR必须无效。共同要求B/C/Broker/Backend/WSS原码、实际同会话逐层一致、Backend接受=去重Broker、无新增回放/覆盖/丢弃/过期/错误STALE及严格源STOP。温度和RR不能借ECG窗签PASS。

| 新窗口 | 执行状态 | 验收状态 | 缺少的真实证据 |
|---|---|---|---|
| ECG60 | NOT_RUN | NOT_PASS | 新C实际安装及新300秒五层实收/STOP |
| 非人体物表温度 | NOT_RUN | NOT_PASS | 新入口追踪与真实UART→五层共同窗 |
| RR15 | NOT_RUN | NOT_PASS | 经批准切源/冷态导联及新300秒五层共同窗 |

## 末态与最小剩余方案

真实测试Backend/TLS、ACL账号及正式服务当前状态 **UNKNOWN（本轮未连接核验）**，没有自动启动、恢复、撤销账号或宣称清理完成。新C尚未部署；旧设备的CIPSEND/STOP和物理供电不能由本地测试反推。候选网络初始化失败已改为有界停止，但未更改授时功能；同一实际ESP启动上下文的可信时间及新鲜NTP仍是未来窗口前置，先前冷态TIME根因没有因此关闭。

下一步仅需PI批准准确C应用安装对象及三个独立窗口，然后一次收集当前电气/探针/供电附件，完成新鲜备份→安装→独立只读→逐窗执行。云服务到期恢复、物理停机及各恢复对象保留独立批准。某窗失败停止该窗，继续离线分析，不能自动消耗下一START。

历史CPU ROM根因UNRESOLVED、B40928/新C独立冷启动NOT_VALIDATED、同窗ECG/RR NOT_VALIDATED、阻抗绝对标定NOT_CALIBRATED、温度绝对精度NOT_CALIBRATED、CAN故障注入NOT_VALIDATED均独立保留。既有算法与基础CAN通过结论不变。没有修改保护分支、进入三板集成或运行Security Gate。

公共证据及工具SHA统一在 `../evidence/B5-C-EGRESS-FINAL-R1/`，敏感原件、固件及完整恢复数据留在受限EFS。本报告是本次唯一收尾报告，旧报告仅保留历史并指向此处。
