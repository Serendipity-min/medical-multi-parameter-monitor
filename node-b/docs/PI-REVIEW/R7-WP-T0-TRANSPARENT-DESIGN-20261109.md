# R7 WP-T0 · ESP8266 SSL 透传候选

来源为 [R7 @ ee7c2a0](https://github.com/Serendipity-min/medical-multi-parameter-monitor/blob/ee7c2a0/node-b/docs/PI-REVIEW/R7-20261109.md)。本候选保留裸机、8 MHz、现有 CAN、Router、coreMQTT 和 USART3。启用 `--esp-passthrough` 时自动关闭音频，仅用于隔离 TLS 端口 28895 的五板构建。启用 `--esp-230400` 时优先协商 230400，已验证恢复才可降级至 115200。测量不带音频，音频驱动和既有目标继续保留。

## 唯一串口所有者

| 阶段 | 命令或数据流 | 失败处置 |
| --- | --- | --- |
| 命令态 | 现有 AT、入网、可信授时、CA 校验、证书名称和 SNI，保留 SNTP 使用的普通被动接收。授时结束后切主动接收，易失设置 `CIPRECONNINTV=36000`（3600 秒），再建立单路 SSL。 | 沿用现有超时和 STOP 门禁。ESP 自动重连间隔大于现有 QoS1 期限与 MQTT 保活，避免旧 MQTT 会话接到新 SSL 上。 |
| 进入 | SSL 建立后设置 `CIPMODE=1`。发送裸 `AT+CIPSEND`，2 秒内按序收到 `OK`、`>` 才交接给 coreMQTT。 | 明确的 `ERROR` 保持命令态。缺提示、次序错误、UART 异常或已收到 OK 后失败，锁存未知状态。 |
| 透传 | 同一个适配器使用 `esp_mqtt_send/recv` 搬运 MQTT 3.1.1 裸字节。USART3 RX IRQ 仍入原环，`service()` 仍只推进 CAN、时钟和队列。稳定态无 `CIPRECVLEN?`、`CIPRECVDATA`、逐包 `CIPSEND=` 或 `SEND OK`。 | UART 部分写入或错误锁存未知状态，禁止重送未知半帧。进入透传后禁止普通 AT，业务流中的三连加号（含跨写调用）整段拒绝。 |
| 退出 | 冻结 MQTT 发送，等 USART TC，再静默 ≥25 ms。仅发送一次无 CRLF 的 `+++`，再次等 TC，静默 ≥1001 ms 并丢弃残留 RX。只以 `CIPMODE?` 的模式 1 回读及 OK 恢复命令边界，再确认 `CIPMODE=0`，最后 `CIPCLOSE`。 | 逃逸和探测预算 1800 ms，模式恢复 2000 ms，关闭预留 2000 ms。STOP、预算不足、UART 异常或逃逸结果未知时关闭 MQTT 并封住普通 AT，保留诊断，需人工恢复。 |
| 重连 | 只有边界已证明且业务窗口有余量时，走现有上层退避和入网/TLS 流程，重建 MQTT clean session。QoS1 期限仍为 5000 ms。 | 模块如果已退回命令态且不接受本次逃逸，视为边界未知。静默丢链由 QoS1 或 keepalive 期限暴露。 |

固件按 ESP-AT 命令规范要求的 `OK` 与 `>` 检查进入。该版示例的 TCP 步骤只展示了提示符，真实模块返回形状仍是单板验证项。 [ESP8266 ESP-AT 2.3 命令规范](https://docs.espressif.com/projects/esp-at/en/release-v2.3.0.0_esp8266/AT_Command_Set/TCP-IP_AT_Commands.html) · [透传命令顺序示例](https://docs.espressif.com/projects/esp-at/en/release-v2.3.0.0_esp8266/AT_Command_Examples/TCP-IP_AT_Examples.html)

### 下行与确认

- 无音频订阅的 Broker 下行只接受 CONNACK、PUBACK 和 PINGRESP 及其固定剩余长度。边界上的 `CLOSED`、`WIFI DISCONNECT`、`ready` 等落入非法 MQTT 头，立即终止本会话。跨短读保留解析状态。若文字夹入两字节字段，字段本身无法可靠区分；仍由 coreMQTT 的报文检查、在途 ID 和期限约束。禁止扫描或删除 MQTT 载荷中碰巧出现的控制词。
- `send` 成功只说明 STM32 已把整段交给 UART 发送路径，最后一字节可仍在 DR/移位寄存器。普通模式的 `SEND OK` 也只确认 ESP 层。QoS1 只有匹配的 PUBACK 才释放 Router 在途记录。QoS0 真正到达必须在 Broker 端逐帧比对，C 侧发送计数不能充当收达证明。
- 若以后验证音频，应在同一 MQTT 字节流里继续使用现有调度与 ACK 归属，并扩展下行规则和资源验收。当前透传构建不接音频分支。

## Host 的边界

真实 C Router、coreMQTT 和 UART 收发状态机接虚拟对端。对端按 20 ms 合并、ESP 2048 B 收入上限、单次 1460 B 发出限制建模，裸流直出 MQTT 应答。专门边界夹具模拟分片、断链文字、坏长度、半写、UART 错误、缺提示和逃逸失败。容量扫点每次运行同一 P3 输入 110 秒。附加 CPU 时延在串口发送与接收方向逐字节注入，未模拟真实 IRQ/CAN 抢占或无线重传。250/370 ms 是报文交付后的对端应答延时参数，用于敏感性分析。普通模式的终态延时固定 42 ms，另用原 P3 的 55 ms 对端应答参数校准。 [Host 夹具](../../../gateway/b5/test_five_p3_egress.c) · [扫点入口](../../tools/five_appliance_p3.py)
