# R8 WP-X / WP-Y 离线交付回执

2026-11-09 · [R8 @ f22a56d](https://github.com/Serendipity-min/medical-multi-parameter-monitor/blob/f22a56d/node-b/docs/PI-REVIEW/R8-20261109.md) · 冻结源码 `5d39062e829c859280914308059c833271f75e7d`

| 对象 | 本轮结果 |
| --- | --- |
| WP-X Host | PASS。四种命令、45 s 边界、一次性与 DIRTY 锁、14 流 1,261 帧复算，以及损坏、缺失、重复和会话边界。 |
| Windows ARM / VPS ARM | PASS。Arm GNU 14.2.1，boot、code、HEX 逐位一致。Windows 的 R7 230400 透传旧目标三项 SHA 与已审证据一致。 |
| 对端校验器 | Windows 和 VPS 离线 CLI PASS。VPS 独立从 C 生成 1,261 帧并复算，损坏一帧时退出 1，报告对应缺失序号。 |
| WP-Y Host | PASS。300 s 三槽位对照及 3/4/6 槽位扫点合计 28 组。 |
| 旧回归 | Windows 统一 Host 17 组通过。FIELD01 与新台架 Python 合计 64 项及 8 子例通过。 |
| 现场 | NOT_RUN。未启 Broker，未连接设备，未执行 S0。等待 PI 书面放行。 |

负责人原话已录入独立 EFS 台账：“同意 WP-X 和 WP-Y 开工和批次卡，热点我可以配合”。1 条，SHA-256 `156097658099766eb0563c865c97b42c795b55bdd8369b4a5d010d818bdbd32c`。R8 §5 A–F 原范围已授权，G 仍待 PI。批次有效期从书面放行起算 7 天，Broker 单次运行上限 4 小时。

## WP-X 镜像和校验

- 单一镜像由 `BENCH N115/N230/P115/P230` 选普通/透传和波特率。启动前 45 s 内只受理一次。通过入网、授时、TLS 和 MQTT 门禁后，按 P3 的流、周期、批大小生成 120 s 合成数据，排空最多 9 s。就绪时预留清理预算，绝对上限为启动后 210 s。
- CAN 和音频驱动均未链接。合成数据经原 Router、`mp_json`、coreMQTT 和传输适配层发至 `mpm/bench/v1/GW-B5-001/#`，含 `MOCK` 与 `synthetic=true`。波形固定点样本加 `seq % 10`，让校验器能识别相同长度的错序帧，数值量级和 P3 一致。
- 运行循环按秒输出 `B5 DIAG`，并输出每个 C 侧 PUBACK 的 node、stream、seq、replay 和往返毫秒。阻塞重连、关闭和串口繁忙可拉长诊断间隔。DWT 计数含普通等待和透传裸流 RX 分项，真实周期与日志开销待实板测量。
- 链路失败会记录检测时刻。在剩余窗口允许且已经证明 socket 关闭、CIPMODE=0、UART 回到 115200 的情况下，最多重连一次。同一合成窗口和序号继续推进。退出或恢复未知时报 DIRTY，后续 BENCH 被锁住。N230/P230 若实际降到 115200，不将该运行记为 230400 样本。
- Broker 观察器记录本机单调到达时刻、UTC、主题和载荷。校验器按一次 `BENCH T0` 的会话与源时钟锚点核对内容、序号、QoS、逐流交付、间隔与迟到。PUBACK 往返取 C 串口日志，订阅者侧到达时刻单列。判读 UTC 迟到前需核对观察机时钟。F1 仍需负责人按提示手动关热点约 10 s 再打开。
- TLS 固定为 28895，继续读取既有 sector3 配置。现场发 BENCH 前须在受限环境核对现存配置实际指向获准的隔离 Broker 和授时对象，并确认观察账号只读台架主题。配置不匹配就停在发命令前。

构建命令为 `python -X utf8 gateway/dual_can/build_arm.py --b5 --egress-final --tri --unified --split-flash --five-node --five-appliance --no-audio --transport-bench`。sector4 **29,804 B**，余 **35,732 B**，SRAM `.data + .bss` **55,968 B**。完整 SHA 和来源归档摘要见证据文件。 [离线证据](R8-OFFLINE-EVIDENCE-20261109.json)

校验器离线入口为 `python node-b/tools/transport_bench_peer.py verify <capture.jsonl> <serial.log> <新report.json>`。Host 可运行 `python -m pytest -q node-b/tests/test_transport_bench.py`，由真实 C 生成样本并运行 CLI，包含负例。放行后的观察入口为 `record <受限配置.json> <新capture.jsonl> <新ready> --seconds <时限>`，配置包含 `host`、`observer_client_id`、`username`、`password`、`cafile`。 [校验器](../../tools/transport_bench_peer.py) · [Host 回归](../../tests/test_transport_bench.py)

## WP-Y 逐流和队列判读

300 s 输入为 **3,151 批**，其中波形 **1,350 批**。在 370 ms 档，230400 的 0/30/60 µs 和 115200 的 0/30 µs 都交付 **3,138/3,151** 批，波形 **1,347/1,350**，丢弃、顶替、迟到为 0。30 秒等相位采样均为 12 个实时批次、0 个历史批次，未见增长。窗末未排空，完成率随输入和截点而变，容量上限未测。

115200、60 µs、370 ms 档交付 **2,942/3,151**，波形仍为 1,347/1,350，但丢弃 **17**、顶替 **192**，末端历史队列增长至 **56**。R7 110 s 同档已有 29 次顶替，回执已修订，不能将 115200 的 0–60 µs 全段合并判为跟上。

| 230400，额外 CPU 0/60 µs | 250 ms | 370 ms | 500 ms | 700 ms | 相对 3 槽 SRAM |
| --- | --- | --- | --- | --- | --- |
| 3 槽 | 跟上 | 跟上 | 丢弃/顶替 | 丢弃/顶替 | 基线 |
| 4 槽 | 跟上 | 跟上 | 跟上 | 丢弃/顶替 | +452 B，台架含 ACK 跟踪 +464 B |
| 6 槽 | 跟上 | 跟上 | 跟上 | 跟上 | +1,364 B，台架含 ACK 跟踪 +1,400 B |

“跟上”指本次输入下丢弃、顶替、迟到为 0 且末端队列采样稳定。槽位造成的可见退化在 3 槽的 370–500 ms 间、4 槽的 500–700 ms 间，6 槽在已扫范围内尚未触发。RAM 差值来自 ARM 编译器对真实结构的大小，链接对齐和额外栈变化需随未来候选复核。台架交付镜像仍用 3 槽。 [逐格输入、交付、队列及原生日志摘要](R8-OFFLINE-EVIDENCE-20261109.json)

复跑为 `python -X utf8 node-b/tools/five_appliance_p3.py --r8-scan --out <新目录>`。Windows 和 VPS 均未运行现场网络。S0、B1–B4、F1/F2、S9 全部为 NOT_RUN。
