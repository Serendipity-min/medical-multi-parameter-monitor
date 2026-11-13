# PI R1 Codex 离线回执

2026-11-09。依据 Claude 审查提交 `7e6980a` 执行。交付分支从 `84e4791` 建立，审查原文摘取为 `922d2fa`，原现场工作树保留。全部实板项为 `NOT_RUN`。历史 FIELD01 唯一 START 已消耗，断电确认仍为 `PENDING`。[PI 原文](R1-20261109.md) · [历史 FIELD01 回执](../FIVE-APPLIANCE-20261107/FIELD01-RECEIPT.json)

| 包 | 原状态 | 本轮状态及提交 |
| --- | --- | --- |
| WP-A | 后端整 90 秒测试失败，旧 Paho 白名单检查失败，三处让路阈值重复 | **PASS（Host）** `7011961`。Backend 在完成年龄或接收年龄达到限值时清值，NIBP 回归覆盖 89.999、90.000、90.001 秒并重发同完成时刻。Backend 37 通过、6 跳过。三处 2500 ms 保留原比较边界，真实 Router 调度夹具通过。Paho 固定字节和补丁校验保留，复用现有 coreMQTT active 构建检查，9 项 Paho 单测和两项完整性入口退出 0。 |
| WP-B | `GW FAIL WIFI` 无子码 | **PASS（Host、Windows ARM）** `ad459b0`。FIELD01 失败路径输出数字或 `NONE` 及 UART 累计错误。9 个夹具走真实入网失败路径，覆盖正常子码、无子码、畸形/截断、超长和回显。ARM 原生退出 0，IRQ 向量核验通过，sector4 57,776 B、余 7,760 B，含 WP-A 的累计差值为 +180 B（对照原 Windows FIELD01）。 |
| WP-C | 现场出站约 8.08 批/s，输入下界约 10.45 批/s | **BLOCKED**。U-02 的设备原始五元组及切换等待证据缺失，U-01 的 VPS 原始 map 和展开参数未在 Windows 归档，U-04 的实际最大中断延迟未知。波特率、计时和 P3 重跑均未进入实现，容量仍为 `CAPACITY_NOT_PASS`。 |
| WP-D | 忽略目录引用缺少可跟踪清单 | **PASS（本机清点）** `1792430`。83 个历史路径中 78 个可核验，5 个 VPS 档案在 Windows 记 `MISSING`。新制品独立登记。 |
| WP-E | START 先于 Wi-Fi 入网 | **PASS（流程文档）**。下文冻结既有事件顺序及新开窗前置回执要求。现有运行时未提供 START 前的 C 入网回执，工具执行路径待单独批准设计后变更。 |

命令、源码 SHA-256、产物 SHA-256、编译/运行退出码见清单。Python 3.11.9、pytest 9.1.1、MinGW-w64 GCC 8.1.0 与 ARM 工具链分别登记。PI-08 的端接、A 入口间断和 ECG/RR 同窗双有效继续单独取证。PI-09 的裸机方案维持。[证据清单](../FIVE-APPLIANCE-20261107/PI-R1-EVIDENCE-MANIFEST.json) · [P3 报告](../FIVE-APPLIANCE-20261107/P3-REPORT.md)

## U-01 至 U-14

### U-01 · 两套构建口径

| 项 | Windows 历史实装来源 | VPS 离线验证 |
| --- | --- | --- |
| 工具链 | Arm GNU 14.2.Rel1 GCC 14.2.1、GNU ld 2.43.1、Newlib 4.4.0、SPL V1.4.0 | GCC 13.2.1、Ubuntu Newlib 4.4.0、SPL V1.4.0。Cortex-M4 hard-float nano 库和 specs 由包装器选取，ld 版本 UNKNOWN |
| 编译/链接 | `-Os -flto`、Cortex-M4 Thumb hard-float、分段链接、`--gc-sections`、nano/nosys specs；完整归一化参数及对象顺序见清单 `windows_field01_flags_from_original_receipt` | 同一构建入口及参数声明。包装器展开的完整命令 UNKNOWN |
| sector4 | map 中 `.text` 起于 `0x08010000`、长 `0xe08c`，`.data` 装载地址 `0x0801e09c`、长 `0x60`，含中间段总跨度 **57,596 B**，余 7,940 B | 交接回执为 **63,204 B**、余 2,332 B。原始 map 未在 Windows 找到，逐段占用 UNKNOWN |

实装身份和现场候选以实际提交的 Windows 工具链制品及对应安装回执为准。若要求两套工具链都可交付，预算先用两者中较小的剩余量 2,332 B，随后各自对新候选重算。两组相差 5,608 B，已确认 GCC 版本及库选取环境不同，具体差值归因仍为 UNKNOWN。对齐相同编译器、库、specs 与构建参数后做 map/符号逐段差分，才可拆出贡献。[构建交接](../FIVE-APPLIANCE-20261107/FIRMWARE-SDK-ESPAT-HANDOFF-20261109.md) · [构建入口](../../../gateway/dual_can/build_arm.py) · [证据清单](../FIVE-APPLIANCE-20261107/PI-R1-EVIDENCE-MANIFEST.json)

### U-02 · UART 查询与手册

实物 `baud,databits,stopbits,parity,flow` 为 **UNKNOWN**。历史替换模块回执记录 `OK`，字段为命令、字节数、错误和终态，可访问档案中未找到参数行。归档哈希一致的官方 PDF 在 §3.1.8 印刷页 32–33（PDF 第 36–37 页）给出 ESP8266 **80–4,500,000 baud**，说明查询值可能因分频略有差异，设置不保存到 Flash。该节未给出设置后最小等待或 ACK 切换时序，实际 1 MB dev 模块两档速率的能力仍待验证。[替换模块回执](../../../gateway/esp_at_probe/evidence/replacement-module-query-2026-09-20.json) · [官方 PDF 第 36 页](https://espressif-docs.readthedocs-hosted.com/_/downloads/esp-at/en/release-v2.3.0.0_esp8266/pdf/#page=36) · [官方网页版](https://docs.espressif.com/projects/esp-at/en/release-v2.3.0.0_esp8266/AT_Command_Set/Basic_AT_Commands.html#at-uart-cur-current-uart-configuration-not-saved-in-flash)

### U-03 · UART 错误和 P1 流控

ECG60 和 RR18 各有 71 条 `B5 DIAG`，两窗 `uart_err` 采样均为 0，启动 `UNI UART baseline=0 total=0`。FE/NE/ORE 合并计入硬件错误，软件 RX 环溢出另累计再求和。逐项独立计数 **UNKNOWN**。本机《STM32F4神舟号_原理图_V2.0》第 5 页 P1 ESP-01 头座只有 RXD/TXD、电源、复位/使能及 GPIO，**无 CTS/RTS 引出**。实物高波特率丢字节风险仍为 UNKNOWN。[错误计数源码](../../../gateway/mqtt/src/platform.c#L59) · [板上路由说明](../B5-G3-01-AT-STOP-REVIEW.md)

### U-04 · NVIC 与 CAN 溢出

FIELD01 代码配置 `NVIC_PriorityGroup_4`，四位抢占优先级，子优先级 0。P1 两窗均记录 AIRCR PRIGROUP=3、CAN1/2 优先级均为 3。

| 中断 | 抢占优先级 | 证据 |
| --- | ---: | --- |
| USART3 RXNE | 0（复位默认推定） | 固件仅启用 IRQ，未显式设置该优先级。历史实板 IPR 值 UNKNOWN |
| CAN1 RX0 | 3 | 源码与 P1 `UNI IRQ can_a=3` |
| CAN2 RX0 | 3 | 源码与 P1 `UNI IRQ can_b=3` |
| SysTick | 15 | SDK V1.4.0 的 CMSIS `SysTick_Config` 设置最低优先级 |

P1 两窗 `ABC A_CAN` 与 `B5 DIAG` 的两段 CAN 溢出采样均为 0。最大中断延迟 **UNKNOWN**。[USART3 和 SysTick 初始化](../../../gateway/mqtt/src/platform.c#L653) · [CAN IRQ 配置](../../../gateway/dual_can/b4_bxcan.c#L102)

### U-05 · 真实 SEND OK

P1 ECG60/RR18 的 `SEND_OK_wait` 样本增量为 **2,384 / 2,376**。末次累计直方摘要分别为 p50 上界 **25 / 25 ms**、p95/p99 上界 **50 / 50 ms**、最大 **45 / 43 ms**。累计摘要含启动。FIELD01 未产生逐事务 SEND OK 样本，真实链路独占耗时占比 UNKNOWN。[P3 机器证据](../FIVE-APPLIANCE-20261107/P3-EVIDENCE.json)

### U-06 · sector3 与 RAM 字段

取归档 C Flash sector3 字段首个 NUL 前的字节，与两份相同的 RAM 临时配置逐字段比对。只列字节数与 SHA-256 前 8 位。

| 字段 | 是否相同 | sector3 字节 / 摘要 | RAM 字节 / 摘要 |
| --- | --- | --- | --- |
| SSID | 否 | 15 / `00fbf133` | 11 / `f39d82da` |
| Wi-Fi 密码 | 否 | 8 / `f07910aa` | 10 / `c775e7b7` |

### U-07 · FIELD01 当次热点

2.4 GHz **UNKNOWN**，隐藏 **UNKNOWN**，兼容模式 **UNKNOWN**，空闲自动休眠 **UNKNOWN**。历史成功窗的信道仅证明当时使用过 2.4 GHz。

### U-08 · 脱敏 Wi-Fi 日志

```text
ECG60: GW WIFI_SIGNAL channel=11 rssi=-26
RR18:  GW WIFI_SIGNAL channel=11 rssi=-31

FIELD01:
UNI UART baseline=0 total=0
GW OK AT
GW OK ECHO
GW OK VOLATILE
GW OK STA
GW AT_VERSION value=2.3.0.0
GW FAIL WIFI
B5 STOPPED NO_AUTOREARM
```

START 接受至 Wi-Fi 失败 15.125 秒，观察器未收到遥测/音频，原串口档 SHA 与机器回执一致。[FIELD01 机器回执](../FIVE-APPLIANCE-20261107/FIELD01-RECEIPT.json)

### U-09 · 既有事件序列与新准入（WP-E）

1. 既有流程为隔离 Broker 与观察器就绪 → `receiver/READY.json` → 控制器 `HOST_READY.json` → 现场发 `POWER_ALLOWED`，控制器开始总上电预算 → 插 USB_UART 给 C 上电，COM15 枚举/打开 → 新 `FIELD01 DISARMED` → `C_BOOT_BANNER.json` → 先创建 `START_SENT.json` 再发送一次 START → C `FIELD01 START_ACCEPTED` → AT/Wi-Fi/授时/TLS/MQTT → 固件发 T0 后主机记 `T0.json` → 150 秒评价 → STOP、`C_STOPPED.json`、`HOST_ENDED.json` 与观察器收尾。插入 USB_UART 开始固件 45 秒就绪计时。主机从许可计总预算 210 秒，保留 10 秒收尾，收到新启动标记后还收紧为至多再等 45 秒。
2. 新窗口的准入回执应先核对热点匹配和隔离 Broker，并由另行批准的 C 预检提供实际加入/IPv4 就绪证据。回执绑定本次事务、C 启动代次、获准 Wi-Fi 配置来源和单调时间，只保存结果枚举及诊断计数。缺失、超时、不同启动代次或 Wi-Fi 失败时停止在 START 前，记录为 `PRECONDITION_BLOCKED`。预检涉及真实 Wi-Fi 状态，其动作、时限及授权计数由负责人另定。
3. 现有固件在接受 START 后才执行关联。仅用旧固件、被动扫描或主机侧 TLS 自检，无法提供 C 的同次入网回执。实施前需冻结可验证的前置回执路径及同次上电时限。旧事务和 START 消费记录保留。获得 T0 后的异常单列为评价窗结果。

[控制器](../../tools/field01_short_window.py#L34) · [固件 START 入口](../../../gateway/b5/network_main.c#L469) · [隔离与 USB_UART 历史回执](../FIVE-APPLIANCE-20261107/FIELD01-ISOLATION-20261107.md)

### U-10 · 合同原文和边界

《FIVE-NODE-04》§5 原文为“**NIBP 的 90 s 有效期从 E 的测量完成时刻计算，不会因用户开始说话而暂停。**” §4 M3 写“**90 s 后失效。**” 合同正文未明确书写数学比较符。P2 已冻结 AI/C 在整 90 秒拒读及边界前 1 ms 可读，故本轮采用审查建议的严格 `<90 s`，让 Backend、WSS 与 AI 同步。WSS 使用 Hub 快照，Web 根据快照 validity 显示，未发现独立 90 秒比较。通用 Hub 两个年龄判断同时收敛至到期即失效，5 s 的数值期限保留。[五板合同 §5](../FIVE-NODE-MIGRATION/04-Five-Node-Contract.md#5-五板窗口与当前血压验收) · [P2 边界记录](../FIVE-APPLIANCE-20261107/P2-REPORT.md) · [Web 视图](../../../cloud/web/src/model/viewModel.ts#L24)

### U-11 · 原严格大于是否有意

**UNKNOWN**。原始引入提交 `26e695f` 无说明该 1 ms 差异的动机，时间未到及回拨由年龄比较前的方向检查处理。WP-A 保留队列音频 `>2500 ms`、在途和补传 `>=2500 ms`，夹具覆盖 2499、2500、2501 ms 和未来时间戳。

### U-12 · CI Paho 步骤

最近一次记录为 **SKIPPED**，2026-10-10 14:31:43（北京时间，UTC 06:31:43）。旧 workflow 在 P5 scope 跳过该步骤。本地复现旧检查退出 1，WP-A 后新检查和其单测退出 0。[GitHub Actions 运行](https://github.com/Serendipity-min/medical-multi-parameter-monitor/actions/runs/38031226035)

### U-13 · 本机原件清单

本机 FIELD01 构建、Host、隔离公开回执与唯一 START 的五个受限原件均可核验，五个受限原件 SHA 全部匹配跟踪回执。VPS 的 receipt、map、构建日志、SDK 包及其 PDF 归档路径在 Windows 标为 `MISSING`。官方同哈希 PDF 本轮从公开源读取，VPS 归档位置独立保留。清单内每个可用文件均有路径、字节数和 SHA-256。[证据清单](../FIVE-APPLIANCE-20261107/PI-R1-EVIDENCE-MANIFEST.json)

### U-14 · HSE 8 MHz 与 PLL

C 双总线文档写明继承 H3 的 8 MHz HSE，PCLK1 8 MHz，以 1×16 TQ 得到 500 kbit/s。驱动也有 42 MHz、6×14 TQ 分支。FIELD01 的 `system_hse.c` 直接以 HSE 驱动，PLL 与总线分频关闭。最初选择 H3 无 PLL 的独立决策记录及五板 C 实板 PLL 试验均为 **UNKNOWN**。[双总线设计](../../../gateway/dual_can/README.md#L56) · [时钟源码](../../../gateway/dual_can/system_hse.c)
