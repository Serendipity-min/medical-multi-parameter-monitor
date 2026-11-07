# FIVE-APPLIANCE-PI-02 独立报告

审查起点为 `10a0a0c3468f6d75ad335b681959c00ffd54d8b7`，工作分支为 `codex/five-appliance-integration-v1`。此次记录包含软件定向回归和本机隔离联合测试。[P2 机器回执](P2-EVIDENCE.json)

| 结果分类 | 裁定 | 证据范围 |
|---|---|---|
| 功能通过 | PASS | 单项数值、固定一般建议、多项分开显示及语音提示、MC01/CRC、MR02/C 解析、五板来源、血压完成与过期、Host TTS 停止状态机 |
| 吞吐通过 | LOOPBACK_PASS | 91.297 秒同窗，现有尺寸的遥测与两种音频组包并行，原期限内到达 C 解析器 |
| 仍未运行 | NOT_RUN | 目标 TLS 与实际 ESP-AT、实体 K1、真实 ASR/TTS、实装与人体、300 秒综合实测、真实模型、正式部署、FreeRTOS |
| 已知失败 | DEVICE_CAPACITY_NOT_PASS | P1 设备观测约 8.08 批/秒，低于五板原输入约 10.45 批/秒。本轮负载投影仍无音频服务余量 |

## P2-A 问答和时效

| 请求 | 事实 API | C 播报 |
|---|---|---|
| 单项数值 | 按指定流读取当前快照。高压与低压属于 E 的同一次完成，可单独读取或一起显示 | 播报合格事实。缺事实使用固定拒答，失效、离线、历史数据拒答 |
| 一般建议 | “怎么办”“解释”“正常吗”等进入固定一般建议。混合请求优先按一般建议处理，返回无数值的固定文案 | 播报固件内固定建议 |
| 多项数值 | 分别显示选中的可用事实及各自有效性 | 提示一次询问一项读数，避免跨来源共用一份 MR02 数值身份 |
| 未识别项 | 提示指定一项读数 | 播报同一澄清提示 |

MR02 数值与有来源的拒答继续使用原 session、CRC、网关、来源、原始时间戳、序号与代次字段。状态 5/6/7 是一般建议、澄清和缺事实三种非数值指令，保留会话和回复时限，清零事实身份字段，载荷仅允许标记 `!`。实际播报文本来自 C 的固定文案。上一版解析器会拒绝这三个新增状态，联合验证使用同版本 C 与 worker。

定向回归覆盖 5,000/90,000 ms 前 1 ms 可读、边界到达后拒读、排队期间到期的旧数值帧被 C 拒绝。延迟到边界时重新编码得到拒答。Host TTS 夹具确认播放期间到期或事实资格变化进入 STOP→ACK→QUERY→IDLE。E 的新完成序号使旧完成失去播放资格。同代标量的较早有效事实按原采集时效处理。原 Backend 快照在恰好 90.000 秒的视图条件为包含边界，AI 事实与 C 播报条件为严格小于 90 秒。本轮拆开旧测试中共用的期望值，保留两层原行为。录音范围仍为 1～2 秒。

Host 启动、K1/CRC/TTS 和旧音频入口均通过。Python/Backend 定向回归为 **64 passed**。一般建议采用固定规则是本轮实现选择。MOCK 路径没有模型生成读数。

## P2-B 回环联合测试

本机 Mosquitto 2.0.21 使用独立回环监听和临时测试账户。真实五板 Backend 通过 MQTT 接收固件 `mp_topic/mp_json` 序列化的模拟数据。真实 WebSocket 供观察和事实查询。真实 MC01 打包、组装、事实 API、MR02 生成与 C 解析跨过本机 Broker。识别文本由测试替身返回，PCM 逐字节校验。

同窗收取 969 个遥测包，Backend 拒绝和丢弃均为 0。WebSocket 收齐 ECG 229 批、RESP 92 批、PPG 92 批。HR、RR、SpO₂、PR 和 D 温度各 92 次，另有网关状态 19 次、节点状态 76 次和 E 血压完成 1 次。测量完成前无血压读数，完成后当前高压可播。90.198 秒时 C 解析器接受过期拒答。所有测量仍为 `MOCK/synthetic`。

| 并行音频 | PCM 字节 | MQTT PUBLISH 字节 | 首末块组包 | 组包完成到 MR02 抵达 | 首发到 C 解析 |
|---|---:|---:|---:|---:|---:|
| 64 块，250 ms 间隔 | 32,320 | 36,096 | 15.735 s | 31 ms | 15.766 s |
| 125 块，250 ms 间隔 | 64,000 | 70,500 | 30.969 s | 16 ms | 31.016 s |

实测组包低于原 90 秒，计入合成录音长度后至解析器仍低于原 300 秒语音回合。125 块的温度回复到达时尚余约 4.147 秒事实有效期。一般建议、多项澄清及血压过期拒答另用快速 64 块验证，仅用于功能路径。回环计时覆盖 Broker、实际快照和 API，真实识别与物理发声耗时待测。

负载来自同一 C 序列化器。遥测实送 431,029 字节，约 10.61 批/秒、4.72 kB/秒，未计 TCP/TLS/AT 和 ACK。实送范围为 ECG 866–868、RESP 697–698、PPG 671–672、NIBP 199 字节。P1 记录的 RESP 幸存包约 676 字节，本轮选用的有符号合成样本略大。两种音频分别增加约 2.26 kB/秒的上行 PUBLISH 负载。C 端发送由一个回环 MQTT 客户端串行负责。

按 P1 的 8.08 批/秒作为服务上限，以本轮真实包长和提交时序做 FIFO 算术投影。仅遥测就有 817 个包的预测队龄达到 5 秒，尾部服务债务约 28.74 秒。5 秒在这里用作统一队龄观察线。状态及血压仍各用自身时限。这是受限速率下的投影，设备的实测丢包数沿用 P1 原件。回环性能通过，设备容量保持未通过。[P1 实际服务与边界](../FIVE-NODE-MIGRATION/P1-20261106/RESULTS.md)

## P2-C 资源和部署核对

| C 资源 | 审查起点 | P2 | 增量 |
|---|---:|---:|---:|
| Flash 加载总量 | 58,136 B | 58,392 B | +256 B |
| sector4 加载 | 57,744 B | 58,000 B | +256 B |
| sector4 余量 | 7,792 B | 7,536 B | −256 B |
| SRAM 静态及保留段 | 115,772 B | 115,772 B | 0 B |
| CCM PCM | 64,000 B | 64,000 B | 0 B |

ARM 构建和 IRQ 向量检查通过。Flash、SRAM 128 KiB、CCM 64 KiB 均在链接边界内，CCM 余 1,536 B。数据口径为链接占用，实板栈高水位待测。

| 接口 | 准备状态 |
|---|---|
| MQTT 和 ACL | 测试为动态端口上的 MQTT 3.1.1 回环，三角色各自通过业务流。MQTT 5 反例中 C 写回复、Backend 写录音、worker 写遥测均得到拒绝 PUBACK 135。拟议 Broker 18895、C TLS 28895 保留在隔离模板和 ARM 布局，目标 TLS 未运行 |
| WebSocket 和 AI | Backend 直连路径已校正为 `/ws/v1/monitor`。拟议 Backend 18965、AI 入口 18966。实际回环验证使用动态 Backend 端口与 worker 进程内 ASGI 请求 |
| 监护只读令牌 | Backend 从 `MONITOR_VIEW_TOKEN` 读取，AI 快照读取端从 `P6_MONITOR_VIEW_TOKEN` 获取同一受限读令牌，使用 WebSocket 首帧 |
| AI 调用令牌 | `P6_AI_TOKEN` 独立用于 API Bearer，由 worker 环境注入 |
| MQTT 凭据 | Backend 从 `MONITOR_MQTT_CONFIG` 指向的受限配置读取，worker 从 `P6_MQTT_USERNAME/P6_MQTT_PASSWORD` 读取，C 使用各自的持久配置。此次仅用临时生成的三组回环账户 |
| 模型与识别 | 测试使用 MOCK 与合成 ASR 文本。真实模型侧 `ARK_API_KEY` 与前两种令牌独立，P2 未使用。实际 whisper 二进制和模型待目标环境核验 |

本机为 FastAPI 0.141.1、Pydantic 2.12.5、uvicorn 0.40.0、websockets 16.0、paho-mqtt 2.1.0 和 httpx 0.28.1。Backend 锁定的 FastAPI 为 0.135.1，另外八项锁定依赖与本机不同。AI 还需要 httpx，由 AI 运行环境提供。依赖和入口已核对，锁定部署环境实跑与目标 TLS 仍待验证。[隔离环境模板](../../../cloud/deploy/five-appliance.env.example) [Broker ACL](../../../cloud/broker/five-appliance-acl.example)

## 复现与保留记录

按上一阶段的 Host 构建命令生成新目录下的 C 解析器，再从工作树根运行以下本机测试。Mosquitto 复用已有可执行文件，运行后回收本次监听及临时凭据。[Host 构建入口](RESULTS.md)

```powershell
python -X utf8 node-b/tools/five_appliance_p2.py --runtime <existing-Mosquitto-root> --native <P2-native-output> --out <new-ignored-output>
```

原五板 `f9bdff8`、M0 `26e695f`、R6 `12d3161`、P1 回执和实装恢复入口均保留。本轮源码及报告留在指定工作分支的本地工作区，设备仍使用已有镜像记录。[原五板镜像与恢复记录](../FIVE-NODE-MIGRATION/FIVE41-20261106/CURRENT-IMAGES.json)
