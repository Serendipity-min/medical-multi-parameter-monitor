# P7-TRI入场计划（M0离线设计；现场与完整T0均未执行）

**P7_TRI_T0_OFFLINE_PLANNING=COMPLETE；P7_TRI_A_B_C_FIELD=NOT_AUTHORIZED。** 可追溯源级结构见[接口审查](audit-context/TRI-INTERFACE-DOSSIER.md)，精确提交/磁盘与Git字节SHA见[源索引](../../evidence/CODEX-M0-MULTIRATE-20261031/tri-interface-sources.json)。本文件是下一阶段提案，不是合并、实板/云服务或Flash入口。

## 候选身份与适用范围

| 对象 | 当前可冻结的软件/历史登记 | 尚不能冻结为物理事实 |
|---|---|---|
| A | 源候选 `3fa14b00a0823d2855e9dd8bd1c6c8545abb8dc5`；A CANopen应用、OD/PDO源SHA已登记 | 实装BIN、完整构建链/OD与实际器件一致性UNKNOWN；不把Git HEAD当烧录证据 |
| B | 本轮父提交中的B CANopen/BIO/TEMP工具源码SHA；历史B41012安装BIN `1dbbf27177caa429f037ac72c43581a519e8ff70ac6224411c9c4ffe9529432d` | 当日真实身份/供电/导联/SDK Close后状态UNKNOWN；RR输入QRS真值未定 |
| C | 历史C49132 BIN `72131dbb5ef6bc0e0d33e328925c685403bae928aea9447a81f8291c6ae5c1ab`；当前C/OD/模型/队列源SHA | 历史镜像B-only；当前源码与原91项编译输入完整字节对应NOT_REPROVEN，不能直接签发A+B能力 |
| 双CAN候选 | B4软件提交 `ffa440b31b8b4993967f0e9aef1b3071a0d1dcfe`，存在双独立端口/Node3 OD模型 | 不等于B5 C49132已安装双CAN工作镜像，不自动适配网络/温度/停止/配置布局 |
| H3/P4/P5/P6 | H3 A-C、P4资料、安全基线、P5最终审查47e59a6、P6文本TTS77dd14d分别有独立来源 | 未合并/未重新验收进R6；语音/AI、生产配置和Security Gate不随P7许可开放 |

三份当前“真实实装候选”的全链尚未齐全；缺项明确UNKNOWN，没有虚构A二进制或用B4 BIN顶替C49132。后续冻结需BIN/ELF或AXF/symbols、生成源、OD/PDO、编译宏、编译器、工具与诊断ABI一致；原恢复/身份材料只在EFS。

## 接口、资源与待核查

| 资源 | 源码/协议事实 | 入场前物理或集成证据 |
|---|---|---|
| A CAN1 ↔ C CAN1 | 500kbps；A=Node1、C=Node3；A PPG/SpO2/PR/NIBP，C按bus0仅接A | 两端120Ω、总线/收发器/供电/地参考、当日A传感器配置；NIBP控制权限单独签署，禁止自动启动袖带 |
| B CAN1 ↔ C CAN2 | 500kbps；B=Node2、C=Node3；B ECG250Hz/RESP50Hz/HR/RR/TEMP，bus1仅接B | PB12/PB13板版本/跳线/收发器/两端120Ω；不能复用“Node-A OFFLINE”作为A+B同时在线依据 |
| C CAN2时钟/滤波器 | CAN2依赖CAN1时钟，共享过滤器分区CAN2SB=14；C在两段各有独立Node3实例，不桥接CAN帧 | 不运行时单独复位CAN1或重分滤波器；用新候选验证两段独立错误/管理预算 |
| C PB12/PB13音频 | CAN2与I²S2音频时钟冲突；现有资源头有编译拒绝；PB10亦涉及ESP USART3 | 本阶段禁用冲突音频；TTS/麦克风若需要，单独引脚/时钟设计与回归，不直接合并语音分支 |
| 应用空间/CPU/队列 | C49132距历史48KiB应用区末仅20B；B5节点2优先FIFO，非无限无损 | 新集成代码体积、RW/ZI/栈、CPU/IRQ/UART/WiFi/MQTT峰值及A公平性；不随意侵占sector3/config或改链接布局 |
| UTC、BOOT/epoch、seq | 五路PDO映射/单位/时效、node/stream/source与启动代次已审查；旧epoch需撤销 | 新候选时钟资格/跨节点切代、WSS目标频道、REPLAY不续活、缓存失效/背压必须离线再验；不把UTC设定当同步测量 |
| 网关与云 | 当前Hub有gateway/node/stream键、session/seq拒旧、无效null/空波形、慢订阅者快照覆盖 | 当期部署版本、MQTTv3.1.1+TLS资源/账户/ACL/租期UNKNOWN；没有连接核验或恢复服务，历史租期不能再用 |

详细PDO1–5/0x181…0x681与0x182…0x682、ECGµV到mV、RESP相对量/温度age、A NIBP完成身份与90s时效等见接口审查。必须原样传播B异常HR有效位，不能在C/UI硬抹；MOCK/synthetic为非人体工程语义，REPLAY单列，不能冒作患者LIVE。

## 渐进入场提案

| 阶段 | 提议范围 | 准出/后续权限 |
|---|---|---|
| T0 | 纯Host双总线合成/文件驱动、实际OD/协议/Router/Hub/UI逻辑；无SDK/COM/socket/云进程 | 先冻结候选/夹具/哈希和范围，验证身份/时效/有效位、STOP、重放、队列公平性；本轮仅3组件通过，完整T0 NOT_RUN |
| T1 | A→C单路，B物理断开/无效，仅A云业务 | 另签接线/供电/镜像/云执行卡；NIBP指令另授权。A无效不被旧B状态填补 |
| T2 | B→C单路 | 同BIN/布线/工具/工况可引用现有B5工程证据；任一改变需定向复验，不能以A0/QRS未决消除RR例外 |
| T3 | A+B→C同时在线10分钟 | T0/T1/T2及C新双口候选/电气/云资源通过后另批；CAN1/2新增错误为0，value/valid/source不串线，CPU/队列/WiFi/MQTT负载有证据 |
| T4 | T3通过后30–60分钟压力及隔离故障恢复 | 故障注入、断网重连、旧epoch/REPLAY、单CAN失败逐项另批，不在正式云/实板自动注入；24h soak另属预发布门 |

T0合成可用真实QRS+RESP以及已知非QRS刺激检查协议，但不能用它确认本台SKX无QRS。T3十分钟超过旧B5单START/420s硬停，须新Scope/时限/停止策略，禁止修改旧硬停或复用已消费卡凑时长。

## 云、恢复和回退审计

新C双CAN集成候选应先在独立软件分支明确选择B4双口能力与B5/TEMP/队列/STOP的最小合入面；本轮未合并、未修改代码/链接/配置。P5 coreMQTT及P6 AI/语音不能自动加入；P4安全基线与新TLS/ACL/部署差异需独立Security Gate，不因Host回归通过而豁免。

硬件更新前须有按新镜像/sector边界冻结的备份、options/身份、差分写入/配置兼容分析和回退来源SHA；先前恢复包不自动适用新BIN。烧录/回滚、sector3变更、云启停/ACL、SDK重连各是新权限对象。不能把“需要回退”解释为自动执行回退。

现场异常STOP_TARGET保留原生返回和允许范围的现场证据，停止业务/控制动作；不得自动Reset/Go/重刷/重连。具体断电/隔离负责人和程序应由下一张现场卡指定。冷启动ROM与SDK Open/Close风险不因纯Host替身PASS而关闭。

## 下一轮具体申请：T0纯Host集成

请求PI下一轮仅批准：独立分支冻结A/B/C源与OD/PDO/模型/Router/Hub/UI接口；复用 `node-b/tools/run_b4.py` 及已有测试，先修正其旧TEMP-invalid假设与当代B41012的冲突；只作必要夹具/薄适配，不改冻结B5正式评测器、算法门限或固件行为。第一次运行前固定修订源/测试SHA、输入、期望和退出码。

建议上限：一套确定性双总线Host模拟+Hub/UI内存/文件检查，修订后一次完整集成回归；遇失败保留原码/日志，定向排障和有限相关重验，任何扩大范围再登记。墙钟预算拟议≤30分钟（不是现场租期），无需下载依赖；已安装编译/运行环境不足则NOT_RUN并给离线方案。不得启动Backend/MQTT/WSS服务、隧道、浏览器联网、SDK/COM或硬件进程。结果只报HOST_INTEGRATION，T1/T3仍零授权。

若PI希望改走M1单板现场，须另先解决[入口缺口](TOOL-REUSE-AND-SCOPE-GAPS.md)和逐次[禁用卡](disabled-cards/README.md)，冻结现场所需工具/预算/签署及状态；本计划不以“批准T0”代签M1。提交推送后等待决定，不自动执行T0完整集成。
