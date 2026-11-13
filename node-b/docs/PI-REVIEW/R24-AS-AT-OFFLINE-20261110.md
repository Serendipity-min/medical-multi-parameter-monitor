# R24 离线回执

承接 [R23](https://github.com/Serendipity-min/medical-multi-parameter-monitor/blob/8612e94/node-b/docs/PI-REVIEW/R23-20261110.md) 和 [R24](https://github.com/Serendipity-min/medical-multi-parameter-monitor/blob/1c9d95f/node-b/docs/PI-REVIEW/R24-20261110.md)。本轮只构建和做 Host 验证。五板、非人体工装和热点保持关闭。C 仍装 WP-AR 镜像。

| 项目 | 裁定 |
| --- | --- |
| WP-AS 时间锚和 CANopen TIME | Host PASS。实板漂移、断网数据账和恢复时长待测。 |
| WP-AT 标量 | Host PASS。断网 180 s 的标量按原身份和采集时间有序补传，240 s 的额定输入保留通过。 |
| WP-AT 状态 | C 本地保留 Host PASS。云端历史状态补传 BLOCKED，WP-AT 整体验收未闭合。 |
| 镜像 | Windows Arm GNU 14.2.1 构建通过，待 PI 在 VPS 位级复核。 |

## R23 三项追查

以下以 R22 回执记录的受限 UART 和 Broker 原件为准，已核对两份原件的 SHA-256。原始串口、载荷和凭据留在受限档案。 [R22 实板回执与原件摘要](R22-AR-FIELD-20261110.md)

### 第二次掉线

Broker 于本地对齐时间 14:37:30.257 收到同会话的 OFFLINE 遗嘱，序号为 `UINT32_MAX`，比 C 的 `PASS_ESCAPE_SENT`（14:37:36.538）早 **6.281 s**。重入后使用新会话，退出开始至重新建链 9.109 s，Broker 实时遥测空档 15.593 s。遗嘱证明 Broker 会话在 C 退出透传前已经丢失。 [遗嘱设置](../../../gateway/b5/network_main.c) · [MQTT 遗嘱注册](../../../gateway/mqtt/src/gateway_transport.c)

退出前 60 s 的 503 行 UART 记录没有 `GW` 错误或步骤行。最后一次退出前诊断显示 UART 错误总数保持 218、CAN 发送失败和溢出为 0、`network_fault=0`、`mqtt_fail=0`。最后 5.042 s 内仍记录到 SpO₂、PR、HR、RR 的四次 PUBACK，均在 1,501–2,516 ms 桶，最大 1,732 ms。两个在途槽约 4.778 s 未清空，`send_budget()` 的五秒期限可能解释 C 的退出触发。缺少逐票年龄和对端断链原因，**C 触发分支及掉线发起方均为 UNKNOWN**。

### RESP 前导零

Broker 原件第 8,963 条是 QoS0、683 B ASCII 载荷。第 40 个样本在字节偏移 574 缺少小数点，形成非法前导零。数组有 52 个逗号分隔片段，尾项和 `]}` 结束符残缺，超过 C 的 RESP 每批 50 点边界。相邻异常载荷和 LWT 仅相隔约 41 ms，现有数据无法确定因果。

当前序列化器对 RESP 固定输出小数点和六位小数，缓冲区不足返回 0，发送端只提交成功序列化的确切长度。已有序列化等价夹具的 48,000 次比较通过。观察器仅拆分字段并按 UTF-8 解码，未见主动改写数字。缺少 C→ESP TX 波形或独立订阅原件，无法区分发送路径、对端和观察路径的异常。UART 218 是 C 的 RX 计数。**来源 UNKNOWN**。 [序列化器](../../../gateway/data_model/model.c) · [发送入口](../../../gateway/mqtt/src/gateway_transport.c)

### SNTP 恢复耗时

时间以主机收到热点开启回执为零点，实际物理切换时刻未测。此前四次 Wi-Fi 失败各耗时约 15.1 s，退避为 2、4、8、16 s。首个 Wi-Fi OK 发生在零点前 3.782 s。

| 尝试 | SNTP 结果时刻 | 端点索引 | 模块粗时钟查询 | 新鲜样本与裁定 |
| --- | ---: | ---: | ---: | --- |
| 1 | −3.532 s | 1 | 40 ms | 48 B，RTT 140 ms，`reason=10`，与模块时间不一致 |
| 2 | +28.984 s | 2 | 39 ms | 0 B，1,000 ms，`reason=2` |
| 3 | +61.515 s | 0 | 39 ms | 0 B，1,000 ms，`reason=2` |
| 4 | +94.109 s | 1 | 38 ms | 0 B，1,000 ms，`reason=2` |
| 5 | +126.687 s | 2 | 40 ms | 0 B，1,000 ms，`reason=2` |
| 6 | +158.437 s | 0 | 39 ms | RTT 75 ms，与模块时间差 +334 ms，接受 |

五次接入退避为 30.000、30.015、30.000、30.000、30.016 s，合计 **150.031 s**。TLS、MQTT、首条实时遥测分别在 +161.062、+161.187、+161.847 s。零回复的外部原因仍为 UNKNOWN。当前 `MP_H3_FRESH_SNTP` 建链先过 `fresh_sntp()`，再进入 CA/SNI/TLS 路径。WP-AS 的 UTC 锚只供采集与 CAN TIME，沿用该门控。ESP 模块实际证书日期校验设置 UNKNOWN。 [建链实现](../../../gateway/mqtt/src/gateway_transport.c)

## WP-AS

- C 每 10 s 在两段 CAN 上发送 CANopen TIME（`0x100`）。B 既有 `node_clock_read()` 在超过 30 s 未收 TIME 时撤销时标，发送路径随即不再发无时标波形。C 在断网时继续轮询 CAN 并继续发 TIME，因此本包只改 C。 [C 授时](../../../gateway/dual_can/b4_gateway.c) · [B TIME 策略](../../canopen/node_policy.h) · [B 波形发送](../../canopen/b_canopen_app.c)
- UTC 由锚点加本地单调毫秒差外推。有效期为末次锚的 610,000 ms，正常在线约每 10 s 更新一次，给断网留约 600 s。新鲜 SNTP 回来后以每 100 ms 最多 1 ms 逐步收敛，已缓存批次不改时间，后续同节点同流时间戳保持非递减。过期停发 TIME，C 拒收无可信时间戳批次并累计 `unstamped`。
- 外推误差上界以最后可信时间的误差加 `|时基 ppm| × 经过秒数 / 10^6` 秒估算，另计 TIME 传输延迟和毫秒量化。经过秒数应从最近一次真实新鲜 SNTP 算起，包含断网前未重新采样的在线时间。若时基为 100 ppm，610 s 外推项为 61 ms。板级时基 ppm 和温漂缺实测，实物误差上界为 UNKNOWN。

## WP-AT

标量和状态各有独立环。波形继续使用 56 槽并覆盖最旧波形，三者不互相借位。标量保留原始固定点值、采集时间、流、序号与会话身份。恢复时先发实时，再用空闲槽逐条补传标量，至少留一槽供下一条实时 QoS1。队首只有收到 PUBACK 才移除，最后才补波形。`B5 RETENTION` 在原诊断基础上增加库存、写入、补传、过龄覆盖和容量压力计数。缓存为易失 RAM，断电和重启后的持久化不在本次目标内。

现有 Backend 模型拒绝 `source=REPLAY` 的节点或网关状态，MQTT 适配器也拒绝它们进入历史主题。旧状态发到现有状态主题会混入当前状态语义。候选将状态事件完整保留在 C，当前状态仍按现有协议发布。要验收云端状态补传，PI 需裁定历史状态通道及去重语义，或者明确接受状态只在 C 保留。QoS1 在 ACK 丢失时可能重交同一身份，Host 的顺序与零重复结果限定在成功确认路径。 [Backend 模型](../../../cloud/backend/app/models.py) · [MQTT 适配器](../../../cloud/backend/app/adapters.py) · [状态处理](../../../cloud/backend/app/hub.py)

### RAM 和排空估算

| 项目 | Windows ARM 链接或计算结果 |
| --- | ---: |
| 原完整帧 / 紧凑历史项 | 432 B / 28 B |
| 240 s 标量（5 条/s，含 NIBP 压力包络为 6 条/s） | 33,600 B / 40,320 B |
| 240 s 五路周期状态（合计 1 条/s，另有状态边沿） | 6,720 B |
| 实际预留（标量 1,472 项，状态 736 项） | 61,824 B CCM，`NOLOAD`，余 3,712 B |
| 常规 SRAM 空余，扣除链接保留的 24 KiB 堆和 8 KiB 栈 | WP-AR 21,160 B → 新候选 20,696 B |
| 两段 SRAM 合计静态余量 | 86,696 B → 24,408 B，两个区域不可互换 |
| 180 s 名义波形（350 点/s） | 原始 32 位样本值 252,000 B，按 4.5 批/s 完整帧需 349,920 B |
| 180 s 全流按旧完整帧（10.5 批/s） | 816,480 B |

预算覆盖额定 240 s，并为状态切换和非周期事件留余量。超过输入包络且环内没有超过 240 s 的可覆盖记录时，保护现有记录并计 `pressure`。标量用单个在途历史项保序。以 R23 平均 PUBACK 0.32 s 推算，900–1,080 条标量的理想排空约 4.8–5.8 分钟，实际还取决于实时负载。约 3 分钟排空尚未证实。

## 验证和镜像

- Host 180 s 压力夹具输入 1,080 条标量（含 NIBP 1 条/s）、180 条状态与 540 条波形。标量全部按时间和身份确认，状态全部在 C 保留，波形先发生覆盖。覆盖断线后重取同一身份，精确 240 s 边界、超额压力和超龄覆盖。真实 coreMQTT Host 夹具覆盖实时优先、保留实时槽、标量 PUBACK 以及旧状态未发。
- CANopenNode Host 夹具跑过 tick 回绕，600 s 内两段各发 61 个 TIME，B 的真实 TIME 策略全程可读，C 收到 601 条 HR，`unstamped=0`。正反向校正连续收敛，锚过期后 TIME 停发并拒收无时标批。
- 对 `production_diag.exe` 与 `production_outage_egress.exe` 分别运行 `0 22 115200 0 pass 55 110000`。115200 透传 110 s 的 Host 输出逐字节一致，均入队 1,156、本地发布 1,143、窗末队列 12 和在途 1，丢弃、顶替、身份错误和重复均为 0。此对照使用模拟对端。
- Windows Host `python gateway/microphone/test_unified.py` 共 27 组通过。Python 回归为 `node-b/tests/test_field01*.py`、`test_r18_s1_capture.py`、`test_transport_bench.py`、`gateway/microphone/test_unified_install.py`，共 85 项及 12 个子例通过。

```text
python gateway/dual_can/build_arm.py --b5 --egress-final --tri --unified --split-flash --five-node --five-appliance --no-audio --esp-passthrough --pass-lifecycle --production-diag --outage-retention
```

| 产物 | 字节 | SHA-256 |
| --- | ---: | --- |
| boot，sector0 | 392 | `ee6e50b1a95cffa1b601ff43bd5073e791d9efb7f74e65395f95d585f5d2e653` |
| code，sector4 | 55,580（余 9,956） | `c2b5cd730e95d7b5ef38c4ed00903252ca5e1072ecafcdb6a3fcb8e7edafcbdb` |
| HEX | — | `0345f8ae2098236c64720572e6eee272b2dfbe6103c31db336608d6496c759e1` |

去掉 `--outage-retention` 重编 WP-AR，再去掉 `--production-diag` 重编 S1b。FIELD01 两个目标在基础参数上加 `--field01 --transport-profile`，F-P230 再加 `--esp-230400`。WP-AR、S1b、F-P115、F-P230 的 boot、code、HEX 均与各自原构建逐位一致。下一次实板验收仍需独立批次卡与完整 SHA 放行。
