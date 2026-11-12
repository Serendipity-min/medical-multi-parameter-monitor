# R62 · WP-AZ AZ-0 / AZ-1 回执

2026-11-12。AZ-0 直连台架 **BLOCKED**，AZ-1 **离线 PASS**，源码 `2c9709474d11d09d8538783d44aea189a1864af8`。AZ-2 / AZ-3 为 **NOT_RUN**。本工作包的后端、ACL 和固件候选均未部署。独立的 R61 run4 另有 S7 回执。 [R62 §1、§2、§5](https://github.com/Serendipity-min/medical-multi-parameter-monitor/blob/b9fdfff/node-b/docs/PI-REVIEW/R62-WP-AZ-CARD-20261112.md)

## AZ-0 独立台架

负责人确认复用 **TW-TTS**，现场没有 3.3 V USB-TTL，Windows 当时无串口枚举。模块未接台架或供电，未发送物理 UART 帧。

| 取证项 | 结果 |
| --- | --- |
| 模块型号与协议 | 型号由负责人确认为 TW-TTS。既有项目合同记录参考手册 V0.21。实物版本、回码和照片 SHA 为 UNKNOWN。 |
| UART 与接线 | 合同记载 9600 8N1、`R` 输入、`T` 输出。R62 确认 C 的 PA2/PA3 接 TTS。本轮未重测实物电平和线序。 |
| 电源与喇叭 | 独立 5 V 电源型号、额定输出、现场扬声器规格均为 UNKNOWN。合同中的模块标称 35–55 mA 未用于推定实际静态、播放或峰值电流。 |
| 读法、音量、ACK 与状态回码 | 均为 NOT_RUN。下表为离线编码结果。 |

复用 `gateway/voice/tts_frame.c` 生成 4 个 0xFD + 大端长度 + 0x01 0x04 + UTF-8 的台架向量。本机留存于忽略目录 `node-b/build/az0-frame-vectors/`。

| 测试句 | UTF-8 / 帧字节 | 帧 SHA-256 |
| --- | ---: | --- |
| 体表温度约31.3摄氏度 | 28 / 33 | `7383892d995f4e7c4810d5c7c5315b9c420be462d323b6c58ed1f22d6393e750` |
| 血压，收缩压108，舒张压71，毫米汞柱 | 50 / 55 | `2cc1762ea37c78d9c75870201ec77011aa6a8a48c017b097d6b3dfa744f29a74` |
| 体表温度约31.3°C，血压108/71 mmHg | 42 / 47 | `09c1068f9165306f68a20bded4301a8100f05a6a89704f7a38ab3e0193429b84` |
| 「台架测试语音，」+「体表温度约31.3摄氏度，血压收缩压108，舒张压71，毫米汞柱。」×2 +「结束。」 | 192 / 197 | `74109e522af03a5be9d881d574003be63a3abf68004a2237fa079108348edbf6` |

完成 AZ-0 仍需现场 3.3 V USB-TTL、独立 5 V 供电及电流测量。若要采集模块 `T` 端的回码，按原合同先核对其电平与适配器输入兼容。扬声器接 `SPK±` 差分端，电源与 USB-TTL 共用模块的信号地 `G`。 [TW-TTS 参考手册 V0.21](https://tianwen51.com/new/bbs/forum.php?mod=viewthread&tid=2621)

## AZ-1 协议与行为

- 后端为 TEMP、NIBP、SpO₂、PR、HR 生成独立 `speech` 文本，按 §5 转写单位，UTF-8 最长 200 B。网页原有 `text`、免责声明和规则不变。设备支路仅在 `MONITOR_BROADCAST_DEVICE=1` 时向 `mpm/v1/GW-C-001/voice/broadcast` 以 QoS1、retain=false 发布，失败只记 `mqtt_broadcast_failed`。同毫秒或时钟回拨时用上次尝试的 `issued_ms+1` 保证进程内单调。
- R62 §5 未指定字段字节序，双方实现选用网络大端。头部为 19 B，最多 219 B 全帧。无后端内存计数 `id`。

| 偏移 | 字段 |
| ---: | --- |
| 0 | 4 B ASCII `MPB1` |
| 4 | 1 B 版本 `01` |
| 5 | 8 B unsigned epoch `issued_ms` |
| 13 | 4 B unsigned `ttl_ms=15000` |
| 17 | 2 B unsigned UTF-8 字节数 |
| 19 | 1–200 B UTF-8 文本 |

- C 仅在 `--tts-broadcast` 档位订阅此主题，验收 QoS1 且非保留、头和载荷长度、有效时间锚及严格递增的 `issued_ms`。设备时间已到 `issued_ms+15000` 或发行时间超前至少 15 s 时拒绝。播放前复查有效期，三槽等待队列满时拒绝新帧。去重状态跨 MQTT 重连保留，在 C 重启时清零。
- 透传接收白名单仅在此档位新增 SUBACK 与有界 QoS1 PUBLISH。MQTT 层核对完整主题。SUBACK 拒绝时不启动 TTS 支路，保留遥测会话。现有 TTS 状态机处理 UART 的 ACK 和播放结束，间隔至少 5 s。每次服务最多试写一个字节、读四个状态字节、取一条等待消息。STOP 清空等待队列并沿用驱动的有界停止尝试。
- 此候选使用 USART2 9600、PA2/PA3、中断优先级 15。ARM 构建检查实际 IRQ 和向量，新强外设处理器仅 USART2。无麦克风采集/音频 DMA、无强 `DMA1_Stream0_IRQHandler`、无 `mpm/mic/v1/`。分段布局离线校验通过，HEX 和二进制仅覆盖 sector0/4，保留 sector3、Options 和其他扇区。

## 离线验证与 ARM 制品

- Python `cloud/backend/tests gateway/voice/tests` 为 **115 passed、6 skipped、3 subtests passed**。覆盖默认关闭时零发布、golden bytes、五类文案、同毫秒顺序和发布失败后仍可摄入与读快照。
- 统一 Host 32 组均通过。新增 P3 夹具覆盖坏魔数、版本、长度、超长、过期、乱序、重复、未授时、三槽满、播放前过期和 5 s 间隔。真实 coreMQTT 与透传字节替身验证拒绝 SUBACK 后保留会话、两字节 MQTT 剩余长度的 200 B MPB1 文本、下行 PUBACK、TTS 写入和上行 QoS0/QoS1 并行推进。既有 TTS Host 独立测试 3,351 检查通过。以上证据均为软件。
- 使用 Arm GNU Toolchain 14.2.Rel1、GCC 14.2.1（arm-14.52）及 STM32F4 SPL v1.4.0。去掉 `--tts-broadcast` 重建，boot、code、HEX 的 SHA 与冻结 WP-AY0 全部一致。

```text
python -X utf8 gateway/dual_can/build_arm.py --b5 --egress-final --tri --unified --split-flash --five-node --five-appliance --no-audio --esp-passthrough --pass-lifecycle --production-diag --outage-retention --tx-integrity-diag --link-resilience --formal-cloud --tts-broadcast
```

| 制品 | 字节 | SHA-256 |
| --- | ---: | --- |
| boot | 392 | `ef85ab637e5de088e26403eeed1dd26528f8457cb52dc11ad7ddc403a3a2a841` |
| code | 61,228 | `9d1902461e340a20672be54ef255215ddb95a3936d0030fc4cdb5db818a9d083` |
| HEX | 173,423 | `704fff446b551c1191a17761e3a90112af7941428a19f1158d2132fd31a39c7f` |

| 区域 | WP-AZ 占用 | 余量 |
| --- | ---: | ---: |
| sector0 | 392 B | 15,992 B |
| sector4 | 61,228 B，较 WP-AY0 增 2,748 B | 4,308 B |
| 常规 SRAM，含链接器保留的堆与栈 | 116,048 B，较 WP-AY0 增 1,048 B | 15,024 B |
| CCM | 61,824 B | 3,712 B |

本机制品位于 `node-b/build/b4-c-arm-20261112T093527665856Z`。Host 全矩阵回执 SHA-256 为 `0ba945bbaaca97dc9fe4d89e905f41667be1372d2f027a2edca74adb6d8b00b2`。实物 ACK、播放电流、声音和与真实遥测的时序仍待硬件阶段验证。

## Broker ACL 草案

基于仓库 `cloud/broker/acl`。将 `gateway-c` 的正式网关写通配收窄为现有上行分支，避免该账号经旧通配写入新增下行主题。后端保留原读授权，新增精确下行写授权。AZ-2 应先按实际配置核对当前上行分支，再按审批应用。此草案未部署。

```text
user gateway-c
topic write mpm/v1/GW-C-001/status
topic write mpm/v1/GW-C-001/+/status
topic write mpm/v1/GW-C-001/+/telemetry/+
topic write mpm/v1/GW-C-001/+/replay/+
topic write mpm/v1/GW-C-001/+/event
topic read mpm/v1/GW-C-001/voice/broadcast

user backend-reader
topic read mpm/v1/GW-DEV-001/#
topic read mpm/v1/GW-C-001/#
topic write mpm/v1/GW-C-001/voice/broadcast
```
