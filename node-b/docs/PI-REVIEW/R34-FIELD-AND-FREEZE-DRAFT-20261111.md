# R34 两窗口现场方案与镜像冻结清单草案

两窗均为 **NOT_RUN**。提交 PI 复核后，需以完整 SHA 和动作额度签发批次卡。当前现场状态沿用 S3 收尾回执，五板和工装均已断电，C 保留 S2-c。 [R34 合同](https://github.com/Serendipity-min/medical-multi-parameter-monitor/blob/2860534/node-b/docs/PI-REVIEW/R34-20261110.md) · [S3 回执](R32-S3-FIELD-20261110.md) · [WP-AW 构建与 Host 回执](R34-WP-AW-OFFLINE-20261111.md)

## 窗口 1：C 单板 PF6

`03f9464` 的 WP-AP 已用当前工作树和 Arm GNU 14.2.1 复建。BIN 4,884 B，SHA-256 `37cdfe82829e480719ddc558c3d4d764671dbec803c2462da57fcc6dc42995ed`。HEX SHA-256 `7e3d46c72d1323d6ffa181d827c451412c85056fdb34271b0a0c23f229188118`。均与原回执一致。独立镜像与生产共用 PF6/PC0 序列，向量和装载内容全在 sector0，运行无 CAN、Wi-Fi 入网或 MQTT。Host 已重跑 PF6 夹具。建议与 WP-AW 分开，避免为生产镜像加入能主动打断会话的试验命令。 [WP-AP 原回执](R18-AP-OFFLINE-20261110.md)

1. 建议额度为 C 安装一次、冷启动一次、`PF6` 命令一次。A/B/D/E 与工装保持断电，热点关闭，隔离 Broker 启动 0 次。沿用 CFG-U。先双读整片及 Options，绑定身份、S2-c 现状和回退档案。只写 sector0，写后核对整片，sector4、sector3、Options 及其他区域须逐字节保持。安装会话上限 210 s。现用分段安装器要求 0/4 双段与指向 sector4 的向量，不能直接装此镜像。签发前须离线验收仅接受 sector0 整块和本 SHA 的写入入口及原件比对，仍按冷启动使用，不依赖 Reset/Go。
2. 开关冷启动，COM15 被动就绪后只发送一次 `PF6`。预登记为 `pc0_pre=1`、`pc0_end=1`、`pulse=1`，释放后 3 s 内收到完整 `ready`，随后 500 ms 内 `AT` 确认。记录 `ready_ms` 和 AT 结果。若有仪器，同步观测 PC0 高电平与 PF6 开漏低脉冲，按原 21 ms 设计核对。无波形原件时，电气脉宽记 UNKNOWN，诊断结果只证明读数、复位响应和 AT 确认。
3. 冷启动观察上限 60 s。PC0 低、`pulse=-1`、缺 `ready`/`AT`、意外复位、读回漂移、HALT/ROM 或电气异常均停窗并保存原件。未通过时不重复命令、不进入下一窗口。当前待机镜像恢复由签发卡给出单独的回退额度。

## 窗口 2：WP-AW 和五板 300 s

使用回执所列 WP-AW 完整 SHA。建议额度为 C 安装一次及五板冷启动一次，隔离 Broker 一次，人工短断热点一次（开、关、开，收尾关，共至多四次切换）。窗口 1 结束断电后，核对当前 PF6 镜像及备份，再用已验证的 `unified_install.py` 冷启动安装路径写 C sector0/4，验证整片与 Options。恢复原应用的可选回退不计入试验动作，须单独放行。

1. 保持 CFG-U、原 CAN 接线和非人体工装，冷启动五板，血压泵关闭。隔离 Broker 开连接日志与逐条载荷观察，主机同步记录 UART 和现场动作。等待 AT、MQTT 与四个源节点就绪，记录至少 30 s 稳态后，以首组满足时间锚有效、节点就绪的同步快照为 300 s 起点。以采集 UTC 划窗，跨界波形按采样率拆点。Broker 按流、会话、序号和批内点索引去重。末端继续观察至少 5 s 接收该窗在途包，再开始断网。意外断链时保留原件并标记连续 300 s 窗口状态，不自动重试。
2. 短断热点约 40 s，现场计时后恢复，五板与工装保持供电。预登记为已建立会话断链数增加一次，重入可见 2 s 起步，后续接入失败按 2、4、8、16、30 s 退避并继续尝试，无网络导致的 `PASS_REENTRY_LIMIT` 或 LINK 锁止。热点恢复后以 90 s 内首条实时遥测为待审目标，并记录 SNTP/握手分相。保持在线至少 300 s 验证连续数清零、累计数不回退。短断内记录 `B5 LINKRES` 的触发、暂停、暂留波形和退出前后 `TXCHK`，没有触发也保留为实测结果。预登记总运行上限建议 25 分钟，届时留档断电。
3. 稳态目标沿用既有口径，实时队列峰值 ≤16/24，丢弃、顶替、UART 基线后增量及 CAN 错误增量均为 0。同步核对 C 入队、本地发布及 Broker 实收，逐流传输完整度 ≥99%、零重复、保序。记录稳态 `B5 LINKRES` 增量，预计触发 0 次。`console_max` 仍按已有 ≤40 ms 线记录，新诊断占用留作实测。

| 300 s 项目 | 预登记分母与读数 |
| --- | --- |
| ECG、PPG 名义点覆盖 | ECG 75,000 点，门槛 74,250；PPG 15,000 点，门槛 14,850。另列 C 侧组批与 Broker 对账，以及 A 的源头空档、质量重置证据。名义覆盖低于 99% 时保留原值。能证明为 A 的质量门控缺口时单列 SOURCE_LIMIT，传输层按实际已接纳数据核对。源头与传输无法区分时记 UNKNOWN，不用批数代替点数。 |
| 标量与节点 | SpO₂、PR、HR、RR、温度各按 300 个名义采集时刻，至少 297 条，另列 VALID 比例。E 按心跳和节点状态核对，NIBP 因未触发记 NOT_RUN。 |
| 已知输入限制 | RESP/RR 的有效性和已归因的 A PPG 质量门控缺口不否决传输层判定。保留对应点数、批数与证据。 |
| 范围 | 本窗仅支持非人体条件下的传输层与出口完整性。容量余量、真人五板结论和缓解对断链率的影响仍需各自证据。 |

两窗共同停止条件为身份、Flash 或 Options 漂移、电气异常、HALT/ROM、异常复位、时限或记录器失效。WP-AW 的网络断链按其恢复路径观察，本地故障锁止时留档停机。禁止触发 START、KEY、泵、真实云和配置写入。分别记录人工动作回执、实测时刻和无法独立对齐的时间边界。

## 冻结清单

建议送审的最终组合为 115200 透传、四个 QoS1 槽、音频关闭。公共参数为 `--b5 --egress-final --tri --unified --split-flash --five-node --five-appliance --no-audio --esp-passthrough --pass-lifecycle`。在此基础上，推荐 WP-AW 全部四项。资源来自本轮离线候选和既有归档 map。常规 SRAM 余量已扣除 24,576 B heap 和 8,192 B stack 保留区，CCM 余量以 64 KiB 减静态占用计算。

| 附加组合 | code B | sector4 余 B | SRAM 余 B | CCM 余 B | 用途 |
| --- | ---: | ---: | ---: | ---: | --- |
| `--production-diag --outage-retention --tx-integrity-diag --link-resilience` | 58,116 | 7,420 | 16,080 | 3,712 | WP-AW 测试候选 |
| `--production-diag --outage-retention --tx-integrity-diag` | 57,248 | 8,288 | 16,120 | 3,712 | S2-c 冻结基线 |
| `--production-diag --outage-retention` | 55,900 | 9,636 | 20,680 | 3,712 | S2 冻结基线，省 TX 诊断 |
| `--production-diag` | 54,088 | 11,448 | 21,160 | 65,536 | WP-AR 诊断对照，无约三分钟保留 |
| 公共参数 | 52,988 | 12,548 | 21,472 | 65,536 | S1b 恢复对照 |

- `--production-diag` 保留，用于对账及确认槽位、PUBACK 和队列。
- `--outage-retention` 保留，用于时间锚和标量/状态分级保留。历史状态仍只保留在 C，S3 排空约 676 s 已接受。
- `--tx-integrity-diag` 建议保留，现有断链仍需可观测性，WP-AW 构建也依赖该选项。若以后剔除，另行校核依赖与证据并冻结新摘要。
- `--link-resilience` 待窗口 2 和 PI 位级复核通过后再冻结。确认源码提交、完整 boot/code/HEX SHA-256、工具链、构建参数、链接余量、Flash 布局、隔离窗口回执和发布目标的配置边界。当前制品为测试候选。

回退到原五板用 `gateway/microphone/unified_install.py --phase install` 重装归档原分段制品（boot 392 B、code 56,072 B）。以最新成功安装回执作为 `current-install`，绑定受限备份、身份与原制品摘要。只还原原 sector0/4，按当前已授权配置保留 sector3 和 Options，并将整片与预期镜像逐字节核对。不要把工具的 `restore` 当成通用原五板入口，其目标是该次指定备份。若回退卡包含启动核验，热点关闭，按当次批准的冷启动方式被动观察原应用横幅并断电。 [回退入口](../FIVE-APPLIANCE-20261107/FIELD01-RESULTS.md#flash-与回退) · [历史原应用启动核验](PREFLIGHT-R5-FIELD-RECEIPT-20261109.md#回退与启动)
