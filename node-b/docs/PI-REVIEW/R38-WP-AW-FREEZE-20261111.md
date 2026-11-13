# R38 D2 · WP-AW 候选冻结包

**2026-11-11 · D2 已放行，待 PI 位级复核。** 冻结对象为 `FIVE_APPLIANCE_C_2S_V1`，源码 `2a8ee475667fac0ccf23a212bdda17c78de98c35`。R36 的非人体 300 s 稳态传输达标，窗口 2 总体仍为 `NOT_PASS`。D2 接受下列已知限制，保留新鲜 SNTP 门禁。C 最终保留镜像与回退到原五板应用的决定待负责人确认。 [R38 §4、§6](https://github.com/Serendipity-min/medical-multi-parameter-monitor/blob/0fef4f6/node-b/docs/PI-REVIEW/R38-20261111.md) · [R36 窗口 2 实板回执](R36-WINDOW2-FIELD-20261111.md)

## 制品与复现

下表是 R36 使用的完整构建制品。原样封存并按字节核对 SHA-256。Intel HEX 保留原始 CRLF，所有数据记录解码后与 boot、code 两段逐字节一致。

| 制品 | 字节 | SHA-256 |
| --- | ---: | --- |
| [boot](r38-wp-aw/FIVE_APPLIANCE_C_2S_V1-boot.bin) | 392 | `15e6c6b18e1528dc624fa4602ff7a90c1c68af8adb464f1e64e0a930f8d1e203` |
| [code](r38-wp-aw/FIVE_APPLIANCE_C_2S_V1-code.bin) | 58,092 | `ce8d3490d03c728c7bde0fa90a12da0a192653513905571883456455b01d2a8d` |
| [Intel HEX](r38-wp-aw/FIVE_APPLIANCE_C_2S_V1.hex) | 164,603 | `2150d84a533195b6c4a374dc0efca37eb9d2002c3bd285902e70466ca29293db` |

在源码 `2a8ee475667fac0ccf23a212bdda17c78de98c35` 的独立检出中，从仓库根目录执行以下命令。原构建使用 Windows Arm GNU Toolchain **14.2.Rel1**（Build `arm-14.52`，GCC `14.2.1 20241119`，GNU objcopy `2.43.1.20241119`）与 `STM32F4xx_DSP_StdPeriph_Lib_V1.4.0`（含 CMSIS）。`P5_ARM_TOOLCHAIN_BIN` 指向对应平台的工具链 `bin`，`P5_STM32F4_SDK_ROOT` 指向 SDK 根目录。构建脚本在 `node-b/build/b4-c-arm-*` 输出制品。校验原始文件字节，HEX 使用二进制方式读取。 [冻结版本构建入口](https://github.com/Serendipity-min/medical-multi-parameter-monitor/blob/2a8ee475667fac0ccf23a212bdda17c78de98c35/gateway/dual_can/build_arm.py)

```text
python -X utf8 gateway/dual_can/build_arm.py --b5 --egress-final --tri --unified --split-flash --five-node --five-appliance --no-audio --esp-passthrough --pass-lifecycle --production-diag --outage-retention --tx-integrity-diag --link-resilience
```

固定运行组合为裸机、115200 透传、4 个 QoS1 槽、音频关闭，保留生产计数、断网保留、发送完整性及重入/节流四项诊断或功能。使用构建器的五板 TLS 端口默认值和持久配置模式。凭据及目标配置由现有 sector3 提供。归档编译命令和执行脚本已核对，39 项源文件摘要、69 项项目头文件摘要与本机构建归档一致，项目源文件与冻结提交的内容一致。R36 已在 VPS 以 Arm GNU 14.2.1 复建，三项 SHA 逐位一致，Host C 30 组和 pytest 85 项及 12 个子例通过。本次封存使用既有制品与 map，R39 独立复核待执行。 [R36 §2 位级复核](https://github.com/Serendipity-min/medical-multi-parameter-monitor/blob/093c371/node-b/docs/PI-REVIEW/R36-20261111.md#2-复核vpsarm-gnu-1421)

## Flash、SRAM 与 CCM

来自该 SHA 的链接 map 和实际 HEX 装载地址。区间为左闭右开，单位为字节。

| 区域 | 链接区间 | 占用 | 余量 |
| --- | --- | ---: | ---: |
| Flash sector0，向量 boot | `[0x08000000, 0x08004000)` | 392 | 15,992 |
| Flash sector4，应用 code（含 `.data` 装载内容） | `[0x08010000, 0x08020000)` | 58,092 | 7,444 |
| 常规 SRAM | `[0x20000000, 0x20020000)` | 静态及对齐 82,224，heap 保留 24,576，stack 保留 8,192，合计 114,992 | 16,080 |
| CCM，断网保留环 `.ccm_retention` | `[0x10000000, 0x10010000)` | 61,824 | 3,712 |

boot 实际覆盖 `[0x08000000, 0x08000188)`，code 实际覆盖 `[0x08010000, 0x0801E2EC)`。SRAM 余量是扣除链接器保留堆栈后的静态值。sector3 `[0x0800C000, 0x08010000)` 保留原配置，Options 和其他扇区均在镜像覆盖范围外。窗口 2 仅安装 C 的 sector0/4，整片 Flash、Options 和身份读回已通过。 [R36 实板读回](R36-WINDOW2-FIELD-20261111.md#镜像与现场动作)

## 已知限制（R33–R38）

### NOT_PASS

| 项目 | 冻结时保留的裁定 | 来源 |
| --- | --- | --- |
| 窗口 2 整体与恢复 ≤90 s | 41 s 人工热点断开后，实时遥测于热点恢复约 551–582 s 后到达。首次 Wi-Fi 关联至 SNTP 放行 548.341 s，SNTP 失败后的退避标记到下一轮 AT 合计 504.138 s，放行到首条实时遥测约 2.991 s。C 自动重连且无 LINK 停止，连续断链计数 +1。 | [R37 §2](https://github.com/Serendipity-min/medical-multi-parameter-monitor/blob/9893a8d/node-b/docs/PI-REVIEW/R37-20261111.md) · [D1 时间线](R37-D1-TIMELINE-20261111.md) |
| 窗口 2 断网期五路标量 ≥99% | 即使取最有利边界，四路各至多 25/41，温度至多 24/41。保留环记录 1,517 条过龄。MQTT 恢复依赖新鲜 SNTP 可达，轮询三个端点，每轮一个请求，退避 2/4/8/16 s 后封顶 30 s。断网加恢复超过 240 s 时，标量可能在回放前过龄。方案 A 的约 3 分钟无损范围以链路及授时及时恢复为条件，S3 实测断网 203 s，五路实收 1,030/1,030。 | [R33 §1](https://github.com/Serendipity-min/medical-multi-parameter-monitor/blob/0fef4f6/node-b/docs/PI-REVIEW/R33-20261110.md) · [R37 §2–3](https://github.com/Serendipity-min/medical-multi-parameter-monitor/blob/9893a8d/node-b/docs/PI-REVIEW/R37-20261111.md) · [R38 §3](https://github.com/Serendipity-min/medical-multi-parameter-monitor/blob/0fef4f6/node-b/docs/PI-REVIEW/R38-20261111.md) |
| S3 排空 ≤390 s | 实测 676 s，回放 1,239 条。负责人接受该耗时为已知行为，WP-AV 已取消。 | [R33 §1](https://github.com/Serendipity-min/medical-multi-parameter-monitor/blob/0fef4f6/node-b/docs/PI-REVIEW/R33-20261110.md) · [R34 §1](https://github.com/Serendipity-min/medical-multi-parameter-monitor/blob/0fef4f6/node-b/docs/PI-REVIEW/R34-20261110.md) |
| S3 探头移除触发预测 | 两次取下探头均无协议错误，预登记的复现预测未达，探头假设削弱。 | [R33 §1–2](https://github.com/Serendipity-min/medical-multi-parameter-monitor/blob/0fef4f6/node-b/docs/PI-REVIEW/R33-20261110.md) |

### UNKNOWN

| 项目 | 证据边界 | 来源 |
| --- | --- | --- |
| 协议断链字节级根因、STM32→ESP 线上完整性 | R33 汇总 9 次断链，旧策略曾在 S2 集中断链时锁止。现有 STM32 发送计数未见短写、超时或重入，线路字节和 ESP 内部缓冲无直接观测。H7（停顿时 ESP 透传缓冲处理异常）仍为假设，重建距离也不足以确认环形缓冲回绕。 | [R33 §2](https://github.com/Serendipity-min/medical-multi-parameter-monitor/blob/0fef4f6/node-b/docs/PI-REVIEW/R33-20261110.md) |
| R36 零回复位置、热点上游及同期 TLS 可达性 | 三端点合计 17 次零回复。按 D1 逐轮原件，首末两次零回复为 14:59:52.951 和 15:08:28.934，含 `reason=10` 后两次。热点上游或出口共路径问题是 R38 的推断。同期无独立热点探测或 UDP 抓包，SNTP 拒绝期间 TLS 能否建立也未知。 | [D1 §§a、d、e](R37-D1-TIMELINE-20261111.md) · [R38 §§2–3](https://github.com/Serendipity-min/medical-multi-parameter-monitor/blob/0fef4f6/node-b/docs/PI-REVIEW/R38-20261111.md) |
| `reason=10` 样本与误拒判定 | UDP 收到 48 B。被拒包内时间戳、小数值、`delta_ms`、匹配 `query_ms` 和实际偏差方向均未记录，是否误拒未知。S3 校正量与 R36 样本偏差均不足以测出板上时基漂移。 | [D1 §b](R37-D1-TIMELINE-20261111.md#b-reason10-原值与成功对照) · [R37 §4](https://github.com/Serendipity-min/medical-multi-parameter-monitor/blob/9893a8d/node-b/docs/PI-REVIEW/R37-20261111.md) · [R38 §2](https://github.com/Serendipity-min/medical-multi-parameter-monitor/blob/0fef4f6/node-b/docs/PI-REVIEW/R38-20261111.md) |
| R36 人工动作与 `protocol error` | 热点实际关、开及各步断电的精确时刻未知。开启区间约 31 s。`protocol error` 落在推定的关闭时刻区间内，早于 C 转义约 5.6 s，与实际拨动的先后及因果未知。D1 表中首条 AT 是每轮入口的可观测近似，线上 CONNACK 精确时刻也未知。按 R38 §6 沿用现有打点方法，未来若有窄余量判据，由批次卡预登记回报时刻、C 日志边界和不确定区间。 | [R36 实板回执](R36-WINDOW2-FIELD-20261111.md) · [D1 §§a、c、f](R37-D1-TIMELINE-20261111.md) · [R38 §6](https://github.com/Serendipity-min/medical-multi-parameter-monitor/blob/0fef4f6/node-b/docs/PI-REVIEW/R38-20261111.md) |
| 队列瞬时峰值及节流敏感性 | S3 排空期采样最大 2/24，独立瞬时峰值未知。600/800/1,000 ms 的精确触发率未知。冻结阈值 1,500 ms，R36 稳态触发 0 次。R35 将其裁定为长停顿保护，现有断链前的 PUBACK 间隔不足以证明该阈值能降低断链率。 | [R33 §1](https://github.com/Serendipity-min/medical-multi-parameter-monitor/blob/0fef4f6/node-b/docs/PI-REVIEW/R33-20261110.md) · [R35 §3](https://github.com/Serendipity-min/medical-multi-parameter-monitor/blob/0fef4f6/node-b/docs/PI-REVIEW/R35-20261111.md) · [R36 实板回执](R36-WINDOW2-FIELD-20261111.md) |

### NOT_RUN 及验收边界

| 项目 | 当前状态 | 来源 |
| --- | --- | --- |
| WP-AW 恢复后连续在线 300 s 清零 | 窗口 2 仅在线约 256 s，清零实板未验收。 | [R37 §2](https://github.com/Serendipity-min/medical-multi-parameter-monitor/blob/9893a8d/node-b/docs/PI-REVIEW/R37-20261111.md) · [R38 §3](https://github.com/Serendipity-min/medical-multi-parameter-monitor/blob/0fef4f6/node-b/docs/PI-REVIEW/R38-20261111.md) |
| WP-AW 独立非人工断链下的重入 | 现场仅有计划短断过渡期的协议错误和随后自动恢复。独立非人工事件的恢复仍为 Host 证据。 | [R37 §2](https://github.com/Serendipity-min/medical-multi-parameter-monitor/blob/9893a8d/node-b/docs/PI-REVIEW/R37-20261111.md) · [R38 §3](https://github.com/Serendipity-min/medical-multi-parameter-monitor/blob/0fef4f6/node-b/docs/PI-REVIEW/R38-20261111.md) |
| 长时浸泡、容量余量、断链率改善 | ≥2 小时浸泡暂缓，持续容量上限、余量和断链率改善未验收。ESP 电源/UART 的电气假设亦未经仪器检验。 | [R33 §§2–4](https://github.com/Serendipity-min/medical-multi-parameter-monitor/blob/0fef4f6/node-b/docs/PI-REVIEW/R33-20261110.md) · [R34 §4](https://github.com/Serendipity-min/medical-multi-parameter-monitor/blob/0fef4f6/node-b/docs/PI-REVIEW/R34-20261110.md) |
| 真人五板 300 s、NIBP | R36 的 300 s 结论覆盖非人体工装的传输与出口完整性。血压泵未触发，NIBP 为 `NOT_RUN`。RESP/RR 有效性和 A 的 PPG 源质量门控仍是已知限制。R36 的 RR 实收 299 条、VALID 0；PPG 本窗覆盖 99.30%，历史源端缺口仍保留。 | [R34 §3.1](https://github.com/Serendipity-min/medical-multi-parameter-monitor/blob/0fef4f6/node-b/docs/PI-REVIEW/R34-20261110.md) · [R35 §5](https://github.com/Serendipity-min/medical-multi-parameter-monitor/blob/0fef4f6/node-b/docs/PI-REVIEW/R35-20261111.md) · [R37 §2](https://github.com/Serendipity-min/medical-multi-parameter-monitor/blob/9893a8d/node-b/docs/PI-REVIEW/R37-20261111.md) |
| 历史状态回放、波形保留 | 历史节点和网关状态只保留在 C，云端历史状态通道暂缓。波形尽力保留，超出部分允许缺口。 | [R34 §4](https://github.com/Serendipity-min/medical-multi-parameter-monitor/blob/0fef4f6/node-b/docs/PI-REVIEW/R34-20261110.md) · [R35 §5](https://github.com/Serendipity-min/medical-multi-parameter-monitor/blob/0fef4f6/node-b/docs/PI-REVIEW/R35-20261111.md) |

### PF6 硬复位路径未经硬件验证

窗口 1 按 R36 决定跳过，实板为 `NOT_RUN`。既有 Host 和离线诊断镜像证据可复核，板级 GPIO0 绑带、PF6 复位脉冲和 ESP `ready`/AT 响应仍待实测。 [R35 §4.1](https://github.com/Serendipity-min/medical-multi-parameter-monitor/blob/0fef4f6/node-b/docs/PI-REVIEW/R35-20261111.md) · [R36 §1](https://github.com/Serendipity-min/medical-multi-parameter-monitor/blob/093c371/node-b/docs/PI-REVIEW/R36-20261111.md) · [WP-AP 离线回执](R18-AP-OFFLINE-20261110.md)

## 回退入口

R38 §4 的直接回退对象为 **S2-c**。本机归档的三个制品已逐一核对。复现时用上述构建命令移除 `--link-resilience`，R36 已确认该组合与 S2-c 逐位一致。 [S2-c 制品与命令](R29-WP-AU-OFFLINE-20261110.md) · [S2-c 实板回执](R30-S2C-FIELD-20261110.md)

| S2-c 制品 | SHA-256 |
| --- | --- |
| boot | `16c7f4e72e0bd443311a61265b5ab6d641acbdf53a89a0d5a006b06a4e669fd1` |
| code | `8a790e5dea80b5c24abd2c76754d83f1984b0cd0bbe158a420708b2869c62f80` |
| HEX | `f3e8a19e17af0ef38bf2362ed5412b288e5b5e57beb9e0e9eeba6c348464e457` |

获准回退时，沿用 `gateway/microphone/unified_install.py` 的 `--phase install --cold-boot`，以原始整片备份和当前成功安装回执绑定 C 身份及现状，输入 S2-c 归档分段制品和对应布局。写入范围为 sector0/4，整片及 Options 写后核验，保持 sector3 和其他扇区。工具的 `restore` 对应指定备份恢复。原五板应用的历史回退路径与启动证据见链接，是否采用由负责人在 PI 复核后决定。 [冷启动安装器](../../../gateway/microphone/unified_install.py) · [原五板应用回退入口](../FIVE-APPLIANCE-20261107/FIELD01-RESULTS.md#flash-与回退) · [原应用历史启动核验](PREFLIGHT-R5-FIELD-RECEIPT-20261109.md#回退与启动)
