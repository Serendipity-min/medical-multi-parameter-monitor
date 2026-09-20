# Gateway-C 硬件与工具只读核对

日期：2026-09-20。分支：`dev/p-gateway-cloud-v07`。
本轮仅阅读资料、枚举设备、检查工具版本和服务器服务状态；未复位、停止 MCU、烧录或修改服务器配置。

## 本机资料与识别结果

用户所指目录在磁盘上的实际名称为：

- `E:/stm32/stm32文件`：开发板原理图、STM32F407 数据手册、参考手册和标准外设库。
- `E:/stm32/ai_serial_console`：串口控制台、MCP 和构建/下载脚本。
- `E:/stm32/元器件链接_技术手册`：ESP8266 TCP 与 OneNET MQTT 教程。
- `D:/MQTTX/cli/mqttx.exe`：本次执行 `--version` 返回 1.13.0；MQTTX 是客户端，不能代替服务器 Broker。

Windows 当前能枚举 `USB-SERIAL CH340 (COM15)` 和 `J-Link driver`，设备状态均为 OK。
这只能证明 USB 设备被识别，不能代替 MCU 当前芯片 ID、固件和 ESP AT 版本的实测。

板卡资料记录 STM32F407ZGT6、1 MiB Flash、8 MHz HSE；原理图题名为 STM32F4 神舟号 V2.0。
既有记录曾识别到 ai-console-0.1.0，但本轮未读取当前运行固件，不将历史识别结果视作本轮实测。

## 接口与操作边界

原理图第 3 页显示 CH340 的握手信号经晶体管连接 RESET/BOOT0。
第 5 页显示 P1 为 ESP-01 插座，供电为 3.3V；P5 选择 USART3 与 RS232 或 Wi-Fi/蓝牙的连接。
结合本机引脚手册，ESP 接口候选为 PB10/TX、PB11/RX，P5 短接 3–5、4–6。
上述为资料中的接法，实际模块、插接方向、跳帽、供电和并接外设仍需用户确认。

COM15 连接 STM32 USART1（PA9/PA10），不是直接连接 ESP8266。
当前控制台源码仅提供 info/status/ping/LED 命令，没有 USART3 AT 查询或桥接功能。
因此不能通过向 COM15 直接发送 AT 命令来验证 ESP 固件。

检查 `mcp/stm32_console_mcp.py` 发现，初始化串口时先用默认握手状态打开设备，再设置 DTR/RTS 为 False。
这可能在自动下载电路上产生瞬态，不能保证零复位。`flash.py --probe` 虽不写 Flash，
仍通过 ROM Bootloader 识别，会控制复位/启动引脚。本轮未调用这两条路径，也未调用 J-Link 连接、halt 或 reset。
此外，烧录脚本的实际实现不能仅凭说明文字认定已在擦除前完成 UID 核验；后续如需烧录，必须先明确备份、目标校验与恢复流程。

## ESP8266 资料取舍

两份 PDF 是功能教程，不能证明当前模块的 AT 版本、Flash 容量或 TLS 证书校验能力。
OneNET 教程采用 ESP 内置 MQTT AT 命令，与合同要求的 STM32 MQTT Client + ESP TLS Socket 不同；不直接移植该架构。

该教程第 4–5 页建议将 USB-TTL 的 5V 接到模块 3V3，不能照做。
板上 P1 供电为 3.3V；[乐鑫 ESP8266EX 数据手册](https://documentation.espressif.com/0a-esp8266ex_datasheet_en.html)
给出的工作电压范围为 2.5–3.6V。带稳压底板的输入与裸模块 3V3 引脚必须区分。

[ESP8266 ESP-AT 官方 TCP/IP 文档](https://docs.espressif.com/projects/esp-at/en/release-v2.2.0.0_esp8266/AT_Command_Set/TCP-IP_AT_Commands.html)
提供 SSL Socket、CA 验证、Common Name 和 SNI 命令，但必须以实物 `AT+GMR` 及支持命令为准；不默认当前模块具备这些能力。

## 服务器只读结果

用户已确认腾讯云防火墙放行 TCP 8883，本轮未修改防火墙。

| 检查项 | 结果 |
|---|---|
| 系统 | Ubuntu 24.04 / x86_64 |
| 现有 Nginx / medical-monitor | active |
| Docker | 已安装且 active |
| Mosquitto / mosquitto_passwd | 可执行文件已存在 |
| Mosquitto systemd 服务 | inactive |
| 80 / 443 / 18765 | 存在监听 |
| 1883 / 8883 | 尚无监听 |

放行 8883 不等于 Broker 已提供 TLS 服务。尚未读取或修改 Broker 配置，不启动可能已有的未知配置。

## 待确认

1. ESP8266 实物型号、是否已插入 P1、当前 P5 跳帽与供电；是否有直连 ESP 的 USB-TTL 读取路径。
2. 当前 STM32 程序是否允许短暂复位，以便通过现有控制台读取信息；此确认不包含擦除或烧录授权。

以上确认前暂停硬件探测与写入。MQTT/TLS 云端迁移仍未完成，不能将本次环境核对作为合同准出验收。

## 后续实物确认与串口读取

用户随后确认：ESP8266 已插入开发板右上角 Wi-Fi 插座，P5 跳帽全部拔掉，
当前仅接入 ESP8266，并允许短暂复位、烧录以读取信息。

- 调用现有控制台 `info` 返回“不是预期 JSON”，未获得型号或 AT 固件信息。
- 随后以 115200、8N1 被动监听 COM15 三秒，打开前将 DTR/RTS 置 False，未发送命令。
  收到连续 `DMA_ADC` 日志，包含 seq/raw/avg/min/max/mv/dma_errors 字段，
  说明当前运行的是 ADC/DMA 输出程序，而非该 MCP 所要求的 ai-console JSON 控制台。
- 这次失败不是 Windows 无法识别串口；COM15 能接收连续文本。
- P5 全部拔掉时，按原理图 USART3 与 Wi-Fi 插座的 TX/RX 两路未接通；
  更换 STM32 固件不能修复物理断路，故本轮未继续烧录或调用 Bootloader 探测。
- 下一步由用户在断电状态下按原理图编号短接 P5 的 3–5 和 4–6。
  编号须以实物丝印/方形焊盘方向核对，不能把页面图的朝向直接当作实物朝向。
  Wi-Fi 插座的原理图编号为 P1，不要求用户找到另一个插座。

P5 接通后再准备可回滚的 STM32 查询固件，读取 ESP AT 版本和 TLS 支持情况。
当前仍不能认定 ESP 已响应、已联网或满足 MQTT/TLS 条件。

## P5 接通后的授权硬件实测

用户确认接好 P5，并授权继续复位/烧录读取信息。本节为后续操作，已超出前述首次只读核对阶段。

1. J-Link SWD 实测：Cortex-M4，DBGMCU 芯片族 ID `0x413`，Flash 容量 1024 KiB，
   VTref 3.300V；UID 与本机历史目标记录匹配。
2. 整片 Flash 读取两次，1,048,576 字节完全一致，SHA-256：
   `852d7618f8fc46c80cbe035ebd41f4e21e4d5a76a26cf10a39e0600f7a89ffb8`。
3. 独立构建 `gateway/esp_at_probe`；仅包含固定 AT 查询，不设置 Wi-Fi、证书或 ESP 固件。
4. 首次 J-Link 下载报告 RAMCode 加载失败。复位停核、重新比对原 Flash 后下载成功；
   下载器报告处理首扇区 16 KiB，4912 字节固件回读通过。
5. PC → USART1 → STM32 → USART3 → ESP 查询完成，所有响应接收错误与缓冲溢出均为零。

| 查询 | 实测结果 |
|---|---|
| AT | OK |
| AT+GMR | OK |
| AT version | 1.1.0.0（May 11 2016 18:09:56） |
| SDK version | 1.5.4（baaeaebb） |
| compile time | May 20 2016 15:08:19 |
| AT+UART_CUR? | ERROR |
| AT+CIPSSLCCONF? | ERROR |
| AT+CIPSSLCCN? | ERROR |
| AT+CIPSSLCSNI? | ERROR |
| AT+CIPRECVMODE? | ERROR |

结论：P5 接通后 AT 通信成功；此前不能读取 ESP 的接线/固件通道问题已解决。
上述新式 SSL 查询在当前固件上不可用，不能据此宣称支持合同要求的服务端证书验证。
也不能仅凭 ERROR 断言模块完全不支持任何 SSL。
升级方案尚需确认 ESP 模块型号、Flash 容量与原固件备份路径，不擅自选择或覆盖 ESP 固件。

完成查询后已恢复 STM32 原始首扇区，并验证完整 1 MiB Flash 与备份一致；
COM15 被动监听确认 `DMA_ADC` 输出恢复。ESP 固件、Wi-Fi 配置及服务器均未修改。

证据：[硬件查询 JSON](../../../../gateway/esp_at_probe/evidence/hardware-query.json)。
测试代码：[诊断固件说明](../../../../gateway/esp_at_probe/README.md)。
原始 Flash、备份校验、下载/恢复日志、原始 AT 回复仅存于本机
`C:/Users/Serendipity/.codex/private/stm32-gateway-probe-20260920/`，不进入 Git。
