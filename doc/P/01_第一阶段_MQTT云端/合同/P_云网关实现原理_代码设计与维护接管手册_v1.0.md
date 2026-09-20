# P 云网关实现原理、代码设计与维护接管手册

> **版本**：v1.0  
> **日期**：2026-09-20  
> **代码基线**：`cfb30d0a4a52f36e9dca6733b761741aae226de6`  
> **对应 PR**：#2  
> **适用对象**：后续 P 负责人、Codex/Gemini 自动化开发代理、服务器维护人员、需要接管 Gateway-C / Cloud / Web 的开发人员  
> **目的**：不仅说明“怎么维护”，还说明 **系统为什么这样设计、代码怎么走、每一层负责什么、数据怎么从 CANopen 进入 Web、哪些地方不能随意修改、如何安全扩展**。

---

# 0. 先读这一页：系统到底怎么工作的

当前系统不是：

```text
STM32 → 自定义 TCP → PC → Web
```

也不是：

```text
ESP8266 → Nginx → 浏览器
```

当前正式结构是：

```text
Node-A / Node-B
        ↓
CANopen over CAN
        ↓
Gateway-C / STM32F407-C
        ↓
Canonical Data Model
        ↓
MQTT 3.1.1 Client
        ↓
ESP8266-C AT SSL Socket
        ↓
MQTT over TLS
        ↓
Tencent Cloud Mosquitto
        ↓
FastAPI Backend
        ↓
WebSocket Snapshot
        ↓
Nginx
        ↓
Browser Monitor UI
```

核心原则只有四条：

1. **传感器厂家协议不越过 Node-A / Node-B**；
2. **CANopen 负责板间标准通信**；
3. **Gateway-C 负责把 CANopen 数据变成统一业务数据，再通过 MQTT 上云**；
4. **Browser 永远只看 Backend 的统一 Snapshot，不知道 CANopen、MQTT 和传感器细节**。

后续维护人员只要不破坏这四条，系统就不会轻易失控。

---

# 1. 当前代码目录怎么理解

## 1.1 Gateway

```text
gateway/
├── canopen/
│   ├── src/
│   │   ├── mp_od.c
│   │   ├── mp_stack.c
│   │   ├── mp_can_driver.c
│   │   └── mp_adapter.c
│   ├── stm32/
│   ├── tests/
│   └── tools/
│
├── data_model/
│   ├── model.h
│   └── model.c
│
├── storage/
│   ├── router.h
│   └── router.c
│
├── mqtt/
│   ├── src/
│   │   ├── main.c
│   │   ├── platform.c
│   │   ├── gateway_config.h
│   │   └── ...
│   ├── build.py
│   ├── provision.py
│   └── README.md
│
└── third_party/
    ├── CANopenNode/
    └── paho-embedded-c/
```

理解方式：

```text
canopen
= 怎么从 A/B 得到标准 CANopen 数据

data_model
= 数据在 Gateway 内部统一长什么样

storage
= 网络断了以后怎么排队、缓存、补传

mqtt
= 怎么把统一数据送到云端

third_party
= 标准协议栈，不要随便修改
```

---

# 2. Cloud

```text
cloud/
├── broker/
│   ├── mosquitto.conf
│   └── acl
│
├── backend/
│   ├── app/
│   │   ├── models.py
│   │   ├── adapters.py
│   │   ├── mqtt_adapter.py
│   │   ├── hub.py
│   │   ├── main.py
│   │   └── diagnostics.py
│   └── tests/
│
├── web/
│   ├── src/main.ts
│   ├── src/style.css
│   └── index.html
│
├── deploy/
│   ├── nginx/medical-monitor.conf
│   ├── medical-monitor.service
│   ├── medical-monitor-mqtt.service
│   ├── medical-monitor-mock.service
│   ├── broker_logging.py
│   ├── refresh_broker_certificate.py
│   └── upgrade_mqtt.py
│
├── tools/
└── evidence/
```

理解：

```text
broker
= 收设备 MQTT

backend
= 把 MQTT 变成 Web 能理解的状态

web
= 只负责显示

deploy
= 服务器怎么运行、升级、回滚

evidence
= 测试证据，不是运行依赖
```

---

# 3. 第一阶段是怎么一步一步做出来的

## 3.1 第一步：先不等传感器，定义“云端需要看到什么”

最开始 A/B 还没有真实传感器数据。

因此先定义统一语义：

```text
Gateway
Node
Stream
Timestamp
Sequence
Validity
Source
Value / Samples
Unit
```

目的：

> 云端不依赖某块传感器的私有协议。

例如：

```text
SPO2
```

云端只知道：

```text
Node-A
Stream = SPO2
Unit = %
Value = 98
Validity = VALID
```

云端不关心：

```text
AFE4490 哪个寄存器
SPI 怎么读
算法怎么计算
```

---

## 3.2 第二步：先用 Mock MQTT Publisher 打通云端

没有 Gateway-C 时：

```text
Mock MQTT Publisher
        ↓
Mosquitto
        ↓
Backend
        ↓
WebSocket
        ↓
Web
```

这样先解决：

- TLS；
- MQTT；
- Topic；
- ACL；
- Backend；
- WebSocket；
- Canvas；
- UI；
- Online / Offline；
- LIVE / REPLAY / MOCK。

这一步最大的价值：

> 硬件以后接入时，云端不是从零开始。

---

## 3.3 第三步：把 ESP8266 降级成“网络接口”

没有让 ESP8266 自己承担业务数据模型。

职责：

```text
ESP8266-C
├── Wi-Fi
├── DNS
├── TCP
├── TLS
└── AT Socket
```

MQTT 逻辑放在：

```text
STM32F407-C
```

好处：

- MQTT 数据模型由 Gateway 控制；
- 以后 ESP8266 换 ESP32，业务层不变；
- 不依赖 ESP MQTT AT；
- Paho Embedded C 可以复用。

---

# 4. Gateway-C 网络代码怎么跑

## 4.1 `gateway/mqtt/src/platform.c`

这是：

> **Paho Embedded C 与 ESP8266 AT 之间的适配层。**

Paho 需要两个核心函数：

```c
mqtt_read()
mqtt_write()
```

项目把它们映射到：

```text
AT+CIPSEND
AT+CIPRECVLEN?
AT+CIPRECVDATA
```

数据路径：

```text
Paho MQTT Packet
      ↓
mqtt_write()
      ↓
AT+CIPSEND
      ↓
ESP8266 SSL Socket
      ↓
Broker
```

反向：

```text
Broker
  ↓
ESP SSL Socket
  ↓
CIPRECVLEN
  ↓
CIPRECVDATA
  ↓
mqtt_read()
  ↓
Paho
```

---

# 5. 为什么 UART 接收用了 Ring Buffer

ESP8266 的 AT 回复不是只在你主动请求时出现。

存在：

- 普通 OK；
- ERROR；
- SSL 数据；
- 异步状态；
- 网络数据。

因此：

```text
USART3_IRQHandler
      ↓
ring buffer
      ↓
主循环解析
```

中断里只做：

```text
收字节
放 Ring Buffer
```

中断里禁止：

- JSON；
- MQTT；
- CANopen；
- printf 大量日志；
- 网络状态机。

否则很容易出现实时阻塞。

---

# 6. TLS 是怎么保证的

Gateway 建连顺序大体是：

```text
Wi-Fi
 ↓
SNTP / 时间
 ↓
开启 CA Verify
 ↓
设置证书名称 CCN
 ↓
设置 SNI
 ↓
AT+CIPSTART="SSL"
```

为什么一定先有时间？

因为 TLS 证书存在：

```text
Not Before
Not After
```

设备时间错误会导致证书验证异常。

---

# 7. MQTT 是怎么工作的

当前：

```text
MQTT 3.1.1
```

Gateway：

```text
Client ID
Username
Password
Keepalive
LWT
```

### 状态

Gateway：

```text
ONLINE
```

使用 retained。

异常断线：

```text
LWT = OFFLINE
```

Browser 后来打开时，也能立即知道最新 Gateway 状态。

---

# 8. Topic 为什么这样设计

当前：

```text
mpm/v1/{gateway}/status

mpm/v1/{gateway}/{node}/status

mpm/v1/{gateway}/{node}/telemetry/{stream}

mpm/v1/{gateway}/{node}/replay/{stream}

mpm/v1/{gateway}/{node}/event
```

例如：

```text
mpm/v1/GW-C-001/NODE-B/telemetry/ecg
```

不要改成：

```text
ECG/device3/value
```

或者：

```text
room1/heart/...
```

因为当前 Topic 已经承担：

```text
协议版本
Gateway 身份
Node 身份
实时/历史
Stream
```

---

# 9. MQTT QoS 的逻辑

当前：

```text
ECG / PPG / RESP
→ QoS 0

HR / RR / SpO2 / PR / TEMP
→ QoS 1

NIBP
→ QoS 1

Status / Fault
→ QoS 1

REPLAY
→ QoS 1
```

原因：

高频波形更看重：

```text
实时
```

不是：

```text
每一包绝不重复/绝不丢
```

否则弱串口 + TLS + QoS1 很容易积压。

重要标量和事件更适合 QoS1。

---

# 10. Mosquitto 怎么限制权限

`cloud/broker/acl`

当前核心权限：

```text
mock-publisher
→ 只能写 GW-DEV-001

gateway-c
→ 只能写 GW-C-001

backend-reader
→ 只能读允许的 Gateway
```

这是必须保留的安全边界。

不要因为测试方便改成：

```text
topic readwrite #
```

---

# 11. Backend 启动过程

`cloud/backend/app/main.py`

启动：

```text
FastAPI lifespan
      ↓
读取 View Token
      ↓
读取 Allowed Origin
      ↓
创建 Hub
      ↓
读取 MQTT Config
      ↓
创建 MqttAdapter
      ↓
启动 MQTT Task
      ↓
启动 10Hz Snapshot Tick
```

如果正式环境没有：

```text
MONITOR_MQTT_CONFIG
```

Backend 会直接失败。

这是故意的。

目的：

> 防止 MQTT 没工作但 Web 还显示“服务正常”。

---

# 12. `mqtt_adapter.py` 做什么

它是：

```text
Mosquitto
   ↓
Paho Python Client
   ↓
MqttAdapter
```

关键参数：

```text
MQTT v3.1.1
TLS >= 1.2
reconnect 1~15s
pending queue 256
```

MQTT 网络线程收到消息后：

```text
on_message
  ↓
有界 Queue
```

Asyncio：

```text
run()
  ↓
一次最多处理 64
  ↓
decode_mqtt()
  ↓
Hub.ingest()
```

这样：

> MQTT 网络线程不会直接修改 Web 状态。

---

# 13. 为什么 Queue 必须有界

如果：

```text
MQTT 输入 > Backend 消费
```

无限 Queue 会：

```text
内存持续增加
→ OOM
→ Backend 崩溃
```

当前：

```text
max = 256
```

满：

```text
dropped += 1
```

然后可以从 `/health` 观察。

---

# 14. `models.py` 是云端数据防火墙

`Telemetry` 使用：

```text
strict=True
extra=forbid
allow_inf_nan=False
```

所以会拒绝：

```text
未知字段
NaN
Infinity
类型错误
单位错误
Node/Stream 对不上
MOCK 冒充 LIVE
非法 NIBP
错误波形
```

这部分不能为了“兼容”随便改成：

```text
extra = allow
```

否则 Gateway Bug 会悄悄穿透云端。

---

# 15. Node 和 Stream 关系

当前：

```text
NODE-A
├── PPG
├── SPO2
├── PR
└── NIBP

NODE-B
├── ECG
├── HR
├── RESP
├── RR
└── TEMP
```

Browser 和 Backend 都以这个关系工作。

新增 Stream 需要从数据字典开始，不允许只改 Web。

---

# 16. `adapters.py` 做什么

输入：

```text
MQTT Topic
+
JSON Payload
```

输出：

```text
Telemetry
```

它先从 Topic 解析：

```text
Gateway
Node
Stream
Kind
```

然后如果 Payload 也声明身份：

```text
必须一致
```

例如 Topic 是：

```text
NODE-A / spo2
```

Payload 写：

```text
node_id = NODE-B
```

直接拒绝。

---

# 17. LIVE 与 REPLAY 为什么分开

实时：

```text
/telemetry/
source=LIVE
```

历史：

```text
/replay/
source=REPLAY
```

Backend 强制校验二者一致。

REPLAY：

- 不刷新设备在线状态；
- 不覆盖实时值；
- 不触发当前实时报警；
- 单独进入历史区域。

---

# 18. `Hub` 是 Backend 的当前状态中心

`hub.py`

核心结构：

```text
current
replays
events
subscribers
```

`current` key：

```text
gateway
node
stream
```

例如：

```text
GW-C-001
NODE-B
ECG
```

只保存：

```text
当前最新有效状态
```

不是长期数据库。

---

# 19. 去重逻辑

同一：

```text
session_id
```

情况下：

```text
seq <= old.seq
```

不会重新覆盖。

新 Session：

```text
允许 seq 从 0 开始
```

同时旧时间不能覆盖新数据。

这个逻辑解决：

- QoS1 duplicate；
- Gateway 重连；
- 重启；
- LWT；
- Session 切换。

---

# 20. STALE / OFFLINE 是怎么得到的

Gateway / Node：

```text
无 Broker
→ OFFLINE
```

或者：

```text
Heartbeat 超时
→ STALE/OFFLINE
```

Stream：

一般：

```text
5s
```

NIBP：

```text
90s
```

原因：

NIBP 不是连续流。

---

# 21. Browser Snapshot 是什么

Backend 每：

```text
100ms
```

生成一次 Snapshot。

结构：

```text
type = snapshot
schema_version = 1

gateway_id
gateways
gateway_state
broker_connected

nodes

server_time

streams

replay
event
```

Browser 不接 MQTT。

这是非常重要的边界。

---

# 22. WebSocket 为什么先发 Token

浏览器连接：

```text
/ws/v1/monitor
```

连接后第一帧：

```json
{
  "token": "...",
  "gateway_id": "GW-C-001"
}
```

不放：

```text
?token=...
```

因为 URL Token 容易进入：

- 浏览器历史；
- Nginx log；
- proxy log；
- analytics。

---

# 23. 慢 Browser 为什么不会拖垮 Backend

每个 Subscriber：

```text
Queue(maxsize=1)
```

如果旧 Snapshot 没取走：

```text
丢旧
保留最新
```

监护界面最重要的是：

```text
当前状态
```

不是：

```text
浏览器积压 30 秒历史状态
```

---

# 24. 当前 Web 怎么工作

`cloud/web/src/main.ts`

当前完成：

- WebSocket；
- Gateway 选择；
- Snapshot 解析；
- ECG Canvas；
- RESP Canvas；
- PPG Canvas；
- HR；
- RR；
- NIBP；
- SpO2；
- PR；
- TEMP；
- Node/Gateway 状态；
- MOCK/REPLAY 标识；
- Fullscreen；
- 8/16 秒显示窗口。

前端现在可以重构视觉，但不能修改数据协议。

---

# 25. 阶段二为什么加入 Canonical Data Model

原阶段一 Gateway 合成数据可以直接构造 JSON。

真实 CANopen 以后不能这样做：

```text
CANopen
  ↓
直接拼 MQTT JSON
```

否则 CANopen 与 MQTT 强耦合。

所以现在变成：

```text
CANopen
  ↓
MpFrame
  ↓
Router
  ↓
MQTT
```

---

# 26. `MpFrame` 的意义

Gateway 内部统一结构。

它保存：

```text
node
stream
timestamp
seq
boot/session
valid
synthetic
replay
sample_rate
samples/value
```

以后输入可能是：

```text
CANopen
UART
模拟器
```

只要转换成 `MpFrame`，后面逻辑不变。

---

# 27. CANopen 到 Gateway 的处理流程

代码：

```text
mp_stack
 ↓
Gateway RPDO Mirror
 ↓
mp_adapter
 ↓
MpFrame
 ↓
mp_router
```

`mp_adapter` 只读：

```text
Gateway 自己 RPDO 镜像区
```

禁止直接读取：

```text
测试 Node 的 OD 内存
```

否则就绕过 CAN 总线，测试失去意义。

---

# 28. 为什么波形需要批次

CAN：

```text
ECG 250Hz
PPG 50Hz
RESP 50Hz
```

如果每个点都 MQTT：

```text
350 次 MQTT publish / s
```

对：

```text
115200 UART
ESP8266 TLS
```

压力太大。

因此：

```text
CAN 高频采样
      ↓
Gateway 1 秒聚合
      ↓
MQTT 一次发送数组
```

例如：

```text
ECG = 250 samples
```

---

# 29. 时间戳为什么是“最后一个样本”

一秒批次：

```text
samples[0...249]
```

`timestamp`：

```text
最后一个样本采集时间
```

Browser 按：

```text
sample_rate
```

向前恢复每一点时间。

这样和现有 Canvas 时间轴一致。

---

# 30. CANopen OD 为什么不是“数据名称表”那么简单

当前对象字典还承担：

```text
标准对象
NMT
Heartbeat
EMCY
SDO
PDO Mapping
Identity
```

项目数据放私有对象：

```text
2100
2110
2111
2120
2130
```

Gateway 镜像：

```text
3100 / 3200
```

这是标准 CANopen 的使用方式。

---

# 31. 当前 CANopen Node ID

```text
Node-A = 1
Node-B = 2
Gateway-C = 3
```

不要随便修改。

因为 COB-ID、Heartbeat、SDO 都与 Node-ID 有关系。

---

# 32. PDO 当前映射

大致：

```text
TPDO1 主波形
TPDO2 第二波形
TPDO3 标量
TPDO4 时间
TPDO5 质量/Boot Generation
```

A：

```text
TPDO1 = PPG
TPDO2 = 保留
```

B：

```text
TPDO1 = ECG
TPDO2 = RESP
```

---

# 33. Boot Generation 为什么重要

如果 Node-B 重启：

```text
旧 ECG batch
```

不能和：

```text
新 ECG batch
```

拼起来。

因此：

```text
boot_generation
```

变化：

```text
Gateway 清旧半批波形
重新开始
```

---

# 34. Router 是怎么处理网络故障的

正常：

```text
MpFrame
  ↓
Live Queue
  ↓
MQTT
```

断网：

```text
MpFrame
  ↓
RAM Cache
```

恢复：

```text
新 LIVE
  ↓
优先发送
```

然后：

```text
REPLAY
```

低优先级补传。

---

# 35. 为什么不是先把历史补完

假设断网：

```text
5 分钟
```

恢复后如果先补历史：

```text
网页一直看到 5 分钟前
```

这是错误的监护语义。

必须：

```text
实时优先
```

---

# 36. 当前 Router 容量

```text
Live Queue = 16
History RAM = 32
```

注意：

> 这是测试阶段容量，不代表最终离线保存时长。

当前允许丢，并有：

```text
dropped
```

计数。

---

# 37. 当前 Replay 调度

繁忙时：

```text
至少 8 条 LIVE
→ 才允许 1 条 REPLAY
```

同时：

```text
REPLAY >= 2s 间隔
```

空闲：

```text
>=500ms
```

目标：

```text
实时不被历史饿死
历史也不会永远饿死
```

---

# 38. 为什么 QoS1 也不能代表“数据一定到 Web”

QoS1 最多证明：

```text
Publisher
  ↓
Broker
PUBACK
```

不证明：

```text
Backend 已处理
数据库已保存
Browser 已看到
```

所以最终高可靠系统需要：

```text
Gateway Cache
+
必要的应用 ACK / Storage
```

当前尚未完成。

---

# 39. Server 上服务怎么启动

systemd：

```text
medical-monitor-mqtt
medical-monitor
medical-monitor-mock
medical-monitor-certificate.timer
```

依赖关系：

```text
Broker
 ↓
Backend
 ↓
Web
```

Mock 是独立测试数据源。

---

# 40. Broker 为什么由 Python Wrapper 启动

现在：

```text
systemd
 ↓
broker_logging.py
 ↓
Mosquitto
```

目的：

Mosquitto 原始日志可能包含：

```text
IP
Client
其他文本
```

Wrapper：

```text
先在内存分类
 ↓
只保存固定事件名称
 ↓
只保存数字码
```

---

# 41. 日志里面有什么

允许：

```text
tls_error
authentication_denied
mqtt_connected
mqtt_disconnected
queue_depth
accepted
rejected
dropped
```

禁止：

```text
Payload
Topic
Password
Token
Username
真实地址
```

---

# 42. Release 模型

服务器不是：

```text
覆盖旧目录
```

而是：

```text
releases/version-A
releases/version-B

current -> version-B
```

升级：

```text
创建新 release
 ↓
测试
 ↓
切 current
```

回滚：

```text
current → old release
```

---

# 43. 为什么绝对不能原地覆盖

原地覆盖会导致：

```text
半新半旧
```

例如：

```text
Backend 新
Web 旧
Deploy 新
```

这种状态最难排查。

---

# 44. `upgrade_mqtt.py` 的安全检查

现在明确检查：

```text
root
release name
SHA256
目标不存在
ZIP traversal
绝对路径
symlink
```

并且用：

```text
python -O
```

测试仍然有效。

不要把这些改回 `assert`。

---

# 45. 第三方代码管理

## Paho

固定：

```text
upstream commit
SHA256
PATCHES.md
license
```

## CANopenNode

同样：

```text
固定 commit
upstream.json
SHA256
license
```

禁止：

```text
直接 git pull 覆盖 vendor
```

---

# 46. 后续新增 Stream 的标准流程

例如未来增加：

```text
MAP
```

正确流程：

```text
数据字典
 ↓
CANopen OD
 ↓
PDO Mapping
 ↓
MpStream
 ↓
model.c
 ↓
MQTT
 ↓
Backend models.py
 ↓
Web ViewModel
```

禁止：

```text
直接在 Web 写 MAP = (SYS + 2*DIA)/3
```

除非明确标：

```text
derived
```

并经过合同批准。

---

# 47. 前端安全修改规则

UI 可以随便重构视觉，但不能：

```text
把 MOCK 隐藏
把 INVALID 显示成 0
把 STALE 显示成上次值
把 REPLAY 画成 LIVE
自己判断“危险/正常”
自己生成报警
自己启动 NIBP
```

除非 Backend 正式提供对应语义。

---

# 48. 现在 UI 可以基于什么稳定接口开发

冻结：

```text
schema_version = 1
```

Snapshot：

```text
gateway_id
gateway_state
nodes
streams
replay
event
```

前端应该再做一层：

```text
Snapshot
 ↓
ViewModel
 ↓
UI
```

这样未来 Backend 增加字段：

```text
alarm
patient
measurement_state
```

不会破坏整个 UI。

---

# 49. 现有 UI 最大技术债

当前：

```text
main.ts
```

承担：

- HTML；
- WebSocket；
- State；
- Canvas；
- Interaction；
- Render。

后续 UI 重构应该拆分。

建议：

```text
src/
├── types.ts
├── transport/
│   └── monitorSocket.ts
├── state/
│   └── monitorStore.ts
├── model/
│   └── viewModel.ts
├── waveform/
│   └── renderer.ts
├── ui/
│   ├── layout.ts
│   ├── numerics.ts
│   └── status.ts
├── style.css
└── main.ts
```

---

# 50. 后期维护人员绝对不要破坏的 20 条规则

1. 不直接在 main 开发；
2. 不删除 MOCK 标识；
3. 不让 synthetic=true 变 LIVE；
4. 不让 REPLAY 覆盖 LIVE；
5. 不让 Web 直接连 MQTT；
6. 不让 Gateway 直接绕过 Canonical Model；
7. 不让 Backend 接受未知字段；
8. 不取消 Topic ACL；
9. 不开匿名 MQTT；
10. 不开明文 1883；
11. 不关闭 ESP 证书校验；
12. 不把真实 Secret 放 Git；
13. 不用无限队列解决丢包；
14. 不把 QoS1 写成“绝不丢”；
15. 不把 RAM Cache 写成“断电不丢”；
16. 不把测试 Node 写成真实 A/B；
17. 不把 RR 测试值写成正式算法；
18. 不删除失败验收记录；
19. 不原地覆盖服务器 release；
20. 不绕过 CI / Review 直接部署。

---

# 51. 接手人应该做什么

按顺序：

```text
1. 读总合同 v0.7
2. 读本手册
3. 读 P 第一阶段合同
4. 读 CANopen 数据字典
5. 看 README
6. 跑 CI 对应本地测试
7. 本地启动 Web
8. 使用 Mock
9. 看 /health
10. 再碰硬件
```

---

# 52. 本地最小测试

Backend：

```bash
python -m pytest cloud/backend/tests -q
```

CANopen：

```bash
python gateway/canopen/build_host.py
```

C → Backend：

```bash
python gateway/canopen/tools/check_canonical.py
```

Web：

```bash
cd cloud/web
npm ci --no-audit --no-fund
npm run build
```

---

# 53. 什么情况下不能直接改

以下任何一项需要新合同/接口变更：

```text
MQTT Topic
Snapshot schema_version
CANopen OD Index
PDO Mapping
Node ID
单位
采样率
Source 枚举
Validity 枚举
NIBP 结构
RR 定义
认证方式
```

---

# 54. 当前未关闭事项

仍未完成：

```text
真实 Node-A
真实 Node-B
三板 CAN 电气联调
CAN transceiver / 120Ω
正式 RR
Flash 离线缓存
24h
真实人体数据安全门禁
用户账号认证
长期数据库
最终报警策略
BOOT0 独立启动确认
```

这些必须继续保留在风险清单里。

---

# 55. BOOT0 特别说明

阶段二出现：

```text
重新上电进入 System ROM
```

J-Link 手动进入 Flash 可以执行测试。

因此最终 Gateway-C 独立运行前必须确认：

```text
BOOT0
Option Bytes
板载跳线
上电电平
```

当前不要擅自修改 Option Bytes。

---

# 56. UI 重构与 Backend 的关系

当前 Backend 已经足够作为 UI 重构冻结接口。

UI 项目必须：

```text
只改 cloud/web
```

除非新需求明确需要接口。

如果前端开发者认为：

```text
“为了做这个页面必须改 Backend”
```

正确动作不是直接改，而是：

```text
提交 Backend Interface Change Request
暂停
等待 P 确认
```

---

# 57. 最后的理解模型

把系统记成 5 个盒子：

```text
A/B
负责采集

CANopen
负责板间标准通信

Gateway
负责统一数据和网络可靠性

Backend
负责状态和浏览器接口

Web
负责显示
```

每个盒子都只做自己的事情。

如果后续任何一个改动跨过两个以上边界，就先问：

> “是不是应该先设计接口，而不是直接写代码？”

这就是本项目后续可维护性的核心。
