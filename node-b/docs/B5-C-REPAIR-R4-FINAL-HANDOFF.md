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
