# R4 TIME/主动关闭修复一次综合增补

状态：软件冻结后待负责人一次确认。本增补不是新的无限测试合同；其余范围、I/L/E/T/R门禁及300秒判据全部继承 `AUTH-B5-C-REPAIR-R4-BATCH.md` 和PI R4合同。

## 已实际消费的对象

原I一次已通过：C48888B，全片 `6d3eee3ed63f6256ff34b415cd3edc04cfdebcd37eec108dba833105bda2dcb8`，sector3/options及保护区不变，独立C只读PASS。原E的START一次在15次查询/15075ms、UTC未有效的TIME门停止，未进入T0。

负责人明确追加的同候选E复验一次也已消费：粗时间这次1次查询/6ms即有效；48B新鲜NTP零回复后，主动CIPCLOSE先返回CLOSED，解析器误判为意外URC而停止。没有TLS/MQTT/300秒评价；两次均不是854B出口失败。TEMP/RR原对象仍0次。负责人随后回报“全部断电”，停止原件已保留。

## 修复范围与唯一字节对象

候选、源清单、BIN/ELF、完整before/after、manifest、工具及恢复绑定见同次冻结的 `node-b/evidence/B5-C-REPAIR-R4/TIME-CLOSE-R1/`。只接受其中唯一 `candidate.json`，不重装47120B或旧48888B冒充新修复。

- CLOSED只有在当前命令主动CIPCLOSE时作为中间URC；仍须末尾OK才确认关闭。无OK、发送中意外CLOSED/ready/busy、部分串口和未知终态仍停止，不盲补发。
- 原15次查询按绝对2秒时隙调度，粗授时准备≤约30秒；60秒共同就绪、1000ms新鲜nonce样本、5000ms严格PUBACK、2048B、420秒均不变。合成19秒就绪例不是本机实测同步时刻；持续无可信时间仍失败。
- 不修改B40928、算法/寄存器/GY配置、CAN、gen5、MQTT库、数据UTC或Backend时效。

## 本次一次确认覆盖的对象

| 对象 | 本增补额度 |
| --- | --- |
| I-TC，沿用安装scope但新attempt/token | C仅sector0/1/2安装一次，180秒。新鲜双全片/options精确匹配当前C48888；实际身份、保护、正常Flash运行、DISARMED先通过，Halt/正常Reset/Go各≤1；写后双全片/options及所有尾部、gen5、sector7/11核验。B不写、sector3不写。 |
| I-TC-RO | 安装后C独立只读一次≤90秒，reset/halt/go/写0。 |
| L | 仅隔离测试环境新鲜只读与TLS/CONNECT/SUBACK/WSS就绪；若仅两个原unit按RuntimeMax到期且所有冻结条件相符，各start≤1，不修改ACL/HUP/正式服务；每窗实际预算≥625秒，准备余量另计。 |
| E-TC `B5_FINAL_ECG60_R4TC` | 新ECG60一次，B只读≤1、C人工RESET≤1、B5START≤1；45秒预热＋300秒评价＋15秒尾段、420秒业务硬停。 |
| T-TC `B5_FINAL_TEMP_OBJECT_R4TC` | 未消费温度对象重绑定至同一新候选，一次B只读/一次C RESET/一次START；非人体固定物表。 |
| R-TC `B5_FINAL_RR15_R4TC` | 未消费RR对象重绑定至同一新候选，一次B只读/一次C RESET/一次START，沿用既有冷态RR源/导联操作。 |

各对象独立真实计数，不复用已消费token；三窗必须属于同一新候选。SDK/主机准备问题在START前可按R4规则安全修正；发送过START的失败不自动再发。没有额外诊断START或无限复位额度。

恢复包只准备新候选→本次安装前C48888全片 `6d3eee3e…da2dcb8`，**默认禁用、须明确选择条件后另行执行**；不是自动恢复C46584/H3/C24104。部分写或未知镜像不能套用成功镜像恢复包。原R4的C46584恢复资产继续保留，不串用。

## 一次人工准备和停止

负责人一次确认上述确定字节包、ESP在板供电例外及新增额度后：保持B/C J5关闭、C USB及J-Link电脑USB拔下，全暗10秒；仅将整只JTAG从B转C，方向不明就停；只恢复C原J5和J-Link电脑USB，B断电、C USB断开，不按RESET。CAN/独立地/BOOT、ESP、温度和源/导联不动。完成后回报冷态事实；安装/只读/L通过后集中说明回接B步骤，不逐条重新申请。

ESP例外只表示获准在板供电，自主联网状态仍UNKNOWN。ROM/HALT/Fault、字节/身份漂移、电气异常、原生SDK错误、未知AT边界、TLS/正式服务异常或420秒失控立即STOP_TARGET；负责人按预批方法断B/C J5、C USB及J-Link电脑USB。停止目标后继续离线研究，不自动恢复。

原始失败、TIME原文、末尾STOP、五层原码/日志、真实退出及“本轮尚未300秒”结论不覆盖。只在新候选冻结或三窗/授权外真实阻塞时集中交付，唯一报告仍为 `B5-C-REPAIR-R4-FINAL-HANDOFF.md`。
