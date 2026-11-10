# R29 发送路径审读与 WP-AU 离线回执

审读和诊断候选均已交付。实板 S2-c 为 NOT_RUN。候选只新增观测，原发送节流、5 s 事务期限、重入恢复策略与 Flash 布局继续沿用 S2。 [R28](https://github.com/Serendipity-min/medical-multi-parameter-monitor/blob/a44b8cc/node-b/docs/PI-REVIEW/R28-20261110.md) · [R29](https://github.com/Serendipity-min/medical-multi-parameter-monitor/blob/a44b8cc/node-b/docs/PI-REVIEW/R29-20261110.md)

## 发送路径审读

| 检查 | 源码与结论 |
| --- | --- |
| 短写、超时和续包 | `send_bytes()` 在 STOP 或预算到期时返回实际写入数。透传的 `pass_send()` 将任何短写或已见 UART 错误转换为负值，并将透传标为未知。适配器随后关闭本地连接，coreMQTT 遇负值退出，`gateway_mqtt_begin()` 返回失败并走原连接关闭路径。coreMQTT 能重试正数短写，当前透传入口只返回全长或负值，因此短写不会按成功记账，原连接也不会继续提交下一包。 [平台](../../../gateway/mqtt/src/platform.c) · [适配器](../../../gateway/mqtt/src/mqtt_transport_adapter.c) · [MQTT 调用](../../../gateway/mqtt/src/gateway_transport.c) |
| 发送重入 | TXE 等待、USART1 控制台、JSON 波形序列化均会触发 `platform_poll()`。其 `polling` 防护覆盖回调自身的嵌套调用。当前生产候选的 `service()` 推进 CAN、入队、时间锚与本地控制，音频关闭，回调不调用网络 egress。网络推进与 `gateway_mqtt_begin()` 的入口仍在主循环。审读未找到回调内重入发送的路径。 [主循环与回调](../../../gateway/b5/network_main.c) · [平台轮询](../../../gateway/mqtt/src/platform.c) |
| 缓冲所有权 | Router 先复制帧给发布者。`mp_json()` 写静态 JSON，coreMQTT 发布期间同步持有该载荷，适配器再按向量复制到独立的 `network.tx`，发送返回后才清除。RX 使用独立环及 MQTT 接收缓冲。回调中的新帧只进入 Router，未找到覆写正在发送 JSON 或打包缓冲的路径。 [模型](../../../gateway/data_model/model.c) · [适配器](../../../gateway/mqtt/src/mqtt_transport_adapter.c) · [MQTT 发布](../../../gateway/mqtt/src/gateway_transport.c) |
| IRQ 与临界区 | CAN RX IRQ 只向 CAN 收包环提交帧，USART3 IRQ 读取状态和 DR 并维护接收环及错误计数。未找到这些 IRQ 写 USART3 TX 或打包缓冲的路径。主线程在 TXE 就绪后写 DR，IRQ 与回调耗时可拉长间隔。 [CAN IRQ](../../../gateway/dual_can/b4_bxcan.c) · [USART3 IRQ 和 TX 循环](../../../gateway/mqtt/src/platform.c) |
| QoS0 声明长度 | `mp_json()` 失败返回 0，成功返回去掉 C 字符串终止符的长度。该长度同时用于 coreMQTT 的 Remaining Length 计算和 payload 向量。QoS0 不含 Packet Identifier，适配器逐段检查总长后复制，透传使用总向量长度写出。审读未发现 QoS0 声明长度与适配器写入长度分叉。 [模型](../../../gateway/data_model/model.c) · [coreMQTT](../../../gateway/third_party/coreMQTT/source/core_mqtt.c) · [适配器](../../../gateway/mqtt/src/mqtt_transport_adapter.c) |

当前调用路径未发现明确的字节完整性缺陷。STM32 寄存器写入成功只能证明本地提交，线上的字节和 ESP 的接收仍无法用现有软件直接核对。若 S2-c 出现短写、TXE 超时或重入，应按相应的故障路径定位。若计数均正常，仍须结合 Broker 原生原因、PUBACK 和报文环判断，结论限定在可观测的 STM32 侧。

## WP-AU 诊断口径

候选用 `--tx-integrity-diag` 启用，默认关闭。新增记录仅含数字与类型标记。

| 串口行 | 字段与取样 |
| --- | --- |
| `B5 TXCHK` | 与 `B5 PROD` 同 tick、约每 5 s。累计 STM32 TX DR 写入字节、进入写入阶段的透传报文数（含短写）、短写次数、TXE 等待超时次数、报文内最大写入间隔、重入次数和最大相邻 PUBACK 间隔。另有本会话最近一次 `req/wr`。TXE 超时只统计实际等待 TXE 期间预算用尽，其他提前结束可表现为短写。 |
| `B5 TXEXIT` / `B5 TXPKT` | 每次离开已有透传发送的会话时，在发 `+++` 前输出快照。保留最近 16 个传输报文的开始 tick、MQTT 类型、流、序号、请求和写入长度、耗时、最大字节间隔。控制报文的流标记为 255。 |
| `B5 TXREENTRY` | 首次重入时的 tick、外层和内层流及序号、是否在 `platform_poll` 回调中。计数不改变原判定或返回。 |
| `B5 TXACK` | 匹配在途 Packet ID 的首个 PUBACK。每项为 `ack_tick/packet_id/last_DR_to_ack_ms/adjacent_ack_ms`，会话首条间隔为 0。同一会话最多保留 256 项，退出时输出最近 16 s 的可用记录，`ack_overwritten` 记录覆盖。现场应按 Broker 遗嘱和对齐后的 tick 裁切遗嘱前 5 s，并确认最早记录覆盖所需时间。 |

字节间隔为两次写 TX DR 之间的毫秒 tick 差，分辨率不足以还原每个位。PUBACK 时延以最后一次写 DR 为起点。周期行最长保守按 175 B，115200 8N1 线时约 **15.2 ms**。退出回执逐行写出，单行保守低于 30 ms 线时，满环整组线时上限约 **1.12 s**，会增加故障后至 `+++` 的观测间隔。实际 `console_max`、发送时序扰动和恢复耗时仍需 S2-c 实测。

## Host 与构建

- Host C **28 组通过**。透传夹具覆盖完整写入、6 ms 人工 TXE 间隔、模拟回调重入、TXE 超时短写后拒绝继续原连接、逐条 PUBACK 时序及 ACK 环覆盖。
- Python **85 项及 12 个子例通过**。115200 透传 110 s Host 对照的收发、队列及模拟时序输出一致。唯一差异为在途槽增加 4 B，存最后一次写入时间。
- Windows Arm GNU **14.2.1** 构建通过，sector4 余 **8,288 B**，常规 SRAM 扣除链接保留堆栈后余 **16,120 B**，原 CCM 保留区为 **61,824 B**。关闭诊断重编，S2 的 boot、code、HEX 与 R25 冻结值逐位一致。

```text
python gateway/dual_can/build_arm.py --b5 --egress-final --tri --unified --split-flash --five-node --five-appliance --no-audio --esp-passthrough --pass-lifecycle --production-diag --outage-retention --tx-integrity-diag
```

| 产物 | 字节 | SHA-256 |
| --- | ---: | --- |
| boot | 392 | `16c7f4e72e0bd443311a61265b5ab6d641acbdf53a89a0d5a006b06a4e669fd1` |
| code | 57,248 | `8a790e5dea80b5c24abd2c76754d83f1984b0cd0bbe158a420708b2869c62f80` |
| HEX | — | `f3e8a19e17af0ef38bf2362ed5412b288e5b5e57beb9e0e9eeba6c348464e457` |

待 PI 在 VPS 位级复核、负责人按完整 code SHA 放行后执行 S2-c。三分钟标量无损验收仍未执行。
