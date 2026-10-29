# R4 单次批量现场包：I / L / E / T / R

状态：候选离线冻结后申请，尚未启用。本卡由 `MPM-B5-C-REPAIR-R4-EXECUTION-CONTRACT` 管理；唯一候选身份见同次提交的 `node-b/evidence/B5-C-REPAIR-R4/candidate.json`，各私有对象绑定本卡SHA、工具SHA和各自一次性令牌。不得使用47120B诊断候选。当前B40928/C46584，两板已供电，J-Link在B、USB在C，接法不变（负责人本轮回报）；安全断电及冷态转接未完成。

负责人一次确认本包，明确继续沿用本批ESP在C板供电的非隔离例外（自主联网状态UNKNOWN），并完成下述准备后，I/L/E/T/R正常门禁连续执行，不逐对象重复申请。任何未完成现场事实不填写true，已有授权不重复消费。

| 对象 | 次数、范围与条件 |
| --- | --- |
| I `B5_C_EGRESS_APP012_UPDATE` | 一次、180秒。仅C sector0/1/2 `[0x08000000,0x0800C000)`；同连接新鲜双1MiB Flash/双16B options，真实身份、正常Flash运行、DISARMED、保护及C46584全片SHA严格匹配。Halt/正常器件Reset/Go各≤1；新BIN尾部采用原件。双全片/options、向量、gen5、sector7/11和DISARMED复核。任何异常即停，不重擦、不自动恢复、不强设PC/MSP/VTOR。 |
| I-RO | 安装后C独立只读一次≤90秒，reset/halt/go/写均0；正常运行、完整镜像、配置和DISARMED通过才准入。 |
| L | 使用既有测试环境只读核验；仅两个已知独立Backend/TLS unit因原RuntimeMax到期停止且全部配置/权限/PID前置相符，允许各start≤1，总限300秒。每窗预留≥625秒实际云预算（现场准备另留180秒）；真实TLS、CONNECT/SUBACK和WSS鉴权齐全。禁止ACL/HUP/正式Broker/正式Backend/Nginx/AI改动，不开放8884。 |
| E `B5_FINAL_ECG60_R4` | B只读一次，C实体RESET≤1，B5START≤1。普通ECG60/1mV、R→RA/L→LA/F→RL-N/LL空；ECG≥74250点、HR58–62且有效≥295条。TEMP真实独立，RR保持实际语义。 |
| T `B5_FINAL_TEMP_OBJECT_R4` | 独立B只读一次、C实体RESET≤1、B5START≤1。GY-641V3不改配置/接线，固定非人体物表无绝对参考；有效温度≥295条、2500ms源龄及原2ms源点映射，不声明医学体温或绝对精度。ECG/RR按实况。 |
| R `B5_FINAL_RR15_R4` | 独立B只读一次、C实体RESET≤1、B5START≤1。负责人按已有冷态方法将黄L由LA移至LL/F，R仍RA、F仍RL/N，LA空；电池呼吸15bpm/1.5R/周期30bpm/窒息0。RESP≥14850点、RR14–16且有效≥295条；无QRS时HR INVALID。 |

三窗各45秒预热、300秒共同评价、15秒尾段，≤60秒建立T0，420秒业务硬停；人工准备300秒、唯一新DISARMED行确认RESET、按后30秒内START。保持5000ms严格PUBACK、1000ms新鲜NTP、2048B、原采样率/来源/UTC/Backend时效。各窗一个新session、目录和`.used`，失败不消费下一窗，不追加START。

目标失败后只读被动尾段最多5秒，且不得跨原START后440秒被动上界；主机常规及最终健康检查有总deadline，原监督器445秒上界不延长。未知AT边界不盲发CIPCLOSE；STOP必须保存源tick/reason/phase/pending与真实到达时间。目标停止未确认，负责人立即关B/C J5并拔C USB及J-Link电脑端USB；主机结束不等于MCU/ESP停机。

数据范围仅GW-B5-001、非人体MOCK/synthetic，A段、INMP441、TTS及人体断开。所有实际输入流保留。Broker实收、Backend去重接受及WSS必须一致；retain/Will、观察基线和末尾单独记账，差异不能补造。任何新覆盖/溢出/过期/丢弃/REPLAY替代/错误STALE/发送失败/质量伪造均不通过。

## 人工操作集中步骤

**安装准备，仅在负责人确认本包后：**关B/C J5，拔C USB及J-Link电脑USB，确认板、ADS、两屏和ESP全暗，等10秒；整只JTAG从B转C（方向不明即停）；只恢复C原J5和J-Link电脑USB，B断电、C USB断开，不按RESET。CAN/独立地/BOOT/ESP/温度PC10、PC11/源及导联不动。一次回报全部完成、无异常及ESP例外。

**I/I-RO/L通过后再回接：**同样全暗10秒，JTAG从C转B；恢复C J5、C USB_UART/USB232（不用USB_SLAVE）、B J5，观察B屏约10秒后接J-Link电脑USB。一次回报实际COM、屏刷新、无异常、ECG60/1mV、电池无充电USB、RA–LA–RL、各隔离条件和可即时断电。工具记录就绪后才提示本窗唯一C RESET，不要求聊天回复作为START时间门。

T窗前只确认非人体固定物表；R窗前一次集中说明冷态换源/导联及重启记录步骤。禁止LL/RL短接或RLD接地。B不重刷、不用调试Go/复位掩盖异常。新出现ROM/HALT、Fault、身份/字节漂移、电气异常、原生SDK错误、TLS/正式服务异常或协议边界未知时STOP_TARGET，继续离线定位。

## 恢复与收尾对象

`B5_C_EGRESS_APP012_RESTORE`仅作为本包可选择的一次健康、完整已知新候选回退对象：sector0/1/2恢复本轮C46584，目标完整SHA `707d88987431cb4cdf4580d8f627ba58eea4980429d95fc6dcde6ceb8718ca4a`，180秒、双全片/options、DISARMED与正常入口验证。**默认不执行**；部分写或未知Flash不能用本恢复卡。不是H3/C24104恢复，sector3/options不写。

通过默认保留新候选/gen5后按约定安全断电。账号/ACL不自动撤销；测试unit到期不代表环境清理。本包未包含共享云R-CLOUD撤销或额外诊断START。最终结论只依据同一候选三窗及安全末态；CPU ROM、同窗HR/RR、阻抗/温度绝对标定、CAN故障注入原样保留。
