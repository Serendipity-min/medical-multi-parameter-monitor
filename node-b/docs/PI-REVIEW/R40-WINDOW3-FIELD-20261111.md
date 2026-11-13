# R40 窗口 3 实板回执

**2026-11-11 · `STOP_TARGET`，预登记采集 `NOT_RUN`。** 五板冷启动后，冻结应用在 MQTT 建链前进入本地停止。现场随后确认全部断电。本窗没有人体接触、袖带加压或遥测载荷。 [R40 §2–§8 批次卡](https://github.com/Serendipity-min/medical-multi-parameter-monitor/blob/752de06/node-b/docs/PI-REVIEW/R40-20261111.md)

## 现场核对与额度

- 负责人将输入调整为 ECG 模拟器仅输出 60 bpm ECG，血氧、体温和血压计划用志愿者。模拟 ECG 派生 HR 按模拟来源记载，真人 PR 对比模拟 HR 的生理判据不适用。未采集上述数据。
- 上电前，现场确认五板、模拟器、工装和泵采用电池，记录笔记本拔掉充电器，其他市电设备断开，志愿者与设备分离。现场确认志愿者条件、知情同意、两人分工及三种血压停手段。Windows 现场记录显示交流供电断开。J-Link 用于 C 单板只读核验，核验后现场确认已从 C 断开。
- C 单板只读上电 1 次，五板冷启动 1 次，隔离 Broker 1 次。安装、Flash 写入、热点切换、START、J-Link 复位和血压泵启动均为 0。未使用上电异常的重来额度。本地故障锁止按 R40 §4 引用的 R36 停止条件留档停机。
- 以 C 单板上电提示为相对零点，+24.453 s 收到 C 已上电回报，+146.391 s 记 C 已关回报，+157.516 s 记 J-Link 已断开和热点已开。+173.047 s 发五板上电提示，+201.672 s 收到五板已上电回报，+230.359 s 记停机断电提示，+257.578 s 记全部断电回报。以上为主机打点，实际拨动开关秒数 `UNKNOWN`。人体佩戴时长 0。

## C 镜像只读核验

源码 `2a8ee475667fac0ccf23a212bdda17c78de98c35`。首次完整 1 MiB Flash、16 B Options 以及目标身份与 R36 的安装后归档逐字节一致。读回 code SHA-256 为 `ce8d3490d03c728c7bde0fa90a12da0a192653513905571883456455b01d2a8d`。完整读回后的 CPU 快照在 Flash 应用态，未见 Fault。 [R38 冻结包](R38-WP-AW-FREEZE-20261111.md) · [R36 安装回执](R36-WINDOW2-FIELD-20261111.md)

额外第二次整片读取期间，负责人提前关闭 C。只读工具记录 `C_RO_PARTIAL_READ`、退出码 1、目标写入 0、`Close_completed=true`。双读一致性未完成。首份完整读回已满足 R36 的整片、Options 和身份比对口径。J-Link 断开后才进入五板冷启动。

## 冷启动停止

以 COM15 首条收录为相对零点。Broker 观察器和连接日志均已就绪，原生连接日志中成功 MQTT 连接仅有观察器，C 的载荷实收 0。

| 主机相对时刻 | 串口证据 | 含义 |
| ---: | --- | --- |
| 0.000 s 起 | `GW PASS_ESCAPE_SENT` → `GW PASS_AT_OK` → `GW PASS_BOOT_AT_OK` | 初始转义与 AT 确认已完成 |
| 1.109 s | `UNI UART baseline=222 total=222` | 启动时已建立 UART 基线，随后进入建链 |
| 1.156 s | `GW PASS_BOOT_SOCKET_UNCONFIRMED` | 旧 socket 关闭或缺失状态未获确认，Wi-Fi、TLS、MQTT 阶段尚无成功标记 |
| 1.156–1.500 s | `GW PASS_CLOSE_UNCONFIRMED` → `GW PASS_SOCKET_UNCONFIRMED` → `GW PASS_HARD_RESET` → `GW PASS_HARD_RESET_OK` | 固件走 ESP 硬复位分支，按源码该成功标记要求收到 `ready` 并取得 `AT` 的 `OK`。PF6/PC0 实际电气波形、脉宽与电平没有独立测量 |
| 1.500–1.515 s | `GW PASS_LOCAL_FAULT` → `B5 STOPPED NO_AUTOREARM` | 冻结源码在 `pass_reconnect()` 发现 UART 累计错误数偏离基线时打印该标记并停止。新增错误的数量、类别与出现时刻 `UNKNOWN` |

这次串口记录来自 C 应用的停机分支，未观察到 C 进入 ROM 的证据。ESP 硬复位与 J-Link 复位是不同动作。本窗可以确认 ESP 硬复位分支返回 `ready` 与 AT 成功，仍缺少独立板级波形。冷启动后哪段产生新增 UART 错误、旧 socket 核对为何未确认，均待 PI 判读。 [应用停止条件](../../../gateway/b5/network_main.c#L196) · [ESP 硬复位确认](../../../gateway/mqtt/src/platform.c#L757) · [启动 socket 核对](../../../gateway/mqtt/src/gateway_transport.c#L1123)

## R40 §5 观测与裁定

| 项目 | 结果 |
| --- | --- |
| 300 s 传输层、ECG/PPG 点数、五路标量、入队/发布/Broker 对账、队列、丢弃、UART/CAN 稳态增量、`console_max`、稳态节流 | `NOT_RUN`，未进入稳定采集。Broker 实收 0 仅用于说明未建链 |
| HR、SpO₂/PR、体温、RR 的有效性和合理性 | `NOT_RUN`。计划 HR 来自 60 bpm 模拟 ECG |
| NIBP 空载和人体测量、结果到达、90 s 分类 | `NOT_RUN`，泵启动 0，袖带未接触人体 |
| 已建链后的非人工断链、自动恢复及在线 300 s 清零 | `NOT_RUN`，未建立 MQTT 会话 |
| 音频 | 冻结镜像为 `--no-audio`，窗口内无音频试验 |

现场回报已断电。COM15 已消失，隔离观察器已退出，Broker 服务和两个监听端口均已关闭。C 保留冻结镜像。

## 受限原件校验摘要

| 原件 | 记录数 | SHA-256 |
| --- | ---: | --- |
| COM15 被动记录 | 16 | `ebbccf27efcb1ddb15effdd0363a72068794f7f60485622fa5295f761cf73114` |
| Broker 载荷观察 | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| Broker 原生连接日志 | 14 | `9df8b389a9d53ceb54318546e0366343acd178be480102e344085ca078d96cf7` |
| 动作台账 | 13 | `dba7acc97573f46ea142f73d650d95a8ef600cf17dfd3b0f2cb44c5451b929e9` |
