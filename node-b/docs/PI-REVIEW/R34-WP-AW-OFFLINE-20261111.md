# R34 WP-AW 离线回执

交付范围为 S2-c/WP-AU 上的 `--link-resilience`、Host 验证和 ARM 测试制品。板级验证为 **NOT_RUN**。WP-AV 已取消，S3 排空约 676 s 保留为已知行为。2 小时浸泡未安排。 [R34 合同](https://github.com/Serendipity-min/medical-multi-parameter-monitor/blob/2860534/node-b/docs/PI-REVIEW/R34-20261110.md) · [现场与冻结草案](R34-FIELD-AND-FREEZE-DRAFT-20261111.md)

## 运行策略

- 新选项依赖 WP-AU 的构建组合，默认关闭。AT 边界已确认的网络断链可继续重入，退避为 2、4、8、16、30 s，之后保持 30 s，低于合同的 60 s 上限。Wi-Fi、SNTP、TLS 或 MQTT 接入失败沿用原有获取退避，失败不累加已建立会话的断链次数。
- 已建立会话的连续断链数在稳定 300 s 后清零，累计数保留至下次启动。原软复位额度与断链数分开，保留 PF6 与 STM32 软复位的原准入和次数限制。启动 UART 风暴、基线失败、启动后 UART 错误增量、无效配置或身份、明确 STOP 仍可锁止。AT 边界在原恢复梯度后仍无法确认时保持本地锁止。
- 有 QoS1 在途时，用最老在途事务年龄与最近一次 PUBACK 年龄的较小值判断停滞。这样空闲时间不会计入新事务的停滞。超过 1,500 ms 后，新实时 QoS0 波形留在 Router，标量和状态仍走原调度。已取出但未写出的波形回到实时队列，队列已满时进入原历史环。匹配的 PUBACK 到达即放行，原 5 s 事务期限到期按原路径退出。
- `B5 LINKRES` 与 5 s 生产诊断同 tick。`triggers` 为暂停次数，`paused_ms` 为累计暂停时间，`held_packets` 计每次暂停开始时已有和之后新入队的波形。`held_bytes_upper` 是同批波形的 MQTT 序列化上界，按每批 `384 + 12 × 点数` 计。暂停期不为统计重新格式化波形。行长最大 173 B，115200 8N1 线时约 15.0 ms，现场 `console_max` 待测。

## PUBACK 校准

从各窗口首个 MQTT 建链起裁取稳态，取区间内最后一个累计快照。`B5 PROD_ACK` 或 `B5 LAT stage=6` 度量事务起点到确认的延迟。`B5 TXCHK` 另有累计相邻 ACK 最大间隔，`B5 TXACK` 只在退出透传时转储。S2-c 与 S3 分别找到 61、67 条退出转储项，均在所选稳态窗之外。S1b-2 与 WP-AR 未启用逐条记录。 [离线提取器](../../../gateway/b5/link_resilience_calibrate.py)

| 原件 | 稳态范围与末快照 | ACK 数 | p50 / p95 / p99 桶上界（ms） | 事务最大（ms） | 相邻 ACK 最大（ms） |
| --- | --- | ---: | --- | ---: | ---: |
| S2-c | 前 1,200 s，末快照 1,196.171 s | 7,169 | 500 / 500 / 1,000 | 1,171 | 1,276 |
| S3 | 前 300 s，末快照 295.281 s | 1,764 | 500 / 500 / 1,000 | 751 | 1,097 |
| S1b-2 | 前 180 s，末快照 175.907 s | 1,047 | 500 / 1,000 / 1,000 | 763 | UNKNOWN |
| WP-AR | 前 600 s，末快照 596.953 s | 3,576 | 500 / 1,000 / 1,000 | 811 | UNKNOWN |

下表每格给出可能超过阈值的**已确认事务数上界**。桶横跨阈值时整桶计入，缺少分桶时使用总数。非零上界的实际触发次数和暂停字节为 UNKNOWN。即便单笔确认慢，其他在途事务的 ACK 也可能一直在推进。

| 原件 | T=600 ms | T=800 ms | T=1,000 ms | 选定 T=1,500 ms |
| --- | ---: | ---: | ---: | ---: |
| S2-c | ≤334 | ≤334 | ≤2 | 0 |
| S3 | ≤72 | 0 | 0 | 0 |
| S1b-2 | ≤1,047 | 0 | 0 | 0 |
| WP-AR | ≤220 | ≤220 | 0 | 0 |

1,500 ms 覆盖四批已确认稳态事务的最大延迟，并覆盖 S2-c/S3 已记录的相邻间隔上界。对被这些记录覆盖的已完成事务，门控上界为 0 次、0 B。缺少连续在途变化与逐条 PUBACK 的联合时间线，所以严格历史逐事件重放和较低阈值的实际触发率仍为 UNKNOWN。最后一个快照之后的尾段不用于上界判断。Host 使用同一输入和 ESP 替身做独立对照。这项节流是缓解试验，H7 仍待证实。

| 受限 UART 原件 | SHA-256 |
| --- | --- |
| S2-c | `13d855af2c1d34ac30647e8af2ff1af56d41716ee99f62cf482f5899d065475b` |
| S3 | `971c8e48dd3752e0c1d2020db44ff661f3882d78b5085ac9f7b7076f4385dd69` |
| S1b-2 | `30ba5b14b3f82a7ad3fbdfccf50243048b559571208f253d0943166a4cb0f9dc` |
| WP-AR | `7e7776271d540dd28c7ad42c655780a1808996ba92ff4b58fd53cf85fd46336e` |

## Host 和制品

`test_unified.py` 30 组通过，Python 定向回归 96 项与 12 个子例通过。Host 覆盖 20 次连续会话断链、接入失败、300 s 清零、本地 UART/配置/STOP 锁止及原冷启动基线用例。停滞测试中，跨阈值时一个已开始的报文在阈值之后写入 465 B，随后新 QoS0 写入 0 B；标量在暂停中写入 178 B，两条标量均确认，三条排队波形各发一次，5 s 期限保持。465 B 是该 Host 报文的实测，跨阈值的余量取决于已开始的单报文长度。

同输入的 110 s 透传 Host 对照开启和关闭选项均实收 1,143 批（约 10.39 批/s），队列峰值 13/24，溢出、顶替、丢弃、身份错误、重复均为 0。新选项触发 0 次、暂停 0 B，除新增诊断行外对照输出一致。该模型不计真实 MCU 新增指令和控制台开销。

```text
python -X utf8 gateway/dual_can/build_arm.py --b5 --egress-final --tri --unified --split-flash --five-node --five-appliance --no-audio --esp-passthrough --pass-lifecycle --production-diag --outage-retention --tx-integrity-diag --link-resilience
python -X utf8 gateway/microphone/test_unified.py
```

Windows Arm GNU 14.2.1。关闭 `--link-resilience` 后 boot、code、HEX 与 R30 的 S2-c 冻结摘要逐项相同。启用选项的摘要见下表。资源和回退入口见现场与冻结草案。

| 制品 | 字节 | SHA-256 |
| --- | ---: | --- |
| boot | 392 | `15e6c6b18e1528dc624fa4602ff7a90c1c68af8adb464f1e64e0a930f8d1e203` |
| code | 58,116 | `d72b088b025c2c3cd4c4aca33179ae4119fea6e39417c8c001d6984b404d6e7f` |
| HEX | 164,664 | `78069e5519280c627443ddf8f47a36c156daf3354fce7a8b10e5fad363ae1889` |

sector4 余 **7,420 B**，常规 SRAM 扣除保留区后余 **16,080 B**，CCM 余 **3,712 B**。相对 S2-c，code 增 868 B、常规 SRAM 增 40 B，CCM 占用相同。待 PI 独立位级复核。
