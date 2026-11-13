# A_CANOPEN_RELIABILITY_HANDOFF

A1 软件阶段完成，未上板。实现提交 `b12c19604197d0d7b3e6e195c33c7d27d281616a`；联合 Host 验证发现并修正第五 TPDO 子索引后的最终 Node-A 提交为 `e1516c33aab8fd6b02d377abfdf3395da6d868bc`。原件导入提交为 `2c4885404723a0a7c303c8c0184940e9ed188108`。本报告/后续 Gateway 候选提交不再改变该最终 Node-A 工程源码。

修改仅涉及五个原 CANopen 适配/OD 文件，另加 node_policy.h/node_irq.h。原采集、USART、血氧/血压、双屏及看门狗等 159 文件与导入 SHA 清单逐字节一致。活动文件 SHA-256 见 evidence/a1-source-identity.json，不将修复后的源码误称原始快照。

修复：CO_RESET_NOT 正常推进；COMM 只重建 CAN；APP 清可信时间/质量、锁止通信并等待显式本地初始化，不复位双屏。Heartbeat 500ms，EMCY 0x81 避开 SYNC。第五 TPDO 标准 eventTimer 子索引 0x1804:05、SYNCStartValue :06 已改正。测试用 0x1018 身份不使用真实 UID。

TIME 消费者用可信 CANopen TIME 毫秒分量与接收 tick 建立整秒锚，30s 过期后 epoch=0；软 RTC 不充当 UTC。Host 覆盖跨秒/回绕/过期/重新授时。CAN 临界区嵌套恢复原 PRIMASK，UART 实现未改。PPG 仅新点发送，20ms 网格线性重采样须有两个实点夹住，禁止外推；中断接收时基不等同 ADC 真实采集时刻，UNO 真实帧率与授时延迟仍待 H2。bit8 明示重采样。SpO2/PR 遵从显示侧共享值、探头/暂停/时效，NIBP CAN 时效收紧至90s，原屏历史结果不变。

|本轮验证|原始退出码|证据|
|---|---:|---|
|原件 Host 重复初始化负例|3|evidence/baseline-host.log / baseline-host-exit.json|
|最终 Host 实际协议栈/OD/应用，外部 I/O 桩|编译0、运行0|evidence/a1-final-host.log / a1-final-host-exit.json|
|原件 Keil 全量 rebuild|0，0错误/0告警|evidence/baseline-keil.log|
|最终 Keil 全量 rebuild|0，0错误/0告警|evidence/a1-final-keil.log / a1-final-keil-exit.json|

最终 Keil：Code 46,344、RO-data 3,072、RW-data 1,528、ZI-data 15,616 bytes；原件依次 45,316 / 3,072 / 1,492 / 15,556。是编译器区域统计，不是运行时栈峰值或时延实测。

修复中首次 PPG 受栈启动自动 sendRequest 影响发送初始旧点（Host退出3），首次 Keil 依赖 DEBUG_PPG 才声明的诊断变量（退出2）均保留失败日志；现改为明确新点门控及显示侧共享 PR 值，最终重测通过。联合跨栈首次质量 PDO 不周期发送的失败，保留在 Gateway physical_can/evidence/wire-initial-quality-failure*，修复后真实 Node-A Host 发出359条记录并通过 C/MQTT/Backend 验证。

未运行：烧录、Flash/UID读取、双板通电、实际CAN ACK/错误/传感器频率/双屏实时性、生产Broker及真实云端。Host 桩不替代 Keil，更不替代真机。当前 P6 USB 档位及完整引脚/H1清单见 gateway/physical_can/README.md，停止等待硬件准入授权。
