# FIELD01 PREFLIGHT R5 实板回执

2026-11-09 · 北京时间。使用 `d95a714` 的 WP-M 主机与 R5 批准的镜像 2。负责人确认 §6，并明确以本次书面授权替代 WP-M 的 PI 放行。台账保留原话。固定接法为 CFG-U。[WP-M Host 与 Windows 回执](PREFLIGHT-R5-WP-M-RECEIPT-20261109.md)

## WP-N 接线基线

| 步骤 | 电源灯与 COM15 | 观察 |
| --- | --- | --- |
| BP-1 | OFF，灯灭，COM15 不存在 | 负责人确认 USB_UART 全程连接，J-Link 只接 SWDIO/SWCLK/GND，J5 未接，A/B/D/E 断电。 |
| BP-2 | ON，灯亮，COM15 出现 | 无控制台字节；监听打开时间为主机许可后 27515 ms，物理拨动时刻无独立时间戳。 |
| BP-3 | 保持 ON，COM15 仍在 | SWD 只读连接原生退出 0，C 身份匹配，工具报告参考电压 3300 mV。显式 Halt、Reset、Go、下载均为 0。 |
| BP-4 | OFF，COM15 消失 | 电源灯立即熄灭，10 秒后仍灭，接线保持原位。 |

按判定表选用无横幅模式。复位时 COM15 已打开，因此 S2 和 S3 也实际收到候选镜像的启动横幅。

## WP-O 实板

会话 A 的整片和 Options 双读与上次回退原件一致，配置 CRC 通过。只安装已审镜像 2 的 sector0/4，写后整片核验通过。S2 由安装工具的 Reset/Go 进入新启动。S2 门控通过后执行一次纯 Reset/Go，期间 Flash 写入和显式 Halt 均为 0。

| 指标 | S2 · 230400 | S3 · 500000 |
| --- | --- | --- |
| 启动绑定 | BOOT_MS，boot_ms=1422，banner_seen=true | BOOT_MS，boot_ms=356，banner_seen=true |
| UART_CUR | 115273 / 8 / 1 / 0 / 1 | 115273 / 8 / 1 / 0 / 1 |
| Wi-Fi / IPv4 | ok=1 code=NONE ms=2623，ch 1，-31 dBm，IPv4=1 | ok=1 code=NONE ms=1789，ch 1，-31 dBm，IPv4=1 |
| RETIME | OK | OK |
| NEGOTIATE | OK actual=230547 | OK actual=500000 |
| STRESS | rate=230400 n=50 fail=0 uart_err=0 rx_high=49 ms=609 | rate=500000 n=50 fail=0 uart_err=0 rx_high=143 ms=595 |
| GMR 每次耗时 | 12.18 ms | 11.90 ms |
| RESTORE / END | OK / PASS NONE uart_err=0 | OK / PASS NONE uart_err=0 |
| 主机原生退出 | 0 | 0 |

115200 的既有实板基线为 18.44 ms/次。本批通过 ESP→STM32 的 AT 级压测，业务出口容量、CAN 并发与 150 秒窗口未测。

## 回退与启动

会话 B 全程关闭热点。原应用 sector0/4 已回退，整片与会话 A 备份逐字节一致，现用 sector3 和 Options 保留。回退 worker 原生退出 0。
原应用启动横幅观察为 **PASS**。Reset/Go 起 156 ms 捕获归档横幅 `UNI DISARMED V1 C_BC_ABC NO_FLASH_WRITE`。该观察在回退同一上电会话内完成。负责人两次确认最终开关 OFF、电源灯灭。与 BP-4 不同，本次关机后 Windows 仍枚举 COM15；观察器已关闭串口，未再连接目标。

## 台账与证据

EFS 台账 29 条，SHA-256 为 `845ee27f90ec26f1d0961de0710ebe4901a9661554cdc4b2ed4096745dcc218f`。上电 **4/4**，包括一次过期提示后的现场上电。镜像 2 重装 1/1、回退 1/1、纯复位 1/3、PRE 230 与 PRE 500 各 1 次、PRE 115200 为 0。START、KEY、联云命令和 sector3 写入均为 0。

| 上电 | 主机记录或负责人回复时间 | 用途 |
| --- | --- | --- |
| BP-2 | 15:23:25 | 接线基线 |
| A-expired | 15:26:35 | 旧提示过期后曾上电，已关；无写入或 PRE |
| A-rearm | 15:27:13 | 会话 A 双读、安装及两次 PRE |
| B | 15:30:20 | 会话 B 回退与被动启动观察 |

| 串口原件 | SHA-256 |
| --- | --- |
| BP | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| S2 | `fdd57437e917c0e668c8fa42545c7ce68cb2b62fd54e1a7e7a490b9cf7c0e178` |
| S3 | `85052e218b9237e92a3eeec08c6fd699cad19b380edb5afaef21ad44b387f9f3` |
| B | `55630611f2dbd1618b4b132b38a5f568960c01bfd36dc2d371016f0a50e91982` |

原始串口、身份、整片、Options 和台账本体保存在受限 EFS。
