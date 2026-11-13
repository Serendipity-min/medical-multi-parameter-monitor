# 多参数生理监护仪样机：P5 裸机 coreMQTT 迁移正式执行合同（v1.0）

> **文件编号**：MPM-P5-GW-SOW-001  
> **版本**：v1.0 / 正式签发版  
> **签发日期**：2026-10-08  
> **执行对象**：Codex（项目 Gateway-C P 侧研发）  
> **代码仓库**：https://github.com/Serendipity-min/medical-multi-parameter-monitor  
> **建议仓库内路径**：`doc/P/P5_coreMQTT裸机迁移正式执行合同_v1.0.md`  
> **授权状态**：**P5 软件开发与常规功能验证：AUTHORIZED**；真机写入及影响云端服务的破坏性测试：**HOLD，须现场测试窗口确认**；统一 Security Gate：**NOT AUTHORIZED**；P6/P7：**NOT AUTHORIZED**；P4 合并：**NOT AUTHORIZED**。  
> **验收口径**：未完成的测试必须标记 `NOT_RUN/BLOCKED`，不能用推测、模拟、历史 P4 证据冒充 P5 的真机结论。

---

## 0. 签发决议（Codex 必读，优先级最高）

本合同取代《P5_P6_coreMQTT_FreeRTOS分阶段验证路线与执行合同_v0.1.md》**作为 P5 的具体执行依据**；v0.1 仍保留为历史规划材料，不覆盖、不删除。P6/P7 仍只保留规划属性。项目负责人已经明确裁定：

1. **允许 P5 与 Node-A / Node-B / 三板 CAN 外部集成并行开发**，但 P5 不接管 A/B 分支和实际三板 CAN 准出。
2. **Security Gate 须再次获得单独明示授权**；本次“开始 P5”不包含 Semgrep、Trivy、Gitleaks、clang-tidy、ASan/UBSan 固定安全回归、Fuzzing、全量漏洞验证等统一安全门操作。普通编译、常规单元测试、功能/接口回归允许执行。
3. **P6 阶段性 24h soak/pre-release** 保留到 P6 单独签发后执行；不是 P5 的门槛，也不等于整机最终 Release 稳定性。
4. P5 本轮只更换 **Hardened Paho Embedded C → FreeRTOS/coreMQTT v2.3.1（MQTT 3.1.1）**。继续采用 **STM32F407 裸机**，不引入 FreeRTOS，不升级 MQTT 5.0。
5. **允许 Codex 在独立 P5 分支修改代码、运行普通测试、形成提交并 push P5 分支；允许创建 Draft PR 指向 P4；不允许直接修改或 push `P4`/`main`、自动合并 PR、删除其他开发分支。**
6. 如出现仓库漂移、工作树脏、权限冲突、数据契约变化、必须调整 TLS 安全参数、无法证明 QoS1 PUBACK 语义或硬件前置条件不满足，**停止相关操作并向项目负责人报告，不自行扩大授权**。

**期望本轮终点**：`P5 软件迁移实现 + 普通回归 + 证据 + Draft PR`；若真机和 Security Gate 尚未授权或尚未完成，则状态为 `P5_PENDING_HARDWARE_AND/OR_SECURITY`，**不得声称 P5 全量准出，不得合并 P4，不得启动 P6**。

---

## 1. 仓库只读核验基线（签发时已确认，执行前必须复核）

2026-10-08 通过 GitHub 连接只读核对结果：

| 关键分支或事实 | 签发时状态 | Codex 执行要求 |
|---|---|---|
| `P4` | `8dee339491cfd4edc468bb9451511d421f26db5e` | 唯一 P 侧集成基线，先核验再创建 P5 分支 |
| `main` | `50699048010c57ba10f8573461844c525b022a07` | 历史稳定主干，不在本合同修改 |
| `dev/node-a-v07` | `7a85914d6ae1f6e370c6c6e9e1d224296fa57ab1` | Node-A 独立开发，不在本合同修改 |
| `dev/node-b-v07` | `ce84b33b705403775790d4723978d586aeb877a4` | Node-B 独立开发，不在本合同修改 |
| `P5-coremqtt-baremetal` | 签发时不存在 | 确认工作树干净后，从上述 P4 创建 |
| PR #4、PR #5 | 已合并至 P4 | 两者是基线事实，不重新执行历史合同 |
| 当前 Gateway | 裸机 STM32F407 + 加固 Paho + MQTT 3.1.1 + ESP8266 AT/TLS | P5 前务必保存可构建对照物 |

**重要差异**：上传截图中的本地 `doc/P/` 目录有顶层 P5/P6 v0.1 与阶段性报告；2026-10-08 读到的远端 P4 `doc/P/` 列表只有 `README.md` 和五个阶段/维护目录。**因此本地截图不等于远端已提交文件**。Codex 必须检查本机真实工作树及未跟踪文件，遇到本地文档差异不得覆盖、删除或自动 stash/clean；先报告并请求确认。

读取顺序：

1. `doc/P/README.md`
2. `doc/P/90_维护/多参数监护仪_P端云网关维护手册与工作流程_v1.1.md`
3. `doc/P/01_第一阶段_MQTT云端/合同/P_云网关实现原理_代码设计与维护接管手册_v1.1.md`
4. `doc/P/90_维护/ADR_Gateway_MQTT客户端与FreeRTOS迁移路线_v0.1.md`
5. `gateway/mqtt/README.md`、`gateway/canopen/README.md`
6. 当前 `gateway/mqtt/src/`、`gateway/mqtt/build.py`、`gateway/third_party/paho-embedded-c/PATCHES.md`、`gateway/third_party/verify_paho_integrity.py`
7. 本合同 v1.0；若发现与当前代码冲突，按 **真实代码 > 最新提交/PR > 现行维护手册/ADR > 本合同的路径建议 > 历史记录** 调查，并报告差异。合同的**禁止事项、授权边界与行为等价要求不得自行降低**。

**Codex 预检命令示例（在项目 Git 根目录；只读或远端更新引用）**：

```bash
git status --short --branch
git branch --show-current
git remote -v
git fetch --prune origin
git rev-parse HEAD
git rev-parse origin/P4
git rev-parse origin/main
git branch -a
# 只读检索相关已存在文件和可能的 P5 分支
git ls-files 'gateway/mqtt/**' 'gateway/third_party/**' 'doc/P/**'
git ls-remote --heads origin 'P5*'
```

**前置 GO/NO-GO**：`origin/P4` 与签发锁定 SHA 不一致时先暂停，交付新的 diff/漂移清单；本地未提交修改、P5 分支已存在、未跟踪用户文件冲突时先暂停。绝不 `git reset --hard`、`git clean -fd`、`git stash`、强推或自动改写历史。

---

## 2. 项目架构、已验收边界与 P5 唯一变量

### 2.1 当前真实链路

```text
P 侧 CANopenNode 合成 Node-A / Node-B（当前：一块 F407、CAN1 静默 loopback）
  → OD / PDO → Canonical Data Model → Router (LIVE 优先、RAM cache、REPLAY)
  → Hardened Paho MQTT 3.1.1 → ESP8266 AT + CA/SNI/CCN/TLS
  → Mosquitto :8883 → FastAPI Backend → WebSocket Snapshot v1 → Nginx → Web
```

真实 Node-A、Node-B、三板外部 CAN、正式 RR 算法、Flash 持久缓存均未因 P5 变成“已验证”；A/B 实物集成可以与 P5 **并行**，但必须分别出具独立证据。Gateway 当前是 **publish-only**，不接收 MQTT 订阅业务、不做 OTA/远程控制；RR 在正式算法完成前仍为 `INVALID`。

### 2.2 本合同唯一架构改变

```text
P4: STM32F407 bare metal + Hardened Paho Embedded C  + MQTT 3.1.1
                        ↓ 仅 MQTT 客户端实现迁移
P5: STM32F407 bare metal + coreMQTT v2.3.1          + MQTT 3.1.1
```

以下不变：芯片/启动方式、CANopen/OD/PDO、数据模型、`mp_json()`、`mp_topic()`、Router、采样率、LIVE/REPLAY、Topic/Payload、波形 QoS0、状态/标量/REPLAY QoS1、LWT retain、MQTT Client ID/认证来源、Keepalive 15s、MQTT Clean Session、Mosquitto/TLS:8883、Backend/Web、ESP8266 AT 固件、CA/CCN/SNI 时间校验、Flash 配置格式和地址。

**不能用“coreMQTT 更现代或更安全”代替以上逐项行为证据。**

### 2.3 明确禁止

- 不引入 FreeRTOS、coreMQTT-Agent、MQTT v5、OTA/订阅/下行命令、异步多任务网络架构。
- 不修改 A/B 分支、真实传感器固件、CAN 帧接口、数据字典、Web UI、Broker 配置和生产服务器。
- 不修改芯片 BOOT0、Option Bytes、ESP8266 AT 固件、`client_key`，不关闭 TLS CA/CCN/SNI 验证，不把凭据写入源码/日志/PR。
- 不启用新 Flash 缓存，也不修改 `gateway/mqtt/STM32F407ZGT6_FLASH.ld` 的 896KiB 应用区 / sector 7 配置区，除非暂停并另行审核。
- 不覆盖 `gateway/third_party/paho-embedded-c/`、PATCH-01/02/03、`upstream.json`、`patched.json`、既有验收 JSON/PNG 或历史合同。
- 不自行执行统一 Security Gate、其“quick/pr/release/doctor”入口、全量 Semgrep、Trivy、Gitleaks、clang-tidy、旧 Paho 的 ASan/UBSan 安全回归、Fuzzing、畸形包/攻击实验、公共互联网扫描。

---

## 3. 源码路径清单与目标文件树（区分现有和计划）

**符号**：`[E]` P4 已存在、只读参考；`[M]` P5 计划修改；`[N]` P5 新建；`[P]` 历史保留不改。方括号仅为说明标记，不是目录名。所有新路径须先与当前树去重，遇同名文件不得覆盖。

```text
medical-multi-parameter-monitor/
├─ gateway/
│  ├─ mqtt/
│  │  ├─ README.md                              [M] 当前实现切换与操作说明
│  │  ├─ build.py                               [M] active MQTT 源/头白名单与完整性校验
│  │  ├─ provision.py                           [E] 不改私有配置注入契约
│  │  ├─ STM32F407ZGT6_FLASH.ld                [E] 不改 Flash/RAM 分区
│  │  ├─ src/
│  │  │  ├─ main.c                              [E/M] 仅发现必要的连接生命周期适配时改
│  │  │  ├─ gateway_transport.c                 [M] coreMQTT context / CONNECT / PUBLISH / PUBACK / Yield
│  │  │  ├─ gateway_transport.h                 [M] 去掉 Paho 的 MQTTClient.h 依赖
│  │  │  ├─ gateway_platform.h                  [M] 删除/隔离 Paho 专用 Timer/Network 类型
│  │  │  ├─ platform.c                          [M] 仅抽出原有 AT 收发的可复用有界函数
│  │  │  ├─ gateway_config.h                    [E] 结构体/地址/魔数绝对不变
│  │  │  ├─ heap.c                              [E] 不更改既有 _sbrk 边界
│  │  │  ├─ mqtt_transport_adapter.h            [N] coreMQTT transport 适配声明
│  │  │  ├─ mqtt_transport_adapter.c            [N] TransportInterface_t / 单调时间桥接
│  │  │  └─ core_mqtt_config.h                  [N] 有界 timeout/buffer 的项目配置
│  │  └─ tests/                                [N] 仅常规功能测试，不是 Security Gate
│  │     ├─ README.md                           [N] 本地测试入口与可运行条件
│  │     ├─ run_p5_host_tests.py                [N] 使用真实 coreMQTT 源的固定用例
│  │     ├─ test_p5_qos_ack.c                   [N] 迟到/错号/超时 PUBACK、QoS0/1 逻辑
│  │     ├─ test_p5_connect_keepalive.c         [N] CONNECT/LWT/保活/断线状态
│  │     ├─ test_p5_transport.c                 [N] 长度、部分发送/接收、超时、错误传播
│  │     └─ mocks/                              [N] 单元测试专用模拟 ESP 传输字节流
│  ├─ third_party/
│  │  ├─ paho-embedded-c/                        [P] Hardened Paho 全量历史保留
│  │  ├─ verify_paho_integrity.py               [P] 继续保留并可单独人工核验
│  │  ├─ CANopenNode/                           [E] 不改
│  │  ├─ coreMQTT/                              [N] 官方 v2.3.1 精简固定 vendor 快照
│  │  │  ├─ LICENSE                             [N] 官方 MIT 许可原文
│  │  │  ├─ README.md                           [N] tag、commit、入库文件清单及原因
│  │  │  ├─ upstream.json                       [N] tag+commit+各 vendor 文件 SHA-256
│  │  │  └─ source/
│  │  │     ├─ core_mqtt.c                      [N] 官方原样
│  │  │     ├─ core_mqtt_serializer.c           [N] 官方原样
│  │  │     ├─ core_mqtt_state.c                [N] 官方原样
│  │  │     ├─ include/
│  │  │     │  ├─ core_mqtt.h                    [N]
│  │  │     │  ├─ core_mqtt_serializer.h         [N]
│  │  │     │  ├─ core_mqtt_state.h              [N]
│  │  │     │  └─ core_mqtt_config_defaults.h   [N]
│  │  │     └─ interface/
│  │  │        └─ transport_interface.h         [N]
│  │  └─ verify_coremqtt_integrity.py           [N] 离线只读 SHA-256 + 构建白名单校验
│  ├─ canopen/                                 [E] 接口/loopback/测试框架不改
│  ├─ data_model/                              [E] Canonical Model/序列化不改
│  └─ storage/                                 [E] Router/cache/LIVE+REPLAY 不改
├─ cloud/                                      [E] Broker/Backend/Web 均不改
└─ doc/P/
   ├─ README.md                                [M] 增加 P5 导航和真实状态（勿改写历史）
   ├─ P5_coreMQTT裸机迁移正式执行合同_v1.0.md    [N] 本合同，受控版
   ├─ P5_P6_coreMQTT_FreeRTOS分阶段验证路线与执行合同_v0.1.md
   │                                          [P] 如果本地存在则保留；远端 P4 未见该文件
   ├─ 04_第四阶段_P5_coreMQTT裸机迁移/           [N] P5 单独阶段材料
   │  ├─ README.md                             [N]
   │  ├─ 设计/P5_接口迁移与构建清单_v1.0.md     [N] 变更映射/关键常量/等价性
   │  └─ 验收/
   │     ├─ P5_普通功能验证报告_v1.0.md        [N] PASS/FAIL/NOT_RUN
   │     ├─ P5_资源对照与回滚记录_v1.0.md      [N] 对照数据与固件 SHA
   │     └─ P5_证据索引_v1.0.md                [N] 证据位置/来源/时间/状态
   ├─ 90_维护/                                [P] P4 维护/ADR 原文保留
   └─ 99_历史/                                [P] 历史合同与记录原文保留
```

说明：上述 `[N]` 为**规划目标文件**，不是声称仓库已经存在。为了降低无关变更，若 Codex 调研发现某个新文件可以由已命名的同功能文件承载，须先写明映射再实现；不能把计划名当成与现有代码冲突时可直接覆盖的许可。`gateway/mqtt/build/` 等生成目录必须保持 gitignore，不提交固件 BIN、ELF、私有配置、原始秘密日志。

---

## 4. 逐文件改造规则（不可跳步）

| 真实 P4 落点 | P5 操作 | 硬性要求/不得发生的变化 |
|---|---|---|
| `gateway/mqtt/build.py` | 替换 active 依赖清单、头文件路径和编译源；在构建前先校验固定 coreMQTT vendor | 编入三份必需官方 `.c`；移除 active Paho 编译/依赖；不使用通配把上游所有测试/示例/formatter 纳入 ELF；保留 ARM 构建命令与产物路径 |
| `gateway/mqtt/src/gateway_transport.h` | 暴露稳定的 `gateway_mqtt_open/publish/yield` 和 `gateway_network_open/close` 接口 | 取消 `#include "MQTTClient.h"`；保持 `main.c` 的外部调用契约 |
| `gateway/mqtt/src/gateway_transport.c` | 替换 `MQTTClient` 状态机为 `MQTTContext_t`、QoS 状态记录、CONNECT/Publish/ProcessLoop | 严格保留 Will、Topic、Payload、QoS、CleanSession、ClientID、Keepalive、日志脱敏；不得在 `MQTT_Publish` 返回后直接 ACK QoS1 |
| `gateway/mqtt/src/platform.c` | 提取现有 `mqtt_read()/mqtt_write()` 中已验证的 AT 传输逻辑，为新适配器提供底层 send/recv | **不重写 AT 协议状态机**：保持 `CIPSEND`、`CIPRECVLEN?`、`CIPRECVDATA` 的长度和二进制边界；网络等待中继续 `platform_poll()` 维护 CAN 协作进度 |
| `gateway/mqtt/src/gateway_platform.h` | 将 Paho `Timer/Network` 专用 typedef 与新的传输接口隔离 | 保持 `g_uptime_ms`、串口轮询和 SNTP 数据时间语义；不误改 UART IRQ/启动 |
| `gateway/mqtt/src/main.c` | 优先保持不变，只有证明 `Router ack`/连接生命周期接口需要适配时作最小更改 | `mp_router_take()`、`mp_router_ack()`、`mp_router_online()`、缓存和断线重连链路保持；不能把 REPLAY 冒充 LIVE |
| `gateway/mqtt/src/core_mqtt_config.h` | 放置经过核对的 receive-poll/send/keepalive 上界和 buffer 配置 | 以官方 v2.3.1 宏为准；使用真机资源数据设上限；**不要定义** `MQTT_DO_NOT_USE_CUSTOM_CONFIG` 使自定义配置失效 |
| `gateway/mqtt/src/mqtt_transport_adapter.[ch]` | 定义 `NetworkContext_t` 实例、`TransportInterface_t.send/recv` 和单调时钟适配 | 只包裹已验证 ESP 收发；零/负数/部分读取/实际写入字节数按上游 API 契约传递，错误不可当成功 |
| `gateway/mqtt/src/gateway_config.h` | **不改** | `sizeof(GatewayConfig)==312`、配置地址 `0x080E0000`、MAGIC 不变；没有新的敏感字段 |
| `gateway/mqtt/STM32F407ZGT6_FLASH.ld` | **不改** | FLASH 应用区 896KiB，独立 sector 7；SRAM 128KiB，原有 24KiB heap/8KiB stack 预留布局不变 |
| `gateway/canopen/`、`gateway/data_model/`、`gateway/storage/` | **只跑普通回归，不改代码** | 若迁移需要改变它们的接口，停止并报告为何违反“只换 MQTT Client” |
| `cloud/`、Web 和 Mosquitto | **不改** | Topic、Payload、Broker 证书/配置、WebSocket Snapshot v1 均保持兼容 |
| `gateway/third_party/paho-embedded-c/` + verifier | **不删不改** | 历史来源、PATCH-01/02/03、`upstream.json/patched.json`、历史完整性与安全结果保持可审计 |

### 4.1 关键 API 映射（v2.3.1，不能套用 v5 签名）

| P4 Paho | P5 coreMQTT v2.3.1 | 验证重点 |
|---|---|---|
| `MQTTClientInit` | `MQTT_Init` | context、固定网络 buffer 的生命周期；毫秒时钟实函数，不是永远返回 0 |
| `MQTTConnect` | `MQTT_Connect` | 同样 3.1.1 CONNECT、身份、clean session、LWT；检查 CONNACK 成功才上线 |
| QoS1 状态 | `MQTT_InitStatefulQoS` | 初始化有限条 outgoing 记录；目前单一串行发布通道建议 1 个 outstanding，无入站订阅记录 |
| `MQTTPublish` | `MQTT_Publish` + `MQTT_ProcessLoop` + MQTT 事件回调 | QoS1 需对应 packet ID 的 PUBACK 后才能算成功 |
| `MQTTYield` | `MQTT_ProcessLoop` | 保活 PINGREQ/PINGRESP、网络错误/半包处理，不阻塞 CAN 协作流程 |
| Paho `Network.mqttread/mqttwrite` | `TransportInterface_t.recv/send` | 适配 `NetworkContext_t`，按 `int32_t` 返回读写字节/异常；保留二进制精确长度 |
| Paho `Timer` | `MQTTGetCurrentTimeFunc_t` | 返回 `g_uptime_ms` 单调毫秒；**与 SNTP epoch / 生理数据 timestamp 独立** |

官方 API：`https://freertos.github.io/coreMQTT/v2.3.1/core__mqtt_8h.html`。**注意：`MQTT_InitStatefulQoS` 是 v2.3.1 的五参数形式；不要照搬 MQTT5/main 分支含属性参数的更新接口。**

### 4.2 必须实现的 QoS1 语义（最高优先级）

P4 `gateway_mqtt_publish()` 返回成功的 QoS1 消息意味着 Paho 客户端已处理相应 PUBACK，主循环才执行 `mp_router_ack(..., true)`。coreMQTT v2.3.1 的 `MQTT_Publish()` 成功只表示已完成必要的发布发送步骤，**不是 PUBACK**。迁移须维持 Router 的等价语义：

```text
mp_router_take() → 得到独立 MpFrame 副本
  → 序列化、生成 topic、选择 QoS
  ├─ QoS0：MQTT_Publish 成功提交完整发送 → success（不声称 Broker ACK）
  └─ QoS1：MQTT_GetPacketId() → MQTT_Publish()
           → 在有界等待内持续 MQTT_ProcessLoop()
           → 事件回调看到同一 packetId 的合法 PUBACK
                ├─ 是：success → mp_router_ack(frame, true)
                └─ 否/超时/断线/非法状态：failure → mp_router_ack(frame, false)
  → 维持原 Router 回存/REPLAY/重连流程
```

强制要求：

1. 当前维持一个 MQTT context、一个串行发布者；同一时刻最多 1 个等待中的 QoS1 packet ID，不添加线程/Agent。
2. PUBACK 必须由库解析并通过正常回调/状态被识别，验证 `packetId` 对应**本次**请求；迟到、错号、重复 PUBACK 都不能确认别的帧。
3. 超时后不得把未知 Broker 结果当成功；与 P4 一样按 Router 失败回存、断线重连处理；QoS1 + 应用层 seq/session 可能出现**至少一次/重复**，不得承诺恰好一次。
4. `MQTT_ProcessLoop` 的 `MQTTNeedMoreBytes` 和有限轮询行为需按官方约定合理处理；不能把未收全包视为 PUBACK，也不能无限循环。
5. 缓冲区、publish payload 和 Will 都必须在上游库可能引用期间有效；避免栈指针悬垂；JSON 不可因容量不足截断后仍发送。
6. 任何意外 inbound `PUBLISH` 都必须**禁止业务消费、禁止执行命令，并使连接进入失败/重连处理**；不能因为 coreMQTT 有收包 callback 就默许下行订阅业务。
7. 不能把 ESP 的 `SEND OK` 当成 Broker 的 PUBACK；两者位于不同协议层。
8. 跨 MQTT 断线重连必须初始化干净的 coreMQTT context/outgoing record，避免旧 packet ID/回调跨会话错误确认新帧。
9. Paho 与 coreMQTT 的 `retained`、LWT topic/payload、broker 连接状态与在线/离线语义需实测逐项比较，不能仅看网页最终显示。

### 4.3 Transport 约束

- 用 `NetworkContext_t` 保管必要的 AT 连接状态，`TransportInterface_t` 仅负责**已建立 TLS socket**上的二进制读写；AT/TLS 建立继续由既有 `gateway_network_open()` 执行。
- `send` 可以收到任意合法长度；不得直接假定都小于 `2048` 而静默截断。若超过已验证 ESP AT 边界，显式分段且逐段严格发送，或者在发送前用有界容量检查拒绝，不能靠 UB/越界继续运行。
- `recv` 的 `0` 只代表超时/当前无数据（依官方约定）；负值才表示传输失败；保留被动接收先查询 `CIPRECVLEN?` 的实现和缓存剩余字节逻辑。
- 继续使用 UART3 IRQ 只收字节、主线程协作 CAN 的时序结构；AT 等待期间继续 `platform_poll()`，不做阻塞重构。
- 确保 `MQTT_ProcessLoop`、CONNACK、PUBACK 的等待预算与 ESP AT 底层阻塞超时一致，避免 15s keepalive 被意外超时吞掉；实际参数进入 `设计/P5_接口迁移与构建清单_v1.0.md`。
- SNTP `minimum_epoch`、CA 验证 `AT+CIPSSLCCONF=2,0,0`、`AT+CIPSSLCCN`、`AT+CIPSSLCSNI`、`AT+CIPSTART="SSL",...,8883` 保持原样；失败不得降级为明文 TCP。

---

## 5. 官方 coreMQTT v2.3.1 的来源固定与第三方治理

**已核对的官方版本**：

```text
repository: https://github.com/FreeRTOS/coreMQTT
tag: v2.3.1
tag object SHA: f4616fa5753781aef73ed645edd5793a8028291d
peeled commit SHA: 2beef04725328923e05e576b884212d53ec97af7
protocol: MQTT 3.1.1
license: MIT
```

官方仓库版本链接：`https://github.com/FreeRTOS/coreMQTT/tree/v2.3.1`。上述 SHA 是 GitHub tag 和其实际 commit 的身份，**不是任何本地文件的 SHA-256**。文件 SHA-256 必须由 Codex 对官方固定 commit 的真实字节逐一计算、记录、再本机复核，禁止虚构。

**实施步骤**：

1. 使用官方**准确 tag/commit** 获取上游源码；先验证 tag 对应上述 commit。避免将 `main`、MQTT5 示例、最新版 API 混入。
2. 只 vendor `LICENSE`、三份核心 `.c`、四份 include `.h`、`transport_interface.h` 和所需许可证/说明；每个文件保证字节级不修改。
3. 生成 `gateway/third_party/coreMQTT/upstream.json`：至少包含 repo、tag、**commit**、许可、文件相对路径与对应 SHA-256；不得将 Git blob SHA 当作 SHA-256。
4. 新建 `gateway/third_party/verify_coremqtt_integrity.py`，实现：清单路径必须位于 vendor 根内、拒绝目录穿越、文件集合白名单、文件 SHA-256 校验、active build 源名单校验；只读检查，失败阻止构建。禁止运行时联网安装或从浮动分支下载源码。
5. 本项目配置和 Transport Adapter 放到 `gateway/mqtt/src/`，不要就地修改第三方库头/源。
6. 保留原 Paho 的源文件、固定完整性与补丁历史，但**P5 固件不再链接 Paho 的 MQTTClient/MQTTPacket 客户端源文件**。普通构建仅运行新的 coreMQTT integrity 检查；旧 Paho 的安全回归等单独授权。

**可编译源码白名单**（具体 include 配套以 v2.3.1 `mqttFilePaths.cmake` 验证）：

```text
gateway/third_party/coreMQTT/source/core_mqtt.c
gateway/third_party/coreMQTT/source/core_mqtt_serializer.c
gateway/third_party/coreMQTT/source/core_mqtt_state.c
```

不得凭方便自动把 `test/`、演示、FreeRTOS kernel、coreMQTT-Agent、MQTT5 代码或其它第三方模块引入目标镜像。

---

## 6. 执行分解、提交顺序与每步准出

| 阶段 | Codex 执行内容 | 立即交付物 | 通过后方可继续 |
|---|---|---|---|
| **P5-00 基线冻结** | 只读检查状态、确认 P4 SHA/工作树/PR/路径；基线重建（工具已具备时） | `baseline.md`：Git SHA、平台、P4 资源/ELF/BIN SHA、依赖状态 | 工作树干净且 P4 预期一致；否则 STOP |
| **P5-01 分支** | `git switch -c P5-coremqtt-baremetal origin/P4`（分支已存在先停） | 新分支标识与 HEAD | 不触碰 P4/main |
| **P5-02 固定上游** | 下载/拷入准确 coreMQTT v2.3.1 官方文件，MIT 许可，清单与校验器 | vendor tree、`upstream.json`、只读校验结果 | 文件 hash 全 PASS，无浮动依赖 |
| **P5-03 适配层** | 将 Paho `Network` 适配替换为 coreMQTT transport callback；仅在必要处修改 `platform.c` | 新 Adapter、有限超时边界、host transport 测试 | AT 二进制路径/错误传播等价 |
| **P5-04 客户端迁移** | coreMQTT 初始化、Connect、Will、publish、QoS1 等 ACK、keepalive、失败清理 | `gateway_transport.c/.h`、普通功能测试 | QoS1 不提前回 ACK、保留 publish-only |
| **P5-05 构建替换** | 修改 `build.py` 的 active source/include 白名单；只编译 coreMQTT；host + ARM 正常构建 | ELF/BIN/map/size 及 hash/符号检查 | 仍为裸机、MQTT3.1.1；配置地址不变 |
| **P5-06 等价回归** | CANopen / Canonical Model / Router / Backend **普通测试**，隔离 broker 功能验证（可得环境才跑） | 按第 7 节填完整测试矩阵 | 失败不继续压到真机 |
| **P5-07 真机阶段** | 仅在负责人批准硬件窗口后临时烧录、合成数据 smoke、故障验证、完整 Flash 恢复 | 真机报告、配置脱敏摘要、备份哈希/恢复证明 | 未批准则 `NOT_RUN`, 不得伪造 PASS |
| **P5-08 归档与交付** | 更新 README、设计/测试/资源/回滚记录；commit 并 push P5；可开 Draft PR→P4 | P5 commit、Draft PR、测试证据索引、STOP/BLOCKED 清单 | 不自动合并、不启动 P6、不执行 Security Gate |

**建议提交粒度**（只在每部分可独立编译/检查时提交；名字可调整但内容不可混写）：

```text
chore(p5): pin coreMQTT v2.3.1 and offline integrity manifest
refactor(p5): adapt ESP AT transport to coreMQTT interface
feat(p5): preserve MQTT311 publish and PUBACK semantics with coreMQTT
build(p5): switch gateway active source allowlist and measure firmware
test(p5): add deterministic MQTT equivalence regression
docs(p5): record P5 migration results and outstanding gate
```

不要为了填满这些提交强行拆坏的代码；也不要一次把 vendor、网络、测试、docs 混进无法审查的巨型提交。**每个提交应有摘要和必要的本地测试结果**。

---

## 7. P5 普通功能验证矩阵（必须逐项记 PASS/FAIL/NOT_RUN）

> 禁止假定某测试已执行。下表“目标/预期”不是实测结果。只在授权的环境运行；第三方安全扫描不在本矩阵内。

| ID | 测试与条件 | 成功判据 | 证据 |
|---|---|---|---|
| H01 | upstream 文件、tag/commit 和哈希 | 与官方固定 commit 及 SHA-256 清单完全一致；没有 Paho active 链接 | `vendor-verify.json` 或日志摘要 |
| H02 | `python gateway/mqtt/build.py` ARM 构建 | `gateway_mqtt.elf/.bin` 存在，编译器返回 0，`-Wall/-Wextra/-Werror` 平台源无告警 | `build.log`、`size.txt`、BIN SHA |
| H03 | active 源符号/构建清单 | 包含 coreMQTT 目标源，不再编译/链接 Paho MQTT Client/Packet；无 FreeRTOS/MQTT5 | 源清单、ELF 符号摘要 |
| H04 | CONNECT / CONNACK + 基本认证 | 使用 MQTT 3.1.1、相同 Client ID、认证字段、clean session、TLS 端口；拒绝失败 CONNACK | 固定 broker/宿主模拟测试 |
| H05 | 遗嘱与 retained 行为 | LWT topic、retain/QoS/payload 与 P4 一致；异常断连后 Broker 状态语义一致 | 协议对照/测试日志 |
| H06 | QoS0 完整发送 | 波形 QoS0，无伪造 PUBACK；发送失败返回 0 并触发原 Router 失败逻辑 | Host 用例 |
| H07 | QoS1 正常 PUBACK | 匹配 packet ID 后 `gateway_mqtt_publish` 返回成功，Router 才 ack | Host 用例和时间序列 |
| H08 | QoS1 延迟/错号/丢失 ACK | 不提前成功，超时/错号走失败回存/重连；无无限等待 | Host 用例与失败状态 |
| H09 | 部分发送/短读取/零长度/负错误 | 不越界、不截断为有效消息、错误码正确传到调用者 | Adapter Host 用例 |
| H10 | `MQTT_ProcessLoop` 正常/半包/超时 | 空闲维持 keepalive；半包重试有界；未完成的接收不触发假成功 | Host 用例 |
| H11 | 意外 inbound `PUBLISH` | publish-only：不消费业务内容、不执行命令，连接按设计失败/重连 | Host 用例 |
| H12 | Router LIVE/REPLAY | 在普通 Host 测试中验证先 LIVE 后受控 REPLAY、序号/时间/来源不变 | `python gateway/canopen/build_host.py` 等 |
| H13 | Canonical 数据接口 | `mp_json()/mp_topic()` 与 P4 相同，RR `INVALID`，synthetic/source 语义正确 | `check_canonical.py` 及 JSON diff |
| H14 | Backend 兼容 | `python -m pytest cloud/backend/tests -q`（仅普通功能测试）通过 | pytest 结果与环境版本 |
| H15 | Flash/内存配置 | 应用不超 896KiB；RAM 总布局 <=128KiB；sector7 0x080E0000 原样；无无限堆增长 | map/size/linker 检查 |
| H16 | RAM/CPU/网络性能对照 | P4 vs P5 包括 `.text/.data/.bss`、heap/stack、buffer、CPU/单次协作延迟、重连耗时；填真实值，不允许“未知即通过” | `P5_资源对照与回滚记录_v1.0.md` |
| I01 | 隔离环境 Broker MQTT311 | QoS0/1、Will/retain、Client ID、心跳和断连完整闭环；不改生产 Broker | 隔离 Broker 测试报告 |
| B01 | F407 真机合成源 smoke（需测试窗口） | 当前 `CAN1 silent loopback` 的双合成节点经 TLS→Broker→Backend 送达 | 真机测试摘要与脱敏日志 |
| B02 | F407 真机断 Wi-Fi/恢复（需测试窗口） | Gateway OFFLINE/ONLINE 与 Router 回存/REPLAY 保持，消息来源仍标 `MOCK` | 带时间的状态转移摘要 |
| B03 | Broker 重启（需单独确认测试窗口） | 仅在允许影响项目 Broker 时执行，Broker 恢复后 Gateway 重连且缓存状态合理 | 操作窗口和恢复报告 |
| B04 | 上电/烧录/恢复（需测试窗口） | 原始 1MiB 双读一致、临时固件 verify、测试后原 Flash 全片恢复 verify；不动 BOOT0/Option Bytes | 备份哈希/烧录与恢复核验摘要 |

### 7.1 既有普通回归入口（只运行不含 Security Gate 的内容）

```bash
# ARM 编译（本机已装 ARM GNU/ST 标准库；构建命令不烧录）
python gateway/mqtt/build.py

# CANopen、Router 和序列化既有普通功能测试
python gateway/canopen/build_host.py
python gateway/canopen/tools/check_canonical.py
python -m pytest cloud/backend/tests -q

# 新建的 P5 固定普通功能测试（Codex 需实现）
python gateway/mqtt/tests/run_p5_host_tests.py
```

说明：Windows 环境下，现有 `gateway/canopen/build_host.py` 可在 WSL/Linux 中运行；不得因为本机缺工具链而自动改系统级包源或盲目安装。某命令因环境不可用时填 `BLOCKED`、保留错误并报告。**明确不得运行** `python gateway/canopen/run_security_regression.py`，该脚本使用 ASan/UBSan，属于本次单独授权范围之外的旧安全固定回归；同理不得触发统一 Security Gate 的自动或手动扫描。

### 7.2 对照数据和阈值

必须在**同一工具链/构建选项**下独立构建 P4（保存在构建目录之外的临时只读对照）和 P5，列出：固件 `.text/.data/.bss`、完整 RAM/预留堆栈、网络缓冲区与 coreMQTT QoS records、ELF/BIN SHA256、最大单次 MQTT 阻塞与 CAN 协作延迟、Broker 重连到首条有效帧时间。

- 不可把历史文件 `gateway/canopen/evidence/host/build.json` 的数字当作本轮重新构建结果；只能作为历史参照。
- 若 P5 链接越界、静态内存叠压 128KiB、配置 sector 冲突、资源测不到或出现采样/协作退化且无法解释，标记 `BLOCKED/FAIL` 并停止相关推进。
- 如 P5 **静态 RAM 比 P4 增加超过 2KiB**或 **重连耗时增加超过 20%**，要求生成差异分析并请负责人审核；这属于**项目评审触发阈值**，不是已测得的现状，也不允许 Codex 自行放宽。即使低于阈值仍须完整执行功能验证。
- 仪器/日志缺乏可信测量条件的 CPU/stack high-water mark，不得编造数值；可写 `NOT_MEASURED` 并使资源准出保持待审。

---

## 8. 真实硬件与网络服务的独立授权边界

P5 允许普通代码开发和非破坏性本地编译，不等于允许不经确认直接烧写开发板、修改证书区或重启线上 Broker。即使已连接板子，Codex 在以下事项**必须先获得负责人明确的本轮硬件测试窗口确认**：

- `J-Link` 临时烧录、片上 Flash 擦写或恢复。
- 向硬件 UART 输入 `D/A/B/C/R/G/E` 故障注入命令。
- 使用 `--ssh-alias` 启动/停止/重启项目云端 Broker（包括执行现有 `board_acceptance.py` 的关联路径）。
- ESP client_ca 写入、PKI 分区操作或证书更新（原则上 **P5 不应要求更改**）。

获准硬件测试后才按当前 `gateway/mqtt/README.md` 与 `gateway/canopen/tools/board_acceptance.py` 的规范执行：

1. 先确认仪器、供电、实物接线、UART3 PB10/PB11、USART1 调试串口和当前 BOOT0/启动情况。
2. 原始 1MiB Flash **双读哈希一致**，备份在仓库外；不开启任何自动刷写。
3. 用原 `provision.py` 注入仓库外私有配置（输出仍在仓库外），配置地址 `0x080E0000`；保持 TLS 完整证书/主机名校验。
4. 对已运行的 P2 固件使用工具支持的 `--quiesce` 正确退出 Wi-Fi，避免 ESP 残留未完成 CIPSEND。
5. 临时固件烧写必须 verify；按本合同 B01→B02→必要时 B03 的顺序验收，测试只使用合成源。
6. 测试结束完整恢复原始 Flash 及 sector7，回读/verify 一致；不能仅恢复 sector0，不能声称“J-Link 引导成功即上电自启成功”。
7. 在验收报告中明确 `physical_nodes=false`、`real_patient_data=false`；不将真实传感器/临床报警设为通过项。

若未获硬件窗口，应停在普通功能验证完成，标记 B01–B04 `NOT_RUN`；**允许产出 Draft PR，不得作出 P5 实物验收完成结论**。

---

## 9. 代码质量、变更约束与数据安全

- 所有变更用最小 diff；不做与迁移无关的美化、目录迁移、依赖全量升级或前后端重构。沿用现有代码排版和中文注释维护约定。
- 保持 `main.c` 的两个 CANopenNode 合成生产者、CAN1 静默 loopback、Router `mp_router_take/ack/online` 的调度；不改为真实三板模式。
- `AT+CWJAP` 密码等敏感命令不可入日志；不能输出原始 MQTT CONNECT 内容、token、payload 中的敏感字段。PR 描述只出现脱敏摘要。
- Host 测试模拟数据必须明示合成；必要的固定 broker 本地测试不得访问公共目标，更不能向真实医疗设备发送控制包。
- 第三方 MIT 许可证、上游信息、源码及固定哈希属于代码审计必须交付的普通**静态来源核验**，不等于安全扫描授权。
- 本合同允许**正常编译时的源码检查和常规 deterministic 单元测试**；不授权新增漏洞利用验证、模糊测试、动态扫描或安全工具门禁。
- 保持当前 `gateway_config_valid()` 配置有效性规则及 `sizeof(GatewayConfig)==312` 的断言，不以生产系统安全能力对外宣称；目前配置 Flash 是样机明文存储边界。

---

## 10. 交付物清单、状态与证据规范

Codex 最终须在 P5 分支交付：

**代码**：官方固定 coreMQTT vendor + MIT LICENSE + `upstream.json` + 离线 verifier；新的 Transport Adapter；修改后的 Gateway MQTT Client；`build.py` 唯一 active 白名单；真实 `.elf/.bin` 的本地路径和 SHA（产物不提交）。

**普通测试**：P5 固定 Host 功能套件；既有 CANopen/Router/Backend 普通回归的结果；可用环境下隔离 Broker 功能对照；全部测试编号的 PASS/FAIL/NOT_RUN/BLOCKED 明细及命令、时间、平台、commit。

**文档**：`doc/P/README.md` 的当前阶段导航；P5 迁移设计与模块映射；P5 功能验收报告；资源对照/回滚记录；证据索引（带实际相对路径、脱敏摘要、来源类型）；不改写 `90_维护/` 既有 P4 维护手册 v1.1 的历史版本及 `99_历史/`。

**仓库操作**：每次提交均需有可审核范围；完成后 push `P5-coremqtt-baremetal`，可开 Draft PR → `P4`，PR 必须标注 **`Security Gate: NOT AUTHORIZED/NOT_RUN`、`Hardware: NOT_RUN/PENDING`（如适用）、`NO AUTO MERGE`**。

建议证据索引字段：

```text
check_id | category | environment | command_or_procedure | started_at
commit_sha | result(PASS/FAIL/NOT_RUN/BLOCKED) | evidence_path
artifact_sha256(optional) | notes | requires_authorization
```

不允许的归档行为：编造测试日志、拷贝 P4 已通过结果填 P5 PASS、提交原始凭据/证书私钥、上传完整 Flash dump 到公共 GitHub、删除 Paho 历史、把 GitHub PR 的绿色构建状态等同于 Security Gate 已通过。

---

## 11. 阶段停止条件 / 回滚 / 合并门槛

### 11.1 任何一条触发 STOP 并报告

- `origin/P4` 和合同锁定 SHA 漂移，且尚未完成差异复核。
- 工作树含与本任务冲突的未提交内容；P5 分支已存在且状态未知。
- 第三方 tag/commit/hash/许可证不符，或下载路径需要不可信镜像。
- 构建失败、配置扇区发生漂移、RAM/Flash 越界、CAN 采样受明显阻塞。
- QoS1 在**没有正确 PUBACK** 时发生 Router 成功 ACK，或发生跨会话错号确认。
- publish-only、TLS 证书校验、Topic/Payload、REPLAY 语义变化。
- 需要修改 `gateway/canopen`、`data_model`、`storage`、`cloud` 或 A/B 节点代码才能继续。
- 需要未授权的 Security Gate、真机烧写、Broker 重启或修改生产云服务。

停止报告必须写：当前阶段、commit、触发项、实际证据、建议修复与是否涉及新授权。**只暂停受阻操作，不得丢弃已有安全工作。**

### 11.2 回滚方法

- **软件**：P4 原始 Paho Commit `8dee339491cfd4edc468bb9451511d421f26db5e` 始终保留不变；失败时不合并 P5，不修改 `origin/P4`。可在**独立只读 worktree** 重新构建 P4 固件以比对；不借 `git reset --hard` 擦除用户工作区。
- **固件**：只有硬件窗口授权后，才由已备份双读一致的原始 1MiB Flash 进行全片恢复和校验。特别覆盖最后配置 sector7；存储的备份文件须在仓库外。
- **网络/云端**：P5 原则上不改云服务；获准故障窗口里影响 Broker 的测试，在 `finally`/恢复步骤中确认服务复原并记录。
- **依赖**：Paho 仍在仓库内，并保持历史 patch/manifest/verifier；回滚构建由 P4 编译器、依赖及脚本决定，不需要把 coreMQTT 冒充 Paho 向后兼容。

### 11.3 区分四类状态，严禁提前宣布完成

| 状态 | 判断标准 | 是否允许合并 P4 |
|---|---|---|
| `P5_DEV_IN_PROGRESS` | 正在编码/单测，有失败或未执行项 | 否 |
| `P5_FUNCTIONAL_READY` | 固定 vendor、普通 Host/ARM/接口测试全部 PASS，资源对照已有；真机和 Gate 可能待执行 | 否；可以 Draft PR |
| `P5_PENDING_HARDWARE_AND/OR_SECURITY` | 功能已完成，但真机窗口或 Security Gate 未获得独立授权/尚未通过 | **否** |
| `P5_ACCEPTANCE_CANDIDATE` | 真机合同项（如要求）全部真实 PASS，Security Gate 已另行获授权并获得结果，其他无阻断 | **仍须项目负责人审查批准** |

**P5 分支合回 P4 的最终准出条件**：本人/项目负责人对 P5 PR 和真实证据作最终裁定；所有必须项完整，Security Gate 另行授权运行且没有新的 blocker，真机结果真实、资源可接受、仍 MQTT 3.1.1、没有改变 A/B CAN 数据合同。没有任何自动合并权。P6 分支只能在 **P5 正式合入后的最新 P4** 和 P6 独立合同签发后创建。

---

## 12. Codex 首次动作与汇报格式（可直接执行）

### 12.1 首次只读汇报（在写入前）

Codex 先完成第 1 节检查，并用以下格式返回：

```text
P5_PRECHECK
REPO_ROOT             = <真实路径>
CURRENT_BRANCH        = <真实分支>
WORKTREE              = CLEAN / DIRTY
LOCAL_HEAD            = <SHA>
REMOTE_P4_HEAD        = <SHA>
EXPECTED_P4_HEAD      = 8dee339491cfd4edc468bb9451511d421f26db5e
MAIN_HEAD             = <SHA>
EXISTING_P5_BRANCH    = YES / NO
LOCAL_DOC_DRIFT       = <具体未提交文件或 NONE>
TOOLCHAIN_READY       = YES / NO / PARTIAL
BASELINE_BUILD        = PASS / FAIL / BLOCKED / NOT_RUN
GO_NO_GO              = GO / STOP
RISKS_AND_BLOCKERS    = <事实清单>
```

如果是 `STOP`，**不能自行创建分支或修改代码**；先等负责人回复。若 `GO`，按第 6 节 P5-01 至 P5-08 依次完成软件部分；每个里程碑提交一次摘要，不跨阶段连续开发 P6。

### 12.2 最终汇报格式

```text
P5_FINAL_REPORT
BASELINE_P4_SHA       = ...
P5_BRANCH             = ...
P5_HEAD               = ...
COREMQTT_TAG/COMMIT   = v2.3.1 / 2beef04725328923e05e576b884212d53ec97af7
MQTT_WIRE_VERSION     = 3.1.1
ACTIVE_CLIENT         = coreMQTT / NOT_SWITCHED
BUILD_GATEWAY         = PASS / FAIL / NOT_RUN
HOST_TESTS            = <passed>/<planned>; failed=<...>; skipped=<...>
QOS1_PUBACK_EQUIV     = PASS / FAIL / NOT_RUN
CAN_ROUTER_EQUIV      = PASS / FAIL / NOT_RUN
BACKEND_EQUIV         = PASS / FAIL / NOT_RUN
HARDWARE_SMOKE        = PASS / FAIL / NOT_RUN（附窗口授权）
BROKER_FAULT_TEST     = PASS / FAIL / NOT_RUN（附窗口授权）
SECURITY_GATE         = NOT_AUTHORIZED / 另行授权后实际结果
RESOURCES             = <P4/P5 数值与证据>
ROLLBACK_READY        = YES / NO
EVIDENCE_INDEX        = <仓库内路径>
DRAFT_PR              = <真实 URL 或 NOT_CREATED>
MERGED_TO_P4          = NO
P6_STARTED            = NO
REMAINING_BLOCKERS    = <实际列表>
```

### 12.3 首次投喂 Codex 的简短指令

> 你现在获得 **P5 软件实施及普通功能验证** 的授权。请在仓库根目录读取 `doc/P/P5_coreMQTT裸机迁移正式执行合同_v1.0.md`，严格按其中第 0—12 节执行。首先只读核验 P4/HEAD/工作树/本地文档冲突，按 `P5_PRECHECK` 汇报；有任何 STOP 条件，先停下等我的决定。GO 后才允许创建 `P5-coremqtt-baremetal` 并进行 Paho→coreMQTT v2.3.1（MQTT 3.1.1）裸机迁移。保持 ESP AT/TLS、Broker/Topic/Payload、CANopen/Router、Backend/Web 和 Flash 配置不变；QoS1 必须收到匹配 PUBACK 才 ACK Router。允许普通编译与功能测试、P5 分支 commit/push、Draft PR→P4；**不允许** Security Gate、ASan/UBSan 安全固定回归、真机烧写/云端 Broker 故障操作（未经另行确认）、合并 P4、P6/FreeRTOS、MQTT5。最后提供真实日志摘要、文件变动、SHA、资源对照、测试矩阵及阻塞项；绝不伪造未运行的验收结果。

---

## 附录 A：核对来源（正式合同制订依据）

- 项目仓库与 P4 HEAD：<https://github.com/Serendipity-min/medical-multi-parameter-monitor/tree/P4>
- P4 Gateway 构建：<https://github.com/Serendipity-min/medical-multi-parameter-monitor/blob/P4/gateway/mqtt/build.py>
- P4 MQTT 客户端：<https://github.com/Serendipity-min/medical-multi-parameter-monitor/blob/P4/gateway/mqtt/src/gateway_transport.c>
- P4 UART/ESP AT 层：<https://github.com/Serendipity-min/medical-multi-parameter-monitor/blob/P4/gateway/mqtt/src/platform.c>
- P4 主循环：<https://github.com/Serendipity-min/medical-multi-parameter-monitor/blob/P4/gateway/mqtt/src/main.c>
- P4 硬件与备份说明：<https://github.com/Serendipity-min/medical-multi-parameter-monitor/blob/P4/gateway/mqtt/README.md>
- P 侧 README：<https://github.com/Serendipity-min/medical-multi-parameter-monitor/blob/P4/doc/P/README.md>
- 官方 coreMQTT v2.3.1：<https://github.com/FreeRTOS/coreMQTT/tree/v2.3.1>
- 官方 coreMQTT v2.3.1 API：<https://freertos.github.io/coreMQTT/v2.3.1/core__mqtt_8h.html>
- 本轮用户再次明确的授权边界：P5 与 A/B/三板 CAN 可并行；Security Gate 单独授权；P6 24h 阶段性测试；先发 v1.0 后启动 P5。其余按现有 P4 原始事实执行。

---

## 签发结语

**本 v1.0 正式执行合同已签发，仅针对 P5（裸机 + coreMQTT v2.3.1 + MQTT 3.1.1）的软件改造、普通测试、可回滚证据与 Draft PR。**

**P6 未签发；统一 Security Gate 未授权；真机破坏性操作/云端故障窗口待确认；P4 合并必须等待单独复核。**
