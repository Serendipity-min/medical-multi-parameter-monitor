# R35 WP-AW 本地运行回归修复回执

C 缺少网络配置时保留 `FIVE AUTO CONFIG_MISSING LOCAL_ONLY` 和 `platform_poll()` 路径，配置有效后才进入网络建链。`pass_reconnect()` 移除了重复的配置判断，保留 UART 错误增量停机。 [R35 复核](https://github.com/Serendipity-min/medical-multi-parameter-monitor/blob/a0a5abd/node-b/docs/PI-REVIEW/R35-20261111.md)

## Host 验证

扩展 `production_link_control`，调用真实固件入口、CANopen 网关和 Router，以替身捕获 CAN 发送和网络调用。同一用例在修复前因 `stop()` 断言失败，修复后通过。

- 配置无效的前 21 秒，出现一次 `LOCAL_ONLY` 提示，两路持续发送 CAN 心跳，`b4_hw_stop()` 调用及网络尝试均为 0。
- 冷启动无有效 UTC 时，TIME 帧为 0。Host 在第 1 秒注入有效 UTC 锚点，两路各发出 3 帧 CANopen TIME，DLC 均为 6。此验证覆盖有效锚点下的周期发送。
- 第 21 秒使配置有效，固件首次进入 `gateway_network_open()`。重入、UART 错误增量和 STOP 仍由同组用例验证。

`python -X utf8 gateway/microphone/test_unified.py` 的 30 组全部通过。 [Host 用例](../../../gateway/b5/test_link_control.c)

## 新候选

Windows Arm GNU 14.2.1，使用 R34 回执中的构建命令。移除 `--link-resilience` 重建后，boot、code、HEX 均与 S2-c 归档逐字节相同。 [构建命令](R34-WP-AW-OFFLINE-20261111.md#host-和制品)

| 制品 | 字节 | SHA-256 |
| --- | ---: | --- |
| boot | 392 | `15e6c6b18e1528dc624fa4602ff7a90c1c68af8adb464f1e64e0a930f8d1e203` |
| code | 58,092 | `ce8d3490d03c728c7bde0fa90a12da0a192653513905571883456455b01d2a8d` |
| HEX | 164,603 | `2150d84a533195b6c4a374dc0efca37eb9d2002c3bd285902e70466ca29293db` |

sector4 余 7,444 B，常规 SRAM 扣除保留区后余 16,080 B，CCM 余 3,712 B。新摘要待 PI 独立复核。

窗口 1 建议暂缓，PF6 硬复位路径的硬件验证记为已知限制。窗口 2 以 R35 补充的预登记为准，包括非人工断链后在 25 分钟上限内最多重开一次 300 秒窗口，以及 PPG 名义覆盖 92–95% 按源质量门控证据单列。现场状态为 `NOT_RUN`，批次卡待 PI 复核新 SHA 后签发。 [R35 窗口与冻结条款](https://github.com/Serendipity-min/medical-multi-parameter-monitor/blob/a0a5abd/node-b/docs/PI-REVIEW/R35-20261111.md#4-两窗口方案裁定)
