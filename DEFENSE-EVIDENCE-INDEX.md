# 答辩证据索引｜2026-11-06

先读[当前项目状态](PROJECT-STATUS-HANDOFF.md)，再按下表定位。证据分为历史工程通过、限定实板观察、离线验证和未通过项；**P1离线修复不能表述为已安装或五板实板通过**。历史文档中的“下一步/待执行”不代替当前状态。

## 架构与开发底座

| 答辩问题 | 现有证据 | 使用范围 |
|---|---|---|
| 系统技术栈与传感器→CAN→MQTT→Web/语音链路 | [技术路线](node-b/docs/FIVE-NODE-MIGRATION/01-Technology-Route.md) | 以M0为编写基准；五板职责和当前制品以本次交接为准。当前C为裸机单所有者coreMQTT/AT，不能称已运行FreeRTOS。 |
| 从P4到M0如何演进 | [演进说明](node-b/docs/FIVE-NODE-MIGRATION/02-P4-to-M0.md) | 历史阶段与软件迁移，不替代当前实板结论。 |
| M0三板底座及原失败怎样保留 | [冻结M0实测报告](https://github.com/Serendipity-min/medical-multi-parameter-monitor/blob/26e695ffda43a7a76aa54d1c4e3a5631ac0dc42e/node-b/docs/M0-ABC-BASELINE-20261103/FIVE-NODE-RESULTS.md) · [制品清单](node-b/docs/M0-ABC-BASELINE-20261103/RELEASE-MANIFEST.json) · [恢复入口](node-b/docs/M0-ABC-BASELINE-20261103/RESTORE-ENTRY.md) | 分组、非人体、工程范围；不是临床精度或五板完整稳定性证明。 |
| 五板拆分与节点/Topic来源 | [五板职责合同](node-b/docs/FIVE-NODE-MIGRATION/04-Five-Node-Contract.md) · [M1离线交付](node-b/docs/FIVE-NODE-MIGRATION/07-M1-Offline-and-Owner-Wiring-20261104.md) · [离线验证摘要](node-b/docs/FIVE-NODE-MIGRATION/M1-20261104/VALIDATION-SUMMARY.json) | 合同描述目标，M1摘要是离线验证；后续实物完成情况看FIELD01/FIVE41。 |

## 接线、CAN与五板真实窗口

| 答辩问题 | 现有证据 | 使用范围 |
|---|---|---|
| 双CAN为什么分段、120Ω并联为何约41Ω | [接线与端接说明](node-b/docs/FIVE-NODE-MIGRATION/06-CAN-Wiring-and-M1-Contract.md) | 电路/方案依据；实际接线及阻值以当前交接中的负责人回执为准。 |
| 60Ω点对点和41Ω小报文实验做了什么 | [PHY01正常对照及历史记录](node-b/docs/FIVE-NODE-MIGRATION/PHY01-20261105/RESULTS.md) · [41Ω三节点300秒](node-b/docs/FIVE-NODE-MIGRATION/PHY01-20261105/41OHM-RESULTS.md) | 后者为心跳＋温度小报文观察，不覆盖ECG/RESP完整波形或电气裕量。 |
| 温度、血压如何迁移到独立节点 | [A/D点对点](node-b/docs/FIVE-NODE-MIGRATION/FIELD01-20261106/AD60-POINT-TO-POINT-RESULTS.md) · [E血压101/67及失效](node-b/docs/FIVE-NODE-MIGRATION/FIELD01-20261106/DE-NIBP-101-67-RESULTS.md) | E同次匹配/失效分项通过；原TTS STOP未确认失败仍在，不签整机通过。 |
| 五板ECG60组实收怎样 | [ECG60实板结果](node-b/docs/FIVE-NODE-MIGRATION/FIVE41-20261106/ECG60-300S-RESULTS.md) | 41Ω工程诊断，严格窗内ECG69,633/75,000；血压106/64同次匹配；完整性NOT_PASS。 |
| 五板RR18组实收怎样 | [RR18实板结果](node-b/docs/FIVE-NODE-MIGRATION/FIVE41-20261106/RR18-300S-RESULTS.md) | 独立RR18输入，RESP14,303/15,000；血压97/66同次匹配；不能同时签有效ECG。 |
| 两组如何汇总与追溯 | [对照与交接](node-b/docs/FIVE-NODE-MIGRATION/FIVE41-20261106/TWO-WINDOW-COMPARISON-AND-HANDOFF.md) · [原始证据哈希索引](node-b/docs/FIVE-NODE-MIGRATION/FIVE41-20261106/FIELD-WINDOW-EVIDENCE-INDEX.json) | C串口、B原码、隔离Broker、真实网页和收尾回执均有定位/哈希；完整私有原件不随Git交付。 |
| 实际烧了哪些版本 | [当前五板镜像](node-b/docs/FIVE-NODE-MIGRATION/FIVE41-20261106/CURRENT-IMAGES.json) · [安装与回退约束](node-b/docs/FIVE-NODE-MIGRATION/FIVE41-20261106/STARTUP-INSTALLS-AND-NEXT-WINDOW.md) | 版本身份采用字节数＋SHA＋安装回执；P1离线构建不是当前实装。 |

截图可直接使用：[106/64有效](node-b/docs/FIVE-NODE-MIGRATION/FIVE41-20261106/browser/ECG60-E-106-64-valid.png) · [106/64到期](node-b/docs/FIVE-NODE-MIGRATION/FIVE41-20261106/browser/ECG60-E-90s-stale.png) · [97/66有效](node-b/docs/FIVE-NODE-MIGRATION/FIVE41-20261106/browser/RR18-E-97-66-valid.png) · [97/66到期](node-b/docs/FIVE-NODE-MIGRATION/FIVE41-20261106/browser/RR18-E-90s-stale.png)。截图证明当次显示，不证明全源点完整。

## P1性能、负例与下一步

| 答辩问题 | 证据 | 可陈述结论与限制 |
|---|---|---|
| 两项队列缺陷怎样定位和修改 | [修复前真实源码复现](node-b/docs/FIVE-NODE-MIGRATION/FIVE41-20261106/OFFLINE-ROUTER-REPRODUCTION.md) · [P1完整报告](node-b/docs/FIVE-NODE-MIGRATION/P1-20261106/RESULTS.md) · [前后原生结果](node-b/docs/FIVE-NODE-MIGRATION/P1-20261106/OFFLINE-RESULTS.json) | 四项定向用例修改前原生3、修改后0；12批真实PPG载荷的合成短突发由仅留1批变为FIFO保留12批。离线时序不冒充现场。 |
| 为什么不能宣称修好后五板稳定 | [P1容量预算](node-b/docs/FIVE-NODE-MIGRATION/P1-20261106/OFFLINE-RESULTS.json) | 源量下界约10.44–10.46帧/s，实测出口约8.07–8.08帧/s；完整入站与逐事务AT延迟缺证，不能把幸存者回放当全量压力通过。 |
| 资源和相关回归是否有记录 | [ARM资源](node-b/docs/FIVE-NODE-MIGRATION/P1-20261106/ARM-RESOURCES.json) · [相关回归](node-b/docs/FIVE-NODE-MIGRATION/P1-20261106/RELATED-REGRESSIONS.json) · [源码交付清单](node-b/docs/FIVE-NODE-MIGRATION/P1-20261106/DELIVERY-MANIFEST.json) | P1离线Flash56,536 B、sector4余9,392 B，RAM/容量不变；旧三板夹具profile错误原生3也保留，不冒用为五板证明。 |
| 复现脚本在哪里 | [文件型复现工具](node-b/tools/five_node_p1_offline.py) · [Router/出口定向夹具](gateway/b5/test_five_node_p1.c) · [原件回放Host桥](gateway/b5/test_five_node_p1_bridge.c) | 需要既有私有原件和本机GCC；Git仅含脚本与脱敏结果。本次Git交付没有重新运行它们。 |
| 旧失败是否被覆盖 | [固定R6失败报告](https://github.com/Serendipity-min/medical-multi-parameter-monitor/blob/12d3161b59fb88d9c9fed01b26d601df69c25b2a/node-b/docs/ABC-VOICE-APPLIANCE-20261105/ABC-R6-RESULTS-20261106.md) · [PPG计数更正](node-b/docs/FIVE-NODE-MIGRATION/FIVE41-20261106/COUNTER-SEMANTICS-ERRATUM.md) | R6音频组包超时/整体NOT_PASS不变；PPG短批计数更正为保留提交，旧解释副本与真实淘汰证据仍保留。 |
| FreeRTOS做到了哪里 | [当前交接](PROJECT-STATUS-HANDOFF.md) · [P1停止与交接结论](node-b/docs/FIVE-NODE-MIGRATION/P1-20261106/RESULTS.md) | 只形成后续架构待决事项，尚未启动迁移。引入RTOS本身不能证明吞吐或时效通过。 |

本索引不要求公开完整Flash、UID、凭据、录音原件或私有原始日志；链接到的Git摘要不能代替这些原件已有的受控存放与保全。
