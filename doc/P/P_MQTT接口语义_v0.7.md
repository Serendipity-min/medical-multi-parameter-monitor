# P MQTT / Web 接口语义 v0.7

依据 P 合同 v0.2。采用 MQTT 3.1.1 over TLS，不使用 MQTT AT 指令或旧 MMP/MVIEW。

## Topic 与角色

| Topic | QoS / Retain | 语义 |
|---|---|---|
| `mpm/v1/{gw}/status` | 1 / 是 | Gateway ONLINE/OFFLINE；CONNECT 设置 OFFLINE LWT |
| `mpm/v1/{gw}/{node}/status` | 1 / 是 | Node ONLINE/OFFLINE |
| `mpm/v1/{gw}/{node}/telemetry/{stream}` | 波形 0，标量 1 / 否 | 当前 LIVE 或 MOCK |
| `mpm/v1/{gw}/{node}/replay/{stream}` | 1 / 否 | REPLAY，不能覆盖当前数据 |
| `mpm/v1/{gw}/{node}/event` | 1 / 否 | FAULT 事件 |

发布端只可写本 Gateway；Backend 只读允许的 Gateway，不能发布；禁止匿名。
Topic stream 小写（如 ecg），后端归一化为 ECG。身份由 Topic 解析，载荷重复声明时必须一致。

## JSON 载荷

共同字段：timestamp（Unix 毫秒）、seq（会话内递增）、session_id（MQTT 会话标识）、
validity（VALID/INVALID/STALE/OFFLINE）、source（LIVE/REPLAY/MOCK）、synthetic、unit。
标量为 value；波形为 samples、sample_rate，value 为 null 或省略。
单条最多 32768 字节、500 点；拒绝 NaN、Infinity、未知字段、Topic 身份不一致。

| Node | Stream | 单位 / 值 |
|---|---|---|
| NODE-A | PPG | relative 波形 |
| NODE-A | SPO2 / PR | % / bpm |
| NODE-A | NIBP | mmHg，`[SYS,DIA]` |
| NODE-B | ECG / RESP | mV / relative 波形 |
| NODE-B | HR / RR / TEMP | bpm / breaths/min / degC |
| Gateway / Node | 状态 | state，ONLINE/OFFLINE |
| Node | FAULT | code，短字符串 |

MOCK 必须 synthetic=true；合成数据不能冒充 LIVE。真机合成源的 Node-A/B 状态也是模拟状态。
RR 趋势与 RESP 波形分开，当前 RR 为合成值，不表示完成正式呼吸算法。

## 时序、失效与背压

- 每路独立去重。同会话重复/倒退 seq、旧时间戳不覆盖当前值；新会话允许 seq 从零开始。
- LWT 的时间戳在 CONNECT 时固定，同会话 OFFLINE Will 特别处理；恢复 ONLINE 可重置序列。
- 一般流 5 秒过期，NIBP 90 秒，Gateway/Node 心跳 15 秒。失效时清空数值与波形。
- Broker 断开立即使 Gateway 离线；Node 离线只影响该节点；采样/网络断点不连成连续曲线。
- MQTT 异步队列最多 256 条，浏览器只保留最新一帧；慢客户端不会无限积压。
- WebSocket：type=snapshot、schema_version=1，含选中 Gateway、节点状态、streams、独立 replay/event。
  后端 10Hz 发布快照，无新 seq 时不重复追加采样点。
- Backend 单进程，重启清空内存，依靠 retained 状态和新数据恢复；无持久化承诺。
