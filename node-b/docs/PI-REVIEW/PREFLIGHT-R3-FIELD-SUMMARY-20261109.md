# FIELD01 PREFLIGHT R3 实板回执与 R4 补证

2026-11-09 · R3 的镜像 1。原始串口、Flash、Options 和完整台账保存在受限 EFS。台账共 **33 条**，SHA-256 为 `81801eb47e6413e5704b935014cc6cf3c21c423148c44666d1395a101435b5a2`。[S0 回执](PREFLIGHT-S0-RECEIPT-20261109.json) · [R3 机器回执](PREFLIGHT-R3-FIELD-RECEIPT-20261109.json)

| 记录 | S1 | S1 冷启动复核 | S2 | S3 |
| --- | --- | --- | --- | --- |
| BEGIN boot_ms | 148 | 149 | NOT_RUN | NOT_RUN |
| AT / GMR | ok / 2.3.0.0 | ok / 2.3.0.0 | — | — |
| UART_CUR | 115273 / 8 / 1 / 0 / 1 | 115273 / 8 / 1 / 0 / 1 | — | — |
| WIFI | ok=1 code=NONE ms=2587 | ok=1 code=NONE ms=2590 | — | — |
| WIFI_SIGNAL | ch 1 / −37 dBm | ch 1 / −41 dBm | — | — |
| IPV4 | ready=1 | ready=1 | — | — |
| NEGOTIATE | MISMATCH actual=115273 | MISMATCH actual=115273 | — | — |
| STRESS | rate=115200 n=0 fail=0 uart_err=0 rx_high=0 ms=0 | rate=115200 n=0 fail=0 uart_err=0 rx_high=0 ms=0 | — | — |
| RESTORE / END | FAIL / BLOCKED NEED_POWER_CYCLE | FAIL / BLOCKED NEED_POWER_CYCLE | — | — |
| END uart_err / 主机原生退出 | 0 / 2 | 0 / 2 | — | — |
| 断电 | 负责人已确认 | 负责人已确认 | — | — |

两次均未发 UART setter，也未切速。镜像 1 在初始门控和恢复确认中都要求 flow=0，实测为 1，因此两处失败。新热点配置的入网和 IPv4 可用性已实测。原 FIELD01 Wi-Fi 失败原因仍为 UNKNOWN，容量与 50 次基线均未取得实板数据。

## 回退整片对照

S0 只读备份来自回退前的 FIELD01 探针。旧安装入口的离线覆盖计划以该备份为底，只在原应用制品覆盖的范围替换字节。原代码从 `0x08010000` 起长 56,072 B，结束地址为 `0x0801DB08`。以下三段均在原代码之后，旧计划沿用了探针尾部的非擦除字节。实际回退以原五板 `prior` 中完整的 sector0/4 制作块，因此这些尾字节为擦除态，和归档一致。范围右端不包含在内。

| Flash 地址范围 | 字节数 | 实际回退读回 | 原五板归档 | 旧覆盖计划中的残留段 SHA-256 |
| --- | ---: | --- | --- | --- |
| `0x0801DB08–0x0801E096` | 1,422 | 全部 `0xFF` | 全部 `0xFF` | `3c91a571f7fab328c0df7b5298423da9c15bdedf5248381825fb9025dc4d8f6a` |
| `0x0801E097–0x0801E09C` | 5 | 全部 `0xFF` | 全部 `0xFF` | `5edd82d98b4eb093fbc15604b2ae5f7e95937fd69ad0e326b04f34f4d628b717` |
| `0x0801E0A0–0x0801E0FC` | 92 | 全部 `0xFF` | 全部 `0xFF` | `d7591d62ef273d388a7abe1a9b8db2123ca6dc46d7651b9139cef03089f2d4f4` |

**实际 Flash 与原归档只在另行授权的 sector3 更新范围内有差异。** Options 相同。回退事务核验了写入和读回，原应用启动为 **NOT_RUN**。回退工具以暂停状态关闭会话，负责人随后确认 C 断电。

## 上电清单

时间为 2026-11-09（北京时间），取串口枚举或负责人确认的记录时间。J-Link 行是首次确认异常的时间。把该事件单独占用一次额度，现场账按 **6 次常规上电 + 1 次异常 = 7 次**计。S0 回执的 2 次仅指 S0 的常规上电。S0 初次供电与反向供电的物理切换时刻没有独立记录。

| # | 记录时间 | C 的供电路径 | 用途与结束状态 |
| ---: | --- | --- | --- |
| 1 | 11:30:27 | USB_UART，J-Link 已接 | S0 整片与 Options 双读。拔 USB_UART 后仍观察到供电，见第 2 行。 |
| 2 | 11:33:29 | J-Link 反向供电 | USB_UART 已拔但电源灯亮。停止目标操作，11:34:34 确认两路断开。 |
| 3 | 11:39:28 | J5，J-Link 用于编程 | 安装镜像 1，11:41:44 确认断电。 |
| 4 | 14:09:16 | J5，J-Link 用于编程 | 另行授权的 sector3 热点更新，14:11:04 确认断电。 |
| 5 | 14:12:13 | J5，USB_UART 日志 | S1 PRE，14:12:33 确认断电。 |
| 6 | 14:13:15 | J5，USB_UART 日志 | S1 冷启动复核，14:13:26 确认断电。 |
| 7 | 14:15:06 | J5，J-Link 用于编程 | 原应用回退，热点已关，14:16:39 确认断电。 |

## 镜像 2 批次结束后的启动验证

负责人已把此检查纳入镜像 2 批次。第 2 次回退后先核对整片与 Options，保留现用 sector3。确认 C 断电且 J-Link 已断开、A/B/D/E 断电、热点关闭。连接 USB_UART 日志，确认 C 电源灯仍灭。启动被动记录器，在新 EFS 目录看到 `HOST_READY` 后协调放置 `POWER_ALLOWED`，紧接着由负责人仅用 J5 上电。见精确横幅即提示断电，未见横幅也须在上电 **60 秒**内关闭 J5。

```text
python -X utf8 node-b/tools/field01_original_boot_watch.py --job <new-EFS-directory> --port COM15 --execute
```

期望横幅为 `UNI DISARMED V1 C_BC_ABC NO_FLASH_WRITE`，已在原五板归档的 code 制品中核对。记录器只读串口，关闭 DTR/RTS，仅保存匹配结果和时间。保持热点关闭，不发 START、KEY 或联网指令。待准确横幅和人工断电两项确认，才可登记原应用启动通过。[启动观察器](../../tools/field01_original_boot_watch.py)
