# FIELD01 原始证据索引

[仓库内脱敏机器回执](FIELD01-RECEIPT.json)汇总首次隔离阻断、两次上电准备、C 读回与安装、唯一 START 及 Wi-Fi 配置比对。指向 `node-b/build` 的链接供原工作区查阅，原件与制品不随 Git 交付。

本轮仅生成隔离服务只读输出、离线构建、Host 测试和镜像计划证据。运行时原件无本轮文件。受限证据沿用原保存位置。

| 证据 | 位置与口径 |
| --- | --- |
| 合同及历史容量边界 | [Issue #8](https://github.com/Serendipity-min/medical-multi-parameter-monitor/issues/8)、[P3-EVIDENCE.json](P3-EVIDENCE.json) |
| 监听检查 | [只读命令输出](../../build/field01-host-20261107/isolation-readonly-stdout.txt)。SSH 只返回 TCP 监听数量和两项历史服务状态。证书、ACL、设备端握手无本轮原件 |
| 最终 ARM | [构建原回执](../../build/b4-c-arm-20261107T082730582664Z/receipt.json)、[分段布局](../../build/b4-c-arm-20261107T082730582664Z/unified-layout.json)、[链接映射](../../build/b4-c-arm-20261107T082730582664Z/gateway.map)、[构建日志](../../build/b4-c-arm-20261107T082730582664Z/build.log)。同目录保留 ELF、HEX、分段 BIN 和 LTO `.su` |
| Host | [原始退出码与输出](../../build/field01-host-20261107/verified/native-results.json)，同目录保留各用例构建/运行日志 |
| Flash 与回退 | [离线回退证明](../../build/field01-host-20261107/rollback-proof-public.json) 和[五板已安装镜像清单](../FIVE-NODE-MIGRATION/FIVE41-20261106/CURRENT-IMAGES.json)。原 C 分段制品、独立读回、实装后全片读回及 Options 通过历史私有运行路径清单索引，逻辑键为 `C_image_dir`、`C_original_backup`、`C_current_install` |
| 本轮实板原件 | `NOT_RUN`。无新鲜板卡读回、串口原件、Broker 包、音频、TTS 回执或现场收尾回执 |

## 后续取证口径

- `FIELD01 AT` 是累计毫秒。UART 命令、等待提示、写载荷和等待 SEND OK 以驱动相位边界计时；空查询、有效查询和读取是 `cmd_all` 的细分，避免重复相加。
- `FIELD01 QUEUE` 提供队列、历史淘汰、准入让步与遥测 PUBACK 后票据回收。积压时的 AT 忙/闲来自服务轮询采样。时间戳附近如有连续多行，串口输出期间队列仍可推进，整组视为相邻读数。
- `FIELD01 FLOW` 每流依次给出入队、出队、入历史、实时发送成功、历史发送成功、实时发送源龄累计及最大值。QoS0 发送成功指 ESP 接收该 MQTT 写入，Broker 到达须另外核对。区间平均源龄用源龄累计增量除以实时成功增量。
- `FIELD01 CAN` 提供两段 CAN 错误计数、NMT、心跳和启动代次。音频用现有 `UNI AUDIO` 追踪采样与 ACK，另用隔离订阅核对首末块和组包期限。既有 `field01_receiver.py` 只订阅遥测树，正式开窗前还需验证隔离的音频块元数据取证入口。
- 按实际单调时间比较 T0～35 s、T35～130 s 和 T130～150 s，注明串口边界偏差和最后的排空段。保存逐流实际到达时间、原时间戳、序号、有效性和源端缺证。原始载荷、Flash、UID、网络配置和音频留在受限目录。

## 离线复现

```powershell
python gateway/dual_can/build_arm.py --b5 --egress-final --tri --unified --split-flash --five-node --five-appliance --field01
python gateway/microphone/run_five_appliance_tests.py --field01 --out node-b/build/field01-host-repro
```

回退校验复用 `unified_install.prepare` 离线入口。分别传入当前候选和历史原 C 分段制品，以同一份历史备份与最后已验证的实装回执为比对输入。用原制品的两个计划写入块覆盖候选的预期读回，验证结果与最后实装档案完整相等。

隔离服务续办见 [FIELD01 隔离链路恢复回执](FIELD01-ISOLATION-20261107.md)。新记录器通过 `--audio-metadata` 采集音频上下行头部，保存路径仍受 EFS 约束。

首次上电准备的 [脱敏机器回执](../../build/field01-isolation-issue8/FIELD01-PRESTART-RECEIPT.json) 含受限原件 SHA-256。原件通过本地忽略目录中的事务指针索引，包含主机就绪、停止、进程退出、空串口捕获和 Broker 观察器收尾回执。

唯一 START 的 [机器回执](../../build/field01-isolation-issue8/FIELD01-USB-POWER-RECEIPT.json) 包含串口原件和进程回执 SHA-256。C 的 Wi-Fi 连接失败发生在 T0 前，故无 Broker 实板遥测或音频原件。
