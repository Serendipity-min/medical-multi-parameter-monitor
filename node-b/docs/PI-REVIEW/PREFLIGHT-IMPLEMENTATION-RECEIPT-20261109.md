# FIELD01 PREFLIGHT 实现与验证回执

2026-11-09 · **待 PI 审核**。规格为 Claude 的 `feefd17d3442466954955efce79723d4d36bef34`，实现与构建源码为 `2ef8a8245cf8e6cea6aa3d46adda1f7eb3833a54`。本轮为 Host 和离线 ARM，S0–S4 均 `NOT_RUN`。C 仍按负责人报告保持断电，USB_UART 和 J-Link 未接。原 FIELD01 事务与 START 消费记录保留。[PI 规格](https://github.com/Serendipity-min/medical-multi-parameter-monitor/blob/feefd17d3442466954955efce79723d4d36bef34/node-b/docs/PI-REVIEW/PREFLIGHT-DESIGN-20261109.md) · [实现架构](PREFLIGHT-ARCHITECTURE-20261109.md)

## 实现口径

- 固件在 DISARMED 启动时接受一次 `FIELD01 PRE`、`FIELD01 PRE 230` 或 `FIELD01 PRE 500`。PRE 只在原 45 秒准入内接收，有独立 60 秒诊断限时。主循环独占 ESP AT，回调仅处理未武装控制和人工 STOP。CAN、音频和业务网络在 PRE 中无初始化入口。DC-1 的 Wi-Fi/UART 故障和 CAN 溢出替身不会触发业务 STOP 锁存。
- 切速为 115200、230400、500000 白名单，OS16。收完整 setter OK 后等本端 TC 和 20 ms 保护间隔，要求区间内 RX 安静，再更改 BRR 并查五元组。恢复以 115200 的 AT OK 加五元组为准。一次受控恢复仍无法确认时报告 `NEED_POWER_CYCLE` 并阻止同次 START。20 ms 是待实物验证的工程初值。
- `AT+GMR` 压测最多 50 次，每次上限 300 ms。完整回复边界且版本可解析才算成功，记录尝试数、失败数、UART 错误增量、RX 环高水位和时间。切速后用前后 AT 验证同步。丢失回复边界、ESP 重启提示或 STOP 可提前结束，避免把后续试探当作有效压测。
- `field01_preflight.py` 仅在本次上电许可和新启动横幅后发送一条固定 PRE。发送标记先于串口写入，短写和超时保留标记。公共回执解析固定枚举和数字，原始 C 控制台字节保存在受限目录。断电字段由现场回执确认。[固件编排](../../../gateway/mqtt/src/field01_preflight.inc) · [独立主机脚本](../../tools/field01_preflight.py)

## Host 与 ARM

| 入口 | 工具与原生退出 | 结果 |
| --- | --- | --- |
| `python -X utf8 gateway/microphone/test_unified.py` | Windows Python 3.11.9，MinGW-w64 GCC 8.1.0，0 | 14 个 C 用例的编译/运行均 0。含原 START/T0、既有 Wi-Fi 失败的 9 个输入、PRE AT 的 22 个输入、命令一次性与 DC-1/7 隔离、TC/RX 安静与恢复边界的真实平台寄存器替身。 |
| `python -m pytest -q node-b/tests/test_field01*.py` | Python 3.11.9，pytest 9.1.1，pyserial 3.5，0 | 34 通过、8 子例通过。独立 PRE 脚本的 10 个场景含旧/重复启动、单发、短写、超时、畸形回执和脱敏。 |
| Windows FIELD01 ARM | Arm GNU 14.2.Rel1 GCC 14.2.1 / Newlib 4.4.0 / SPL V1.4.0，0 | IRQ 向量核验通过，boot 392 B，sector4 **61,616 B**、余 **3,920 B**。 |
| Windows 五板 ARM（无 `--field01`） | 同上，0 | IRQ 向量核验通过，boot 392 B，sector4 **58,048 B**。 |
| VPS 原工具链 | GCC 13.2.1 / Ubuntu Newlib 4.4.0 / SPL V1.4.0，1 | 受保护链接失败 `CODE_EXCEEDS_SECTOR4`。map LMA 跨度 **67,256 B**、越界 **1,720 B**。无通过镜像。 |
| VPS 同发行版对照 | Arm GNU Linux 14.2.Rel1 GCC 14.2.1 / Newlib 4.4.0 / SPL V1.4.0，0 | IRQ 向量核验通过。boot、code、HEX 三项 SHA-256 与 Windows 一致，sector4 **61,616 B**。 |

构建入口为下列命令。无 FIELD01 回归去掉最后一个选项。VPS 使用 `git archive --format=tar.gz <源码提交> gateway` 的已校验导出，构建输入 SHA-256 为 `58bc4138e83aef3e60b9818e3ca999863fc08f53b3156c87d87a48e7cf333b3a`，921,779 B。原工具链通过归档 wrapper 选择 Cortex-M4 hard-float nano。各次都使用同一 SPL V1.4.0 树。Windows 为实装候选和预算权威。

```text
python -X utf8 gateway/dual_can/build_arm.py --b5 --egress-final --tri --unified --split-flash --five-node --five-appliance --field01
```

相对 Windows `78a6d00` 的 57,776 B，sector4 **+3,840 B**，在 6,144 B 设计预算内。`.data+.bss` 由 82,432 B 增至 82,444 B，静态 SRAM **+12 B**。加 heap/stack 链接保留后 115,216 B，含 4 B 对齐差。CCM 64,000 B。LTO `.su` 的 `gateway_preflight` 单函数静态帧 464 B，运行时峰值 `NOT_RUN`。VPS 原工具链的 LMA 跨度比 Windows 大 5,640 B，跨版本差异单独登记。Host 的 ISR/CAN 算术留在架构回执，PRE 不裁定 TX 重载、CAN 并发和容量。

## 候选镜像与原始回执摘要

Windows `FIVE_FIELD01_C` 位于本机交付工作树的 `node-b/build/b4-c-arm-20261109T025835499941Z/`，另一个非 FIELD01 ARM 输出为 `node-b/build/b4-c-arm-20261109T025842965579Z/`。原始日志与二进制留在忽略目录。

| Windows 文件 | 字节 | SHA-256 |
| --- | ---: | --- |
| `FIVE_FIELD01_C-boot.bin` | 392 | `92d4657796f7073aea69d593d0ee3baa3e81331041a1e91f2bf1d5224c9c1089` |
| `FIVE_FIELD01_C-code.bin` | 61,616 | `f90540e1e28cf0ba88b0d6e18a5f6a6a3db5771cf9a55283d7a4c09d9134b3f4` |
| `FIVE_FIELD01_C.elf` | 107,156 | `a091424288b122832fea3e8c657d5c7382d67b5e619c0e1727af632f4cd3789e` |
| `FIVE_FIELD01_C.hex` | 174,498 | `f57027f20f5e964abc9254fba386651c4833b61b9f8b743283ec4a009006b295` |
| `unified-layout.json` | 1,052 | `325120b00b08a9f777a207b586e3bdb227ce266291b9708002343db15281c472` |
| `receipt.json` | 145,725 | `772962734a2dc722454b71b5a01ec2119bec74d26919fbcdaed228e49409dea4` |
| `gateway.map` | 177,586 | `c1b4f6f0bcca3b2a99b4aa4ebceba277acc45fee05bcc5a76bddd9425cc3925a` |
| `build.log` | 36,782 | `33eb30df9e3434feee9d558406ddde76d71c4c2632fa1c41f9b166d6c35600e6` |

Host C `node-b/build/unified-host-20261109T025835486129Z/receipt.json` SHA-256 为 `c756727a9d4bfdcf2f1ab6b7a518da04820f7fa9b24131fcd87590c5b3c1c870`。

VPS 原工具链归档在 `node-b/build/preflight-pi-2ef8a824/source/node-b/build/b4-c-arm-20261109T030200155943Z/`，`receipt.json` 为 `130976c6a8922ba402f2d4f1f473e944389dd8f766c65ddc6bea86c11ba8d86d`，`gateway.map` 为 `cc88cf16b759bc8afe7e6e6f1a8dc3fe8bde6cab9deb1a28403a6a06e394ffed`，`build.log` 为 `91903d687e07dba3cd0e8be90dd75f2ec70bd45078d00033380c53195e43625a`。

VPS 对照使用 [Arm GNU 14.2.Rel1 官方 Linux x86_64 包](https://developer.arm.com/-/media/Files/downloads/gnu/14.2.rel1/binrel/arm-gnu-toolchain-14.2.rel1-x86_64-arm-none-eabi.tar.xz)，149,739,784 B，SHA-256 `62a63b981fe391a9cbad7ef51b17e49aeaa3e7b0d029b36ca1e9c3b2a9b78823`。仅解包到任务归档，由工作区所有者使用，保留原 GCC 13.2.1 的独立结果。VPS Linux Python 3.12.3。

VPS 14.2 的输出目录为 `node-b/build/preflight-pi-2ef8a824/source/node-b/build/b4-c-arm-20261109T030435781633Z/`。烧录三项使用 Windows 表中的相同 SHA-256。ELF 与构建记录的摘要单独列出。

| VPS 14.2 文件 | 字节 | SHA-256 |
| --- | ---: | --- |
| `FIVE_FIELD01_C.elf` | 107,144 | `973324309e6808a6d9fb1fcb02e2ef052db7da42c106ad2100be8a5330233b5f` |
| `unified-layout.json` | 1,017 | `c2031b4ed2148ada067694a8d136125b1184750cd47a056859bcd73e204a0934` |
| `receipt.json` | 192,205 | `809978928fc5e6046ffc857dad15420b3bcc2c7a6d55d504cd6bf42bf5754c95` |
| `gateway.map` | 216,026 | `3c9d4634792a76490423a75f586e5d365bdf206a2d291da01bb212a0988133b5` |
| `build.log` | 35,984 | `65cde11cb668ec9801879542dece573f050b02e8354498ce8cff5be8650d729e` |

WP-H 的 Windows map 分账和 ISR 指令估算见架构回执。两种 VPS 结果使用相同候选源码和 SPL。原 Linux 13.2.1 的工具链与链接库组合同时不同，本次实测能复现组合差异，尚未单独归因到编译器版本或具体库对象。

WP-H 同基点 Windows `78a6d00` 的原构建回执含 45 条编译命令及完整的 103 项链接 driver argv（含程序名）。参数和对象次序已归档在 [R1 证据清单](../FIVE-APPLIANCE-20261107/PI-R1-EVIDENCE-MANIFEST.json) 的 `windows_field01_flags_from_original_receipt`。用原链接 argv 加 `-###` 复现 collect2 展开，加载 LTO plugin 及 wrapper，以 `-flto`、分段 linker script、`--gc-sections`、`-lm` 和三组 `-lgcc -lc_nano [-lnosys]` 链接。Windows 实选 `libc_nano.a` 无 `.gnu.lto*` 节。

同基点 `arm-none-eabi-nm -S --size-sort` 取 sector4 内前 30 个符号，单位为 B。仅按符号大小列出，别名可能共用地址。

```text
8704 main                       5732 service.part.0              2732 gateway_network_open
1936 b4_gateway_receive.part.0.constprop.0   1540 mqtt_event.lto_priv.0   1240 gateway_mqtt_progress
1192 gateway_mqtt_open.constprop.0            1160 diagnostic            960 unified_audio_local_poll
896 scalars.constprop.0         760 __udivmoddi4                   740 unified_audio_step
736 field01_snapshot            708 b4_hw_init                     654 qsort
628 mic_record_poll.part.0      576 _printf_i                      568 mp_json
504 rx_step                     504 reply_byte                     504 _svfprintf_r
504 _svfiprintf_r                492 mp_router_put                  480 esp_mqtt_send
460 at_command                  448 PDO_initMapping.constprop.0   448 irq
424 gateway_config_valid        376 unified_audio_fact_current     348 CO_HBconsumer_init
```

## PI 审核后准入

请核对 115200 恢复、60 秒预算、DC-1/7 及独立主机的单发约束。现场白名单需纳入 `ATE0`、`AT+SYSSTORE=0`、`AT+CWMODE=1,0`。必须见 `SYSSTORE=0` 的 OK 才能设 STA 或发 CWJAP。确认候选和原五板 C 的 sector0/4 回退身份后方可进入 S0。实板 UART 五元组、Wi-Fi 子码、压测统计和容量均待现场取证。
