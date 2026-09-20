# P 第二阶段测试报告

日期：2026-09-20。基线：总合同v0.7、MPM-P-SOW-002 v0.1；开发分支dev/p-gateway-cloud-v07。

**当前状态：阶段二合同允许的测试节点范围内准出通过。** 使用J-Link烧录、COM15保存日志，最终r8整轮13项硬件检查通过且无解码/来源异常；公开大屏核验通过。ESP运行模式及开发板原始整片Flash已恢复并回读一致。第二轮修复与本阶段代码、文档、证据统一交付到dev/p-gateway-cloud-v07，不合并main。

## 实现

- CANopenNode固定提交9b8beed8367241e96ac03f916cd5a500bcb2cf23；上游53个文件逐项SHA256固定，协议核心未改写。
- A/B独立OD和CANopen实例，经主机虚拟总线及F407真实CAN1静默loopback验证。Gateway承担NMT/HB/RPDO/EMCY/SDO角色。
- 冻结统一字典、OD/PDO、A/B接口；原main已拆分为CANopen Adapter→Canonical→Router→MQTT/缓存。
- 32帧RAM历史、16项按流公平的实时队列；掉电丢失/溢出显式记录，重连先实时后REPLAY。保持原采集时间、序号、会话与synthetic。
- Backend支持历史EMCY在REPLAY区展示；现有大屏无需重构，RR无算法时显示INVALID/空值。

## 已完成验证

| 类别 | 结果 / 证据 |
|---|---|
| 核心协议 | 主机12类检查：栈启动、双节点、NMT、HB、SDO读取、EMCY/清除、独立丢失恢复、Node/Gateway复位、CAN故障恢复；gateway/canopen/tests/protocol.c |
| 模型/缓存 | 主机11组边界检查：PDO数值、连续波形、容量溢出、in-flight失败回存、实时先行、限速REPLAY、时间/序号保持、RR无效、来源恢复、持续负载下历史不饿死；tests/pipeline.c |
| C→Backend | C栈生成41条模型消息，涵盖9个生理流和节点/Gateway状态；Backend按真实Topic/Schema解码，快照仍schema_version1 |
| Backend回归 | 28项通过；新增正常/异常断连日志、LIVE兼容和历史EMCY不覆盖当前报警；2项既有依赖弃用提示 |
| 浏览器 | agent-browser本机夹具4项通过：原UI接收C模型MOCK、同结构LIVE、历史隔离/RR无效、ECG Canvas；公开页面2项通过，实际接收开发板合成流且RR留空；browser-fixture与browser-public分别留存报告和截图 |
| 云端部署 | 两个Backend模块哈希核验，MQTT健康；正常disconnect notice已落盘；原主站及两个既有页面内容哈希未变 |
| 最终硬件 | r8整轮13项通过，74.09s，无解码或来源异常；包含双节点、独立上下线、EMCY、Node/Gateway协议实例重启、CAN故障期间MQTT继续、30s WiFi缓存/实时优先及Broker重启恢复；board-acceptance-r8/report.json与serial.jsonl |
| 恢复核验 | 原始1MiB Flash经verifybin及独立整片回读比对一致，临时配置已清除；ESP CWMODE=2、SYSSTORE=1；restoration.json |

## 故障修复与日志

1. CAN1无法退出初始化：增加RX PA11上拉；使用静默loopback，TX不对外驱动。
2. 小包频率/全部QoS1使串口积压，某些标量被反复挤走：一秒波形批次、两秒标量、五秒状态，实时波形QoS0，按流公平排队；历史仍QoS1。
3. 大批次JSON格式化期间CAN得不到调度：在格式化循环中协作轮询，与AT等待保持一致。
4. 串口测试命令连续发送时后一条丢失：测试工具等待前一条EMCY清除应答后再发重启。
5. 重连时实时队列尚空可能先发历史：增加新实时帧成功后才开放补传的门槛，重连立即生成当前状态。
6. Gateway复位时OD清零被误判为真实LIVE：保留已知synthetic位，等待质量PDO重新建立有效性。
7. 在ESP发送数据时临时复位STM32可能留下AT数据等待态：增加可选`--quiesce`，升级前先让当前固件断开WiFi。已出现的AT不响应须重新上电后复测；没有擅自改ESP固件或未知复位引脚。
8. 用户重新上电后CPU进入系统ROM启动程序，Flash程序未执行：只读核对向量表后，通过J-Link明确设置Flash向量表、栈与入口启动；没有修改Option Bytes。独立上电运行仍需后续核对BOOT0启动选择。
9. r7持续满载时实时队列长期非空，历史一直无法补传：增加至少8条实时/最多1条历史、忙时历史间隔至少2s的调度配额，并新增主机持续负载回归。

完整失败过程保留在gateway/canopen/evidence各attempt目录，不能删除失败记录只保留成功截图。目录README说明每一轮结果；最终成功报告应另存新目录并明确passed=true。

最终日志最后一条指标为can=23048、drop=476、cache=32、lost=226、replay=1；其中CAN丢弃含主动故障注入，RAM溢出如实计数。Broker恢复后观察到第二次补传才结束验收，故最后一次5s周期指标可能早于最后一条补传。该结果验证状态机与有界补传，**不证明波形无损或缓存已全部排空**。持续负载下的发送配额、容量与QoS边界见缓存设计。

硬件构建采用HSI16MHz、CAN500k和单板静默loopback；资源与固件SHA256见evidence/host/build.json。所有测试生产者明确为synthetic。R/G命令重建各自CANopen协议实例，整机启动由本次临时烧录后重新进入Flash程序覆盖；没有模拟物理三板掉电或外部总线电气故障。完整设备反复断电稳定性仍属于后续验收。

## 准出与后续边界

- [x] Gateway-C CANopen栈可运行；双测试节点、HB/NMT/EMCY/PDO、SDO已验证。
- [x] 同一Canonical模型用于MQTT；云端/浏览器兼容LIVE与REPLAY。
- [x] 字典/OD/PDO/接口/缓存设计冻结。
- [x] CAN与WiFi/Broker故障注入和恢复机制已有实物证据。
- [x] 最新修复固件整轮硬件复测无异常来源；公开大屏读取Gateway-C确认。
- [x] ESP运行模式与开发板原始整片Flash恢复/核验。

代码交付与CI状态以[PR #2](https://github.com/Serendipity-min/medical-multi-parameter-monitor/pull/2)本报告所在提交的检查为准；静态报告不提前声明尚未运行的远端CI成功。CI运行Backend回归、固定CANopen核心校验及主机协议/缓存检查、C→Backend兼容检查和现有Web构建，无服务器或设备凭据。

最终系统仍需三个独立实板、外部CAN收发器与布线终端验证、真实四模块传感器、RR真实数据算法、持久启动代际/Flash缓存、端到端应用确认策略和24h稳定性。这些未完成，不属于当前测试节点验证可以替代的内容。
