# R9 离线交付回执

依据 [R9 @ 4bd9457](https://github.com/Serendipity-min/medical-multi-parameter-monitor/blob/4bd9457/node-b/docs/PI-REVIEW/R9-20261109.md)。冻结源码 `676558879ee006fd278dfe8e4481ba9c969f3dbb`。负责人原话“同意 WP-AA、AB、AC 开工”已录入 EFS 台账，1 条，SHA-256 `ae1f5c566f9fcb1a7ec3c86a3ee83e85734ebad930c69ae31e4716b47f539788`。

| 任务 | Host / 构建 | 新实板 |
| --- | --- | --- |
| WP-AA UART 恢复 | PASS。冻结旧源码复现失败，修复源码通过暖启动、已知/未知档恢复和故障分支。Windows 台架构建通过。 | NOT_RUN |
| WP-AB FIELD01 组合 | PASS。START、PRE 和 STOP Host 组合回归通过。Windows/VPS 两套镜像逐位一致。 | NOT_RUN |
| WP-AC P3 回调拟合 | PASS。130 个虚拟串口场景完成。 | NOT_RUN |

统一 Host 18 组、Python 64 项和 8 子例通过。实板、Broker 和回退均为 NOT_RUN。 [摘要、制品 SHA 与模型逐点结果](R9-OFFLINE-EVIDENCE-20261109.json)

## WP-AA UART 恢复

- 虚拟 ESP 在收到一条错速命令后，把下一次正确波特率的 `AT` 响应置为完整 `ERROR`。用 `b57adf7` 的固件源配当前夹具编译 `R9_LEGACY_REPLAY`，运行 `--h-junk-legacy`，得到旧暖启动和旧恢复均失败。
- 已核验快档时，直接在 230400 发易失 setter，切回 115200 后核对完整五元组及原 flow。覆盖显式拒绝、ACK 丢失但已切换、目标档无回复，以及快档回读 flow 偏离初值。夹具记录已知恢复路径错速发送为 0。
- MCU 暖启动和速率未知的降级探测，仅在当前档得到完整 `ERROR` 后允许再发一次 `AT`。超时或不完整边界保留既有受控换档或停止路径。失败回执仅含 `BENCH RESTORE step=…` 或 `GW UART_RESTORE step=…`，例如 STATUS、CIPMODE、UART_CUR、SETTER、RETIME_BACK、PROBE_BACK。
- H-JUNK 已在 Host 成为可复现机制。R8 实板 DIRTY 的具体步骤仍为 UNKNOWN，230400 生产放行仍待实证。

## WP-AB FIELD01 兼容构建

两套均保留原有 FIELD01 START、T0、停止和 CAN 门禁。F-P230 仅在确认实际速率为 230400 后进入建链，降级到 115200 时该候选会在建链前退出。透传沿用单一 USART3 所有者和硬停门禁。硬停锁存后的 F-P230 收尾采用冷启动口径，停机后的 `GW PASS_MODE_UNKNOWN` 对应冷启动收尾。运行期故障按停机前的回执判定。

`B5 DIAG` 追加 `svc_max_cyc`、`can_rx_a` 和 `can_rx_b`，在原 FIELD01 快照时隙及最终诊断采样。服务峰值于 T0 清零，`svc_cyc/svc_n` 由相邻快照差分。周期峰值包含中断抢占。CAN 两段累计值也用快照差分。普通和透传使用相同输出口径。

共同构建参数为 `--b5 --egress-final --tri --unified --split-flash --five-node --five-appliance`，入口为 `gateway/dual_can/build_arm.py`。ARM GNU 14.2.1。

| 镜像 | 追加参数 | sector4 占用 / 余量 B | SRAM 静态 B | 链接器保留堆栈 B | SRAM 未保留余量 B |
| --- | --- | ---: | ---: | ---: | ---: |
| F-N115 | `--field01 --no-audio --transport-profile` | 54,480 / 11,056 | 76,204 | 32,772 | 22,096 |
| F-P230 | 上述参数加 `--esp-passthrough --esp-230400` | 56,512 / 9,024 | 76,240 | 32,768 | 22,064 |

SRAM 静态为 `.data + .bss`，未保留余量从 128 KiB 扣除静态及链接器堆栈段。Windows 与 VPS 的 boot、code、HEX 分别逐位一致。默认统一、五板、FIELD01、插桩和既有三种 115200 可选构建均与 R7 摘要一致。

## WP-AC 模型估算

P1 实板 ECG60 的 C 侧完成率为 8.071 批/s，采用 R9 的四舍五入目标 8.07。R8 单板 N115 的历史实测是 1,261/1,261 批。按同窗首末计数差分，R8 N115 的实际服务回调约 **74.1 周期/次**。 [P1 实测摘要](../FIVE-APPLIANCE-20261107/P3-REPORT.md) · [R8 实板](R8-FIELD-RECEIPT-20261109.md)

在 P3 的 110 秒固定输入下，固定普通 SEND OK 为 22 ms、虚拟对端应答延时为 55 ms。对每次真实 C `platform_poll()` 所进入的服务回调追加 0–120 µs，步长 1 µs，串口字节附加 CPU 设为 0。最接近的点为 **31 µs/次（8 MHz 下约 248 个额外周期）**，得到 **8.064 批/s**，波形 392/495，丢弃 179、顶替 152。零额外回调开销时，22 ms 档为 9.338 批/s，42 ms 档为 8.047 批/s。因此拟合值依赖固定延时假设。五板实测应检验同窗的平均、峰值及收帧量，再判断业务回调是否解释容量缺口。

| 固定 31 µs/次 | 对端 55 ms 批/s | 丢弃 / 顶替 | 对端 370 ms 批/s | 丢弃 / 顶替 |
| --- | ---: | ---: | ---: | ---: |
| 普通 230400 | 10.205 | 0 / 17 | 8.491 | 62 / 137 |
| 透传 115200 | 10.388 | 0 / 0 | 10.379 | 0 / 0 |
| 透传 230400 | 10.389 | 0 / 0 | 10.389 | 0 / 0 |
| 普通 115200、发送 DMA 模型 | 10.000 | 0 / 38 | 8.537 | 57 / 131 |

透传四点波形均为 492/495，窗末仍有 12 批实时待处理。约 10.39 批/s 是当前输入与截点下的完成率，容量上限仍待测。DMA 模型只替换数据段逐字节投递，按线速发送，每 1 ms 并行推进一次服务，保留命令、SEND OK 与被动接收。370 ms 是对端应答延时敏感性，和实际端到端 PUBACK 时延有不同的计时边界。

复跑命令为 `python -X utf8 node-b/tools/five_appliance_p3.py --service-fit --out <新目录>`。
