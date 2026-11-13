# FIELD01 结果

**PRECONDITION_BLOCKED。唯一 START 已用完，150 秒评价未开始。** C 接受 START 后约 15.1 秒在加入热点阶段失败并停止。两个历史成功窗口用的 RAM 热点配置与本次 sector3 配置不同。C 保留经完整读回验证的诊断镜像，原镜像回退入口已归档。现场断电回执仍待确认。下一窗口先核对实际热点与 C 的有效配置，再按新授权决定是否启动新的短窗。[Issue #8](https://github.com/Serendipity-min/medical-multi-parameter-monitor/issues/8) · [机器回执](FIELD01-RECEIPT.json) · [证据索引](FIELD01-EVIDENCE-INDEX.md)

## 初始离线准备快照

隔离服务主机的只读检查显示，最后一次实装 C 制品的 TLS 端口 `1883`、探针保留的隔离 TLS 端口 `28895` 和历史隔离订阅端口 `18885` 的监听数均为 0。两项历史隔离服务均为 `failed`。证书、设备配置和隔离凭据角色匹配、最小 ACL、订阅和设备路由均待验证。[Issue #8](https://github.com/Serendipity-min/medical-multi-parameter-monitor/issues/8) · [数值回执](FIELD01-RECEIPT.json) · [原始证据索引](FIELD01-EVIDENCE-INDEX.md)

| 项目 | 结果 |
| --- | --- |
| 软件基点 | `codex/five-appliance-integration-v1@4616c30`。探针分支为 `codex/field01-egress-probe` |
| 离线探针 | ARM 链接、IRQ 向量、HEX 与分段二进制校验通过。Host 4 个用例退出码均为 0 |
| 资源 | Flash 加载 57,988 B，sector4 剩 7,940 B。SRAM 静态及保留 115,200 B，其中 heap 保留 24,576 B、stack 最低保留 8,192 B。栈顶到 heap 上界 24,064 B，探针最大单函数静态栈帧 1,264 B，实板栈水位 `NOT_RUN`。CCM 64,000 B，剩 1,536 B |
| 原 C | 最后已验证实装档案为 boot 392 B、code 56,072 B。历史完整读回、分段原制品和公开清单哈希相符。现场身份和当下 Flash 读回 `NOT_RUN` |
| 本轮实板 | 用户报告 J-Link 和 USB 均在 C，COM15。未打开调试器或串口，未刷写、复位或改变供电，START 次数为 0 |
| 现场结果 | CAN/NMT、实际 ESP-AT/MQTT 分相计时、Broker 逐流到达、源龄、64 块音频、TTS 和收尾均 `NOT_RUN`。约 41 Ω 是历史接线记录，未复测 |
| 容量 | 沿用 P1/P3 的 `CAPACITY_NOT_PASS`。历史出站约 8.08 批/s，源产生下界约 10.45 批/s。本轮无新的实测速率或归因。[P3 证据](P3-REPORT.md) |

## Flash 与回退

只规划 C sector0 `[0x08000000, 0x08004000)` 和 sector4 `[0x08010000, 0x08020000)`。离线计划以最后一次实装回执作为读取比对基准，核对了历史 Options 一致、区外字节保留及回退的完整 Flash 逐字节相等。后续若确有安装，回退使用原 C 分段制品，通过 [unified_install.py](../../../gateway/microphone/unified_install.py) 的 `install` 路径重新安装原制品，以新探针的成功回执作为 `current-install`，由工具重新核验身份、当前镜像、Options 和写后整片回读。原工具的 `restore` 语义是恢复更早的备份，须区分这两个入口。本轮的回退证明来自离线字节比对。

## 恢复准入

先恢复并只读验证已授权隔离链路。核对 C 实际保存的 Broker/Wi-Fi、探针 TLS 端口、证书及角色 ACL，预先确认隔离订阅能捕获逐流遥测与音频块元数据。现场再做 C 新鲜读回、设备身份、断电端接、供电与接地核验，确认非人体工装及现场人员。未核实 PE3 的 K1 则跳过录音。

候选只接受一次 `FIELD01 START`，上电 45 秒内须确认节点与网络就绪，随后观察 150 秒。T0 后 35 秒开放一次 K1 录音机会，需事先输入 `FIELD01 KEY`；采集上限 16,160 样本、64 个 MC01 块，沿用原组包期限。T150 主动 `FIELD01 STOP`，核对 TTS STOP/QUERY/IDLE，现场断电。固件保留既有发包排空余量，主持端仍须监督总上电不超过 210 秒。串口和 Broker 原始记录以实际单调时间做区间差分，明确标出尾段排空、异步快照、采样估计与真实 Broker 到达的差别。

## 后续现场进展

隔离服务已恢复，C 新鲜只读回和探针分段安装均通过。现场断电实测 40 Ω、40.9 Ω。首次上电准备在 COM15 打开阶段停止，最终分类仍为 `PRECONDITION_BLOCKED`，阻断原因已由隔离服务不可用变更为串口接入时限内未打开。START 发送次数为 0，150 秒窗口未消耗。探针保留在 C，现场断电回执待收。[续办与证据](FIELD01-ISOLATION-20261107.md)

## 唯一 START 已执行

确认 USB_UART 是 C 的供电方式后，主机捕获新启动标记，C 接受唯一 START。ESP-AT 在加入热点阶段返回 `GW FAIL WIFI`，随后 C 停止。最终为 `PRECONDITION_BLOCKED`，T0 未到达，150 秒评价未运行。START 次数为 1，后续无自动重试。 [续办回执](FIELD01-ISOLATION-20261107.md)
