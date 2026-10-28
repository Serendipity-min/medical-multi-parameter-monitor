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
