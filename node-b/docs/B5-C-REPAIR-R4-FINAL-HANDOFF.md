# R4当前综合交接：真实ECG300秒完成，诊断证据不足；C49048待一次增补

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
