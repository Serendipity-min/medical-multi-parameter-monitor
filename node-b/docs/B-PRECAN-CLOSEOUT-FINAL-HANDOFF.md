# Node-B 正式CAN集成前唯一交接报告

2026-10-23，MPM-B-PREC-001。当前为有未关闭项的交接状态，不能解释为三个专项全部通过，也不能据此启动CAN。仅本文件作为本轮交接入口，后续证据在此更新。

基线实测分支`codex/node-b-bio-v2-field-20261022@bb9bc8e00860ff4f61fa3c4f315edfb76815a59b`已在开工时通过远端HEAD及独立fetch重新核实。实验分支`codex/node-b-precan-closeout-20261023`，独立工作区`E:/medical-monitor-node-b-precan-closeout`；历史实测、B/B2/P4/main/H3/P6/语音及历史标签不修改。

## 三项门禁分别签署

| 专项 | 门禁 | 当前证据与缺口 |
|---|---|---|
| P0 CPU根因 | **BLOCKED — CPU_ROOT_CAUSE_UNRESOLVED** | 离线审计及S0再次确认ROM运行/Flash完整；D0/M0均无可辨认应用输出，后补屏幕接线与候选USART1路由不匹配，观察通道尚未验证。缺进入ROM的可证实机制、纠正措施及独立启动/调试验证，未签PASS。 |
| P1 ECG/RESP同步 | **BLOCKED — BLOCKED_BY_P0** | 依任务顺序尚未启动E3 CH2专项分析及新同步采集；没有同窗双路有效性结果，不签B_ECG_RESP_SIMULTANEOUS_ENGINEERING_PASS。也未证明源不支持同步，不能提前签SOURCE_SIMULTANEOUS_CAPABILITY_BLOCKED。 |
| P2 阻抗幅度 | **BLOCKED — IMPEDANCE_AMPLITUDE_NOT_CALIBRATED_INSTRUMENT_REQUIRED** | 当前仅电池万用表DLX-YQ2915，不具备32kHz动态阻抗标定能力。按负责人“不能做就跳过”跳过实测，Ω真值均null，不要求本轮采购。 |

## P0 已完成的实际工作

已审查旧CPU延期记录、37份SDK日志及相关IO/心跳、48份关联回执、板图/启动源码/冻结AXF反汇编。重点覆盖BOOT锁存与NRST/电源/自动下载电路，J-Link前后策略及Close行为，RCC/Fault/VTOR/映射，DWT依赖和屏幕07软件复位路径。结论及证据边界见[离线审计](PREC-P0-OFFLINE-AUDIT-R1.md)及[回执索引](../evidence/B-PREC-001/historical-receipt-index.json)。尚无足以唯一归因的证据。

S0经单独授权仅执行一次：VTOR三次1FFF0000，15个PCSR样本均ROM；Flash/options SHA与冻结候选一致；BIO ABI无效。显式reset/halt/go/写数据0，Open/Connect/Close各1，不重试。worker/监督器/调用方真实退出3/1/1，约40.672秒；完整结果见[S0/D0报告](PREC-P0-S0-D0-RESULT-R1.md)。首次读值是连接后，Close后状态未知，不能宣称设备全程没有硬件复位。

D0负责人回报无波形、电源灯无变化、无其他异常，后续明确JTAG已拔下。M0只授权一次实体复位及无调试器观察，负责人报告仍无反应，没有分别给出5/15/45秒值。随后补充两路屏幕接线：图纸RS2/P3对应USART2，J4/P5第二路对应USART3；冻结候选源码和AXF均为USART1 PA9/PA10。P3是否接入ADS1292使用的PA2/PA3、屏接口电平尚待查看，暂停新增动作。此前屏幕观察通道未验证的证据不足已补正，详见[复核](PREC-P0-HMI-PATH-AUDIT-R1.md)。不据静态画面伪造无调试器PC/VTOR或判断CPU仍在ROM。后续按[单变量计划](PREC-P0-FIELD-CONTROL-PLAN-R1.md)逐卡，不无限重试，不强设PC/MSP/VTOR、不重刷。

P0下一步：先核实屏型号/电平、P3/P5实际跳帽和JTAG断开状态，解决独立观察通道及潜在引脚冲突的证据缺口；任何改线先电气审查另卡。如需连接取寄存器对照，先提交另卡，明确介入前后证据来源。冷启动须先解决源/模块潜在反供电的安全初态。即使复位恢复，也保持根因未关闭，直到机制、对应纠正措施及预冻结独立验证全部成立。

## P1 后续补证方案

只有P0通过后才分析E3六窗CH2原码、滤波、峰候选、HR原因码及干扰分布，并核对本机V2.2普通ECG模式同步呼吸能力。当前负责人实际源状态已更正为普通ECG60，不是上一轮呼吸24；未擅自切回。

新同步试验须另卡，采前冻结实际模式/目标值、45秒预热与90秒共同评价、HR/RR各自有效率及同时有效率、失效区间、原码和ADC完整性。HR60±2、RR20±1只是待实际源模式确认的参考值，当前不签已冻结现场判据。不把两个不同模式分别通过合并为同步通过；如证实源输出限制，再签相应阻塞并提出其他工程源方案。

## P2 仪器限制

V2.2手册规定呼吸导联II RA–LL、基线“1K”、幅度0.3R–3.0R，但未完整定义R的pp/峰值/RMS、32kHz等效路径及激励条件。现有万用表不能据此测Zmin/Zmax/ΔZpp或不确定度。详见[仪器能力判断](PREC-P2-INSTRUMENT-ASSESSMENT-R1.md)。不通电测欧姆、不接地RLD、不短接LL/RL、不把ADC codes写成Ω。本轮无需增加仪器或开展幅度对照。

若未来另行重启标定，最低需要经电气审查的隔离32kHz阻抗/比值测量能力及夹具，明确浮地/RLD路径、允许激励、三档动态值、重复性及校准/补偿不确定度，接入另行授权。

## 冻结、归档与验证

ECG60/90/120各两轮、RESP12/18/24各两轮的既有通过保持原验收范围；RR206025帧、681/681稳态保存观察有效不改。BIO_V2算法阈值、固件及历史失败原件不改，不用本轮离线测试代替实物验收。

新取证工具8项离线测试通过；真实disabled负例在SDK构造前拒绝，调用方/worker/监督器均1，未接硬件。工具和已用S0/D0/M0卡按SHA留存；S0卡及工具执行后不改写。Close另走继承心跳通道，其证据边界已记录。

私有原件目录`E:/medical-monitor-node-b-precan-private/20261023`采用受限ACL及NTFS EFS加密。L1候选BIN、L2历史安装前整片、L2已安装候选整片/options分级保存，明确区分69d9…历史安装前备份与f713…已安装候选；S0新读Flash/RAM/UID/SDK原件同样受限加密。Git仅提交派生摘要、卡、工具、测试及SHA索引，不提交私有原码/设备身份/整片固件。

本轮提交推送及远端取回校验尚待完成；仅允许本实验分支正常提交推送，无PR、合并、删分支、改标签或Security Gate。远端提交与校验完成后补入本节，未完成前不宣称已交付远端。

MPM-B4-001仍暂停。[CAN后续备忘](PREC-CAN-FUTURE-DESIGN-MEMO.md)仅记录两段独立总线方案，本轮不实施。未完成项如实交接，不自动进入CAN，等待PI新合同。
