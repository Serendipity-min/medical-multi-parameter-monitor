# R68｜GT-246-4 上电冒烟执行回执

2026-11-14，北京时间。执行依据为 [R68 签发卡](R68-GT246-SMOKE-CARD-20261114.md)，提交 `0e7a4b3c46dec23ae68c26d44d01b5181cf10205`，文件 SHA-256 为 `9b934b2a15a10ac9cf282a60610dd590a73d5fd59de4803cd0e430aa77a4f167`。现场沿用 C 的 WP-AZ `2c97094` 和 R67 记录的云端部署。

**本次冒烟 FAIL，已按卡停止并全部断电。** 负责人确认 GT 面板 CAN1、CAN3 红灯常亮。打开 ECG 后，CAN4 绿闪，CAN3 仍红灯常亮。厂家手册第 8 页将红灯常亮定义为对应 CAN 通道总线错误，绿闪表示通道有收发活动。两路报错均位于通往 C 的子段。故障根因仍为 `UNKNOWN`。[厂家设备手册与配置资料](https://www.gcan.com.cn/1d49/59a0/92e2)

| 步骤 | 状态 | 证据 |
| --- | --- | --- |
| S0 实物核对 | PASS | 负责人提供铭牌照片，型号 GCAN-GT-246-4，供电标识为 DC 24 V。 |
| S0 改接前阻值 | NOT_RUN | 41.0 Ω / 40.9 Ω 为原项目历史值。本次原接线全景与改前阻值未取得。 |
| S1 网桥参数读回 | PASS | 18:27:09，GCAN Box 通过 COM18 显示「配置上传成功」。逐路设置见下表。设备现有配置符合可核对项，参数写入为 NOT_RUN。 |
| S2–S3 接线与断电测量 | PASS | 现场先接线初测，隔离 CAN 完成 S1 后重新插回端子。负责人确认 GT 和五板断电、USB 已拔，四段 H–L 均在 60.8–61.0 Ω，跨段 H–H、L–L 均开路。R1、R3 开，R2、R4 关，AP 保持原位。 |
| S4 上电 | FAIL / STOP_TARGET | 负责人确认 GT 和五板均已上电。约 18:38 报告 GT CAN1、CAN3 红灯，后续确认两路均为常亮。C 上电精确时刻未取得。 |
| S5 十分钟观察 | NOT_RUN | 上电异常后中止。C 侧四节点 60 s 心跳判据为 UNKNOWN。上电尝试期间的本机 WSS 记录均为 OFFLINE，无有效标量。 |
| S6 断电 | PASS | 负责人确认 GT 和五板全部断电。断电复查后接线恢复原位置。 |
| 真人输入 | NOT_RUN | 本批未记录真人输入。 |

## 配置读回

GCAN Box `1.1.5.1`，网桥硬件 `HW1.1.1`，固件 `V3.12 / 20260409`。本机界面通道编号为 CAN1–CAN4，与机身丝印一致。下表为设备读回值。

| 子段 | GT 通道 | 端点 | 拨码 | 通道参数及唯一转发目标 |
| --- | --- | --- | --- | --- |
| S1 | CAN1 | C.CAN1 | R1 ON | 经典 CAN，500 kbit/s，正常模式 → CAN2 |
| S2 | CAN2 | A.CAN1、E.CAN1 | R2 OFF | 经典 CAN，500 kbit/s，正常模式 → CAN1 |
| S3 | CAN3 | C.CAN2 | R3 ON | 经典 CAN，500 kbit/s，正常模式 → CAN4 |
| S4 | CAN4 | B.CAN1、D.CAN1 | R4 OFF | 经典 CAN，500 kbit/s，正常模式 → CAN3 |

四路均启用，滤波和 ID 映射关闭，Bus Off 恢复时间均为 1000 ms。采样点与独立故障帧隔离选项未在设备当前端口设置中显示，记为 `UNKNOWN`。AP 按现场原位保留，具体 ON/OFF 未独立记录。配置导出 592 字节，SHA-256 为 `2fbb39b11d95e9d0bf38dfe9ca081a11a72b7de9e7f188dea5bd33b66d51fded`。

## 录制与停止证据

- 本机公网 WSS 从 `18:34:40.049` 至 `18:49:39.421` 实收 8888 帧，Broker 始终显示已连接，网关与 NODE-A/B/D/E 全程 `OFFLINE`，未见有效 SpO₂、PR 或 TEMP。记录文件 SHA-256 为 `e6bbd3a67e1b2c22d3df59f60e82a1737681abed16ddafc05fafacf489fb3a3b`。
- PI 报告独立录制于 `18:35:51` 启动，计划录至约 `19:05:50`，起始帧与本机一致。PI 全窗原件由 PI 自行复核。
- 现场无精确 C 上电时刻、无 C 启动日志或 GT 端口错误计数。CAN4 绿闪只说明本段有活动。两条 C 侧总线的 ACK 和持续收发状态均为 `UNKNOWN`。

## 停止后的断电复核

- 两条 C 侧线束逐根检查，H→H、L→L 均导通，交叉信号测量开路。GT CAN1_GND→C 板 GND 与 GT CAN3_GND→C 板 GND 也分别确认蜂鸣导通。
- 插回后四段 H–L 仍为 60.8–61.0 Ω，C 的 P6、P4 跳帽外观无松动。未取得带电收发器供电、差分波形或控制器工作状态证据。
- WP-AZ 走 `--pass-lifecycle` 启动路径，先做 `pass_startup()`，再调用 `b4_hw_init()`。`UNI UART baseline=…` 在 CAN 硬件初始化成功后输出。供下一轮卡审核的判据为同步采集该启动标记和 GT CAN1、CAN3 的发送成功、发送错误与 BUS_OFF 计数，比较初始化前后的变化。可用该时间线区分启动时缺 ACK 与初始化后持续错误。[WP-AZ 启动代码](https://github.com/Serendipity-min/medical-multi-parameter-monitor/blob/2c9709474d11d09d8538783d44aea189a1864af8/gateway/b5/network_main.c#L795)

现场维持断电，等待 PI 审核和下一步安排。
