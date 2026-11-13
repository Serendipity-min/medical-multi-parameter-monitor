# 五板固件、SDK 与 ESP-AT 接手说明

**2026-11-09。** 固件源码锚点为 `codex/field01-egress-probe@e90f9f6a3ae2534d0988067494e64ef43d3b5128`，集成基点为 `4616c30`。以 [FIELD01 结果](FIELD01-RESULTS.md)、[机器回执](FIELD01-RECEIPT.json) 和 [原五板镜像清单](../FIVE-NODE-MIGRATION/FIVE41-20261106/CURRENT-IMAGES.json) 区分历史实装、当前探针及后续候选。

## 板卡与代码入口

| 板 | 五板角色 | 实装与构建 |
| --- | --- | --- |
| A，节点 1 | SpO₂、脉率、PPG | C.CAN1 上的测量源。实装以原五板镜像清单为准 |
| B，节点 2 | ECG、RESP、心率、呼吸率 | C.CAN2 上的测量源。历史 ECG60 与 RR18 分开取证 |
| C，节点 3 | 双 CAN 汇聚、队列、ESP8266、coreMQTT、K1 录音与 TTS | 最后验证实装为 `FIVE_FIELD01_C`。本机及 VPS 的构建入口是 `gateway/dual_can/build_arm.py` |
| D，节点 4 | GY641 物体表面温度 | C.CAN2。温度传感器使用 UART4，本地显示屏使用 COM2 |
| E，节点 5 | 无创血压 | C.CAN1。血压测量由现场屏发起，结果按完成代次跟踪，90 秒失效 |

A/B/D/E 的目标工程和 ARMCC/Keil 构建仍在 Windows 执行。五板采用两段独立 500 kbit/s 经典 CAN，C.CAN1 为 A/E，C.CAN2 为 B/D。FIELD01 现场断电测得 40.0 Ω 和 40.9 Ω，为受控诊断条件。正式双端 120 Ω 的总线通常约 60 Ω，原 FIELD01 结果没有完成物理层验收。[五板接线合同](../FIVE-NODE-MIGRATION/06-CAN-Wiring-and-M1-Contract.md)

C 的入口为 [network_main.c](../../../gateway/b5/network_main.c)，出站调度为 [egress.h](../../../gateway/b5/egress.h) 与 [router.c](../../../gateway/storage/router.c)，ESP-AT 及 MQTT 位于 [platform.c](../../../gateway/mqtt/src/platform.c) 与 [gateway_transport.c](../../../gateway/mqtt/src/gateway_transport.c)。网络由单一所有者推进。隔离 TLS 入口 28895，观察端 18885 仅经 SSH 转发。历史吞吐约 8.08 批/s，对比源输入下界 10.45 批/s，保持 `CAPACITY_NOT_PASS`。FIELD01 没有得到新的容量或 AT 阶段分解结论。[P3 报告](P3-REPORT.md)

## C 离线构建

SDK 来源为原 Windows 构建使用的本地 STMicroelectronics V1.4.0 树。包内 `Release_Notes.html` 标明 **V1.4.0 / 04-August-2014**，保留包内原许可。ST 的产品入口是 STSW-STM32065，本次使用本地固定版本，避免把官网当前版本当作该归档。[ST 产品页](https://www.st.com/en/embedded-software/stsw-stm32065.html)

在 VPS 以工作区所有者身份执行。依赖根目录须直接包含 `Libraries/`。用 FIELD01 分支独立 checkout 构建。若另用 `--network-link` 的历史 H3 对照目标，须保留其 Git 对象 `a5cdd5b0`。

```bash
export P5_STM32F4_SDK_ROOT=/home/claudedev/workspaces/medical-multi-parameter-monitor/node-b/build/firmware-handoff-20261109/STM32F4xx_DSP_StdPeriph_Lib_V1.4.0
export P5_ARM_TOOLCHAIN_BIN="$(dirname "$P5_STM32F4_SDK_ROOT")/toolchain-bin"
python3 gateway/dual_can/build_arm.py --b5 --egress-final --tri --unified --split-flash --five-node --five-appliance --field01
```

VPS 原有 ARM GCC 13.2.1 缺 Newlib 头文件及 nano 链接库。已在交付目录内解包 Ubuntu 的 Newlib 4.4.0 包，用 `toolchain-bin` 选择 Cortex-M4 hard-float 的头文件、specs 和库。系统包与全局 PATH 无需变更。验证源码位于同目录的 `verify-field01`，从其中执行上面的命令。

本次 VPS 实编 `FIVE_FIELD01_C` 通过，boot 392 B、sector4 63,204 B，总加载 63,596 B，sector4 余 2,332 B，IRQ 向量核验通过。制品位于 `verify-field01/node-b/build/b4-c-arm-20261109T014250124438Z/`，编译日志为 `vps-field01-build-newlib.log`。这是离线构建回执。

用新输出目录里的 `receipt.json`、`unified-layout.json`、`gateway.map` 和栈用量回执核对。最后实装 C 的原 Windows 产物为 boot 392 B、sector4 57,596 B，总加载 57,988 B。Linux 工具链重编产物须另行登记，实际镜像仍以安装回执为准。探针规划只写 C sector0/4，保留 sector3、Options 及其他扇区。安装及原镜像回退须另行授权。[安装与回退证据](FIELD01-ISOLATION-20261107.md)

## VPS 文件校验

交付目录为工作区下的 `node-b/build/firmware-handoff-20261109/`。包、PDF 与临时构建目录由 VPS 本地 Git exclude 隔离。

| 文件 | 字节 | SHA-256 |
| --- | ---: | --- |
| `STM32F4xx_DSP_StdPeriph_Lib_V1.4.0.tar.gz` | 82,765,823 | `aeaf35fdc64e1e4711611d15a279617cd40e81596e4eb127d284eea20ae6c8b9` |
| `ESP-AT-ESP8266-v2.3.0.0.pdf` | 5,111,858 | `df19007477d5ed495386b9a20eec77f76d81e6aa1e4d7f898dc8667ba39b6cdc` |

## 实物 ESP8266 与手册

既有替换模块的完整 `AT+GMR` 版本行如下。最近一次 FIELD01 从 C 记录到 `GW AT_VERSION value=2.3.0.0`，这条缩写日志只保留了 AT 数字版本。

```text
AT version:2.3.0.0-dev(s-bcd64d2 - ESP8266 - Jun 23 2021 11:42:05)
SDK version:v3.4-22-g967752e2
compile time(b498b58):Jun 30 2021 11:28:20
Bin version:2.2.0(ESP8266_1MB)
```

以 **ESP8266 2.3 系列**官方指令集作为当前 AT 核心的参考。上面的 `Bin version` 是镜像标识。实际模块是 1 MB dev 构建，是否支持个别指令、实际返回值以设备查询证据为准。[完整 GMR 实录](../../../gateway/esp_at_probe/evidence/replacement-module-query-2026-09-20.json) · [Espressif 1 MB 构建说明](https://docs.espressif.com/projects/esp-at/en/release-v2.3.0.0_esp8266/AT_Binary_Lists/ESP8266_AT_binaries.html) · [官方 PDF](https://docs.espressif.com/_/downloads/esp-at/en/release-v2.3.0.0_esp8266/pdf/)

| 命令 | 接手时要核对的内容 |
| --- | --- |
| `AT+CWJAP` | 失败可返回 `+CWJAP:<n>`。1 超时，2 密码错误，3 找不到 AP，4 连接失败，其他值按未知保留。手册默认关联时限 15 秒。当前 FIELD01 只留下 `GW FAIL WIFI`，不能据约 15.1 秒倒推子码 |
| `AT+UART_CUR?` | 查询实际 baud、数据位、停止位、校验和流控。历史探针查询得到 OK，归档摘要缺参数值。C 的 STM32 侧使用 USART3，115200、8N1、无硬件流控。ESP 本次实际返回值待核 |
| `AT+UART_CUR=...` | 修改当前 UART 设置，断电不保留。`AT+UART_DEF` 写持久设置，现场排查阶段只查询，变更需独立授权 |

[Wi-Fi 指令与错误码](https://docs.espressif.com/projects/esp-at/en/release-v2.3.0.0_esp8266/AT_Command_Set/Wi-Fi_AT_Commands.html#at-cwjap-connect-to-an-ap) · [UART 指令](https://docs.espressif.com/projects/esp-at/en/release-v2.3.0.0_esp8266/AT_Command_Set/Basic_AT_Commands.html#at-uart-cur-current-uart-configuration-not-saved-in-flash)

## 当前阻断及后续交接

1. FIELD01 的唯一 START 已被 C 接受并消耗。C 在 ESP 加入热点阶段失败，发出停止回执，未到 T0。150 秒评价、C 端 TLS/MQTT 和 K1/TTS 均未运行。现场最终断电回执仍待核。
2. 历史 ECG60/RR18 使用 RAM 注入的同一热点配置，本次探针读 sector3，归档对比证实两字段不同。实际手机热点当时使用哪套参数仍未验证。先在受限环境核对，不在文档中保存 SSID、口令、真实端点或原始串口。
3. USB_UART 同时给 C 供电，接入即开始固件计时。以后若有新授权，先让隔离观察器和主机就绪，再插 USB_UART，等新启动标记才发 START。原授权的 45 秒就绪、150 秒评价和 210 秒上电上限分别保留。
4. 若新授权需定位入网失败，可在离线候选里只提取 `+CWJAP` 的数字子码及是否缺失，并保留 UART 错误计数。完整 AT 命令和回复可能带敏感字段。设备、板上配置、正式云端和五板基线的写操作各自受原授权约束。

[FIELD01 证据索引](FIELD01-EVIDENCE-INDEX.md)
