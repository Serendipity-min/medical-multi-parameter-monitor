# P5 coreMQTT 网关运行机制与源码调用链 v2.0

> **版本标识与代码基线**
> - **文档版本**：v2.0
> - **当前代码修复提交 (CODE_FIX_COMMIT)**：`2e13ff3be398ae33ab4d4ab8a9ba0fec3c5d6855`
> - **前序审计固定起点 (START_HEAD)**：`cc2c3a9fa135958aa26613821f11f411f54f62ae`
> - **第四阶段基线提交 (P4_BASE)**：`8dee339491cfd4edc468bb9451511d421f26db5e`
> - **历史 Security Gate 独立复跑 SHA**：`d1e7388a91149a7c66e6cf1a5df7321bbb8eab12` (CONDITIONAL_PASS / EXIT_2)
> - **历史短 Smoke 固件 BIN SHA-256**：`7694dc197a8b2363ad605e1da784e3fa791af7d69888e23755e69b7e627a099b` (43.812s / 25帧上报)
> - **当前物理开发板回读全片 Flash SHA-256**：`15102707af11cfb7f57bac250bd30e583274d9f992292f5db6576a4b69c37354` (1MiB 双读一致，板载无 P5 固件)
> - **文档正式提交 (DOCS_COMMIT)**：将在本文档纳入 Git 提交后记录于外部交接回执中，正文不自引用。

---

## 1. 系统背景、迁移动机与架构拓扑

### 1.1 从 P4 Paho 到 P5 coreMQTT 的迁移动机与工程边界

在多参数心电监护仪系统（Multi-Parameter Monitor, MPM）开发过程中，网关模块承担着汇聚现场多节点生理波形与体征数据、并在恶劣或断网环境下可靠上云的核心职责。

- **P4 阶段选型与痛点**：
  P4 阶段网关固件采用经过加固的 Eclipse Paho Embedded C 库。虽然完成了基本发布链路，但 Paho Embedded C 在裸机长周期运行中暴露了内存边界难以精确控制、网络断开后内部状态机清理逻辑不透明、以及跨包分片等待与单片机看门狗/协作调度耦合过紧的问题。
- **P5 阶段引入 FreeRTOS/coreMQTT v2.3.1 的动机**：
  coreMQTT 是 AWS / FreeRTOS 专门面向受限嵌入式环境设计的 MQTT 3.1.1 客户端。其核心优势在于：
  1. **零动态内存分配 (Zero Dynamic Allocation)**：所有上下文与序列化缓冲区由调用方静态提供，消除堆碎片与内存泄漏隐患；
  2. **完全解耦的 I/O 契约**：通过 `TransportInterface_t`（包含 `send`、`recv`、`writev`）将协议解析与底层传输（ESP8266 AT 驱动）彻底分离；
  3. **严格的状态机与有界解析**：对 MQTT 报文头、长度字段、PUBACK 校验提供确定性防御。
- **必须澄清的工程事实与边界**：
  - **并非“全系统废弃 Paho”**：后端 Python 数据服务（`cloud/backend`）依然使用标准 `paho-mqtt` 客户端订阅 Broker，架构上是 C 网关（coreMQTT）与 Python 后端（paho-mqtt）共存；
  - **协议版本仍为 MQTT 3.1.1**：未引入 MQTT 5.0 特性；
  - **当前运行环境为单片机裸机 (Baremetal)**：无操作系统，无 FreeRTOS 调度器，所有任务依托 SysTick 与主循环协作轮询完成；P6 阶段 FreeRTOS 任务化迁移尚未启动。

---

### 1.2 两种截然不同的系统拓扑对比

面试或架构答辩时，必须严谨区分以下两种拓扑，禁止将单板合成环境混淆为物理多板已验收环境：

| 维度 | 当前开发/验证拓扑（合成单板回环） | 未来目标物理拓扑（三实体板分布式） |
|---|---|---|
| **物理板卡数量** | 1 块 STM32F407ZGT6 核心板 + 1 块 ESP8266 Wi-Fi 模块 | 3 块物理板（Node-A、Node-B、Gateway-C）+ ESP8266 |
| **CAN 总线形态** | 片内 bxCAN Silent Loopback（静默自回环） | 物理 CAN 总线（双绞线、120Ω 终端电阻、收发器） |
| **CANopen 协议实例** | 1 颗 MCU 内运行 3 个独立 `CO_t` 实例（Node-A、Node-B、Gateway） | 每颗 MCU 独立运行 1 个 `CO_t` 实例 |
| **时钟与采样源** | 单一主晶振与 SysTick 驱动所有节点的虚拟滴答 | 各节点独立晶振，存在微小硬件时钟漂移 |
| **验收状态** | **已完成**：Host 单元测试、ARM 离线构建、短 Smoke 预检 | **未验收/未联调**：物理三板联调属于后续阶段规划 |

```mermaid
flowchart TB
    subgraph Current_Topology["当前验证拓扑：单板合成三实例 (F407 bxCAN Loopback)"]
        subgraph STM32F407["STM32F407ZGT6 (单板裸机)"]
            NA["实例 0: Node-A\n(PPG/SpO2/PR/NIBP)\nOD + TPDO"]
            NB["实例 1: Node-B\n(ECG/HR/RESP/RR/TEMP)\nOD + TPDO"]
            GW["实例 2: Gateway\nRPDO + Adapter + Router\n+ coreMQTT Client"]
            bxCAN["bxCAN 控制器 (Silent Loopback 模式)"]
            NA <-->|内部总线回环| bxCAN
            NB <-->|内部总线回环| bxCAN
            GW <-->|内部总线回环| bxCAN
        end
        ESP["ESP8266-01S (USART3, AT+TLS)"]
        GW <-->|UART AT 桥接| ESP
    end

    subgraph Target_Topology["未来目标拓扑：物理三板独立部署 (未验收)"]
        P_NA["物理 Node-A 板\n(采集前置)"]
        P_NB["物理 Node-B 板\n(采集前置)"]
        P_GW["物理 Gateway 板\n(网关主控)"]
        P_ESP["物理 ESP8266 模块"]
        CAN_BUS["物理 CAN 差分双绞线 (120Ω 终端电阻)"]
        P_NA <-->|CAN_H / CAN_L| CAN_BUS
        P_NB <-->|CAN_H / CAN_L| CAN_BUS
        P_GW <-->|CAN_H / CAN_L| CAN_BUS
        P_GW <-->|USART3| P_ESP
    end
```

---

## 2. 软件总体架构与核心调用链

### 2.1 模块分层与代码文件布局

系统从底层硬件抽象到上层云交互，划分为清晰的五层架构：

```mermaid
flowchart TD
    subgraph Layer5["5. 云端接入与业务呈现"]
        Broker["MQTT Broker (EMQX / Mosquitto)"]
        Backend["Python Backend (paho-mqtt, Hub, FastAPI)"]
        WebUI["Web 大屏 (Vite + TypeScript + 原生 DOM/Canvas 实时波形)"]
        Broker <-->|MQTT 3.1.1| Backend
        Backend <-->|WebSocket| WebUI
    end

    subgraph Layer4["4. 网关协议与传输层 (gateway/mqtt/src)"]
        MQTT_APP["主业务循环\n(main.c)"]
        MQTT_TRANS["网关传输适配\n(gateway_transport.c)"]
        CORE_MQTT["coreMQTT 官方核心\n(core_mqtt.c, serializer, state)"]
        NET_ADAPTER["网络层适配器\n(mqtt_transport_adapter.c)"]
        MQTT_APP --> MQTT_TRANS
        MQTT_TRANS --> CORE_MQTT
        CORE_MQTT --> NET_ADAPTER
    end

    subgraph Layer3["3. 数据管道与离线缓存 (gateway/storage & data_model)"]
        ROUTER["帧路由器与双级缓存\n(storage/router.c)"]
        MODEL["规范数据模型\n(data_model/model.c)"]
        MQTT_APP --> ROUTER
        ROUTER --> MODEL
    end

    subgraph Layer2["2. 现场总线与适配层 (gateway/canopen/src)"]
        ADAPTER["CANopen 采样适配器\n(canopen/src/mp_adapter.c)"]
        STACK["多实例 CANopen 协议栈\n(canopen/src/mp_stack.c)"]
        CANOPEN_NODE["CANopenNode 官方核心\n(CANopen.c, 301/CO_*.c)"]
        ADAPTER --> STACK
        STACK --> CANOPEN_NODE
        ADAPTER --> ROUTER
    end

    subgraph Layer1["1. 硬件抽象与外设驱动 (gateway/canopen/stm32 & esp_at_probe)"]
        BXCAN["bxCAN 环回/控制器驱动\n(canopen/stm32/bxcan_loopback.c)"]
        UART_DRV["USART3 驱动与中断环形缓冲区\n(gateway_platform.c)"]
        SYSTICK["SysTick 毫秒时钟 (g_uptime_ms)"]
        ESP_HW["ESP8266-01S 硬件模块 (AT 指令固件)"]
        NET_ADAPTER --> UART_DRV
        UART_DRV <-->|物理串口| ESP_HW
        STACK --> BXCAN
    end

    NET_ADAPTER <-->|TLS 链路| Broker
```

---

### 2.2 启动与主循环调用时序

系统在单主线程下协作运行。主循环启动、协议初始化、网络建立与持续轮询调用链如下：

```mermaid
sequenceDiagram
    autonumber
    participant Main as main() [main.c]
    participant Plat as platform_init() [gateway_platform.c]
    participant Stack as mp_stack_init() [mp_stack.c]
    participant bxCAN as mp_bxcan_init() [bxcan_loopback.c]
    participant Adapter as mp_adapter_init() [mp_adapter.c]
    participant Router as mp_router_init() [router.c]
    participant Net as gateway_network_open() [gateway_transport.c]
    participant MQTT as gateway_mqtt_open() [gateway_transport.c]
    participant Svc as service() [main.c]

    Main->>Plat: platform_init() [初始化 GPIO, SysTick, USART3]
    Main->>Stack: mp_stack_init(&stack, 0) [初始化 3 个 CANopen 节点实例]
    Main->>bxCAN: mp_bxcan_init() [配置 bxCAN 为静默环回模式]
    Main->>Adapter: mp_adapter_init(&adapter) [清空波形批次与时钟状态]
    Main->>Router: mp_router_init(&router) [初始化 16 实时 / 32 缓存队列]
    Main->>Plat: platform_set_poll(service) [注册网络阻塞期间的协作调度钩子]

    loop 外层连接生命周期循环
        Main->>Net: gateway_network_open() [AT+CWJAP 连 Wi-Fi, CIPSTART 建 TLS]
        Note over Main,Net: 若网络失败，delay_ms(3000) 重试，内部协作轮询 service()
        Main->>MQTT: gateway_mqtt_open(&will) [MQTT_Init, MQTT_Connect, 发送 LWT]

        loop 内层数据分发循环
            Main->>Plat: platform_poll() [间接执行 service(), 推进 CAN 状态机与控制台]
            Main->>Router: mp_router_take(&router, &frame, now)
            alt 获取到待发布帧 (实时或补传)
                Main->>MQTT: gateway_mqtt_publish(&frame) [序列化 JSON, MQTT_Publish, 等待 PUBACK]
                Main->>Router: mp_router_ack(&router, &frame, success) [成功则确认，失败则回退]
            else 队列为空
                Main->>MQTT: gateway_mqtt_yield() [处理 KeepAlive PINGREQ/PINGRESP]
            end
        end
        Main->>Net: gateway_network_close() [清理连接，准备下一次重连]
    end
```

---

### 2.3 关键执行机制：中断、协作轮询与单主线程防饥饿

裸机系统没有抢占式多任务内核，如何保证高波特率串口收发与高实时性 CAN 采样不互相卡死？
1. **系统主频与 SysTick 滴答时钟**：当前工程样机运行在 **16 MHz HSI**（内部高速 RC 振荡器，未启用外部 HSE 晶振及 PLL 倍频至 168 MHz），`SysTick_Config(SystemCoreClock / 1000U)` 配置 1ms 毫秒基准中断，`SysTick_Handler` 仅维护全局递增变量 `volatile uint32_t g_uptime_ms`，严禁在中断中执行耗时计算；
2. **UART3 中断与 8192 B 环形缓冲区**：
   ESP8266 串口数据通过 `USART3_IRQHandler` 接收，中断例程仅将字节压入固定尺寸为 **8192 B**（8 KiB）的静态环形缓冲区 `ring[CAPACITY]`（`CAPACITY = 8192U`，`gateway/mqtt/src/platform.c`），不解析 AT 行，不触发 MQTT 协议逻辑；
3. **协作调度钩子 (`platform_set_poll(service)`)**：
   当网络层处于阻塞等待（如 `at_command` 阻塞等待响应、或 `MQTT_ProcessLoop` 等待网络字节）时，内部循环反复调用 `platform_poll()`。`platform_poll()` 触发 `service()` 回调：
   ```c
   /* gateway/mqtt/src/main.c */
   static void service(void)
   {
       mp_bus_poll();
       /* 预算限制：每次调用最多处理 8ms 的时钟追赶，防止网络完全被 CAN 饿死 */
       unsigned budget = 8;
       while (serviced != g_uptime_ms && budget--)
       {
           serviced++;
           mp_stack_tick(&stack);
           mp_adapter_poll(&adapter, &stack, &router);
       }
       /* 本地调试字符输入处理 */
       ...
   }
   ```
4. **单主线程保证数据一致性**：
   `mp_stack_tick`、`mp_adapter_poll`、`mp_router_take`、`gateway_mqtt_publish` 全部在主线程上下文中串行推进，彻底消除了多线程环境下的临界区锁开销与死锁风险。

---

## 3. CANopen 现场总线与数据适配层

### 3.1 CAN 基础 vs CANopen 协议的区别

- **原生 CAN (Layer 2 - 数据链路层)**：只提供 11 位/29 位 ID、0–8 字节载荷、CRC 校验与仲裁机制，没有任何关于“这是心率还是血压”、“数据该如何解析”、“节点是否掉线”的高层语义；
- **CANopen (Layer 7 - 应用层规范 CiA 301)**：
  1. **对象字典 (Object Dictionary, OD)**：为设备所有参数定义规范化的 16 位索引与 8 位子索引；
  2. **过程数据对象 (PDO)**：无应答高实时数据传输（TPDO 发送，RPDO 接收），通过 OD 映射关系预先绑定；
  3. **服务数据对象 (SDO)**：点对点可靠参数读写；
  4. **网络管理与心跳 (NMT & Heartbeat)**：周期性广播节点生命周期状态（Boot-up、Pre-operational、Operational、Stopped）。

---

### 3.2 节点划分、生理参数映射与异常定义

在当前合成系统中，三实例划分与参数映射定义于 `gateway/canopen/src/mp_od.c` 与 `mp_adapter.c`：

| 节点 | 节点 ID | 映射参数 | 采样频率 | OD 索引与格式 | 异常标志位 / 质量位 |
|---|---|---|---|---|---|
| **Node-A** (前置 A) | 0x01 | PPG (光电容积脉搏波) | 50 Hz | `0x2110:01` / `0x3110:01` (uint16) | 探头脱落、弱灌注标志 |
| | | SpO2 (血氧饱和度) | 1 Hz | `0x2120:01` / `0x3120:01` (uint16, %) | 范围 0–100% |
| | | PR (脉率) | 1 Hz | `0x2120:02` / `0x3120:02` (uint16, bpm) | 0 表示无效 |
| | | NIBP (无创血压) | 1 Hz / 事件 | `0x2120:03..04` (收缩/舒张, uint16) | 充气错误、测量超限 |
| **Node-B** (前置 B) | 0x02 | ECG (心电图) | 250 Hz | `0x2110:01` / `0x3210:01` (int16, 0.1μV) | 导联脱落 (Lead-off) |
| | | RESP (呼吸波) | 50 Hz | `0x2111:01` / `0x3211:01` (int16) | 窒息报警 (Apnea) |
| | | HR (心率) | 1 Hz | `0x2120:01` / `0x3220:01` (uint16, bpm) | 心动过速/过缓 |
| | | RR (呼吸率) | 1 Hz | `0x2120:02` / `0x3220:02` (uint8, rpm) | `0xFF` (`RR INVALID`) |
| | | TEMP (体温) | 1 Hz | `0x2120:03` / `0x3220:03` (int16, 0.1℃) | 探头未连接 |
| **Gateway** (网关) | 0x03 | 自身状态 / 诊断 | 0.2 Hz (5s) | 内部生成，不占外总线 | WiFi 信号、丢包统计 |

> **关键容错语义：`RR INVALID (0xFF)`**
> 当呼吸阻抗算法因体动伪影或基线漂移无法提取有效呼吸率时，Node-B 上报 `RR = 0xFF`。网关适配器保留此原始标志，并在 JSON 中转译为 `null` 或无效质量位，绝不虚构 0 rpm（0 rpm 代表临床窒息），防止误导医护人员。

---

### 3.3 波形批次汇聚与 `MpFrame` 规范模型

高频波形（ECG 250Hz、PPG 50Hz、RESP 50Hz）如果逐点发送 MQTT，会导致巨大的网络开销与 Broker 崩溃。
网关在 `gateway/canopen/src/mp_adapter.c` 中实施 **1 秒固定批次汇聚**：
- **ECG**：每秒累积 250 个采样点（500 字节点阵）；
- **PPG**：每秒累积 50 个采样点（100 字节点阵）；
- **RESP**：每秒累积 50 个采样点（100 字节点阵）。

汇聚后的规范结构体定义于 `gateway/data_model/model.h`：
```c
typedef struct {
    uint8_t node;           /* 源节点 ID: 1=A, 2=B, 3=Gateway */
    MpStream stream;        /* 流类型: ECG, PPG, RESP, HR, SPO2, STATUS 等 */
    uint64_t timestamp;     /* 采样绝对时间戳 (UTC 毫秒, 由 SNTP epoch + 采样偏移计算) */
    uint32_t seq;           /* 该数据流严格单调递增的序号 */
    uint32_t epoch;         /* 网关启动校时锚点 (UNIX 秒) */
    uint32_t boot;          /* 节点启动轮次计数 (高 16 位 Gateway, 低 16 位 Node) */
    bool synthetic;         /* 是否为测试合成数据 (当前固件固定为 true) */
    bool replay;            /* 是否为断网重连后的历史补传帧 */
    /* 载荷联合体：包含标量数据或波形批次数组 */
    ...
} MpFrame;
```

---

## 4. 传输适配层与 coreMQTT 驱动机制

### 4.1 网络 I/O 分工与 ESP8266 AT 责任划分

本系统采用 **MCU + ESP8266 伴侣芯片** 方案。协议栈的职责划分边界极其严格：

```mermaid
flowchart LR
    subgraph MCU["STM32F407 (网关主控)"]
        coreMQTT["coreMQTT 核心库\n(纯逻辑协议状态机)"]
        Adapter["mqtt_transport_adapter.c\n(超时管理 / writev 组包)"]
        Platform["gateway_platform.c\n(USART3 字符收发 / AT 指令解析)"]
        coreMQTT <--> Adapter
        Adapter <--> Platform
    end

    subgraph ESP["ESP8266-01S (Wi-Fi 伴侣)"]
        AT_Engine["AT 指令解释引擎"]
        TLS_Stack["mbedTLS 协议栈\n(CA 校验, SNI, AES 加密)"]
        TCP_IP["LwIP TCP/IP 协议栈"]
        AT_Engine <--> TLS_Stack
        TLS_Stack <--> TCP_IP
    end

    Platform <-->|串口物理线 115200bps\nAT+CIPSEND, +IPD| AT_Engine
    TCP_IP <-->|TLS 1.2 加密连接| Cloud["EMQX Broker (8883)"]
```

- **ESP8266 负责**：
  1. Wi-Fi 物理连接与重连（`AT+CWJAP`）；
  2. TLS 握手、服务端证书 CA 链校验、SNI 域名上报与对端证书主机名校验（CCN）；
  3. SNTP 绝对时间获取（`AT+CIPSNTPCFG=1,0` 配置 NTP 且 UTC 偏移 0，`AT+SYSTIMESTAMP?` 查询系统绝对时间戳）；
  4. 底层 TCP 流量控制与重传。
- **STM32 coreMQTT 负责**：
  1. MQTT 报文编码（CONNECT, PUBLISH, PINGREQ, DISCONNECT）；
  2. 报文解析与 PUBACK 报文 ID 校验；
  3. KeepAlive 保活时钟维护（15 秒超时主动触发 PINGREQ）；
  4. 业务数据队列与断网有损淘汰策略。

> **硬件设计事实：无 GPIO 硬复位引脚，纯软件超时与状态机自愈**
> 当前硬件未连接或配置 ESP8266 的 GPIO RST 硬件复位引脚。遇到 AT 指令超时（单命令 2000–3000ms 滴答超时）或网络断开时，系统完全依靠软件状态机容错：
> 1. 先通过 `gateway_network_close()` 发送 `AT+CIPCLOSE` 拆除残留套接字；
> 2. 重连入口调用 `esp_mqtt_reset()`（关中断重置 `tail = head; errors = 0; network_length = 0;`）原子清空接收环形队列；
> 3. 重新按序执行 `AT`、`ATE0`、`AT+SYSSTORE=0`、`AT+CWMODE=1`、`AT+CWJAP`、`AT+CIPSNTPCFG=1,0`，实现纯软件层的受控冷重连。重试等待期间由 `platform_poll()` 协作维持 CANopen 现场总线心跳。

---

### 4.2 `TransportInterface_t` 适配层与 `writev` 零拷贝拼装

coreMQTT 依赖三组 I/O 函数指针。在 `gateway/mqtt/src/mqtt_transport_adapter.c` 中实现：
1. `send`：发送单段连续内存；
2. `recv`：非阻塞或有界阻塞接收；
3. `writev`：**向量化聚合写**（关键优化！）。
   coreMQTT 在发布报文时，报文头（固定报文头 + Topic 字符串 + Packet ID）与载荷（JSON 字符串）通常位于不连续的内存区域。如果分两次调用底层 `send`，将触发两次独立的串口 `AT+CIPSEND` 握手与网络发包，严重降低吞吐率。
   `mqtt_transport_adapter.c` 实现的 `writev` 将多个分片在本地静态发送缓冲区中紧凑拼装，通过单次 `AT+CIPSEND=<len>` 一次性推送到 ESP8266，且发送完毕后立即对敏感缓冲区实施擦除。

---

### 4.3 QoS 0 与 QoS 1 的可靠性机制对比

```mermaid
sequenceDiagram
    autonumber
    participant Router as router.c
    participant GW as gateway_transport.c
    participant coreMQTT as core_mqtt.c
    participant ESP as ESP8266
    participant Broker as MQTT Broker

    rect rgb(240, 248, 255)
    Note over Router,Broker: QoS 0 发布流程：无 Broker ACK，发完即确认
    Router->>GW: mp_router_take(frame)
    GW->>coreMQTT: MQTT_Publish(QoS0, packetId=0)
    coreMQTT->>ESP: AT+CIPSEND [PUBLISH Header + Payload]
    ESP->>Broker: TCP MQTT PUBLISH (QoS0)
    coreMQTT-->>GW: MQTTSuccess
    GW->>Router: mp_router_ack(frame, success=true) [出队删除]
    end

    rect rgb(255, 245, 238)
    Note over Router,Broker: QoS 1 发布流程：严格等待匹配的 PUBACK
    Router->>GW: mp_router_take(frame)
    GW->>coreMQTT: MQTT_Publish(QoS1, packetId=101)
    coreMQTT->>ESP: AT+CIPSEND [PUBLISH QoS1 ID=101]
    ESP->>Broker: TCP MQTT PUBLISH (QoS1 ID=101)
    Note over GW,coreMQTT: 保持帧在队列中，等待 PUBACK 确认
    Broker-->>ESP: TCP MQTT PUBACK (ID=101)
    ESP-->>coreMQTT: +IPD [PUBACK Header ID=101]
    coreMQTT->>GW: 回调通知: 收到匹配的 packetId=101 PUBACK
    GW->>Router: mp_router_ack(frame, success=true) [出队删除]
    end

    rect rgb(255, 240, 245)
    Note over Router,Broker: QoS 1 异常场景：错号 / 超时 / 丢包
    Router->>GW: mp_router_take(frame)
    GW->>coreMQTT: MQTT_Publish(QoS1, packetId=102)
    coreMQTT->>ESP: AT+CIPSEND [PUBLISH QoS1 ID=102]
    ESP--xBroker: 网络波动丢失
    Note over GW: 达到 bounded timeout (如 3000ms) 未收到 PUBACK
    GW->>Router: mp_router_ack(frame, success=false) [保留在队列，标记待重发]
    GW->>GW: 触发网络异常，准备重连
    end
```

> **核心认知防坑**：
> 1. **QoS 0 ≠ 失败不感知**：若串口写超时或 ESP 返回 `ERROR`，本地发送立刻返回失败；但若已送达 ESP，Broker 是否收到在协议层完全不可知；
> 2. **QoS 1 匹配性校验**：必须验证 PUBACK 中的 `Packet ID` 与本地发送的 ID 严格一致。迟到的、错号的、或上一会话遗留的 PUBACK 均被判定为非法；
> 3. **QoS 1 ≠ Exactly Once**：QoS 1 保证至少一次送达（At Least Once）。在断网重连重发过程中，Broker 或后端可能收到重复报文，因此下游必须支持去重；
> 4. **MQTT PUBACK ≠ Backend 消费确认**：必须深刻理解 MQTT 协议的单跳（Hop-by-Hop）传输属性。Broker 返回的 PUBACK 仅代表第一跳 Broker 节点成功接收了该报文并承担后续路由职责，绝不等于下游 Python 后端、Hub 服务或临床数据库已成功消费、解析和持久化。如果后端服务断线或入库处理异常，Broker 依然会向网关返回 PUBACK。端到端业务确认需在更高应用层另行规划。

---

## 5. 断网缓存、路由器设计与后端去重闭环

### 5.1 双级有界缓存与丢包淘汰模型 (`router.c`)

嵌入式网关 RAM 极度受限（F407 总 RAM 仅 192KB，留给路由缓存仅数千字节），绝不能使用无界动态链表。
`gateway/storage/router.c` 实现了两级静态环形队列：
1. **实时队列 (Live Queue)**：容量 16 帧，优先处理刚采样的波形与状态；
2. **离线缓存队列 (Cache Queue)**：容量 32 帧，当网络断开时，未确认数据与最新关键数据转移至离线缓存；
3. **严格的有界淘汰 (FIFO Drop)**：
   当两级队列总计 48 帧占满时，若继续产生新帧，系统将执行 **最旧帧淘汰**，并递增计数器 `router.dropped`。
   在实际压力测试与历史验收中，明确记录了 `lost=203`。这以无可辩驳的证据表明：**本系统在长时间断网下是有损缓存设计，不承诺全量无损恢复**！

```mermaid
stateDiagram-v2
    [*] --> Disconnected: 系统上电 / 网络未连接

    state Disconnected {
        [*] --> CacheAccumulate
        CacheAccumulate: 采样产生 MpFrame
        CacheAccumulate --> CacheCheck: 写入 Cache (最大 32 帧)
        CacheCheck --> CacheDrop: 队列满 (32 帧已占满)
        CacheDrop --> CacheAccumulate: 丢弃最旧帧, dropped++ (实测 lost=203)
        CacheCheck --> CacheAccumulate: 队列未满, 正常推入
    }

    Disconnected --> Connected: gateway_network_open() 成功

    state Connected {
        [*] --> LiveSend
        LiveSend: 实时发布 (Live Queue 16 帧)
        LiveSend --> CheckCache: 实时队列空闲
        CheckCache --> ReplaySend: 提取 Cache 帧, 标记 replay=true
        ReplaySend --> LiveSend: 成功发送并 ACK
    }

    Connected --> Disconnected: 网络断开 / 发送连续失败 / 控制台 'D'
```

---

### 5.2 后端 Hub 去重、时间窗口与前端呈现

- **三层架构分工**：
  1. **网关层**：生成携带唯一 `(node, stream, seq, boot, epoch)` 的标准化 JSON；
  2. **Broker 层**：负责报文路由分发；
  3. **后端 Python 服务层 (`cloud/backend`)**：
     内置 `Hub` 模块，根据 `(node, stream)` 维护滑动接收窗口。当网关因 QoS 1 重发或网络恢复重传历史帧时：
     - 若收到的 `seq <= last_seq` 且 `boot` 相同，识别为重复帧，记录审计日志并静默丢弃；
     - 若 `replay == true`，将数据归档入历史时序库，不打乱实时大屏的绘制指针；
  4. **前端大屏 (`cloud/web`)**：通过 WebSocket 与后端连接，首帧必须完成 Token 鉴权，仅接收只读实时流与去重后的波形点阵，实现平滑 Canvas 渲染。

---

## 6. 本地控制台调试与 `GEMINI-P5-001` 修复调用链

### 6.1 本地测试单字符指令集

在 `gateway/mqtt/src/main.c` 的 `service()` 函数中，保留了通过串口交互的本地单字符调试入口：

| 字符 | 功能说明 | 对应内部调用 | 预期控制台回执 |
|---|---|---|---|
| `'D'` | 请求主动断开 Wi-Fi 连接 | `disconnect_requested = 1;` | `GW WIFI_TEST_DISCONNECTED` (30s后恢复) |
| `'A'` | 切换 Node-A 使能状态 | `mp_stack_enable(&stack, 1, !enabled)` | `GW NODE_TEST_ENABLED` / `DISABLED` |
| `'B'` | 切换 Node-B 使能状态 | `mp_stack_enable(&stack, 2, !enabled)` | `GW NODE_TEST_ENABLED` / `DISABLED` |
| `'C'` | 模拟 CAN 总线物理通断 | `mp_bus_set_online(!online)` | `GW CAN_TEST_RECOVERED` / `DISCONNECTED` |
| `'R'` | 重启 Node-B 协议栈实例 | `mp_stack_restart(&stack, 2)` | `GW NODE_TEST_RESTARTED` |
| `'G'` | 重启 Gateway 协议栈实例 | `mp_stack_restart(&stack, 3)` | `GW GATEWAY_TEST_RESTARTED` |
| `'E'` | **触发/复位 Node-A 紧急报文 (EMCY)** | `CO_errorReport` / `CO_errorReset` | `GW EMCY_TEST_CHANGED` 或 `NODE_UNAVAILABLE` |

---

### 6.2 `GEMINI-P5-001` 缺陷根因、危害与修复调用链对比

- **缺陷代码 (修复前)**：
  ```c
  if (c == 'E')
  {
      static bool fault;
      fault = !fault;  /* 致命缺陷 1: 在未校验有效性前直接翻转状态 */
      if (fault)
          CO_errorReport(stack.nodes[0].co->em, CO_EM_GENERIC_ERROR, CO_EMC_GENERIC, 0);
      else
          CO_errorReset(stack.nodes[0].co->em, CO_EM_GENERIC_ERROR, 0);
      /* 致命缺陷 2: 若 stack.nodes[0].co 为 NULL，访问 co->em 导致 NULL 指针解引用 HardFault 崩溃！ */
      console("GW EMCY_TEST_CHANGED\r\n");
  }
  ```
- **危害剖析**：
  当 Node-A 因动态初始化失败（如 `CO_new` 内存不足）或重启脱挂时，`stack.nodes[0].co` 被置空。此时若测试人员在控制台键入 `'E'`，MCU 将立刻触发精确总线错误 (`HardFault`)，导致整机系统死锁下线。同时，即使不解引用，异常状态也会错误翻转 `fault` 静态标志，导致后续恢复时 report 与 reset 语义倒置。
- **修复后代码 (当前提交 `2e13ff3`)**：
  ```c
  if (c == 'E')
  {
      static bool fault;
      /* 严谨守卫：同时校验 co 指针与其内部 em 子模块指针 */
      if (!stack.nodes[0].co || !stack.nodes[0].co->em)
      {
          console("GW EMCY_TEST_NODE_UNAVAILABLE\r\n");
      }
      else
      {
          fault = !fault;
          if (fault)
              CO_errorReport(stack.nodes[0].co->em, CO_EM_GENERIC_ERROR, CO_EMC_GENERIC, 0);
          else
              CO_errorReset(stack.nodes[0].co->em, CO_EM_GENERIC_ERROR, 0);
          console("GW EMCY_TEST_CHANGED\r\n");
      }
  }
  ```

```mermaid
flowchart TD
    Start["收到控制台字符 'E'"] --> GuardCheck{"stack.nodes[0].co != NULL\n并且\nstack.nodes[0].co->em != NULL ?"}

    GuardCheck -- "否 (未就绪/已脱挂)" --> Reject["输出: GW EMCY_TEST_NODE_UNAVAILABLE\n保持 fault 静态变量不变\n跳过所有指针解引用"]
    Reject --> End["退出 service()"]

    GuardCheck -- "是 (节点健全)" --> FlipState["fault = !fault"]
    FlipState --> CheckFault{"fault == true ?"}
    CheckFault -- 是 --> SendReport["CO_errorReport(stack.nodes[0].co->em, ...)"]
    CheckFault -- 否 --> SendReset["CO_errorReset(stack.nodes[0].co->em, ...)"]
    SendReport --> Confirm["输出: GW EMCY_TEST_CHANGED"]
    SendReset --> Confirm
    Confirm --> End
```

---

## 7. 静态配置与动态内存资源台账

本样机遵循嵌入式高可靠编码规范：coreMQTT 协议层与传输适配层**完全不依赖动态内存分配**；CANopenNode 实例初始化（`CO_new`）依然使用 `calloc`，但其分配由 `gateway/mqtt/src/heap.c` 的 `_sbrk` 和链接脚本预留的 24 KiB 有界动态堆限制；超出堆边界返回 `ENOMEM`。这不是免碎片的静态对象池，也不替代运行时栈高水位验证。

| 模块 / 结构体 / 内存段 | 分配位置 | 占用大小 (字节) | 归属源文件 / 脚本 | 生命周期与用途说明 |
|---|---|---|---|---|
| `MpStack stack` | BSS 静态段 | 约 38,400 | `gateway/mqtt/src/main.c` | 系统全生命周期驻留，3 节点协议栈实例 |
| `MpAdapter adapter` | BSS 静态段 | 约 3,200 | `gateway/mqtt/src/main.c` | 系统全生命周期驻留，批次波形汇聚与时钟锚定 |
| `MpRouter router` | BSS 静态段 | 49,576 | `gateway/mqtt/src/main.c` | 16 live + 32 cache 帧静态双级缓存队列 |
| `MQTTContext_t` | BSS 静态段 | 约 256 | `gateway/mqtt/src/gateway_transport.c` | coreMQTT 协议状态机上下文 |
| `NetworkContext_t` | BSS 静态段 | 2,120 | `gateway/mqtt/src/mqtt_transport_adapter.c` | 包含 2048 字节发送拼装缓冲区 |
| `ring[CAPACITY]` | BSS 静态段 | 8,192 (8 KiB) | `gateway/mqtt/src/platform.c` | UART3 中断接收环形缓冲区 (`CAPACITY=8192U`) |
| **有界动态堆 (Heap 预留)** | `._user_heap_stack` | 24,576 (24 KiB) | `STM32F407ZGT6_FLASH.ld` | `_heap_start` 至 `_heap_end`，供 `_sbrk` 限制性分配 |
| **主栈预留区 (Stack 预留)** | `._user_heap_stack` | 8,192 (8 KiB) | `STM32F407ZGT6_FLASH.ld` | `_heap_end` 向上静态预留的主栈预留区（无 MPU 硬隔离） |
| **ARM 固件构建总计** | **Flash: 35,624 B** | **RAM BSS: 120,120 B** | **Data: 88 B** | **已链接分配: 120,208 / 131,072 B (91.7%)** |

> **深入理解内存分布与 10,864 B 剩余 RAM 的含义**：
> 1. **配置 RAM 容量**：STM32F407ZGT6 物理 SRAM 总计 192 KiB，但链接脚本 `STM32F407ZGT6_FLASH.ld` 仅规划使用了常规 SRAM 的前 **128 KiB**（`LENGTH = 128K`，即 131,072 B），起始地址 `0x20000000`，栈顶 `_estack = 0x20020000`；
> 2. **已分配静态段**：Data 段（88 B）+ BSS 段（含未初始化全局变量 87,348 B + Heap 预留 24,576 B + Stack 预留 8,192 B + 对齐 4 B，合计 120,120 B），链接期已分配 **120,208 B**，占 128 KiB 配置空间的 **91.7%**；
> 3. **10,864 B 剩余 RAM**：从预留段末尾（`0x2001D590`）到 RAM 上限 `_estack`（`0x20020000`）之间，恰好剩余 `0x2A70` = **10,864 字节**。这 10,864 字节是链接段末尾与 RAM 顶部之间未分配的上方裕量，不是整个栈的严格容量：MSP 从 `_estack` 向下增长，下方另有已链接预留的 8,192 B 栈区域；从 RAM 顶部至 `_heap_end` 的地址距离合计约 19,056 B。预留本身不提供栈溢出硬件保护，不能据此推断运行时最大安全栈深；
> 4. **客观风险与边界**：在极端中断嵌套和深层调用下，该区域的**运行时栈高水位（Stack High-Water Mark）尚未完成真机打标实测**，属于工程样机已知受控风险（RSK-P5-001）。

---

## 8. 4 分钟面试白板讲解提纲

在面试官要求“简要介绍你的 P5 coreMQTT 裸机网关架构”时，可按以下结构在 4 分钟内流畅书写与阐述：

```text
[0:00 - 0:45] 业务背景与定位
- "我们做的是多参数心电监护仪系统工程样机网关，将 Node-A（PPG/SpO2/PR/NIBP）与 Node-B（ECG/HR/RESP/RR/TEMP）的生理数据安全上云。"
- "P5 阶段将原 Paho 迁移为 AWS coreMQTT v2.3.1，协议层实现零动态内存分配与状态解耦，显著降低了裸机长周期运行风险。"
- "强调：MQTT 3.1.1、纯裸机单主线程、后端 Python 仍用 paho-mqtt 订阅。"

[04:5 - 1:45] 拓扑与调度模型 (画出分层框图)
- "当前验证拓扑是单块 F407 利用 bxCAN 静默环回运行 3 个独立 CANopen 实例；目标三板分布式拓扑已做好架构隔离。"
- "调度无 RTOS：系统以 16 MHz HSI 运行，SysTick 维护 1ms 毫秒基准；UART3 中断只写入 8KB 环形缓冲；网络阻塞等待期间通过 platform_poll 协作推进 CAN 采样（单次上限 8ms 防饥饿）。"
- "ESP8266 无硬件 GPIO 复位引脚，遇到断网或超时通过 software timeout、AT+CIPCLOSE、esp_mqtt_reset() 原子清空队列与有序重发 AT 指令自愈。"

[1:45 - 2:45] 数据管道与可靠传输 (画出 Router 双级缓存与 QoS 1 时序)
- "高频波形在 Adapter 处实施 1 秒批次汇聚（ECG 250 点，PPG 50 点），封装为携带单调递增 seq 和绝对时间戳的 MpFrame。"
- "传输采用向量写 writev 聚合单次 CIPSEND，降低串口与网络开销；ESP8266 专职硬件 TLS 与 SNTP 校时。"
- "QoS 1 必须收到并匹配 PUBACK 的 Packet ID，Router 才出队确认；注意 MQTT PUBACK 仅代表第一跳 Broker 接收，不等于后端消费确认；断网时 16 实时 + 32 缓存队列实施有界淘汰（实测 lost=203，承认有损）。"

[2:45 - 3:30] 核心 Bug 复盘与最新最小修复 (GEMINI-P5-001)
- "复盘了历史 CANopen 重启未解挂导致的空指针崩塌问题；"
- "在本次 P5 收尾中，独立识别并最小修复了 GEMINI-P5-001：控制台 'E' 调试命令在 Node-A 脱挂时解引用 NULL 指针的隐患，增加了双指针非空守卫，并编写了全套负向与恢复 Host 自动化用例。"

[3:30 - 4:00] 严谨度与诚实边界
- "我们通过了 42 项 coreMQTT Host 测试、12/11/17 项 CANopen 检查与真实 ARM 离线构建；"
- "诚实说明：物理板卡已完整恢复原始基线固件（双读 Hash 一致），板上不留临时固件；物理三板联调与 FreeRTOS 任务化属于后续阶段。"
```
