# 三板接口上下文（M0离线，未进行T0集成或现场测试）

代码审查基线为 `6669a855662f0655fc7d7b6fc4c9a45ee1ef13b0`。以下是已读路径的结构/假设记录，不是硬件准入、性能证明或安全扫描。关键文件 SHA、读到的候选提交及既有二进制登记见 `tri-interface-sources.json`。没有构建、运行测试、打开SDK/COM、连接云或修改其它工作树。

## 入口、依赖和能力差异

| 对象 | 已读代码及建立的约束 | 未建立的事实 |
|---|---|---|
| A候选 | 独立A工作树HEAD `3fa14b00a0823d2855e9dd8bd1c6c8545abb8dc5`；`node-a/STM32F407_HOSPITAL/HARDWARE/CANopen/canopen_app.h:28` Node-ID=1、`:35` 500kbps；`canopen_app.c:38` CAN1；`:67` 获取测量/时钟一致快照；`:77` 血压仅空闲且90s内；`:124` 通信复位与应用复位分开 | 当天实际A固件/BIN、跳线、电源、终端、传感器和NIBP授权均UNKNOWN；A源码HEAD不等于已烧录身份 |
| B候选 | `node-b/canopen/b_canopen_app.h:4` Node-ID=2；`b_canopen_app.c:16` CAN1，`:45` 500kbps；`:66` 原序号连续性计数；`:76` 每5个真实点抽取RESP，250/50Hz不插值；`:99` 温度资格；`:109` 本通道波形资格；`:123` 过旧/错误样本拒发 | 最近安装B41012B仅为历史实板回执，当前物理身份不重测。CH2 QRS源真值UNKNOWN，质量位不能由C抹去 |
| 通用双CAN C模型 | `gateway/dual_can/b4_gateway.c:18` 两个独立Node3 OD/端口，`:24` 各端只消费本段节点；`b4_bus.c:40` 独立预算；`:52` 只接受500kbps、Node1..3、bus0..1；不桥接CAN帧 | 两路同时在线的实板证明：nothing found；B4软件候选不自动成为C49132能力 |
| **B5/C49132范围** | `gateway/dual_can/build_arm.py:54` B5目标定义 `MP_B5_CLOUD_CANDIDATE`；`b4_resources.h:12` 只允许bus1；`b4_bxcan.c:69` CAN1 Silent，`:86` A过滤器关闭，`:94` A中断关闭；`gateway/b5/network_main.c:190` A link=false，`:207` 只向Node2发NMT；历史C49132记录亦为B-only | 本轮所读源码与C49132全部91项原构建输入逐字节对应尚未重新证明，不能称当前源码即实装完整源码。无论驱动含双CAN，都没有A+B现场准入；启用A需新集成候选、资源/回退审查和Flash许可 |
| 引脚/共享资源 | `b4_bxcan.c:53` 同时开CAN1/CAN2时钟；`:59` CAN1 PA11/12 AF9；`:61` CAN2 PB12/13 AF9；`:77` 一次设置共享过滤器，CAN2SB14；`b4_resources.h:4` I2S2 PB12/PB13冲突编译拒绝 | 板卡版本、收发器、P4跳线/终端、实际PB12/PB13占用UNKNOWN。代码互斥不认证物理布线；不能在运行中单独复位CAN1或重分过滤器 |
| P5/P6/语音 | 只登记读到的独立提交：P5最终审查47e59a6、P6文本TTS77dd14d、B4双总线ffa440b；没有合并 | 不宣称P5/P6/P4保护或语音能力已包含进R6。PB10亦可能被ESP USART3占用，替代引脚/音频另审 |

## PDO / OD / 单位契约

`gateway/canopen/src/mp_od.c:48` 定义五路基址180/280/380/480/680，`:93` 为A/B各建五路、C十路镜像。B静态OD `node-b/canopen/OD.c:117` 起的映射与此对应；A的OD源码单独冻结，不能仅由同名字段断言物理一致。

| 通道 | B(Node2) / A(Node1)对应 | C消费与限制 |
|---|---|---|
| PDO1 0x182 / 0x181 | B ECG int32 µV+原tick；A PPG相对量+tick | `b4_gateway.c:95` 时戳/质量资格，`:117` 节点和流分开；B ECG250Hz、100点批，A PPG50Hz、50点批 |
| PDO2 0x282 / 0x281 | B RESP相对量×1e6+tick；A NIBP完成tick+同值SYS/DIA身份 | `b4_gateway.c:92` 不把A PDO2当波形；`:145` 单独校验NIBP完成、90s时效及新结果身份 |
| PDO3 0x382 / 0x381 | B HR×100/RR×100/TEMP×100/temp_age；A SpO2×100/PR×100/SYS×10/DIA×10 | `b4_gateway.c:130` B三标量、A两标量；`:134` 不改变上游valid；`:136` TEMP age只撤销过旧值，不冒充精确测温UTC |
| PDO4 0x482 / 0x481 | UTC秒+对应本地tick | `b4_gateway.c:70` TIME30s资格、PDO1.5s新鲜、锚差±2s，另限接收到的UTC时间域 |
| PDO5 0x682 / 0x681 | 质量位+启动代次，bit31合成源 | `b4_gateway.c:184` 非零新代次使旧缓冲失效；`:80` B5出口强制MOCK来源，保留有效位与原采样时间 |

`gateway/data_model/model.c:11`/`:13` 集中单位和缩放：ECG µV→mV，RESP相对量、HR/RR/温度/SpO2/PR按100，NIBP按10；`:61` 仅在序列化边界选择LIVE/MOCK/REPLAY，不改原时间/seq。名义2.42V及gain4换算不是绝对电压校准，RESP不代表Ω。`model.h:35` 记录批次末点时间，`:38` 按节点/流seq及epoch/boot，100点和默认250点ABI不能混链（`b4_resources.h:18`）。

## 核心调用链与未强制假设

### `b4_gateway_receive`（b4_gateway.c:161）

输入是半可信CAN帧与驱动到达tick。先拒绝非法bus/DLC/ID/未来时标，再按物理入口拒绝另一节点PDO/HB/SDO/EMCY（`:163`）；按质量PDO的新代次清缓存，真实 `CO_process_RPDO` 在每帧后立即消费，防止CANopen单槽覆盖（`:190`）。波形/标量通过 `fresh`、`sample_utc`、在线HB和质量位生成MpFrame。输入指针/driver时间域来自已初始化驱动，实际晶振、接线、总线负载由代码不能建立，物理保证：nothing found。

### `waveform` → `emit`（b4_gateway.c:90 / :78）

3/4/5ms整数时戳允许单步及批内±1ms相位，8ms真缺点、倒序或重复清批（`:105`），不造插值。valid/source切换亦清半批，避免混资格数据。`emit` 按流递增seq，缺UTC仅计数、不改成发送时刻（`:85`）。B5宏覆盖synthetic/session语义，不能用于声称真实LIVE来源；实际双节点峰值负载未运行。

### Router → Backend → UI

`gateway/storage/router.c:14` 状态不进历史；`:34` 离线迁缓存且重连先发实时；`:54` 同节点/流有界队列，B5 Node2遥测特殊FIFO（`:80`），满队列有计数替换/丢弃，非无限无损；`:153` REPLAY只改副本。这个B优先策略在A+B流量下的公平性尚未本轮验证。

`cloud/backend/app/hub.py:24` 入口按已配置gateway/未来时间检查，`:30` REPLAY独立不续活实时，`:36` gateway/node/stream键，`:56` 同会话seq去重和时间不回退；`:58` gateway会话变更失效旧代次，`:103` 节点session对齐避免旧状态续活；`:111` 5s普通/90s血压时效，`:115` 无效输出null/空波形；`:136` 慢订阅者只保留最新快照。没有启动Backend/MQTT/WSS，没有核对当期部署/ACL/TLS租期，生产一致性UNKNOWN。

### STOP与原生边界

`gateway/b5/network_main.c:32` 硬停回调及`:65` Router离线/`b4_hw_stop`；`:197` 必须完整B5START且有效配置才武装。`gateway/dual_can/b4_bxcan.c:145` 取消待发请求/关协议与中断；这些代码保证不等于验证实板SDK Close之后仍运行。旧B5 scope为B-only、单START、420s；三板10分钟不能直接复用它。固件更新/回滚/SDK重新连接/云服务租期各需新授权。

## 已有纯Host候选入口（本审查未执行）

| 路径 | 已读行为 | 使用边界 |
|---|---|---|
| `gateway/dual_can/tests/link_policy.c` | 纯C assert真实 `b4_hw_protocol_link_up`；无OS/网络/SDK | 既有隔离用例是B4_CAPTURE_SERIAL，不是MP_B5_CLOUD_CANDIDATE；两宏在真实header共享B-only分支，但该用例自身仅按前者分支断言。不能将其通过冒称C49132精确宏/原构建验证 |
| `gateway/dual_can/tests/bxcan_retransmit.c` | 编译真实b4_bxcan.c，RAM寄存器替身；检查时钟、NART、TXACK/FAIL、STOP | 既有编译参数见 `node-b/tools/run_b4_bench.py:54`；`B4_BXCAN_MMIO_TEST=1`不可遗漏；只能Host能力证据 |
| `node-b/tools/run_b4.py` | 本地gcc、真实CANopen/OD、双总线模拟器、文件解码和纯Hub；没有SDK/COM/socket调用 | 范围较大且旧 `b4_backend.py:24` 固定期望TEMP无效，不能盲目把历史夹具当当前TEMP验收；完整T0集成放下轮冻结 |
| `node-b/tools/run_b4_bench.py` | 本地gcc/模拟NOR/台架/寄存器替身 | 包含更多旧恢复测试，不需要为M0重复整包；使用上列最小相关用例即可 |

只读源哈希核验中，mp_od.c、model.h、router.c磁盘文件使用CRLF，与Git blob的LF字节不同但规范化文本一致；源索引分别保留两种SHA，不把文本一致写成字节一致。该边界同样不能替代历史BIN/构建输入证明。

## 保留的入场问题

1. A实际BIN和当前物理身份未取得；A候选OD/CAN源码可冻结，不应把A分支或旧导入清单当实物固件。
2. C49132是B-only；双CAN代码存在但A协议被显式关闭，需下一T0先冻结新集成方案，不能直接“接上A”。
3. 当前板版本、两段各两端120Ω、电源/反供电、收发器、CAN2跳线和音频占用UNKNOWN，不用旧图作今日事实。
4. 48KiB前应用区的C49132仅余20B历史资源记录，不支持无成本增加A/音频；栈/CPU/WiFi/QoS/队列峰值、双节点回退范围需新证据。
5. RR15源真值/物理因果、SDK原生副作用、冷启动ROM、当前云资源租期与Gate F保持开放。以上均不阻止完成M0离线计划，但不提供现场GO。
