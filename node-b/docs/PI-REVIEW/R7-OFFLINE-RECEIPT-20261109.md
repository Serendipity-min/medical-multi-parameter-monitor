# R7 离线交付回执

2026-11-09 · [R7 @ ee7c2a0](https://github.com/Serendipity-min/medical-multi-parameter-monitor/blob/ee7c2a0/node-b/docs/PI-REVIEW/R7-20261109.md) · 构建源码 `dba676d0b9055fa7a8a03ef6bae7daabc26de19d`

负责人原话已录入独立 EFS 台账：“保留麦克风代码降级可选，同意三项开工和单板实板批次卡”。台账 1 条，SHA-256 `76947f613bf18019d1a948c7b3c133a4af00b3ac34e99a0b1bc2628f26db1e3b`。本轮覆盖离线开发验证和 PI 后续起草批次卡。单板试验需另批。

| 任务 | Host / 文档 | Windows ARM | VPS ARM | 实板 |
| --- | --- | --- | --- | --- |
| WP-T0 SSL 透传 | PASS，协议边界夹具、32 组扫点、1 组校准 | PASS，115200/230400，带 DWT 插桩 | PASS，boot/code/HEX 逐位一致 | NOT_RUN |
| WP-U 逐字节与 DMA | 文档完成，已按收益与风险排序并核对 RM0090 | 不适用 | 不适用 | NOT_RUN |
| WP-V 115200 降级 | PASS，验证降级仅报告一次，未知状态保留停止门禁 | PASS | 随透传 230400 重编一致 | NOT_RUN |
| WP-W 音频编译开关 | PASS，出口、调度和 P3 竞争覆盖 | PASS，统一、五板和 FIELD01 | PASS，五板和 FIELD01 无音频制品逐位一致 | NOT_RUN |

[透传设计](R7-WP-T0-TRANSPARENT-DESIGN-20261109.md) · [WP-U 设计补充](R6-WP-R-TRANSPORT-DESIGN-20261109.md#r7-wp-u-实施优先级) · [P3 脱敏数据](R7-P3-TRANSPARENT-HOST-20261109.json) · [容量曲线](R7-P3-TRANSPARENT-CURVE-20261109.svg) · [Windows/VPS 镜像摘要](R7-ARM-REPRODUCTION-20261109.json)

## Host 容量模拟

普通模式以 42 ms SEND OK、55 ms 对端应答延时校准，115200 得 **8.047 批/s**。下表每格按 250 ms / 370 ms 对端应答延时排列。批/s 按 110 秒窗内完成的实时 QoS0/QoS1 批计算，QoS0 在未来实板上须以 Broker 计数和序号核实。

| 波特率 | 每字节附加 CPU µs | 普通 批/s | 透传 批/s |
| ---: | ---: | ---: | ---: |
| 115200 | 0 | 6.616 / 6.479 | 10.389 / 10.380 |
| 115200 | 30 | 6.427 / 6.405 | 10.388 / 10.379 |
| 115200 | 60 | 5.989 / 5.800 | 10.388 / 10.086 |
| 115200 | 120 | 5.109 / 4.732 | 6.549 / 6.252 |
| 230400 | 0 | 9.743 / 7.254 | 10.389 / 10.390 |
| 230400 | 30 | 6.664 / 6.310 | 10.389 / 10.389 |
| 230400 | 60 | 6.893 / 6.872 | 10.388 / 10.379 |
| 230400 | 120 | 5.759 / 5.468 | 10.287 / 9.576 |

- 230400 透传各点在 110 秒截面收达波形 492/495 批（ECG 274/275，RESP 109/110，PPG 109/110）。未覆盖窗末排空验收。全部 33 组的已观测报文无内容校验差错和重复。正常与透传共用音频关闭基线。
- 230400、0–60 µs、370 ms 下，QoS1 三个槽位全满占主循环采样约 63%–67%，窗口尾还有 12 个实时批次。升到 120 µs 后，370 ms 档出现 84 次实时替换。窗口满是可见压力。采样比例不是时间占比，配对扫点也未证明它是唯一瓶颈。
- 230400 透传在 0–60 µs 的配对扫点中，丢弃、顶替和迟到均为 0，窗末仍有 12 个实时批次。约 10.39 批/s 反映本夹具输入与窗尾待处理量，无法估计处理能力上限。115200 在 60 µs、370 ms 档已出现 29 次顶替。持续容量依据逐流交付/输入、丢弃、顶替、迟到与队列趋势判读。真实 ESP、DWT、CAN 并发和现场容量均为 NOT_RUN。

复跑命令为 `python -X utf8 node-b/tools/five_appliance_p3.py --pass-scan --out <新目录>`。统一 Host 17 组全通过，另含 ABC 竞争子运行。FIELD01 Python 61 项及 8 子例通过。透传扫点使用真实 coreMQTT、Router 和 C 收发状态机，串口对端为虚拟实现。

## 镜像和构建范围

统一基本命令为 `python -X utf8 gateway/dual_can/build_arm.py --b5 --egress-final --tri --unified --split-flash --five-node --five-appliance`。ARM GNU 14.2.1。VPS 使用相同 Git 提交的 `gateway` 归档和 StdPeriph V1.4.0，归档长度及 SHA 在镜像摘要中。最终构建检查 `ef4466e` 在 Windows 复跑四组，Flash 制品与 VPS 对照逐位一致，并直接检查代码扇区无音频主题。表内 SRAM 为 `.data + .bss`，CCM 单列。

| 目标附加选项 | sector4 B | 余量 B | SRAM B | 音频 CCM B |
| --- | ---: | ---: | ---: | ---: |
| 五板默认 | 58,048 | 7,488 | 83,004 | 64,000 |
| `--no-audio` | 48,924 | 16,612 | 76,324 | 0 |
| `--field01` | 61,980 | 3,556 | 82,448 | 64,000 |
| `--field01 --no-audio` | 53,776 | 11,760 | 76,144 | 0 |
| `--esp-passthrough --transport-profile` | 50,684 | 14,852 | 76,396 | 0 |
| `--esp-passthrough --esp-230400 --transport-profile` | 51,828 | 13,708 | 76,416 | 0 |

- 五板关闭音频节省 Flash 9,124 B、SRAM 6,680 B、音频 CCM 64,000 B。FIELD01 关闭音频节省 Flash 8,204 B、SRAM 6,304 B、音频 CCM 64,000 B。向量和主题检查确认无音频 DMA/USART2 强中断处理器及音频 MQTT 主题。
- 与 `fd7fa15` 对比，统一、五板、FIELD01、DWT 目标的默认 boot/code/HEX 逐位一致。生产协商构建因 WP-V 新增降级诊断而改变，从 WP-V 单独提交 `10b0124` 到最终源码的制品逐位一致。旧独立 `--audio-link` 在基线和最终源码前的对照版本均因 48 KiB 布局超出 256 B，暂无可比较制品。
- 本轮未访问实板、串口或 Broker，未上电、刷写或启动现场窗口。回执交 PI 复核后再按 R7 起草单板批次卡。
