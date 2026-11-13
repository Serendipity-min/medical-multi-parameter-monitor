# P5 真机合成 Smoke / Wi-Fi 恢复与全片恢复报告

## 当前结论

2026-10-08，按用户已确认并再次要求继续的 COM15/J-Link 硬件窗口完成：
**B01 合成 Smoke PASS、B02 Wi-Fi 恢复 PASS、B04 完整 Flash 备份/恢复 PASS**。
P5 全阶段仍为 **HOLD**：H16 动态资源对照尚未完成，统一 Security Gate 未授权，PR #6 保持 Draft。

受测 HEAD：`c51af827d61e68c395ffed982623253a1e345a37`。该提交归档 AT 复核，没有修改固件源码；
实际 ELF/BIN 与 P0 验证版本相同。本轮没有修改 Gateway、Router、模型、CANopen 或 Cloud 代码。

| 合同检查 | 实测结果 | 证据边界 |
|---|---|---|
| B01 | PASS | F407 两个 CANopen 合成节点 → CAN1 静默 loopback → ESP AT/TLS → Broker → Backend |
| B02 | PASS | 本机 D 故障命令；30 秒断网；真实 LWT OFFLINE、恢复 ONLINE、实时优先及 REPLAY |
| B03 | NOT_AUTHORIZED/NOT_RUN | 没有停止、重启或修改生产 Broker |
| B04 | PASS | 两轮均重新双读 1MiB、临时固件/312字节配置校验、原1MiB完整恢复及独立回读 |
| H16 | PARTIAL/NOT_RELEASED | 有静态资源及本轮 P5 恢复时间；CPU/Stack/CAN延迟及P4真实对照仍缺失 |
| Security Gate | NOT_AUTHORIZED/NOT_RUN | 普通测试及硬件窗口不构成统一门禁授权 |

## 执行与可复核身份

- AT 前置条件由[独立复核](P5_ESP8266_AT独立复核报告_20261008.md)确认；历史 STOP 和原始分析保留。
- 现有 J-Link5.12，SWD4000kHz、STM32F407ZG UID 门禁；串口 COM15 / 115200，打开前禁用 DTR/RTS。
- 每轮临时写入前重新双读完整 Flash，与既有原程序备份逐字节一致；下载后 reset-halt 恢复正常线程上下文。
- 程序地址 0x08000000，配置地址 0x080E0000，配置仍312字节；配置和Flash dump只保存在仓库外私有目录。
- 保持 AT/SYSSTORE=0/STA/SNTP/CA_VERIFY/CCN/SNI/SSL:8883 的既有顺序；实际日志显示这些步骤通过。
- MQTT CONNACK=0；MQTT3.1.1、15s keepalive、clean session、原 Client ID/认证、publish-only 均沿用同一受测源码。
- QoS1 仍经过匹配 PUBACK 才允许 Router 成功 ACK；本次未增加真机错号/延迟 ACK 注入，相关负向覆盖仍由既有 Host/Broker 测试提供。
- Broker观察者跳过初始3条 retained；仅接受 `synthetic=true` 且 `session_id=can-*` 的本轮合成数据。
- Backend使用既有外部WSS浏览器配置和首帧Token鉴权，只读观察；没有使用旧设备入口或修改云端服务。
- `physical_nodes=false`、`real_patient_data=false`。没有修改BOOT0、Option Bytes、ESP固件、client_ca/client_key。

固件摘要：

- BIN：35552字节，SHA256=`fd81076b9b34ad0a8f4ee35c08cd7ea14704f6d7b04620741cdf083c9c6c1069`。
- ELF：SHA256=`c5eb2278669fe520c391c0e4dc69a13539686d724bdff6724cc4cc041e3f9a35`。
- BIN/ELF 位于 `E:/medical-monitor-p5/P5-coremqtt-baremetal/gateway/mqtt/build/`，未提交产物。

## Smoke 结果

两轮均成功连接并验证双节点持续合成数据；第一轮SNTP首次检查失败后正常重试通过，首条有效帧26.234秒。
第二轮首条有效帧7.218秒。时间从测试器启动标记计算，包含J-Link启动开销，不能视为冷上电或CPU性能数据。

- NODE-A：SPO2=97.0；PPG 50个样本、50Hz。
- NODE-B：TEMP=36.7；ECG 250个样本、250Hz；RESP 50个样本、50Hz；RR保持 `INVALID`。
- 每轮至少10条有效ECG消息，固定模型校验通过；Backend只读快照确认双节点有效读数及RR INVALID。
- 第二轮Broker记录85条本轮消息：MOCK79、REPLAY6；包含两节点、Gateway状态及完整9个业务流。
- 本轮未见固定 `GW ASSERT_FATAL`，但未主动触发assert，不能将故障停机路径记为真机验证完成。

## Wi-Fi 恢复结果与测试器修正

第一轮于北京时间16:08:37开始。Smoke通过后，测试器只等待25秒OFFLINE，提前超时退出本项。
该轮标为 **B02未完成**，保留全部诊断及恢复结果，不能用后续成功覆盖这一记录。

第二轮于北京时间16:13:16开始，仅调整仓库外测试器：OFFLINE观察覆盖60秒，成功判据仍要求
真实OFFLINE→ONLINE、实时优先及Backend恢复；重复Backend快照按帧身份去重。固件、30秒D故障行为和MQTT参数完全相同。
第二轮OFFLINE在D后27.375秒到达，解释了此前25秒观察期限的不足；并非重新放宽合同中的功能判据。

以下均相对本次发送D命令的标记，主机时钟粒度15.625ms：

| 观察事件 | D之后 |
|---|---:|
| Broker收到LWT OFFLINE，seq=4294967295 | 27.375s |
| 第一条恢复的VALID MOCK消息（包括节点状态） | 35.797s |
| Broker收到Gateway ONLINE | 36.031s |
| 第一条有效业务遥测（NODE-A PPG） | 36.234s |
| 第一条恢复补传（NODE-A PR / REPLAY） | 37.219s |
| Backend OFFLINE | 27.438s |
| Backend ONLINE | 36.156s |

第一条有效业务遥测先于REPLAY 0.985秒。REPLAY保留较早采集时间、会话和序号；合成标志保持true。
Backend观察到 ONLINE→STALE→OFFLINE→ONLINE，且收到本轮REPLAY。STALE为等待LWT期间的既有过期语义。

最后固定计数：`can=20200 drop=0 cache=32 lost=203 replay=5 nodes=11`。
其中 `drop` 是CAN传输计数，`lost` 是Router缓存淘汰计数，两者含义不同。30秒断网使原32帧RAM缓存满载，
并淘汰203帧；这符合现有有界缓存路径，**本次不能声称断网数据无损**。恢复窗口仅观察了首批补传，未证明缓存全部排空。

## 原 Flash 全片恢复核验

两轮结束前均用本机D命令等待Wi-Fi退出，再临时使用诊断桥清理连接；恢复ESP CWMODE=2、SYSSTORE=1及原回显设置。
MODE/STORE查询核验通过；没有把这些有限查询称为所有ESP RAM参数的完整快照恢复。

两轮都完整恢复原1,048,576字节Flash（包含sector7），VerifyBin通过；独立整片回读与本轮双读备份逐字节一致。
原Flash、写入前双读和恢复回读SHA256均为：

`852d7618f8fc46c80cbe035ebd41f4e21e4d5a76a26cf10a39e0600f7a89ffb8`

恢复后COM15被动监听再次观察到DMA_ADC输出。第一轮总耗时98.766秒，第二轮79.453秒。
这是J-Link引导运行及完整恢复证据，未执行断电冷启动验证。

## 证据、资源与剩余事项

机器证据：[hardware-smoke-wifi-20261008.json](evidence/hardware-smoke-wifi-20261008.json)。
包含两轮实际报告、固定串口状态、合成元数据、Backend状态转换及原文件/执行辅助脚本SHA256。
Backend原始重复快照元数据完整保存在私有目录，公共JSON去重以便审查。

私有目录均位于 `C:/Users/Serendipity/.codex/private/p5-hardware-20261008T061416Z/`：
`functional-window-20261008T080837Z`（首次观察超时）、`functional-window-20261008T081316Z`（重试通过）。
辅助脚本在 `E:/medical-monitor-p5/`；每轮私有目录保留执行版本、备份、回读、固定日志和元数据。

| 静态资源（字节） | 同工具链P4 | 本轮实际P5 |
|---|---:|---:|
| .text | 29676 | 35048 |
| .data | 88 | 88 |
| .bss | 87300 | 87348 |
| RAM含24KiB heap / 8KiB stack预留 | 120160 | 120208 |
| BIN | 30180 | 35552 |

资源原始来源为[P0资源证据](evidence/p0-resources.json)，本轮固件摘要与之逐项一致；静态RAM仅增加48字节。
CPU、stack high-water、最大单次MQTT等待、CAN协作延迟仍NOT_MEASURED；没有P4真机恢复对照，
不能判定重连增幅是否超过20%，H16及资源准出保持待审。

仍待：H16完整动态对照、真机assert故障路径、冷启动条件、另行授权的统一Security Gate及工作流修复、负责人最终PR准出。
生产Broker故障B03仍未授权。PR #6保持OPEN/DRAFT，未合并P4，P6未开始。
