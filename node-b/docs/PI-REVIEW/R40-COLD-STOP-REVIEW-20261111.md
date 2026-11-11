# R40 窗口 3 · 冷启动停机复核

**2026-11-11 · 现场停机条件已确认，首次 socket 检查失败的具体回包仍为 `UNKNOWN`。** 冻结源码为 `2a8ee475667fac0ccf23a212bdda17c78de98c35`。复核时四份原件 SHA-256 均与实板回执一致，现场原件仍存本机 EFS。 [实板回执及原件索引](R40-WINDOW3-FIELD-20261111.md)

## 现场证据

| COM15 原件行 | 观测 | 对应源码 |
| --- | --- | --- |
| 3–5 | 启动 AT 确认成功，`UNI UART baseline=222 total=222` | 冷启动已将既有 UART 错误纳入基线，当时差值为 0。 |
| 6–12 | `AT`、`ECHO`、`VOLATILE`、`STA` 成功。随即 `PASS_BOOT_SOCKET_UNCONFIRMED`，清理也报 `PASS_CLOSE_UNCONFIRMED` 和 `PASS_SOCKET_UNCONFIRMED` | 建链先尝试 `AT+CIPCLOSE`。关闭未确认时，需要 `AT+CIPSTATUS` 成功且 `gateway_socket_absent()` 判定无连接。串口不输出两条指令的原始回包。 |
| 13–14 | `PASS_HARD_RESET` 后约 334 ms 收录 `PASS_HARD_RESET_OK` | ESP 恢复函数成功返回，路径要求先收到 `ready` 再收到 `AT OK`。 |
| 15–16 | 约 3 ms 后收录 `PASS_LOCAL_FAULT`，随后 `B5 STOPPED NO_AUTOREARM` | `pass_reconnect()` 在使用 AT 同步状态前比较 UART 累计值和启动基线。两者不同即执行 `stop()`，关闭 C 的 CAN 处理和网络出口。 |

现场确认的是 C 应用执行到本地停机分支。故障发生在本轮 Wi-Fi 加入和 MQTT 建链之前，Broker 仅有观察器成功建链，载荷记录为 0。硬复位发生在 ESP 路径，缺少独立的 PF6 波形。UART 统计合并 USART3 的 ORE、NE、FE 与软件接收环溢出，本轮无停机前分项读数。具体新增计数、首次增长时点及来源均为 `UNKNOWN`。 [socket 检查](../../../gateway/mqtt/src/gateway_transport.c#L1123) · [ESP 恢复](../../../gateway/mqtt/src/platform.c#L757) · [重连门禁](../../../gateway/b5/network_main.c#L196)

## Host 分段复现

沿用 `test_unified.py` 的生产透传与生产重连控制编译参数，在 `node-b/build` 临时夹具中注入回包和错误。冻结固件源码保持不变。两个夹具分别覆盖真实 AT 状态机和真实 `pass_reconnect()` 判断，以下结果均为 Host 证据。

| 注入条件 | 结果 |
| --- | --- |
| 启动基线 222，`CIPCLOSE` 返回 `ERROR`，`CIPSTATUS` 返回 `STATUS:0` 或 `STATUS:1`、无连接行、结尾 `OK` | 两种回包均被冻结版拒绝，初次建链失败，清理触发一次 ESP 硬复位。 |
| 同上，改为 `STATUS:4`，无连接行、结尾 `OK` | 初次建链通过该检查，未触发硬复位，UART 累计保持 222。 |
| 硬复位期间注入 1 次 USART3 帧错误，随后给出 `ready` 与 `AT OK` | 恢复成功且活动错误为 0，累计错误保留为 223。 |
| 调用首次建链的重连入口，基线 222，累计 222 / 223 对照 | 222 进入重新获取。223 在重新获取和 AT 同步检查前停机。 |

冻结版 `gateway_socket_absent()` 只接受 `2/4/5` 且没有连接行。ESP-AT v2.3.0.0 定义 `0` 为 station 尚未初始化、`1` 为已初始化但尚未发起 Wi-Fi 连接。本轮 socket 核验位于 `AT+CWMODE=1` 之后、主动加入热点之前，因此拒绝无连接的 `STATUS:0/1` 是已复现的冷启动缺口。本轮 ESP 实际返回哪种状态，或者查询是否失败，仍待取证。 [冻结版判断](../../../gateway/mqtt/src/gateway_transport.c#L797) · [Espressif ESP-AT v2.3.0.0 TCP/IP 命令](https://docs.espressif.com/projects/esp-at/en/release-v2.3.0.0_esp8266/AT_Command_Set/TCP-IP_AT_Commands.html)

ESP 恢复路径在等待 `ready` 时可清活动错误，但 `esp_mqtt_reset()` 保留累计统计。恢复成功后的 `pass_reconnect()` 仍使用旧基线，故复位期的一次帧错误足以锁停。Espressif 文档记录 ESP8266 ROM 启动串口日志使用 74880 baud，接收端按 115200 baud 工作时，复位启动输出是可能的错误来源。现场未采集 USART3 原始波形，也无法排除错误先于硬复位出现。 [活动与累计计数](../../../gateway/mqtt/src/platform.c#L1238) · [Espressif 启动日志说明](https://docs.espressif.com/projects/esptool/en/latest/esp8266/advanced-topics/boot-mode-selection.html#boot-log)
