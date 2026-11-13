# 最新交接｜2026-10-29，三路实板验收未通过

唯一综合结论与下一步见[B5-C-EGRESS-FINAL-CLOSEOUT.md](B5-C-EGRESS-FINAL-CLOSEOUT.md)。最后核验实装B40928/C46584；ECG因完整854B发送后SEND OK未确认而提前停止，TEMP/RR未执行。C47120是待批诊断候选，尚未安装，根因未确定。物理断电未确认；测试账户未撤销，不能称全部封存或阶段通过。以下内容仅保留历史。

---

# B5综合结论与最小收尾方案｜2026-10-28温度扩展后

本节为当前状态；以下历史段落和原件保留，不能用旧39948B/42552B部署描述代替当前B40928B/C43036B。当前未完成三路云验收，不能签发B5_E2E_ENGINEERING_PASS。

| 对象 | 真实结果 | 证据边界 |
|---|---|---|
| B温度接收 | PASS，15秒内新增69个有效协议帧、59次观察 | GY-641V3、UART4 PC11接收；不发模块配置；非人体物表温度，非临床体温、无绝对温度标定 |
| 最新ECG60共同窗口 | 完整300秒采集，严格NOT_PASS | 74993个连续ECG源点、14999个RESP源点；Broker2893=Backend接受2893、拒收/丢弃0；STOP420.093秒，各采集进程退出0 |
| ECG新鲜展示 | NOT_PASS | 全窗2845 MOCK/48 REPLAY；REPLAY为ECG17、RESP5、HR6、RR10、TEMP10；评价内72个WSS快照ECG/HR不全有效、19个B节点STALE |
| 温度首个云窗 | 联网准入失败，未开始评价 | START1，GW FAIL AT；B退出续跑确认，失败原件保留 |
| PI新批冷态温度补窗 | 联网准入失败，未开始评价 | 新START1；AT/GMR/Wi-Fi/AWAKE/PASSIVE通过，GW FAIL TIME；未进入TLS/MQTT/共同评价 |
| RR15新候选云窗 | NOT_RUN | 未切换源、未消费RR START；旧B4独立RR通过不替代本次新B/C组合云验收 |

## 当前身份及恢复

B40928B BIN `a1cf57648ca3787de30c1ad7055634c278fbbde538bb0bc562961bd212182ed2`，实板全片 `ceebec5a91835aed3cb70c683fd8de5142e5ba59a2163a1968cec182018b48ae`。原B39948B与安装前全片备份保留，B仅sector0/1/2按已批准事务安装一次。

C43036B BIN `28af9628f428403cc479293adf748e57b68c82a8444458a5ca8de43f311f36d4`，实板全片 `3369c5de14c2f81b37a2ca3a684ac80c65a2b50c63aba9e3ee892a074bb84fbd`。本次温度扩展只安装sector0/1/2；gen5 sector3/options/sector7/11保持，C43036→C42880及更早原件恢复方案保留，未实际恢复、未签恢复演练通过。私有全片、配置、身份、原码只在既有受限EFS，不提交Git。

## 三处问题分别判断

1. **已证明的输出排队问题。** 约ARM+100秒前实时队列仅1–2条、历史0；两次约1.5秒交付停顿后，ARM+104.578秒实时13、历史5，随后出现REPLAY。全窗最大Broker观察间隔2.516秒。B采样及C CAN继续推进，C UART/溢出/丢弃/MQTT失败计数无增量；不能再称B算法失效或原码值传错。单次1.5秒是接收观察间隔，不能当每次AT原生耗时。现有tx_ms只是最后一次发送耗时，不能唯一分解ESP、Wi-Fi、TCP、Broker及PUBACK等待。不得未经对照认定路由器或TCP Nagle为根因。
2. **停止后AT失联存在代码路径，但本次根因未定。** platform.c的send_bytes在业务420秒到达时可立即返回；若处于CIPSEND指定长度数据阶段，ESP可能尚等剩余数据，后续CIPCLOSE/AT不保证作为命令执行。这是可达机制，不是本次ESP实际状态的证明。冷态补测AT恢复，说明当前模块能响应，不证明上次必由此路径触发。没有原始ESP回复时，GW FAIL AT也不能区分ERROR、超时和UART错误。
3. **冷启动TIME门失败已定位到前置阶段。** 候选在启用默认SNTP后最多15次SYSTIMESTAMP查询，达到minimum_epoch才执行已有新鲜UDP/NTP校验；本次在这个前置门失败，新鲜包函数未到达。历史直接48B新鲜NTP595ms通过，并不证明本次冷启动内置SNTP已更新。此次日志未保存每次查询原文，不能断言是无回包、DNS、返回格式或时间值不足。不得设置人工UTC、放宽1000ms门或关闭TLS校验。

官方对应ESP8266 AT v2.3.0.0资料确认：省略服务器的CIPSNTPCFG启用会使用默认服务器；不等于明确绑定历史已验证端点。文档见[SNTP配置](https://docs.espressif.com/projects/esp-at/en/release-v2.3.0.0_esp8266/AT_Command_Set/TCP-IP_AT_Commands.html#at-cipsntpcfg-query-set-the-time-zone-and-the-sntp-server)。本轮未新增AT诊断、未修改服务器。

## 唯一建议方案：保留B与接线，收敛C网络改动后一次批量复验

顺序固定，不继续重复相同START。先在离线环境完成C出口/停止状态的最小修正和可归因记录，准备一版候选；再申请一次应用安装和三个分路窗口的批量对象授权。尚未生成或安装这份未来候选，本节不是新Flash/START许可。

- **启动前授时准入。** 用已有有界工具保留SNTP启用返回、配置读回、时间变化及新鲜48B NTP原码。只有真实UTC有效、新鲜样本满足原1000ms完整门才进入TLS/G3。若内置SNTP仍不更新，先明确绑定可用端点作单变量验证；不能靠电脑人工时间绕过。G3本身60秒就绪和420秒门不延长。任何调整候选授时流程须另冻结并批准，不冒称现有C已修复。
- **C出口调度。** 优先验证并拆开当前同步QoS1等待占用：单个在途ID与5000ms/PUBACK严格门保留，等待期间推进CAN及可发送业务；状态心跳避免排在积压波形后导致STALE。先用实测1.5–2.516秒停顿和真实入流构造离线正负例，记录发送/确认阶段耗时和队列高水位。队列容量由实测突发与ARM RAM约束确定，不能只扩大缓存、把历史标MOCK或放宽Backend5秒时效制造PASS。ESP原生AT等待也可能阻塞，异步QoS1本身不保证解决全部停顿，须用阶段耗时证明收益。
- **420秒收尾。** 保持原业务STOP时刻；在业务门前预留原有单事务上界，避免启动跨越硬停的CIPSEND。已有在途串口数据状态与停止清理分别取证，未知状态不盲发CIPCLOSE，也不自动复位ESP。离线覆盖停止发生在命令、提示符、数据、SEND OK和PUBACK阶段的情况。
- **一次批量复验。** C安装/回退预案绑定当前全片3369…fbd；不重刷B、不改sector3和算法。前置通过后按ECG60→非人体物表温度→RR15顺序，每档45秒预热+300秒评价、420秒硬停，R–LA/R–LL由负责人按既有冷态步骤切换。保留现有数量、MOCK、INVALID、同会话及五层实收判据，任一未通过如实登记；不合并为同窗ECG/RR通过。

## 当前停止与档案

TIME失败后没有再连接目标、发AT、复位、Go、烧录或START。负责人要求先分析方案；物理断电尚未回报完成，因此记录为NOT_CONFIRMED，不声称安全封存或SNTP已关闭。测试服务有驻留上限，测试账号未撤销；未动正式服务、ACL、保护分支或Security Gate。历史CPU ROM根因UNRESOLVED、独立冷启动/同窗双通道/阻抗绝对标定/故障注入保持原状态。

公开核对摘要及SHA：[本次分路证据](../evidence/B5-SEPARATE-CHANNELS-20261028/manifest-sha256.json)；前几版完整失败/安装/STOP回执见[出口修复历史](../evidence/B5-EGRESS-CLOSEOUT-20261028/result.json)。所有原失败保留，无采后放宽判据。当前只完成本地汇总，未以未完成的三路验收结项推送。

---

# MPM-B5-FINAL｜最终工程评价及综合阻塞报告

2026-10-28；独立分支`codex/node-b5-cloud-integration-20261026`；起点`9db588819c1a06511d852d6529f8622269643173`。

**裁定：`B5_E2E_ENGINEERING_NOT_PASS`，不签发`B5_E2E_ENGINEERING_PASS`。** 替代窗口已采得45秒预热后的300秒共同评价。B采集、C实收计数及实际Broker→Backend→WSS接收均有证据；C出口队列损失使完整性不合格，终态收据也未通过冻结的监督门。以下为本轮唯一综合报告，不以软件修复重写历史失败。

## 已完成的对象

| 对象 | 实际结果 |
| --- | --- |
| gen5真实sector3写入 | PASS；同事务双份1MiB before/after、双options及保护核验，约110.906秒，Halt/正常Reset/Go各1；启动DISARMED、Close通过 |
| C gen5独立只读准入 | PASS；实际全片匹配gen5，`DISARMED=00000000` |
| 独立测试云恢复 | PASS；只启动已因6h超时停止的backend、tls各一次；真实CA/SNI/TLS、Broker CONNECT/SUBACK、Backend健康和WSS鉴权通过 |
| 首个G3 | START一次后新鲜NTP门失败；主机观察器提前退出，原始失败保留 |
| 替代批量包 | PI另批；B只读观察到Flash HALT，有条件Go一次后ADC推进；未复位B。随后仅一次C人工RESET和一次新START，采得完整300秒评价 |
| 原部署恢复/撤云 | R-CFG、R-APP、R-CLOUD均未执行；保留当前C42552B＋gen5，未恢复C24104 |

gen5实测全片SHA256：`a5239d616523621593b5e76fd70212aa199e72603b85e359492d642448fff528`。C候选仍为42552B，BIN SHA256 `d5b9624b3da1129b4e045d3b2f669c00d2d93cb7379b15293ff143fe9f130683`；B仍为39948B，BIN SHA256 `676eb7a46ad9cd15c7bf93db51a1931d7711d37c6f2fd636197dc4a85b339b82`。本轮不改应用BIN、BIO_V2阈值、ADS寄存器、CAN协议、正式云配置或保护分支。

## 300秒评价的五层证据

| 层次/判据 | 本轮真实观察 | 裁定 |
| --- | --- | --- |
| B原码及算法 | 稳态保存600次观察，HR全部60且有效；RR全部无效；采样率249.98748SPS，clipped增量0 | 本窗口B端满足 |
| B ADC/CAN | bad_status、SPI/队列/init/长间隙均无新增；B CAN overflow/expired/comm_reset/error/discontinuities增量0；CAN1 ESR无错误 | 本窗口检查通过 |
| C CAN/出口 | 稳态rx增加89973、txack增加619；txfail/overflow/uart_err/mqtt_fail增量0；**router dropped增加1251**，cache持续达到64，终态累计dropped1690 | 出口完整性FAIL |
| B→Broker波形 | 已收到的177个ECG批次和136个RESP批次可严格映射回实际B CAN队列及ADC原码，映射错误0 | 收到子集值正确 |
| ECG覆盖 | 实际可映射17651点，要求≥74250；源序列存在150处缺口 | FAIL |
| RESP覆盖 | 实际可映射6789点，要求≥14850；源序列存在110处缺口 | FAIL |
| HR标量 | 125条，均VALID/60，要求≥295；其中115条MOCK、10条REPLAY | 数量FAIL |
| RR/TEMP标量 | RR124条、TEMP116条，均INVALID且值null，要求各≥295 | 语义正确、数量FAIL |
| Broker→Backend | Broker唯一消息1194；实际Backend accepted增量1194、rejected=0、dropped=0；最大JSON载荷844B，未越2048B缓存 | 收到子集已接受 |
| Backend→WSS | 评价期2974张快照，Gateway及Node-B均ONLINE；5544次有效条目值比较无错值、无Broker缺失键 | 子集同会话实收 |
| 大屏时效语义 | HR有2570张VALID、404张STALE；RR/TEMP在INVALID和STALE间切换，无虚构有效数值 | 保留失效语义；HR全程有效未达 |

点数采用原冻结匹配函数与源UTC评价范围，包含捕获到的REPLAY，是完整性诊断的宽松上界；即使计入这些点也远未达到门槛，不能当实时无缺口覆盖。Broker来源为MOCK1062条、synthetic REPLAY132条，没有真人LIVE来源；REPLAY不冒充新鲜实时值。

C层没有完整逐条CAN载荷记录，本轮不能据rx/ACK计数声称每个TPDO均无丢失。已有B端正常发送、C队列满及丢弃增长、收到子集原码映射正确、Backend零拒收/零丢弃，共同把主要阻塞定位到**C出口排队/发送能力**。同步ESP/MQTT发布与“每流保留最新项、旧项进入64槽历史缓存”的策略在当前实网负载下不足；尚无正常逐包send/PUBACK分段耗时，不能进一步唯一归因于UART、ESP固件、TCP或具体网络延迟。

## 首窗失败、工具修复和停止证据

首窗记录`GW SNTP_REJECT reason=2 received=0 rtt_ms=1003 server_index=0`，表示同一请求在原1秒门内未累计48B回复；SEND OK不代表服务器收包。冻结C已有420秒内轮换端点的路径，旧观察器却在第一次该行即停止全部观察。只读补证随后见C自行联网并发布状态，但Node-B OFFLINE，无ECG/HR，不能补成正式评价。

首窗B工具因主机STOP退出，`close_resume=false`；新连接实读`DHCSR=0x00030003`、VTOR为Flash、Fault为0，暂停时PCSR全F不是真实PC。PI另批后，原恢复工具核对UID、完整Flash/options及真实PC/MSP，Go恰好一次、ADC推进，201次SDK调用、退出续跑通过。暂停是在重新连接后被观察到，不能据此确定发生在Close还是Attach，更不能用它解释历史ROM。

已修复两处主机路径：新授权可在60秒共同就绪门内观察最多两次明确的初始`SNTP_FRESH_SAMPLE`失败；TLS/身份/错误及原1秒、420秒门均保留。B收到纯主机取消时，只在SDK健康且补充CPU只读核验正常后设置Close续跑；ROM/HALT/native错误不Go。47项定向回归通过；首次47项有2项Mock导入缺失错误，修正后通过，失败原件保留。未重跑旧Host/ARM、TLS/UI或算法矩阵。

替代窗口本次NTP直接通过：163ms、uncertainty81ms、配置索引0，TLS/MQTT及新会话共同就绪成功。不能把首窗归结为该索引永久不可达；当前主要阻塞已转为出口完整性。

末尾串口有`GW WRITE_SEND_FAIL`，终态为`mqtt_fail=1 stop=1`。源代码硬停会中止在途发送，随后进行有界TLS关闭；观察器先按错误计数抛错，未解析同一原始数据后的STOP行。**原始串口尾部确有一次`B5 STOPPED NO_AUTOREARM`**，但没有该行独立到达时戳；终态诊断被处理在START后约422.125秒，原冻结观察上限为422秒。不能据此证明原420秒业务停止及其监督界限全部合格，也不追补伪造成功收据。

B正常捕获退出0、close_resume=true，退后未再独立观察CPU；监督器以`MCU_STOP_NOT_CONFIRMED_MANUAL_ISOLATE`退出1，联合完成收据未生成，原冻结review返回`G3_REVIEW_STOP`、退出1。独立诊断脚本退出0仅表示原件分析完成，仍裁定NOT_PASS。事后只读WSS确认Gateway/Node-B均OFFLINE，不作为435秒内OFFLINE的追溯证据。

## 最小剩余工作

1. 修复C实时出口吞吐与排队：至少承载ECG2.5包/秒、RESP1包/秒及HR/RR/TEMP各1条/秒，再加状态消息；当前稳态C的QoS0成功增量245、QoS1确认599，明显不足。保留100点/250SPS、50点/50SPS、QoS语义、2048B及原数量门，不用扩大缓存或把旧帧标新鲜来掩盖损失。先利用本轮原码/日志作定向分析，再冻结必要的C小补丁及新BIN；应用安装/恢复和下一次窗口须新对象批准，本轮不自行重刷。
2. 补齐硬停证据链：业务STOP锁存/时间证据与TLS清理结束分开；主机应保留同一读块的完整STOP事件，避免终态中止发送计数掩盖日志。原420秒业务门保留，不事后扩大422秒观察界限来签本次通过。

无需重复算法准确率、B CAN驱动、gen5生成、云部署、已通过的TLS/Backend接入或完整旧软件矩阵。现有实测已经排除“完全未连云、Backend拒收、JSON越界、收到值换算错误、B采样率受阻”等路径；最小待改对象是C出口能力及停止可观测性。当前授权的两个START、替代批量包3次B连接及一次Go均已消费，不自动追加第三窗。

## 部署、恢复与归档状态

按负责人“当前不断电”指示，板卡保持供电，未进行物理断电封存；C原始STOP证据及事后WSS离线已保存。C仍保留42552B＋gen5，B39948B未改；R-CFG/R-APP/R-CLOUD均NOT_RUN，**未恢复原C24104**，也未恢复正式联网。gen5→gen4和gen5→原gen3→C24104原件均保留，实际恢复未演练。历史H3不是当前默认恢复目标。

G3候选曾请求启用ESP内置SNTP，业务STOP路径仅关闭业务连接，未取得`CIPSNTPCFG=0`关闭回读。因此不能声称ESP全部网络活动已停止；本轮不越权追加AT或断电，物理封存仍待负责人正常停机。

两个测试unit仍运行并受既有6h驻留管理，测试账号/ACL仍存在、未撤销。事后只读复核正式服务活跃、PID及全部冻结配置SHA不变，8884未监听；未改正式GW-C-001、Broker、ACL、Backend、Hub、Nginx、AI或云防火墙。之后正常停机或撤销测试资源使用对应负责人明确动作，不自动执行R-CLOUD。

全部原码、配置/完整Flash/options、真实工具版本/退出、失败及源码快照在受限EFS。公开证据为`node-b/evidence/B5-FINAL-20261028/`；私有位置由本机忽略指针`node-b/build/b5-final-pointer.json`定位，不提交UID、凭据、地址、原始配置或BIN。

CPU ROM根因、B5独立冷启动、同窗ECG/RESP双有效、绝对阻抗标定及CAN故障注入维持独立UNRESOLVED/NOT_VALIDATED/NOT_CALIBRATED状态；既有ECG和独立RR名义六窗结论保留。未合并P4、未触碰保护分支、未启动Security Gate。当前以本综合阻塞报告结项本轮执行，不宣布B5验收通过。
