# B5 C出口第二修正版与单次复测 R2

R1窗口已完成且STOP实测通过，整体NOT_PASS；不复用其安装或START次数。本卡仅准备，须新对象批准及冷态完成事实才启用。沿用R1的全部电气、身份、双读、正常向量、原验收判据和异常停止规则。

## 精确绑定

| 对象 | 身份 |
| --- | --- |
| 新C BIN | 42844B，`086339a05e6a3c03124fd81d41d0c42a1d6b6e52c22e465ae77e401f06485b63` |
| 新ELF | `9a8c9f40caf89e3782d7b585ef1fef889b54b48467fe3b162b07748a1c6ad1fa` |
| 当前R1完整Flash（实测） | `533133d9e7b73b459b65126075e878a571e6b345d0fa58a152d609bc70605d06` |
| 新完整Flash（离线预期） | `1b56bc00b84714c326fe8d75162ee873a7caa7a07c24fa35b30b7e69601c6ea0` |
| 受限恢复包manifest | `20b3c79ff076b4c03b7b1d974b8d805da81787e5da971bb87d9a350ac266baf7` |

修改仅限B5 C出口：完整CAN服务从每1ms改为每5ms，IRQ仍保留原始帧与到达时间，STOP/故障检查仍每次调用执行；JSON固定点编码与原编码逐字节一致，避免逐点通用格式解析。B算法、250SPS、CAN协议/波特率、授时、TLS、QoS、2048B及原共同评价判据不变。主机性能比较不能签实板吞吐PASS。

当前/新应用状态四字节均由各自冻结ELF确定，从`0x2000191A`开始。承接R1必须绑定其真实安装PASS收据；sector3及完整保护区须仍等于gen5原件。工具/源、DLL、包、现场与授权逐事务SHA绑定。

## 独立对象

1. **应用安装**：`B5_C_EGRESS_APP012_UPDATE`，一次连接≤180秒；新鲜双完整Flash/options匹配当前R1、身份/保护正常、Flash运行且DISARMED才Halt≤1。仅sector0/1/2共49152B下载一次，双完整Flash/options及尾部验证；正常Reset≤1、实际PC/MSP向量匹配才Go≤1；新应用正常且DISARMED后正常Close。ESP在板供电例外须本事务批准。sector3/options/ESP固件均不写。
2. **新C预检与回接**：独立C只读一次≤90秒；然后负责人冷态回接B、恢复C USB_UART及B J5，回报COM和源/隔离事实。操作仍为全暗10秒、原方向整只JTAG，不热插、不复位B。
3. **G3一次**：测试云只读检查及既有独立服务预算≥625秒；无需部署或改正式服务。B只读一次；计划内C人工RESET≤1，记录就绪才提示；新启动行和完成回报齐备后B5START≤1。60秒就绪、45秒预热＋300秒评价＋15秒尾段、420秒硬停、419–422秒STOP观察及20秒被动观察均不变。ECG60/1mV、RA–LA–RL、电池隔离、HR58–62稳态有效、RR/TEMP INVALID、A OFFLINE、MOCK/synthetic及原所有数量/完整性判据不变。启动前最多观察原候选已有的两次授时端点失败，不扩大就绪或安全门。
4. **应用恢复（仅准备，未授权）**：`B5_C_EGRESS_APP012_RESTORE`独立一次≤180秒，只从新应用回到本卡当前R1完整Flash `533133d9…05d06`，保留gen5。回到更早42552B/C24104/H3、R-CFG或R-CLOUD仍须各自批准，不自动执行。

冷态转接C：关B/C J5、拔C USB和J-Link电脑USB，全暗10秒，JTAG从B转C；只恢复C J5和J-Link电脑USB，B断电、C USB断开。CAN/参考地/BOOT/ESP/源不动，不按RESET。

ROM/HALT、未知状态、Fault、漂移、短读/native错误或超时立即STOP_TARGET；不强设PC/MSP/VTOR、不重试、不自动恢复。主机退出不能替代ESP停机；异常物理断电沿用R1范围，由负责人执行并回报。所有旧失败和R1新STOP证据保留；完成本轮后统一归档提交。
