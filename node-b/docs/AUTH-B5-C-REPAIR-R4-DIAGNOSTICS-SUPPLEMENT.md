# R4诊断调度修正：一次综合补包

状态：离线冻结，等待负责人一次批准；不是已消费TIME/CLOSE包的自动续跑。PI原R4合同、原批量包的安全、时效和数量门槛全部保留。

## 原窗与最小差异

C48988已实际安装、独立只读PASS。ECG60本次完成300秒评价和420秒STOP：75012个ECG源点映射一致，B保存600条且HR全60，Broker=Backend=2838、拒绝/丢弃0，WSS2974。总判定仍NOT_PASS：主诊断19条、最大间隔18.375秒，队列证据不足。TEMP/RR的START均未消费。负责人随后确认全部断电熄灭。

新C49048B只改变`network_main.c`的诊断调度：主诊断和队列按固定5秒时隙优先输出，已过时隙跳过且不伪造历史记录；温度入口按已有待记录项每安全空档最多输出一行，保留原8项容量和全部历史遗漏计数。仍避开在途QoS1、deferred和AT不同步状态。其他细项继续低频分阶段输出。不修改网络协议、时间、B、CAN、算法、配置或验收条件。

BIN SHA256：`dedca0f4b0de6fb5d00e8e339020f982093e0e4509732a71c77e9c2edf2032bd`。

ELF SHA256：`1842e111adac0e421a68e37f076abf79c308819c59b3e56d6b2aeb67ac37e52e`。

唯一字节、源码、资源、工具、完整before/after及恢复包身份见`node-b/evidence/B5-C-REPAIR-R4/DIAGNOSTICS-R1/`，该目录冻结后不能静默替换。前镜像必须为实装C48988全片`9799f39c731ce0dd33eba00749f945db1255a887939f88a924b6908405392873`。不是C48888、C46584或H3的安装卡。

## 一次批准覆盖的独立对象

| 对象 | 次数与边界 |
| --- | --- |
| I-D | C sector0/1/2安装一次，180秒。新鲜双全片/options、私有身份、正常Flash运行、保护、DISARMED和精确before先通过；Halt/正常Reset/Go各≤1。写后双全片/options和精确after、sector3/7/11及其余字节复核。B不写，sector3不写；异常不重擦、不自动恢复。 |
| I-D-RO | 安装后独立C只读一次≤90秒，reset/halt/go/写0，DISARMED及正常运行通过后继续。 |
| L-D | 原隔离测试环境只读和真实TLS/CONNECT/SUBACK/WSS就绪，每窗预算≥625秒另留准备余量。只有原两个unit按既定RuntimeMax到期且全部冻结条件一致时，各start≤1。不改ACL、不HUP或重启正式Broker，不改正式服务，不开放8884。 |
| E-D `B5_FINAL_ECG60_R4D` | B只读≤1、C人工RESET≤1、START≤1。ECG60/1mV及RA–LA–RL；45秒预热、300秒共同评价、15秒尾段，420秒业务硬停。 |
| T-D `B5_FINAL_TEMP_OBJECT_R4D` | B只读≤1、C人工RESET≤1、START≤1。GY-641V3固定非人体物表，无参考、不宣称绝对精度；其余窗口时限同E。 |
| R-D `B5_FINAL_RR15_R4D` | B只读≤1、C人工RESET≤1、START≤1。沿原批准冷态方法换为RA–LL–RL，独立RR15/1.5R/周期30/窒息0；其余时限同E。 |

三窗必须绑定同一新候选，各用独立目录、token、session和真实五层原件。C诊断≥58条、间隔≤8秒，队列证据≥58条；不得因为本轮修取证而降低要求。ECG≥74250点、RR≥14850点、标量有效≥295条、WSS≥2900、2500ms温度源龄和原2ms映射、5000ms严格PUBACK、1000ms新鲜NTP、2048B、60秒共同就绪和420秒硬停均不变。

同一窗口B/C/Broker/Backend/WSS的源、值、序列、时效和INVALID独立裁定。QoS0/SEND OK/PUBACK不替代云端实收。不得重写UTC、MOCK或Backend时效。原ECG48988失败不追补成新候选通过。

## 现场准备与停止

负责人一次批准本确定字节包及ESP在板供电例外后，按当前全部断电状态全暗10秒，整只JTAG从B转C；只恢复C原J5和J-Link电脑USB，B断电、C USB断开，不按RESET，其他线/BOOT/ESP/源不动。方向不确定即停。完成事实回报后才执行I-D。

I-D/只读/L通过后统一提示冷态回接B、C USB_UART及B J5；记录就绪才提示每窗唯一C人工RESET，以新DISARMED行当场确认START，不等待聊天回报。T前确认固定非人体物表；R前集中提示原冷态切源及黄L由LA移LL/F，其余R→RA、F→RL/N，禁止LL/RL短接或RLD接地。

ROM/HALT/Fault、身份/字节漂移、电气异常、原生SDK错误、TLS/正式服务异常、AT边界未知或420秒失控立即STOP_TARGET，保留原件并继续离线研究。不自动Go、复位、重发START、重刷或恢复。失败不消费下一窗；正常停止也不自动复用START。全部会话结束后按预批方法关B/C J5、拔C USB及J-Link电脑USB、确认全暗。ESP自主联网仍UNKNOWN，不能称已隔离。

## 回退与交付

只准备新C49048→本次before C48988的精确sector0/1/2恢复，默认禁用，另有明确对象批准才执行；部分写、未知Flash不使用成功镜像回退卡。sector3/options不写。不恢复H3或默认正式联网。

唯一报告仍为`node-b/docs/B5-C-REPAIR-R4-FINAL-HANDOFF.md`。历史CPU ROM、独立冷启动、同窗ECG/RR、阻抗/温度绝对标定、CAN故障注入状态不因本次通信通过而改变。测试账号未撤销，测试unit到期不代表云环境已清理。
