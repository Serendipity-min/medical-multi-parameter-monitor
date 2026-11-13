# FIELD01 PREFLIGHT R4 镜像 2 实板回执

2026-11-09 · 北京时间。PI 复核经负责人在会话确认。候选离线回执为 `9682ab5`，现场使用同一镜像。

- 批次结束状态为 `ROLLBACK_FLASH_VERIFIED_S1_BASELINE_PASS_S2_BLOCKED_COLD_BOOT_BANNER_UNCONFIRMED`。候选 code SHA-256 为 `7cfb0805021046c77cd98ef5c087a9558e868fd3eabbd4ffe816b5b015aad251`。
- EFS 台账为 50 条，SHA-256 为 `e400b4cef4965f84afa00b13c2fe363efab04e3b4c802993e9ed7f726142c5e0`。记录的上电会话 9 次，PRE 发送 1 次。START、KEY、联云命令及 sector3 写入均为 0。
- 镜像 2 额度保守计为 8/8。S0′ 原应用双读与回退后的原应用冷启动单列。另将 1 次主机预备前枚举 COM15 计入镜像 2 额度，C 当时是否启动未记录。
- S0′ 整片与 Options 双读 **PASS**。与上次回退整片相同，包含现用 sector3，配置 CRC 和 C 身份通过。
- 镜像 2 sector0/4 安装和整片写后读回 **PASS**。Options、sector3 和其他扇区保留。
- 回退 **PASS**。回退读回与 S0′ 整片逐字节一致，Options 一致，现用 sector3 保留。累计回退额度已用 2/2。
- 原应用冷启动 **BLOCKED**。未收到预期启动横幅。负责人确认曾上电且已断电，确切插线时刻和实际持续时间未知。

## PREFLIGHT

| 会话 | UART_CUR | Wi-Fi / IPv4 | RETIME / NEGOTIATE | STRESS | RESTORE / END |
| --- | --- | --- | --- | --- | --- |
| S1′ 首轮 | — | — | — / — | — | — / C_STOPPED |
| S1′ 复测 | 115273 / 8 / 1 / 0 / 1 | ok=1 code=NONE ms=2587, ch 1, -35 dBm, IPv4=1 | — / OK actual=115273 | rate=115200 n=50 fail=0 uart_err=0 rx_high=2 ms=922 | OK / PASS NONE uart_err=0 |
| S2 首轮 | — | — | — / — | — | — / BOOT_NOT_CONFIRMED |
| S2 复测 | — | — | — / — | — | — / BOOT_NOT_CONFIRMED |
| S3 | — | — | — | — | NOT_RUN |

S1′ 首轮仅捕获通用 STOP，未见新启动横幅，PRE 未发送。停止子码未留存。负责人确认原 USB_UART 会供电，提前启动后达到就绪截止是推断。该供电源切换没有独立断电或第二次冷启动证据。

J-Link 调试器可见，但 Windows 没有枚举其 VCOM。负责人另行批准串口阶段由原 USB_UART 单独供电，J5 关闭、J-Link 拔下。烧录及回退仍由 J5 供电。

S2 首轮主机到期后才观察到 COM15。两条现场回复不一致，按一次上电保守计入。S2 复测 COM15 在线，但采集到 0 字节。两次均未发送 PRE，230400 及 500000 的实板性能仍未测。

第一次回退在 DAP 初始化失败，SDK 日志记录了 connect-under-reset 回退路径，未取得目标身份，未执行显式 Halt、Reset、Go 或 Flash 下载。负责人随后确认 C 板电源开关未开。该接入保守计入镜像 2 供电预算，未写入 Flash。纠正后使用独立事务执行已授权回退。

原 FIELD01 的历史 Wi-Fi 失败原因仍为 UNKNOWN。此批数据用于 UART 和 Wi-Fi 诊断，出口容量、CAN 并发及 150 秒业务窗未测。

## 上电与原始证据摘要

下表时间为主机记录或负责人回复时间。

| 阶段 | 上电确认时间 | 供电与连接 | 断电确认时间 |
| --- | --- | --- | --- |
| S0p-readback | 14:41:42 | J5; J-Link read-only; USB_UART disconnected; hotspot off | 14:44:30 |
| S0p-install | 14:44:55 | J5; J-Link programming; USB_UART disconnected; hotspot off | 14:46:18 |
| S1′ 首轮 | 14:47:05 | 按 J5 加日志线安排；原 USB_UART 实际具备供电能力；J-Link 断开；热点开启 | 14:48:08 |
| S1′ 复测 | 14:54:44 | USB_UART only; J5 off; J-Link disconnected; hotspot on | 14:55:03 |
| S2 首轮 | 14:56:53 | USB_UART connected after host expired; J5 off per owner; no PRE | 14:57:13 |
| S2 复测 | 14:57:47 | USB_UART only; J5 off; J-Link disconnected; hotspot on | 14:58:39 |
| 回退接入失败 | 14:59:24 | J5; J-Link programming; USB_UART disconnected; hotspot off | 板上开关未开，事后确认 |
| 原应用回退 | 15:02:07 | J5; board switch on and LED lit; J-Link SWD; USB_UART disconnected; hotspot off | 15:03:38 |
| 原应用冷启动 | 15:05:27 | USB_UART only per owner; hotspot off; owner reported after host window; exact insertion time unknown | 15:05:27 |

| 现场串口回执 | 原生退出 | PRE | 原件 SHA-256 |
| --- | ---: | --- | --- |
| S1′ 首轮 | 2 | not sent | `c85e2af5a4b6d04e6a05eb384634db90cf6e6cd6aa2ff596fae3d6c678298ede` |
| S1′ 复测 | 0 | sent | `fa9841ad5081314e1051b623854bb6cd805455c425124d0e65cc519ea267527d` |
| S2 首轮 | 2 | not sent | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| S2 复测 | 2 | not sent | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |

S0′ 备份的 J-Link worker 原生退出 `0`。

镜像 2 安装的 J-Link worker 原生退出 `0`。

回退接入失败的 J-Link worker 原生退出 `1`。

原应用回退的 J-Link worker 原生退出 `0`。

被动启动观察器原生退出 `2`。主机从上电许可起观察 59 秒，现场上电上限为 60 秒。期望横幅为 `UNI DISARMED V1 C_BC_ABC NO_FLASH_WRITE`。

原始串口、整片、Options、设备身份和台账本体留在受限 EFS。
