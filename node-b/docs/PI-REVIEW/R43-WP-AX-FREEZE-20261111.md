# R43 · WP-AX 冻结包

**2026-11-11 · C 最终保留 WP-AX。** 负责人在 R43 §6 冻结 `FIVE_APPLIANCE_C_2S_V1`，源码 `b057a65e886cc0000db10faea30733162d19f083`。R42 安装后整片、Options、身份和 code SHA 读回通过。全量复测完成 300 s 静息采集和一组真人 NIBP，传输与 NIBP 工程功能判据达到，SpO₂ 数值合理性未达。 [R43 裁定及冻结决定](https://github.com/Serendipity-min/medical-multi-parameter-monitor/blob/efae10a/node-b/docs/PI-REVIEW/R43-20261111.md) · [R42 安装与实板回执](R42-WINDOW3-FIELD-20261111.md)

## 制品与复现

| 制品 | 字节 | SHA-256 |
| --- | ---: | --- |
| [boot](r41-wp-ax/FIVE_APPLIANCE_C_2S_V1-boot.bin) | 392 | `1692cd7fe7a84e99bce8ae4708ad2a7c7d88280a9e6d2a4a42836a1dea5461bb` |
| [code](r41-wp-ax/FIVE_APPLIANCE_C_2S_V1-code.bin) | 58,480 | `0fa2e77469ba02d213541118219f15cd285536edfe45575cf3518f42d2aab922` |
| [Intel HEX](r41-wp-ax/FIVE_APPLIANCE_C_2S_V1.hex) | 165,691 | `ea8a6a8cee368ad2d5ac39328dcd6e2e0d213f743678236365117237d114fbc7` |

直接引用 `r41-wp-ax/` 的既有制品和[统一安装布局](r41-wp-ax/unified-layout.json)。本轮按原始文件字节复算三项 SHA，并验证 HEX 各数据记录及装载地址和两个 BIN 逐字节一致。

在源码 `b057a65e886cc0000db10faea30733162d19f083` 的独立检出中，从仓库根目录执行以下命令。工具链为 Arm GNU **14.2.Rel1**（Build `arm-14.52`，GCC `14.2.1 20241119`，GNU objcopy `2.43.1.20241119`），SDK 为 `STM32F4xx_DSP_StdPeriph_Lib_V1.4.0`（含 CMSIS）。`P5_ARM_TOOLCHAIN_BIN` 指向对应平台工具链的 `bin`，`P5_STM32F4_SDK_ROOT` 指向 SDK 根目录。制品位于 `node-b/build/b4-c-arm-*`，按二进制方式校验 HEX。 [冻结源码构建入口](https://github.com/Serendipity-min/medical-multi-parameter-monitor/blob/b057a65e886cc0000db10faea30733162d19f083/gateway/dual_can/build_arm.py)

```text
python -X utf8 gateway/dual_can/build_arm.py --b5 --egress-final --tri --unified --split-flash --five-node --five-appliance --no-audio --esp-passthrough --pass-lifecycle --production-diag --outage-retention --tx-integrity-diag --link-resilience
```

固定组合为裸机、115200 透传、4 个 QoS1 槽、音频关闭。保留生产计数、断网保留、发送完整性和重入／节流功能。使用五板 TLS 端口默认值及 sector3 持久配置。R42 VPS 独立复建的 boot、code、HEX 三项逐位一致。Host C 30 组通过，PI 定向 pytest 89 项及 12 个子例通过。关闭 `--link-resilience` 重编的三项制品与 S2-c 逐位一致。 [R41 离线构建与 Host 回执](R41-WP-AX-OFFLINE-20261111.md) · [R42 §3 独立复核](https://github.com/Serendipity-min/medical-multi-parameter-monitor/blob/192ebe0/node-b/docs/PI-REVIEW/R42-20261111.md#3-位级复核vpsarm-gnu-1421-arm-1452独立-worktree)

## Flash、SRAM 与 CCM

区间为左闭右开，单位为字节。Flash 装载来自原始 HEX，RAM 和 CCM 取 R42 §3 的 ELF／链接余量。

| 区域 | 链接区间 | 占用 | 余量 |
| --- | --- | ---: | ---: |
| Flash sector0，向量 boot | `[0x08000000, 0x08004000)` | 392 | 15,992 |
| Flash sector4，应用 code（含 `.data` 装载内容） | `[0x08010000, 0x08020000)` | 58,480 | 7,056 |
| 常规 SRAM | `[0x20000000, 0x20020000)` | 静态及对齐 82,232，heap 保留 24,576，stack 保留 8,192，合计 115,000 | 16,072 |
| CCM，断网保留环 `.ccm_retention` | `[0x10000000, 0x10010000)` | 61,824 | 3,712 |

boot 实际覆盖 `[0x08000000, 0x08000188)`，code 实际覆盖 `[0x08010000, 0x0801E470)`。相对 WP-AW，sector4 余量少 388 B，常规 SRAM 余量少 8 B，CCM 余量相同。sector3 `[0x0800C000, 0x08010000)`、Options 和其他 Flash 扇区都在镜像覆盖范围外。 [WP-AW 布局](R38-WP-AW-FREEZE-20261111.md#flashsram-与-ccm) · [WP-AX 实板读回](R42-WINDOW3-FIELD-20261111.md#安装现场安全和冷启动)

## 已知限制（R33–R43）

### NOT_PASS

| 项目 | 冻结时保留的裁定 | 来源 |
| --- | --- | --- |
| 窗口 2 整体与恢复 ≤90 s | 41 s 人工热点断开后，实时遥测于热点恢复约 551–582 s 后到达。首次 Wi-Fi 关联至 SNTP 放行 548.341 s，SNTP 失败后的退避标记到下一轮 AT 合计 504.138 s，放行到首条实时遥测约 2.991 s。C 自动重连且无 LINK 停止，连续断链计数 +1。 | [R37 §2](https://github.com/Serendipity-min/medical-multi-parameter-monitor/blob/9893a8d/node-b/docs/PI-REVIEW/R37-20261111.md) · [D1 时间线](R37-D1-TIMELINE-20261111.md) |
| 窗口 2 断网期五路标量 ≥99% | 即使取最有利边界，四路各至多 25/41，温度至多 24/41。保留环记录 1,517 条过龄。MQTT 恢复依赖新鲜 SNTP 可达，轮询三个端点，每轮一个请求，退避 2/4/8/16 s 后封顶 30 s。断网加恢复超过 240 s 时，标量可能在回放前过龄。方案 A 的约 3 分钟无损范围以链路及授时及时恢复为条件，S3 实测断网 203 s，五路实收 1,030/1,030。 | [R33 §1](https://github.com/Serendipity-min/medical-multi-parameter-monitor/blob/0fef4f6/node-b/docs/PI-REVIEW/R33-20261110.md) · [R37 §2–3](https://github.com/Serendipity-min/medical-multi-parameter-monitor/blob/9893a8d/node-b/docs/PI-REVIEW/R37-20261111.md) · [R38 §3](https://github.com/Serendipity-min/medical-multi-parameter-monitor/blob/0fef4f6/node-b/docs/PI-REVIEW/R38-20261111.md) |
| S3 排空 ≤390 s | 实测 676 s，回放 1,239 条。负责人接受该耗时为已知行为，WP-AV 已取消。 | [R33 §1](https://github.com/Serendipity-min/medical-multi-parameter-monitor/blob/0fef4f6/node-b/docs/PI-REVIEW/R33-20261110.md) · [R34 §1](https://github.com/Serendipity-min/medical-multi-parameter-monitor/blob/0fef4f6/node-b/docs/PI-REVIEW/R34-20261110.md) |
| S3 探头移除触发预测 | 两次取下探头均无协议错误，预登记的复现预测未达，探头假设削弱。 | [R33 §1–2](https://github.com/Serendipity-min/medical-multi-parameter-monitor/blob/0fef4f6/node-b/docs/PI-REVIEW/R33-20261110.md) |

| R42 原批次实时传输及顶替 | Broker 和固件的计数最大差 0.222%（最有利边界 0.191%），超过 0.1%。SpO₂、PR 各有 2 条实时顶替后回放，去重合并两路各 300 条。全量复测顶替 0，计数差达标。 | [R42 回执](R42-WINDOW3-FIELD-20261111.md) · [R43 统计](R43-R42-OFFLINE-STATS-20261111.md#原批次四次实时顶替) |
| SpO₂ 数值合理性 | 两批分别有 66/291、44/298 条 VALID 越界，94–100% 预登记均未达。VALID 比例达到。 | [R43 §2、§4](https://github.com/Serendipity-min/medical-multi-parameter-monitor/blob/efae10a/node-b/docs/PI-REVIEW/R43-20261111.md) · [分布和质量标志](R43-R42-OFFLINE-STATS-20261111.md#spo₂-分布) |

### UNKNOWN

| 项目 | 证据边界 | 来源 |
| --- | --- | --- |
| 协议断链字节级根因、STM32→ESP 线上完整性 | R33 汇总 9 次断链，旧策略曾在 S2 集中断链时锁止。现有 STM32 发送计数未见短写、超时或重入，线路字节和 ESP 内部缓冲无直接观测。H7（停顿时 ESP 透传缓冲处理异常）仍为假设，重建距离也不足以确认环形缓冲回绕。 | [R33 §2](https://github.com/Serendipity-min/medical-multi-parameter-monitor/blob/0fef4f6/node-b/docs/PI-REVIEW/R33-20261110.md) |
| R36 零回复位置、热点上游及同期 TLS 可达性 | 三端点合计 17 次零回复。按 D1 逐轮原件，首末两次零回复为 14:59:52.951 和 15:08:28.934，含 `reason=10` 后两次。热点上游或出口共路径问题是 R38 的推断。同期无独立热点探测或 UDP 抓包，SNTP 拒绝期间 TLS 能否建立也未知。 | [D1 §§a、d、e](R37-D1-TIMELINE-20261111.md) · [R38 §§2–3](https://github.com/Serendipity-min/medical-multi-parameter-monitor/blob/0fef4f6/node-b/docs/PI-REVIEW/R38-20261111.md) |
| `reason=10` 样本与误拒判定 | UDP 收到 48 B。被拒包内时间戳、小数值、`delta_ms`、匹配 `query_ms` 和实际偏差方向均未记录，是否误拒未知。S3 校正量与 R36 样本偏差均不足以测出板上时基漂移。 | [D1 §b](R37-D1-TIMELINE-20261111.md#b-reason10-原值与成功对照) · [R37 §4](https://github.com/Serendipity-min/medical-multi-parameter-monitor/blob/9893a8d/node-b/docs/PI-REVIEW/R37-20261111.md) · [R38 §2](https://github.com/Serendipity-min/medical-multi-parameter-monitor/blob/0fef4f6/node-b/docs/PI-REVIEW/R38-20261111.md) |
| R36 人工动作与 `protocol error` | 热点实际关、开及各步断电的精确时刻未知。开启区间约 31 s。`protocol error` 落在推定的关闭时刻区间内，早于 C 转义约 5.6 s，与实际拨动的先后及因果未知。D1 表中首条 AT 是每轮入口的可观测近似，线上 CONNACK 精确时刻也未知。按 R38 §6 沿用现有打点方法，未来若有窄余量判据，由批次卡预登记回报时刻、C 日志边界和不确定区间。 | [R36 实板回执](R36-WINDOW2-FIELD-20261111.md) · [D1 §§a、c、f](R37-D1-TIMELINE-20261111.md) · [R38 §6](https://github.com/Serendipity-min/medical-multi-parameter-monitor/blob/0fef4f6/node-b/docs/PI-REVIEW/R38-20261111.md) |
| 队列瞬时峰值及节流敏感性 | S3 排空期采样最大 2/24，独立瞬时峰值未知。600/800/1,000 ms 的精确触发率未知。冻结阈值 1,500 ms，R36 稳态触发 0 次。R35 将其裁定为长停顿保护，现有断链前的 PUBACK 间隔不足以证明该阈值能降低断链率。 | [R33 §1](https://github.com/Serendipity-min/medical-multi-parameter-monitor/blob/0fef4f6/node-b/docs/PI-REVIEW/R33-20261110.md) · [R35 §3](https://github.com/Serendipity-min/medical-multi-parameter-monitor/blob/0fef4f6/node-b/docs/PI-REVIEW/R35-20261111.md) · [R36 实板回执](R36-WINDOW2-FIELD-20261111.md) |

| R40 冷启动的现场回包及 UART 电气来源 | WP-AW 因 C 应用锁停，现场 `AT+CIPSTATUS` 具体回包未知。ESP ROM 以 74880 波特率输出与约 220 个启动 UART 错误相容，仍缺电气波形。WP-AX 常规冷启动已通过。 | [R41 §2](https://github.com/Serendipity-min/medical-multi-parameter-monitor/blob/9e79457/node-b/docs/PI-REVIEW/R41-20261111.md) · [R43 §2](https://github.com/Serendipity-min/medical-multi-parameter-monitor/blob/efae10a/node-b/docs/PI-REVIEW/R43-20261111.md) |
| R42 原批次顶替的逐条时刻与成因 | 四条由逐流回放对账确认，只有两组计数边界。逐事件队列瞬时占用及局部 PUBACK 最大间隔未知。 | [R43 离线统计](R43-R42-OFFLINE-STATS-20261111.md#原批次四次实时顶替) |
| R42 SpO₂、PPG 和体温的来源限制 | 缺参照血氧和 A 侧逐帧探头／质量原始位，SpO₂ 越界成因未知。PPG 覆盖 97.89% / 98.81% 记 `SOURCE_LIMIT`，接纳的批次均发布，具体源端归因未知。GY641 读数为体表红外温度，复测极差 5.37 °C，跳变成因及体温标定未知。 | [R43 §2、§4](https://github.com/Serendipity-min/medical-multi-parameter-monitor/blob/efae10a/node-b/docs/PI-REVIEW/R43-20261111.md) · [R43 离线统计](R43-R42-OFFLINE-STATS-20261111.md) |

### NOT_RUN 及验收边界

| 项目 | 当前状态 | 来源 |
| --- | --- | --- |
| WP-AW 恢复后连续在线 300 s 清零 | 窗口 2 仅在线约 256 s，清零实板未验收。 | [R37 §2](https://github.com/Serendipity-min/medical-multi-parameter-monitor/blob/9893a8d/node-b/docs/PI-REVIEW/R37-20261111.md) · [R38 §3](https://github.com/Serendipity-min/medical-multi-parameter-monitor/blob/0fef4f6/node-b/docs/PI-REVIEW/R38-20261111.md) |
| WP-AW 独立非人工断链下的重入 | 现场仅有计划短断过渡期的协议错误和随后自动恢复。独立非人工事件的恢复仍为 Host 证据。 | [R37 §2](https://github.com/Serendipity-min/medical-multi-parameter-monitor/blob/9893a8d/node-b/docs/PI-REVIEW/R37-20261111.md) · [R38 §3](https://github.com/Serendipity-min/medical-multi-parameter-monitor/blob/0fef4f6/node-b/docs/PI-REVIEW/R38-20261111.md) |
| 长时浸泡、容量余量、断链率改善 | ≥2 小时浸泡暂缓，持续容量上限、余量和断链率改善未验收。ESP 电源/UART 的电气假设亦未经仪器检验。 | [R33 §§2–4](https://github.com/Serendipity-min/medical-multi-parameter-monitor/blob/0fef4f6/node-b/docs/PI-REVIEW/R33-20261110.md) · [R34 §4](https://github.com/Serendipity-min/medical-multi-parameter-monitor/blob/0fef4f6/node-b/docs/PI-REVIEW/R34-20261110.md) |
| R36 窗口 2 的真人与 NIBP | R36 的 300 s 结论覆盖非人体工装的传输与出口完整性。血压泵未触发，NIBP 为 `NOT_RUN`。RESP/RR 有效性和 A 的 PPG 源质量门控仍是已知限制。R36 的 RR 实收 299 条、VALID 0；PPG 本窗覆盖 99.30%，历史源端缺口仍保留。 | [R34 §3.1](https://github.com/Serendipity-min/medical-multi-parameter-monitor/blob/0fef4f6/node-b/docs/PI-REVIEW/R34-20261110.md) · [R35 §5](https://github.com/Serendipity-min/medical-multi-parameter-monitor/blob/0fef4f6/node-b/docs/PI-REVIEW/R35-20261111.md) · [R37 §2](https://github.com/Serendipity-min/medical-multi-parameter-monitor/blob/9893a8d/node-b/docs/PI-REVIEW/R37-20261111.md) |
| 历史状态回放、波形保留 | 历史节点和网关状态只保留在 C，云端历史状态通道暂缓。波形尽力保留，超出部分允许缺口。 | [R34 §4](https://github.com/Serendipity-min/medical-multi-parameter-monitor/blob/0fef4f6/node-b/docs/PI-REVIEW/R34-20261110.md) · [R35 §5](https://github.com/Serendipity-min/medical-multi-parameter-monitor/blob/0fef4f6/node-b/docs/PI-REVIEW/R35-20261111.md) |
| R40 WP-AW 窗口 3 | 冷启动触发 `STOP_TARGET`，采集与 NIBP 均未开始。R42 WP-AX 独立复测完成规定采集。 | [R41 §2](https://github.com/Serendipity-min/medical-multi-parameter-monitor/blob/9e79457/node-b/docs/PI-REVIEW/R41-20261111.md) · [R42 实板回执](R42-WINDOW3-FIELD-20261111.md) |
| R42 原批次 NIBP、全量复测首次串口捕获 | 原批次因笔记本低电在静息采集后结束，真人 NIBP 未做。全量复测首次冷启动缺主机捕获标记，Broker 可见数据，UART 无记录。重新冷启动后完成一组真人实时 NIBP。 | [R42 实板回执](R42-WINDOW3-FIELD-20261111.md#充电后的全量复测) |
| WP-AX 运行中非人工断链与重连清零 | R42 两批有效采集期间均无非人工断链，此路径及重连 300 s 清零为 `NOT_RUN`。WP-AX 人工断网、长期浸泡与容量余量也无新验收。 | [R43 §2](https://github.com/Serendipity-min/medical-multi-parameter-monitor/blob/efae10a/node-b/docs/PI-REVIEW/R43-20261111.md) |
| Broker LIVE 与验收范围 | R42 工程验证使用模拟 ECG／HR、真人 SpO₂／PR、体表温度和一组真人 NIBP。RR 两批均为 0 VALID。固件出口标记 `MOCK`／`synthetic=true`，`LIVE` 来源验收、正式云及临床准确度验证为 `NOT_RUN`。 | [R40 §§1、5、8](https://github.com/Serendipity-min/medical-multi-parameter-monitor/blob/752de06/node-b/docs/PI-REVIEW/R40-20261111.md) · [R43 §2、§4](https://github.com/Serendipity-min/medical-multi-parameter-monitor/blob/efae10a/node-b/docs/PI-REVIEW/R43-20261111.md) |

### PF6 硬复位后重设基线只有 Host 证据

WP-AX 只在收到完整 `ready` 和 `AT OK`、且复位前累计错误等于旧基线时，接受该次复位到 `ready` 之间的错误。Host 覆盖成功重设并继续建链、缺确认或区间外新增错误时维持停机。R42 两批均未触发该路径，板级 GPIO0 绑带、PF6 脉冲、ESP 响应及重设后建链仍为 `NOT_RUN`。 [R35 窗口 1 决定](https://github.com/Serendipity-min/medical-multi-parameter-monitor/blob/a0a5abd/node-b/docs/PI-REVIEW/R35-20261111.md) · [R42 §2、§3](https://github.com/Serendipity-min/medical-multi-parameter-monitor/blob/192ebe0/node-b/docs/PI-REVIEW/R42-20261111.md) · [R43 §4](https://github.com/Serendipity-min/medical-multi-parameter-monitor/blob/efae10a/node-b/docs/PI-REVIEW/R43-20261111.md)

## 回退入口

回退顺序为 **WP-AW → S2-c**。WP-AW 由源码 `2a8ee475667fac0ccf23a212bdda17c78de98c35` 用上述相同参数复建。S2-c 也可从 WP-AX 源码用上述命令去掉 `--link-resilience` 重编，R42 已位级复核。WP-AW 保留 R41 发现的 ESP 硬复位后 UART 基线锁停风险。 [WP-AW 冻结制品](R38-WP-AW-FREEZE-20261111.md#制品与复现) · [S2-c 归档与构建](R29-WP-AU-OFFLINE-20261110.md#host-与构建)

| 回退对象 | boot SHA-256 | code SHA-256 | HEX SHA-256 |
| --- | --- | --- | --- |
| WP-AW | `15e6c6b18e1528dc624fa4602ff7a90c1c68af8adb464f1e64e0a930f8d1e203` | `ce8d3490d03c728c7bde0fa90a12da0a192653513905571883456455b01d2a8d` | `2150d84a533195b6c4a374dc0efca37eb9d2002c3bd285902e70466ca29293db` |
| S2-c | `16c7f4e72e0bd443311a61265b5ab6d641acbdf53a89a0d5a006b06a4e669fd1` | `8a790e5dea80b5c24abd2c76754d83f1984b0cd0bbe158a420708b2869c62f80` | `f3e8a19e17af0ef38bf2362ed5412b288e5b5e57beb9e0e9eeba6c348464e457` |

获得当次回退授权后，两级都沿用 `gateway/microphone/unified_install.py --phase install --cold-boot`。以受限整片双读备份和最近一次成功安装回执绑定 C 身份和现状，选定目标归档分段制品及相应布局，只写 sector0/4，整片和 Options 写后核验。若从 WP-AW 再回退到 S2-c，用 WP-AW 安装的成功回执绑定当时状态。安装器的 `restore` 子阶段对应指定备份恢复。 [冷启动安装器](../../../gateway/microphone/unified_install.py)
