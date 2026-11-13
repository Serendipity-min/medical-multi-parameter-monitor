# 项目状态与交接｜2026-11-06

**当前结论：五板拆分及两组41Ω实测已完成，端到端完整稳定基线仍未通过；P1两项出站缺陷仅离线修复通过，未安装、未实板复测。FreeRTOS待决，尚未启动。**

本次Git交付基点为`codex/five-node-single-module-v1@e8804f8a8092a38a8a5ff9be2f7162dfbcd091e3`。阅读入口：[答辩证据索引](DEFENSE-EVIDENCE-INDEX.md) · [P1完整报告](node-b/docs/FIVE-NODE-MIGRATION/P1-20261106/RESULTS.md) · [本次Git交付说明](node-b/docs/FIVE-NODE-MIGRATION/P1-20261106/GIT-DELIVERY-NOTE.md)。

## 已完成与尚未通过

| 层级 | 真实状态及限制 |
|---|---|
| M0底座 | 冻结三板工程基线`baseline/abc-unified-pre-split-v1`→`26e695ffda43a7a76aa54d1c4e3a5631ac0dc42e`保留；历史BC/ABC ECG60及ABC RR18分组工程结果不等于当前五板通过。 |
| 五板职责 | A=Node1血氧/PPG，B=Node2心电/呼吸，C=Node3双CAN网关，D=Node4温度与独立屏，E=Node5血压与屏。D/E迁移、角色与受限安装/读回已有实物证据。 |
| 点对点 | 已有A/D观察、E的101/67同次匹配及90秒失效证据；E窗口TTS STOP未确认的原失败仍保留，不签整机通过。 |
| 两组五板实测 | 同镜像、各45秒预热＋300秒评价；四源在线与身份可追溯，C两路CAN诊断未观察到错误，E的106/64、97/66在屏/C/Broker/网页同次匹配并到期失效。ECG与RR分组判定，没有合成同窗双有效。 |
| 五板完整性 | **NOT_PASS**：严格窗内ECG匹配69,633/75,000点、RESP匹配14,303/15,000点，PPG覆盖明显不足，历史仍被淘汰；A全窗输入及间断根因未闭环。 |
| P1整改 | **离线定向通过**：PPG有空位时按次FIFO；历史配额可以执行并受实时源龄/队列/在途背压保护。采样率、真实点、身份与原时效未改。 |
| P1容量 | **NOT_PASS**：两组源产生量下界约10.44/10.46帧/s，实测服务约8.07/8.08帧/s；缺少完整C入站及逐事务AT耗时表，幸存者回放不能冒充全量饱和复现。 |
| R6语音 | `codex/abc-voice-appliance-v1@12d3161b59fb88d9c9fed01b26d601df69c25b2a`及原失败保留，未整体合并；音频组包超时未被改写为通过。五板两组窗口没有强制加入麦克风。 |
| FreeRTOS | **待决/NOT_STARTED**。P1仅提出后续架构交接输入，没有启动内核迁移、实现网络重构或批准下一实板窗口。 |

## 当前五板实装镜像

下表来自既有安装/读回回执，**本次仅整理资料，没有重新读取或刷写设备**。完整SHA和回执见[CURRENT-IMAGES.json](node-b/docs/FIVE-NODE-MIGRATION/FIVE41-20261106/CURRENT-IMAGES.json)。

| 板 | 实装应用字节 | 应用SHA256前12位 | 已核对写入分区 |
|---|---:|---|---|
| A | 33,444 | `b20bfdb877aa` | sector0–2 |
| B | 40,040 | `f2276540bb8c` | sector0–2 |
| C | boot392＋code56,072 | boot`0ac74b0de142`；code`b92a232d1249` | sector0/4 |
| D | 24,552 | `ae4e6d11770c` | sector0/1 |
| E | 29,424 | `da890a5e9eb1` | sector0/1 |

C实装Flash总加载56,464 B，sector4余9,464 B。P1离线构建为56,536 B、sector4余9,392 B，**不替代上述实装镜像**；RAM与实时24＋历史56帧容量不变。E没有单份连续整片Flash哈希，回执记录应用读回与区外前后核对，不能补写不存在的证明。

## 最后确认的现场与恢复入口

负责人最后确认ABCDE及外围全部断电，USB/J-Link电脑端拔开，板端J-Link在B，黄L留LL。保留C.CAN1+A.CAN1+E.CAN1（41Ω）、C.CAN2+B.CAN1+D.CAN1（40.9Ω）及参考地；两段H/L独立。D温度RC→PC10、TD→PC11和COM2屏、E血压模块/屏及P5/P6原接线保留。这里是历史现场回执，不是本轮重新测得的状态。

约41Ω窗口只证明当次负载下的工程观察，不代表正常端接、电气波形裕量或长期稳定验收；本次没有新增现场动作。窗后发热/复位/屏异常细节未补充，记UNKNOWN。

设备未变更，不需执行硬件回退。P1源码回退点为`e8804f8`中的两个生产文件；实际镜像恢复约束见[安装与恢复清单](node-b/docs/FIVE-NODE-MIGRATION/FIVE41-20261106/STARTUP-INSTALLS-AND-NEXT-WINDOW.md)。完整恢复原件留受限存储，D/E最初未知程序按负责人决定未备份，不能承诺恢复未知应用。

后续是否采用FreeRTOS、如何改进单所有者网络服务与预算、何时再次实板，均待下一阶段决定。当前不再通过FIFO微调或相同300秒窗口循环寻求通过；main、正式云端及冻结标签均保持不变。
