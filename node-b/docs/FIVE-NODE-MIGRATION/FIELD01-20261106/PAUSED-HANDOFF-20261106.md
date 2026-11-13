# FIELD01 暂停交接（2026-11-06）

负责人明确要求“保存当前进度，下次开始我通知你”。**本任务已暂停，未安排任何新的上电、串口命令、实板窗口、远端服务操作、commit或push。** 下次必须先收到负责人继续通知，再核对实物状态。本记录不提供下一次目标操作的自动授权。

## 最后确认的实物状态

- 最新明确回执：**仅A上电，J-Link在A，其余断电**，USB未接，泵断电。
- 随后提出过断电改成两对约60Ω的接线要求，但负责人以暂停回复，**没有确认已断电、已转线或已量阻值**。不得将该要求当作已执行。
- 最后确认的线束仍是 C.CAN1＋A.CAN1＋E.CAN1 和 C.CAN2＋B.CAN1＋D.CAN1，两段约41Ω，均有三个固定120Ω。
- 暂停时已提醒将仍上电的A及外围断电并拔USB/J-Link电脑端、保留线束；是否完成尚未回复。恢复时第一件事是确认当前电源、探针及实际接线，不能照历史描述直接开始。
- 温度和COM2屏在D，GY641 RC→PC10、TD→PC11，3.3V/GND；血压模块/操作屏在E，保持原非人体工装，泵始终人工操作。本轮未启动泵。

## 当前各板实际固件

| 板 | 当前应用 | 实装与恢复证据 |
|---|---|---|
| A / Node1 血氧 | **33,436B**，`FIVE_NODE_A.bin`，SHA256 `d9cec64e3947a25e43d74057d3c9229d7ed161f026e0b84fa532daf12905e670` | 已写sector0–2、完整Flash/Options/区外及正常启动通过；含时龄、TPDO0发送背压和同ID请求顺序修复。修复后实板CAN复验NOT_RUN |
| B / Node2 ECG/RESP | **40,032B**，原f3五板B镜像 | 已写sector0–2，完整核对/启动通过；采样算法和250/50Hz未变 |
| C / Node3 网关 | **正常五板M1：boot392B＋code55,480B**，sector0/4 | 临时诊断后已恢复，与诊断前正常M1完整Flash逐字节一致。当前不是CAN60诊断程序；完整SHA `f3bfbfdb9d8a9b8d9477b35c9e13161369336edae17a4accdc73bdfdc244837e` |
| D / Node4 温度 | **24,544B**，原f3五板D镜像 | 当前全片、Options、身份、运行态匹配，未重刷；15秒本地源持续刷新，30/30稳定快照有效，新67帧，24.97–25.14℃，负责人确认屏读数一致 |
| E / Node5 血压 | **29,416B**，原f3五板E镜像 | 通过USB232BOOT/COM15 ROM受限写sector0/1并全区核对；区外/Options保持。血压新完成值、本地屏操作过程、90秒失效均NOT_RUN |

A当前完整Flash SHA为 `8d03199f752aa7cb755fa4b8cb3909d9fd0854d3860a37d27df4f77016e804ea`。旧A33,396B、R6 A42,628B、C诊断和C正常M1制品、完整恢复原件均保留，不混用before引用。

最新公开清单与结果：[PREPARATION-MANIFEST.json](PREPARATION-MANIFEST.json)、[M7-FIELD-RESULTS.md](M7-FIELD-RESULTS.md)、[RESULTS.md](RESULTS.md)。

## 本次约41Ω短诊断的真实结果

- 固定60秒双段独立CAN台架，仅一次START；未联网、录音、启泵，使用明确本地测试纪元，不能当真实UTC。
- **44,005ms处A发EMCY 0x081：0x8110 / error register0x10 / bit0x14，即CAN发送缓冲溢出。主机原生退出1。** 发送一次X中止并关闭串口，没有自动重试。未抓到MCU STOP包，不能声称STOP ACK已确认；随后负责人明确全部断电。
- 原始二进制565,632B、完整解码17,676包，CRC/重同步丢弃/截断/序号缺口均0；触发异常后控制器未继续验证同批93包，但原始二进制已保留，离线完整解码。
- 四源均有OP5心跳，C两路已观察的TEC/REC峰值0/0，FIFO溢出0。未同窗读取其他四板自身TEC/REC，未测差分波形或电气裕量。
- 原始CAN点：ECG11,020、RESP2,204、PPG1,686；截止约44.230秒。194个波形模型批次在原始CAN中找到匹配，未匹配0。
- C末次诊断已提交PPG短段12批/75点，质量边界13次；部分批保留有本窗实证。
- A既有数秒源无效段，也有40ms步进与一次−20ms倒序；不可把全部缺口归因到41Ω、光学干扰或单个软件条件。
- 该窗为NOT_PASS，**不是完整60秒、不是正式五板300秒、更不是云/网页/整机通过**。参见[CAN60-41OHM-result.json](CAN60-41OHM-result.json)。

## 定向修复与离线证据

- A发送槽占用时旧应用仍准备下一PPG点。真实A应用＋CANopenNode、CAN忙边界替身复现丢点，原生退出3；增加背压后同一用例退出0，保持20ms连续网格，无补点/降采样/延长250ms。
- `MP_FIVE_NODE_A`构建启用TXFP请求顺序；E及默认构建不改变。新A ARM构建、安装和启动已通过，**实板修复效果尚未验证**。
- C原正常M1保留R6部分批有效修复的选择性适配；没有整体合并ABC分支、没有移入音频调度改动。
- 双段CAN60诊断的Host、ARM及6个取证定向检查通过；这些是软件检查，不覆盖真实A全部源点或40Ω电气裕量。
- 安装工具仅增加复用上一次已验证实装原件的入口，写前仍现场比对完整Flash与Options；没有伪称新做双读。错误current板原件在离线计划阶段拒绝。

## 恢复入口和仓库状态

工作树：`E:/medical-monitor-five-node`，分支 `codex/five-node-single-module-v1`，原HEAD `bd1ee2175c98fe20019f889596e8df40e57eec51`；软件入口 `f3f4ac9b1cb89ac46bad29dccf7eb21017f96dba`。原PHY01未提交修改保留，本轮修改也未commit/push。没有改main、删旁线或改M0标签。

本机入口（忽略文件）：`node-b/build/five-node-field01-current-pointer.json` → `node-b/build/field01-20261106T024011Z`。该运行目录的 `runtime-paths-private-local.json` 指向既有EFS原件，包含各板最新安装/恢复引用；UID、Options、完整Flash、原始UART、SDK日志不进入版本库。

关键私有引用键：`A_current_install`为A发送修复实装；`B_current_install`为本轮五板B；`C_current_install`为诊断后正常M1恢复；`D_current_check`/`D_current_local_check`为D只读及本地15秒；`E_current_install`为USB E实装。A安装的before原件是旧33,396B，C恢复的before是临时CAN60，不能沿用更早安装引用。

现有授权边界仍限：A/B sector0–2，D/E sector0–1，C sector0/4，Options与区外保持，不整片擦除、不解保护；D/E旧原程序不要求备份。暂停后不自动继续任何目标动作。

## 等待负责人通知后的起点

尚未执行的准备方案：全部断电，移开E、B的H/L，仅保留 **C1↔A1、C2↔D1**，量两段应各约60Ω，参考地保留，不外加电阻，J-Link可留A。该方案尚未确认完成，恢复时按现场实际决定。

接着准备 `MPM_NODE_PROFILE=five` 的隔离接收端，定向核对A发送修复、D温度；再安排E血压/屏及点对点。隔离五板后端/网页目前**尚未启动或配置**：暂停前仅在本机阅读了旧隔离服务脚本的结构和服务名，没有发起SSH、服务重启或远端更改。

正确端接的五板300秒仍待D/E无终端接口，暂不签FIVE_CAN_300S_PASS/FIVE_CLOUD_300S_PASS。R6 `12d3161`、M0 `26e695f`及失败原件完整保留；`R6_AUDIO_ASSEMBLY_TIMEOUT`、`R6_LIVE_QUEUE_OVERFLOW_30`、`A_PPG_SOURCE_GAPS`继续开放，不开展ABC R7/R8循环。本轮不以麦克风、语音或自动冷启动为前置。
