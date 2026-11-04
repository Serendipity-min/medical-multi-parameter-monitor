# FIVE-NODE-V2｜五板单模块架构迁移与非人体联调执行合同

**起点**　M0 标签 `baseline/abc-unified-pre-split-v1`，固定提交 `26e695ffda43a7a76aa54d1c4e3a5631ac0dc42e`。**交付目标**　4 块测量板各自配一套采集模块和一块屏，C 保持双 CAN、联网与语音。五台主控均按 STM32F407ZGT6 规划，具体底板跳帽、外设电平和恢复布局在对应板上核对。本次先下发合同。M1 的编译、回放与相关回归可在新窗口直接开始；上电、烧写和气泵操作由现场按实际板和当期范围执行。M1–M4 是待执行的迁移阶段；三场已通过的 M0 直接计入起点。[工程基线及恢复](https://github.com/Serendipity-min/medical-multi-parameter-monitor/blob/26e695ffda43a7a76aa54d1c4e3a5631ac0dc42e/node-b/docs/MPM-M0-ABC-BASELINE-CONTEXT-HANDOFF-20261103.md) · [实测与余量](https://github.com/Serendipity-min/medical-multi-parameter-monitor/blob/26e695ffda43a7a76aa54d1c4e3a5631ac0dc42e/node-b/docs/M0-ABC-BASELINE-20261103/FIVE-NODE-RESULTS.md)

## 1. 交付形态与唯一生产者

| 板 | 拟用 CANopen ID | 物理段 | 屏、测量或网关职责 | 五板配置下允许的监护流 |
|---|---:|---|---|---|
| A | 1 | A.CAN1 → C.CAN1 | 血氧组件、原血氧屏 | SPO2、PR、PPG |
| B | 2 | B.CAN1 → C.CAN2 | ADS1292 系列 ECG/RESP 组件、原 HR/RR 屏 | ECG、HR、RESP、RR |
| C | 3，各独立网段沿用 | 两路 | 双 CAN 汇聚、INMP441、ESP、TW-TTS、喇叭 | 网关状态、遥测和语音上/下行 |
| D | 4 | D.CAN1 → C.CAN2 | 从 B 移来的 GY641 和独立温度屏 | TEMP，标注“物体温度 To”，℃ |
| E | 5 | E.CAN1 → C.CAN1 | 从 A 移来的 HKB-08B+、本地血压屏、原非人体气路与启停控制 | NIBP，收缩压/舒张压，mmHg |

四块测量板各自另发节点状态。在此方案下，A/B 是主干上的普通节点；D/E 独立向 C 发布。一个物理插座可通过无源接点接入多个 CAN 收发器。两段都维持 M0 的 500 kbit/s。传感器、本地屏、收发器与所属 MCU 尽量就近，增加距离放在 CAN 双绞主干上。

## 2. 现场分线、端接与断电判读

接手回执记录的 41 Ω 组合是 C.CAN1＋B.CAN1＋E.CAN1。仓库底板参考图的 CAN1/R7、CAN2/R1 均为固定 120 Ω，P6/P4 不控制端接。新的首选摆位保留 C/A、C/B 为两段端点，E/D 以无终端接口在各段中部接入。端点实际位置随现场线型确定。按[固定终端接线图与执行合同](06-CAN-Wiring-and-M1-Contract.md)逐板断电测量，并按实物核验是否可用 P6 免焊引出。三只固定端口直接并线时外加电阻为 0。

## 3. M1 在原固件基础上完成离线迁移

### M1 离线实施清单（基线源码锚点）

下表均依据 `26e695f`。五板拟用 A=1、B=2、C=3、D=4、E=5；先以实际启用的收发帧和对象字典验证编号，再固化配置。保留两个静态配置，三板用于复现 M0，五板用于迁移。各自构建输出清楚标注节点，保留五个目标的 ELF/map/可烧录制品；无需引入运行时注册平台。

| 改动面 | 复用和修改范围 | 验收抓手 |
|---|---|---|
| A → E 血压模块与屏 | A 构建入口 `node-a/tests/build_keil.py` 调用 `node-a/STM32F407_HOSPITAL/USER/STM32F407_Template.uvprojx`；主循环将两类采集与屏组合。E 从 `HARDWARE/app_bp.c`、`bp_sensor.c`、`hmi_dacai.c`、相应中断及 CAN 适配取出血压链。沿用血压屏 USART3（PB10/PB11，9600，经 SP3232 至 RS232）与 HKB-08B+ 的 UART5（PC12/PD2，115200，TTL），在 E 上核实实际收发器与线序。A 保留原血氧屏/采集。 | E 屏手动开始、停止、错误、完成与历史显示；E 不发布血氧。A 在五板配置不再初始化泵或产生有效血压。血压完成 tick、同值身份镜像、代次与 90 s 语义均从原 CAN 适配移植。 [A 构建](https://github.com/Serendipity-min/medical-multi-parameter-monitor/blob/26e695ffda43a7a76aa54d1c4e3a5631ac0dc42e/node-a/tests/build_keil.py) · [本地状态机及串口](https://github.com/Serendipity-min/medical-multi-parameter-monitor/blob/26e695ffda43a7a76aa54d1c4e3a5631ac0dc42e/node-a/STM32F407_HOSPITAL/HARDWARE/app_bp.c) · [血压 CAN 适配](https://github.com/Serendipity-min/medical-multi-parameter-monitor/blob/26e695ffda43a7a76aa54d1c4e3a5631ac0dc42e/node-a/STM32F407_HOSPITAL/HARDWARE/CANopen/canopen_app.c) |
| B → D 温度模块与屏 | B 当前 CAN/温度构建入口为 `node-b/tools/build_b4_arm.py`（含 `--temp --candidate-r6 --temp-screen` 的组合）；同目录普通 `build_arm.py` 只是早期 BIO_V2 路径。D 复用 `gy641.c`、`b_temperature.c`、`b_temp_screen.c` 及已有屏驱动的发送入口。传感器 TD→PC11/UART4 RX 9600，PC10 保持输入，不写模块寄存器；独立屏协议沿原接口，现固件使用 USART3 PB10 TX 115200。 | D 本地和 D 的 PDO 取同一 `BTemp_Get` 结果。有效时每秒更新物体温度，无效显示 `--.-`。不把 B 的 HR/RR 屏、ECG 前端或 DSP 依赖复制到 D。B 仅保留 ECG/RESP/HR/RR 与原屏。 [B 构建](https://github.com/Serendipity-min/medical-multi-parameter-monitor/blob/26e695ffda43a7a76aa54d1c4e3a5631ac0dc42e/node-b/tools/build_b4_arm.py) · [温度 UART](https://github.com/Serendipity-min/medical-multi-parameter-monitor/blob/26e695ffda43a7a76aa54d1c4e3a5631ac0dc42e/node-b/temperature/b_temperature.c) · [温度屏](https://github.com/Serendipity-min/medical-multi-parameter-monitor/blob/26e695ffda43a7a76aa54d1c4e3a5631ac0dc42e/node-b/temperature/b_temp_screen.c) · [温度原 PDO](https://github.com/Serendipity-min/medical-multi-parameter-monitor/blob/26e695ffda43a7a76aa54d1c4e3a5631ac0dc42e/node-b/canopen/b_canopen_app.c) |
| C 的 CANopen 与逐节点状态 | `mp_od.c` 当前每实例含 10 个 RPDO，硬编码两套远端镜像（0x3100/0x3200）、0x1016 心跳消费者 1/2、SDO client 目标 1。两物理段各保留一套现有协议栈，按段传入远端节点列表（1/5、2/4），把本段两个成员映射到两个现有槽。检查应用层、bxCAN 接收滤波、消费者心跳、定向 NMT/SDO 与 TIME 广播职责。 `b4_gateway.c/.h` 的 `remote=bus+1`、每段单份 `seen_at/generation/online/nibp_tick` 改为按 (段、节点) 查找，保留原到达时刻和每帧 RPDO 处理。波形缓存仅为 A/B 已有流分配。 | 按角色只启用必需 PDO。网段 1 承载 A 波形与 E 血压，网段 2 承载 B 波形与 D 温度。枚举每条总线所有生产者 COB-ID，含 heartbeat/EMCY、SDO 的请求及响应、时间与 NMT，确认共享广播有单一发送职责；其它节点、错误网段与不属于该角色的通道明确丢弃并计数。 [网关对象字典](https://github.com/Serendipity-min/medical-multi-parameter-monitor/blob/26e695ffda43a7a76aa54d1c4e3a5631ac0dc42e/gateway/canopen/src/mp_od.c) · [收发、时间与有效性](https://github.com/Serendipity-min/medical-multi-parameter-monitor/blob/26e695ffda43a7a76aa54d1c4e3a5631ac0dc42e/gateway/dual_can/b4_gateway.c) · [当前状态占用](https://github.com/Serendipity-min/medical-multi-parameter-monitor/blob/26e695ffda43a7a76aa54d1c4e3a5631ac0dc42e/gateway/dual_can/b4_gateway.h) |
| 本地队列 → MQTT → WSS → 页面 | `gateway/data_model/model.c` 按“1 是 A、其余是 B”拼 topic。 `gateway/storage/router.c` 的温度诊断和某些实时 FIFO 仅对 Node 2 生效。更新为明确角色与有效来源，保留实时/补送标志以及 A 缓存覆盖指标。Backend `models.py` 限制 A/B 与 CHANNELS；`adapters.py` 验 topic 与载荷，`hub.py` 据 CHANNELS 生成逐节点快照与失效。网页 `viewModel.ts` 仅输出 A/B 节点状态，`ui/parameters.ts` 的温度参数还写着 I²C/额温，这与已验收 UART4 的 GY641 物体温度冲突。 | MQTT、WSS、网页状态与显示同一个生产者和会话，D/E 各自在线、失联和复接。修正温度标签、接口，以及血压来源和模块名。用真实浏览器看节点状态栏、参数详情、趋势及来源标注，验证回放流不刷新实时值。 [MQTT](https://github.com/Serendipity-min/medical-multi-parameter-monitor/blob/26e695ffda43a7a76aa54d1c4e3a5631ac0dc42e/gateway/data_model/model.c) · [缓存与温度诊断](https://github.com/Serendipity-min/medical-multi-parameter-monitor/blob/26e695ffda43a7a76aa54d1c4e3a5631ac0dc42e/gateway/storage/router.c) · [Backend](https://github.com/Serendipity-min/medical-multi-parameter-monitor/blob/26e695ffda43a7a76aa54d1c4e3a5631ac0dc42e/cloud/backend/app/models.py) · [快照](https://github.com/Serendipity-min/medical-multi-parameter-monitor/blob/26e695ffda43a7a76aa54d1c4e3a5631ac0dc42e/cloud/backend/app/hub.py) · [网页节点状态](https://github.com/Serendipity-min/medical-multi-parameter-monitor/blob/26e695ffda43a7a76aa54d1c4e3a5631ac0dc42e/cloud/web/src/model/viewModel.ts) · [参数页静态文案](https://github.com/Serendipity-min/medical-multi-parameter-monitor/blob/26e695ffda43a7a76aa54d1c4e3a5631ac0dc42e/cloud/web/src/ui/parameters.ts) |
| ASR → 测量问答 → TW-TTS | `cloud/microphone/worker.py` 实际调用 `provider.explain(question, [], [])`。`ai_reference/providers.py` 主动限制数字和高低判断。复用协议、回包、TTS 和原短回复；在 worker 的读数问答入口单独接只读 `cloud/ai/snapshot.py` 的 MONITOR 模式，按新来源更新 `facts.py`。读数由确定性模板从合格快照取 SYS/DIA、单位、测量时间，时间源用完成时刻；模型可识别提问或生成既有一般性解释。 | LIVE、非 synthetic、E 与网关在线、测量有效、同一会话且未过期才播当前读数；缺失、无效和过期播“暂无有效血压”。如已配置台架演示上下限及边界包含规则，由服务端比较收缩压，明确播“按台架配置范围……”，保留规则版本；无规则时只报数并提示未配置。任何提问都不能发起泵控。 [语音 worker](https://github.com/Serendipity-min/medical-multi-parameter-monitor/blob/26e695ffda43a7a76aa54d1c4e3a5631ac0dc42e/cloud/microphone/worker.py) · [当前模型输入与输出约束](https://github.com/Serendipity-min/medical-multi-parameter-monitor/blob/26e695ffda43a7a76aa54d1c4e3a5631ac0dc42e/cloud/microphone/ai_reference/providers.py) · [快照](https://github.com/Serendipity-min/medical-multi-parameter-monitor/blob/26e695ffda43a7a76aa54d1c4e3a5631ac0dc42e/cloud/ai/snapshot.py) · [事实验证](https://github.com/Serendipity-min/medical-multi-parameter-monitor/blob/26e695ffda43a7a76aa54d1c4e3a5631ac0dc42e/cloud/ai/facts.py) |

**PDO 先形成一张可核对的映射表。** M0 的五个 TPDO 基址依次为 0x180/0x280/0x380/0x480/0x680，均加节点 ID。以下将原 PDO 载荷迁入新节点，不要求每节点实际发送全部五种。确认沿用既有布局时，E 可取 0x285（0x2111 完成 tick 与打包 SYS/DIA）、0x385（0x2120 标量）、0x485（0x2100 时间）、0x685（0x2130 质量/启动代次），D 可取 0x384/0x484/0x684（对应标量、时间、质量）；D 的 0x2120 保留字传原始温度帧龄。心跳分别 0x704/0x705。上述是**拟分配值**，沿用协议而改变源 ID 后，实测包必须与对象字典、接收滤波器逐项一致；按角色没有数据的槽禁止产生有效数值。E 的 0x285 不得按 B 的第二路波形解码。D 的帧龄用于取消过期资格，M0 的 TEMP UTC 用的是报告锚，不能把它写成精确测温时刻。[对象与标识符](https://github.com/Serendipity-min/medical-multi-parameter-monitor/blob/26e695ffda43a7a76aa54d1c4e3a5631ac0dc42e/gateway/canopen/src/mp_od.c) · [时龄和血压对照](https://github.com/Serendipity-min/medical-multi-parameter-monitor/blob/26e695ffda43a7a76aa54d1c4e3a5631ac0dc42e/gateway/dual_can/b4_gateway.c)

**Host 只需定向验证以下反例**。沿用真解析、队列和快照函数，模拟物理端口。每行至少有一个成功对照，拒绝路径记录源及原因。

| 输入 | 五板配置预期 |
|---|---|
| D 的 PDO 到 C.CAN1、E 到 C.CAN2；A 再发有效 NIBP、B 再发有效 TEMP；配置中同一总线重复占用发送 ID | 错段、错角色及重复发送身份分别被拒；不得借相邻节点心跳获得有效状态。相同 CAN ID 在同段无法靠报文认证发送者，重复发送身份应在静态配置和每板独测时发现。 |
| D 缺采样、断开或重启；B 在同一段继续传 ECG；D 旧 boot 的延迟帧赶在 D 恢复后到达 | D 温度失效且恢复须有新会话新数据；B 保持在线。温度帧龄超 2500 ms、损坏/丢失串口帧或时间锚缺失不产生有效温度。 |
| 两次完成压力一样但 completion tick 不同；重复发送同一完成；过期后重发旧值 | 两次合法完成各入一次；相同完成不能续 90 s；被新代次取代的旧值不复活；重放不更新当前值。 |
| 输入历史补送、MOCK、过期、其他节点或相互冲突的数据；分别在配置边界的下方、边界、上方提问 | 非 LIVE 等输入不给当前读数或分类；合法值按约定边界一致分档。检查 TTS 实发文本与网页当前值一致、泵命令数始终为 0。 |
| B 波形、D 温度和 E 完成同窗到达；叠加 M0 同类语音上行/重连；同一节点启动代次改变 | 不跨节点合并缓存、不填造补帧；检查每来源计数与时间戳、C 队列高水位/覆盖、ELF/map 与内存余量。Host 结果用于筛查，真实五板和喇叭结果由 M4 给出。 |

M1 提交包含两段的静态节点/COB-ID 表、五个构建目标和对应链接布局、Host 正反例摘要、从 M0 到五板候选的资源差异。候选超出实装 flash 分区或普通 SRAM/CCM 预算时，先缩小改动或调整缓冲分配并重新看 map。05 已按制品勘误，M0 的 Flash 合计为 54,900 B，sector4 空余 11,028 B、预留堆栈后普通 SRAM 空余 15,808 B、CCM 空余 1,536 B。不要复制四套完整网关或为 D/E 分配无用途的波形缓存。分发给现场的是每块板的独立候选及安装说明；在计划中列出板号、应用起点、实际覆盖扇区和恢复来源。

## 4. 实板实施次序

下次收到开始现场联调的当期指令后，按已核实的板与写入范围成批执行。M0 原 C 的 sector0/4 范围不能转用于 A/B/D/E 或新的扇区。范围内的普通修复与定向复测连续进行；出现电气异常、目标身份不清或需扩大写入范围时再停目标。

| 阶段 | 现场动作 | 通过时应看到什么 | 失败后最小回退 |
|---|---|---|---|
| M2　先迁温度 | 核实 D 的底板、现有镜像/恢复能力、原模块电平。断电标记并移接 B 的 GY641 和温度屏。先 D 本地，再 B/D/C 同段，启动各自静态身份。五板配置由 B 释放 TEMP。远端线缆用最终长度做一次检查 | 同一采样在 D 屏、D PDO、C、隔离 Backend 和网页一致，允许量化/显示舍入。用两个不同温度的非人体物体检查随源变化。传感器断开/陈旧显示无效；D 离线时 B 仍在线且波形正常，D 恢复后需有新样本 | 回到短线验证；本地不对先查 UART 与屏。若需恢复三板，断电将模块和屏放回 B，恢复 B41516、对应 C 及三板服务配置 |
| M3　再迁血压 | 核对 E 目标、写入范围和血压屏所用电平转换器。断电标记并移接模块、屏和原气路。E 本地验证后接 A/E/C 同段，A 释放 NIBP。现场人员使用现场确认限压和泄压方式的非人体工装启动与停止，异常先停泵泄压 | 同一真实新完成代次有 SYS/DIA、完成 tick/时间，E 屏、E PDO、C、网页一致；90 s 后失效。A 的 SpO₂/PR/PPG 仍来自 A。测量中、失败以及新值替代旧值状态清楚，旧帧不续时。危险状态或罕见边界优先用故障输入回放验证 | 本地控制异常先停泵、断电，查屏交互、TTL/RS232 和原状态机。必要时模块和屏回 A，恢复 A42608 及对应配置 |
| M4　五板同窗 | A/B/C/D/E 同时工作，使用真实波形源、两段最终线束、隔离 MQTT/Backend/网页/语音服务。复用 M0 编排，替换采集对象和来源映射 | 满足下节窗口表、五个配套应用镜像及服务版本映射。旧三板和五板都能由交接页定位各自恢复入口 | 定位到单段、单节点、C 发送、云端或工具，修后重跑受影响窗口。若整体回退，A/B 原模块和屏归位、恢复对应应用与三板配置，C 依清单恢复，重建原双点对点终端 |

M2/M3 介于两种架构之间时，只评价已迁移的那条总线及其启用流。其他尚待迁移通道标成缺席，避免把三板地址伪装成五板来源。断线测试保持主干和两端终端连续；若终端在供电板内且其行为不确定，用断电配置试验或独立线端终端核实。只把采样模块或节点下线所导致的失效归给该源。

## 5. 五板窗口与“当前血压”验收

| 工况 | 操作与可复核结果 |
|---|---|
| 五板 ECG60 工程窗口 | 同时在线，沿用 45 s 预热、300 s 评价；B 按 ECG60 判 HR 与 ECG 顺序，RESP 原样传输。A 屏与 A 流、D 温度屏与源、E 血压完成事件与网页分别对应。记录总线错误/溢出、每流计数和样本序号、源龄、Backend/WSS 消息与实际页面。语音同窗运行 |
| 五板 RR18 工程窗口 | 断电切换到 M0 已记录的 RR18 导联和模拟器菜单，沿用同一预热和窗口；按原 RR/RESP 判据。HR 按 B 源有效性。允许把不同问答场景分配到两个有效窗，排除不相干的重复采集。保留失败退出及原始索引 |
| 真实读数与过期拒答 | 合格非人体工况下，由现场人员在 E 屏手动测完一次，记该次完成代次，再提问“刚测的高压是多少”。按 E 屏与源、话筒/ASR 实际问句、服务端取事实时刻、下行回包、TTS ACK/DONE、实际可闻文本逐项核对。再测一条过期/无有效结果的询问，网页与喇叭均不得把旧数字当作当前读数。未接 E、恢复后仅有旧包、历史补传、MOCK 的分支用定向回放覆盖 |
| 高低解释 | “高压”映射到收缩压 SYS。若负责人采用了明确的非人体演示范围，记录范围/适用模式、上下界包含关系与版本；服务端用同一规则解释低于、位于或高于该范围。用边界样本检验各类，再用一条合格实测结果核对喇叭。规则尚未冻结时可直接报有效数字，并回答“当前没有可用的判定规则”；将分类功能记为待完成。原 A 屏已有自己的分档，移植前对齐 E 屏/网页/语音所称的规则与模式，避免两屏同值异义 |
| 双网段互不冒名与恢复 | 在分段阶段覆盖 D/E 各一次缺席与重新加入；M4 查两段并发时错段/错源和波形错配为 0。记录每段 TEC/REC、bus-off、FIFO 溢出及差值；出现新错要能解释并复测。失败的 ACK 或被页面拒绝的包不能计入端到端交付 |
| 语音和资源 | 保持 M0 的 2 s / 16 kHz / 125 块 / 64,000 B，在对应窗口核对 C 原始 PCM、完整重组、ASR 输出、真实 AI 路径、回包和可闻结果。记录 240 s 装配预算与 300 s 整轮的实际余量、医疗时效、A 合并/历史覆盖及 STOP。实时队列溢出、过期丢弃、后台拒绝/丢弃按原因和链路分列；沿用 M0 有效窗口的零新增异常要求，专门设计的错源/离线负例单列。沿用原波形速率及序号判据 |
| 使用稳定性与交付 | 实际长线/泵工作时的波形和语音要覆盖。M4 短窗通过即可封存五板工程候选；连续问答与 24h soak 分项标注。若按项目计划做预发布 24h 长测，记录运行时长/断线重连/队列趋势/重录/错误和恢复，再签长期稳定性结论。正式部署时单独记录各组件实际版本与网页构建 |

**时间边界会直接影响演示能否成功。** M0 的 ABC ECG60 一窗，从首块到末块上传用了 234.463 s，TTS 报告完成时刻为评价开始后 293.093 s。NIBP 的 90 s 有效期从 E 的测量完成时刻计算，不会因用户开始说话而暂停。两种时钟的零点不同，因此要在五板实测同一代次的测完、提问、选取事实、开始播放和结束时刻。生成当前值回复时确认有效；到 C 开始播放时再核对截止时间/代次，重连重投或排队过期就改播失效提示。无可靠时间或新代次已取代该值时，也不能播作最新结果。先以正常“测完再问”取得一条仍有效的可闻回复；靠问完再测一笔、重置完成时间或放宽 90 s 得到的结果不能替代这条正例。若只能正确拒答，则记录“失效处理通过、当前值播报未通过”。

定位慢点时先看 MIC 起止、块发送、PUBACK、重组完成、ASR/模型耗时、回包入队和播放。优先复用现有设备侧 3 遥测 + 1 音频在途槽，在遥测有明确余量时优化音频取槽时机或批次；先做原始日志回放，验证医疗流仍在原时效内，再做受影响实板窗口。不能仅提高装配超时，也不靠停传 B 波形、重复刷新 NIBP 或吞掉 A 历史覆盖计数换取通过。若需现场展示持续对话，将逐轮延迟与重复播放情况另列。

**下行协议只做一次与时效有关的扩展。** 旧 `MR01` 只绑定录音 session、audio CRC 和 1–60 字节的 UTF-8 文本。C 核对音频会话后直接提交 TTS，现格式缺少 E 的血压完成身份。普通工程短答沿用 MR01；五板测量答复建议加一个版本化的定长小头（如 MR02），继承录音身份，另带生产节点、启动/测量完成代次、完成时间或可信截止时刻。C 结合自己从 E 收到的当前代次、在线状态与时间锚，在 TTS 实际提交前核对。若下游另有排队，清理已过期条目或在启动播放前再次判断。错配、无时间锚、旧包重投时只允许失效提示。沿用文本上限先做 60/61 字节和中文多字节边界，超限改用完整短模板，不能截去舒张压或单位；覆盖合法旧短答、新测量答复、失效和重复播放。同步更新 worker 打包、C 解析及小型回放，不需更换音频块协议。[MR01 编码](https://github.com/Serendipity-min/medical-multi-parameter-monitor/blob/26e695ffda43a7a76aa54d1c4e3a5631ac0dc42e/cloud/microphone/protocol.py) · [C 接收和 TTS 提交](https://github.com/Serendipity-min/medical-multi-parameter-monitor/blob/26e695ffda43a7a76aa54d1c4e3a5631ac0dc42e/gateway/microphone/unified_audio.c)

**演示事实与规则来源。** 血压只使用 E 的已完成代次，体温页使用 D 的物体温度。把台架数据、MOCK/REPLAY 和成人家庭测量教学场景标清。服务端负责数值、单位和已冻结的范围，AI 负责理解提问或生成既有一般解释，模型故障仍可播可信读数或有效性提示。记录真实 AI 是否被调用，回退模板不能记为模型成功。模型及浏览器均不发泵控命令。项目已有[成年人家庭测量教学规则草案](https://github.com/Serendipity-min/medical-multi-parameter-monitor/blob/26e695ffda43a7a76aa54d1c4e3a5631ac0dc42e/node-b/docs/FINAL-SYSTEM-20261102/P2-RULE-DESIGN-DRAFT.md)，尚未冻结的低值/正常类别保持未启用。

## 6. 恢复、交付和合并

1. **实板前保留对应恢复点。** A/B/C 复用 M0 清单与已有受限备份，负责人已确认 D/E 原程序无需备份。首次使用前核对 D/E 实板身份、接口电平与该板适用的写入范围；逐板列出拟写扇区。C 的既有布局为 sector0 引导、sector4 代码，不能把两段拼成连续 BIN 烧写。A/B/D/E 使用各自的地址和电平接法。转接 J-Link、CAN、模块或气路前确认实际断电。异常泵压先停泵泄压；板卡身份不符、ROM/HALT、读回异常先停目标，离线定位仍可继续。[M0 恢复入口](https://github.com/Serendipity-min/medical-multi-parameter-monitor/blob/26e695ffda43a7a76aa54d1c4e3a5631ac0dc42e/node-b/docs/M0-ABC-BASELINE-20261103/RESTORE-ENTRY.md)
2. **阶段末交付一套可配对材料。** 每板名、Node-ID、固件版本、适用底板、ELF/AXF/map 与可安装文件、写入地址/扇区、恢复步骤；C 保留分段形式。再附两段线束和实测阻值、节点/PDO/主题对应表、隔离云服务和 Web 的部署版本、一页窗口结果和仍未关闭的问题。本地受限材料通过已有指针查找。每一小步不另设签发卡、签名或跑全量旧矩阵。
3. **区分工程通过与发布。** 五板候选可以分别标记“测量传输通过”“有效事实读数播报通过”“分类待冻结”“长稳待测”等状态。出现源错配、过期仍报当前、断一板牵连无关源、泵本地停不下、C 吞吐破坏医疗时效或不可恢复镜像时，对应必需项不能通过。批准的正式规则和部署前提要和最终用途一致。
4. **合并安排。** M4 满足约定范围且五板制品可回退后，集中审阅迁移分支与 main 的累计差异及发布清单，保留 M0 标签，按负责人最终决定合入 main。本轮交付规划；合并前以实际证据更新合同结果列。远端历史分支删名另见[新窗口交接与 36 分支清单](03-Next-Window-and-Branches.md)。
