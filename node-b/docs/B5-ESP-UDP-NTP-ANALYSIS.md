# B5｜ESP侧单包UDP/NTP取证分析

日期：2026-10-27（北京时间）。负责人确认模块未变，明确免除重复开发板识别和全片哈希。本轮只执行单包取证及分析，未重开G3。

**裁定：ESP接受了一次48B发送，但本次记录未捕获NTP回包；socket已关闭。不能签UDP端到端授时通过，也不能唯一认定路由器过滤或内置SNTP故障。**

| 观察 | 实际结果 | 证据边界 |
|---|---|---|
| 前置网络状态 | SNTP关闭、CIPMUX=0、CIPRECVMODE=0、CIPDINFO=false、STATUS=2且无既存socket | 主动接收模式，保持原配置，没有重新入网或修改服务器 |
| UDP打开与发送 | 固定既有第二目标IP:123；CIPSTART OK、提示符到达、一次48B载荷、SEND OK | ESP接受载荷不等于NTP服务器已收到，未做无线/AP抓包 |
| 主动/被动接收 | 未见主动+IPD数据；一次CIPRECVDATA=48返回ERROR；收到NTP包0 | 主动模式下该ERROR不能独立作为链路失败证据，完整主动观察同样没有包 |
| RX记录覆盖 | 载荷后到接收、关闭、最终状态各阶段RX头未记录字节均为0 | 没有用记录间隙跳过已到达UART的回包；仍不能证明网络更晚永远不回包 |
| socket收尾 | CIPCLOSE OK，CIPSTATUS回到2且无连接 | 本次socket关闭已证实，不依赖主机程序退出推定 |
| MCU最小收尾 | Flash运行、DISARMED、无Fault，正常关闭SDK | UID/Flash数据/options显式读取0；未做新整片完整性复核，不冒称该复核PASS |

接收主观察窗为2秒；载荷UART写完后约0.437秒记录到SEND OK，约3.281秒记录到关闭，约3.718秒完成最终状态查询。这些是主机/SWD观测时点，不是精确线缆RTT。没有回包，因此nonce/LI/version/stratum/时间校验为**NOT_RUN_NO_REPLY**，没有补零或制造NTP样本。

第一次执行在发包前因主机解析器只接受CIPDINFO:0、未接受等价false而停止：socket打开0、载荷尝试0、退出1；原始回执保留。这是主机解析过严，不能当作模块故障。修正后继续尚未发送的同一单包许可，另存执行记录且不重用旧.used。跨记录独占payload marker只消费一次；修正记录worker/监督均退出0，总载荷尝试1。该单包许可已经消费，不自动再发。

实际UART_DR的221个字节已从原生API日志离线重建，与冻结计划逐字节一致，其中NTP载荷只有48B一次。该检查没有再访问实板。没有UID/整片Flash/options读取、设备镜像哈希复核、reset/halt/go、Flash写入、模块时间写入、BIO_V2阈值变化、B5START或正式云访问。

与此前电脑侧对照合看：同一目标此前能返回有效NTP包，本次ESP没有捕获回复，但两次路径和时间不同，不能合并成同步网络对照。直接UDP也未证实取得回包，故不能仅凭“内置SNTP未更新”就把问题唯一归给内置SNTP；也不能把单包无回复直接签成路由器永久封UDP123。仍缺ESP请求是否离开AP、服务器/返回路径是否有回复的证据。

下一项有判别力的补证是另行批准的同窗AP/路由器LAN/WAN UDP123抓包，记录ESP源端口、固定目标和本次nonce，并做紧邻电脑对照；普通电脑网卡未必能看到其他Wi-Fi客户端的单播，不能冒充AP侧抓包。本轮未访问或更改路由器，也没有重发请求。

正式G3依然未启动，不能以本次SEND OK代替UTC、TLS、Broker、Backend或WSS接受。下次还需重新核实独立测试服务的到期状态和驻留预算；本轮没有启停服务、撤销账号或改变ACL。

原始请求、完整AT字节流、SDK返回及两个执行记录均在受限EFS。安全摘要与来源见[实际回执](../evidence/B5-ESP-UDP-NTP-01/result.json)，[原件归档](../evidence/B5-ESP-UDP-NTP-01/archive.json)。当前J-Link在C、C原J5、B断电、C USB_UART断开；主机会话已关闭，C收尾DISARMED。CPU历史ROM根因继续UNRESOLVED。
