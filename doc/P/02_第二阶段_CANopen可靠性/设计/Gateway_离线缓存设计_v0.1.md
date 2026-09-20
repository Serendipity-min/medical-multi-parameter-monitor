# Gateway 离线缓存与 MQTT 恢复 v0.1

范围：合同要求的“骨架 + 可验证 RAM 最小版本”。不声称掉电保存、不声称30秒或24小时无损缓存。

## 数据路径与边界

CANopenNode RPDO → `mp_adapter` → `MpFrame` → `MpRouter` → `gateway_transport` / RAM ring。

- 帧包含采集时间、逐流序号、采集会话、节点、stream、有效性、synthetic、replay、固定点值/样本。当前 `MpFrame` 1032字节，最多250点。
- 实时队列16项；每个node/stream只保留最新待发送项，保留队列位置保证标量/状态不会被波形饿死。被替代的旧遥测转缓存。
- RAM历史32项；满时淘汰最老项并递增 dropped。容量是帧数，不能等同固定秒数；断网和高负载下可丢数据，计数必须保留。
- 断网把未发送实时遥测转缓存；ONLINE/OFFLINE状态不缓存。恢复后必须先成功发送新实时帧，再开放历史补传。实时队列非空时，每成功发送至少8条实时帧，且距上次补传≥2s，才允许发送1条历史；队列空闲时，历史发送间隔≥500ms。该配额保留实时优先，也避免持续采集让历史永久等待。
- 出队复制为独立 in-flight 帧，网络等待时允许继续生产。传输失败保留同一时间/序号/会话再入历史缓存；历史明确 REPLAY，原 synthetic 标志不丢失。
- JSON序列化与所有ESP阻塞等待都协作轮询CAN。CAN单次追赶最多8ms，帧发送队列128项、单次最多处理64项，避免无限循环阻塞网络。

## MQTT 保证的真实范围

| 环节 | 策略 | 保证与不保证 |
|---|---|---|
| Gateway会话 | MQTT3.1.1，Clean Session=true | 重连由应用缓存恢复，不依赖Broker离线会话 |
| Backend会话 | Clean Session=true，连接后重新订阅 | Backend离线期间Broker不为它保留遥测队列 |
| 实时波形 | QoS0 | Socket写成功不等于Broker收到，更不等于浏览器收到；连接临界区可能丢失 |
| 标量/状态/EMCY | QoS1 | PUBACK证明到Broker；不证明Backend已处理或落盘 |
| REPLAY | QoS1 | 到Broker后确认缓存项；断线模糊区可能重复，身份不变 |
| Retain | 仅Gateway/节点状态 | 只保存最新状态，不保存波形历史；Backend仍检查采集时间和会话 |
| LWT | QoS1 retain OFFLINE | CONNECT预先生成时间，Backend只接受当前Gateway会话的Will；后续ONLINE可恢复 |

Broker崩溃、Backend离线或重启时，即使Gateway已收到PUBACK，数据仍可能未到Backend。没有端到端应用ACK/持久数据库，本版不能保证这类数据自动找回。RAM缓存是**Gateway已知未发送/失败数据**的主要恢复机制；它不是所有已确认消息的永久镜像。

Backend的实时逐流窗口拒绝重复/倒序；REPLAY只进历史区域，不更新在线性、不覆盖当前读数、不触发当前报警。历史EMCY使用 `/replay/fault`，当前EMCY仍使用 `/event`。当前仅保留最近一条replay展示，不构成长时历史数据库。

## 掉电恢复设计（尚未实施）

真实Flash型号、分区、擦写寿命确认前不写缓存Flash。建议后续使用独立日志分区：记录头包含magic/version/length/node/stream/session/seq/timestamp/CRC；写完整记录及提交标记后才推进写指针。确认游标使用双份代际号和CRC，启动扫描到最后一条完整记录，截断半写尾部；已确认记录可在垃圾回收时按擦除块释放。网络成功不得先于记录落盘被宣称为持久成功。

节点boot_generation应持久递增或使用不重复启动标识；当前板内测试节点使用RAM代际计数，整机复位后由新的可信启动时间区分会话。最终生产配置需完善持久代际/启动唯一性，尤其同秒快速复位边界。本阶段的RAM状态机测试不证明此持久化方案已实现。

## 诊断

板端每5s输出固定字段 `can/drop/cache/lost/replay/nodes`，不输出AT命令、原始ESP回复、网络地址或凭据。验收工具把这些诊断写入JSONL。断线/重启、缓存溢出和补传均可据此追查；无电脑采集时板端日志不会自动永久保存。

云端继续采用第一阶段已部署的文件轮转：Backend/Broker各5MiB×当前+7份备份，按容量留存；不是固定天数承诺。正常MQTT断连code0记录notice，非零code记录warning。查阅 [维护目录](../../90_维护/README.md)。
