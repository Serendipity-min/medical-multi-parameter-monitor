# Node-B 精确现场授权卡索引及历史草案

2026-10-23修订：[AUTH-B-RESP-PATH-MEASURE-001 R2](AUTH-B-RESP-PATH-MEASURE-001-R2.md)按新手册和负责人新要求替代R1后续指引，取消全部电阻测量；A段仅呼吸率20等参数确认和三对源端直流核对，B段为待读数审阅且明确开始后的RA–LL冷接方案。本卡采集/SDK调用0；旧R1虽已获同意，但未收到执行结果，不冒填已完成。下方R1待批状态是旧快照。

最新待批：[AUTH-B-RESP-PATH-MEASURE-001 R1](AUTH-B-RESP-PATH-MEASURE-001-R1.md)。仅一次≤10分钟手工会话：冷隔离、完全脱离设备的线缆TRS九格电阻映射、SKX源端六对直流粗/细筛；SDK调用0、采集0，不含RA–LL新接法或恢复上电。源端动态阻抗仍未证明；厂家照片差异及原因130解释见[路径复核](RESP-SOURCE-PATH-REVIEW-R1.md)。本轮仅准备，未执行。

最新：按负责人固定ECG60/呼吸15/1.5R/窒息0、波形周期20不变，完成一次45秒。采集/监督0、分析3；实际ECG60互证，但30秒评价中38次RR观察全部无效，RESP_PATH_NOT_OBSERVED。CPU问题暂列待查，未发reset/烧录命令。详见[45秒有效性实板结果](RESP-VALIDITY45-001-RESULTS-R1.md)。下方描述按历史阶段保留。

当前最终状态：新零复位卡获批并完成一次10秒；采集/监督0、分析3，RESP_PATH_NOT_OBSERVED，CH1有小幅变化但周期未解出。halt1/go1、未发reset或烧录命令。详见[本次实板结果](RESP-E1-03-RESULTS.md)。E2/E3未执行；本轮各卡已消耗，下方等待/准备文字为各阶段历史，不再作为当前状态。

最新追加：一次复位卡获明确同意，但入口已变为运行态/VTOR08000000，按原卡STOP；实际reset/halt/go均0，未采集、未重试。[新零复位10秒卡](AUTH-B-RESP-PILOT-002-R1.md)及测试已备，单独等待新窗口确认；详见[运行状态审查追加记录](RESP-RUNTIME-STATE-REVIEW-R1.md)。

最新启动只读核验：两次连接均实际PC=1FFF32F0、VTOR=1FFF0000、CPU暂停，Flash/options匹配。当前停在系统ROM，尚未证明最初进入原因；未发reset/go/halt，未继续采集。详见[启动与J-Link流程核验](RESP-RUNTIME-STATE-REVIEW-R1.md)。[一次复位及有条件10秒新卡](AUTH-B-RUNTIME-RECOVERY-RESP-001-R1.md)已备，等待新增复位权限；以下E1失败/E0描述保留为历史。

RESP-003最新执行：R3卡唯一会话在首组诊断触发RESP_DIAG_ABI，worker/监督均exit1，未完成10秒；halt/go/reset/写Flash均0，未重试。E1未签通过，E2/E3未执行。下方E0等待描述为历史快照；当前以[RESP报告](RESP-EXPLORATORY-REPORT.md)及[失败回执](../evidence/B-RESP-003/e1-failure-receipt-01.json)为准，R3一次权限已消耗。

RESP-003当前卡为[AUTH-B-RESP-PILOT-001 R2](AUTH-B-RESP-PILOT-001-R2.md)：厂家ΔΩ未知不再否决探索，E0已通过；电气判断及实际独立呼吸15菜单未确认，当前不执行。下方ALG-002 R1准备与旧卡是保留的历史状态，不复用其执行权限。

> R3最新：负责人逐档确认普通60/90/120、电池及断USB和原接线状态，按ECG-MATRIX卡完成全部六窗并分析，六窗均通过本次组合工程速率判据。本轮无固件/阈值/工具变化，无重新烧录或复位。卡内六次会话已用完；RESP仍待动态阻抗电极对/ΔΩ定义及独立精确授权卡，未执行。结果见[六窗实板结果](B-ALG-002-ECG-MATRIX-RESULTS.md)和[唯一交接](B-ALG-002-FINAL-HANDOFF.md)。以下R1/R2草案均为历史状态，不重复索要已确认J-Link资料。

RESP最新准备：[AUTH-B-RESP-PILOT-001 R1](AUTH-B-RESP-PILOT-001-R1.md)为精确10秒输入检查草案，当前DRAFT_NOT_APPROVABLE_SOURCE_AND_TOOL_GATES；[一次性缺项](B-ALG-002-RESP-INFORMATION-CHECKLIST-R1.md)列明补证和工具冻结条件。未执行、未申请批准，不提供可直接运行的RESP命令。

2026-10-22，Asia/Shanghai。依据合同第1.3、2、5节：真实接线、供电、SWD/串口读取、烧录和采集前须单独书面批准。原合同批准仅覆盖B2-0软件准备；负责人确认“源已到手”不是现场操作许可。缺字段不得用“同上/默认/按需”替代。

## R2更新：首次身份/备份改用独立精确卡

负责人已补充：照片中STM32F407ZGT6为B，当前未通电，模块已连、未接人体；只有Codex操作，无其他调试/自动下载程序。F绿、R红、L黄且模块/线缆同款，设计级F→RLD可确认，未做实测通断。

首次身份/备份统一改用 [AUTH-B-READBACK-001 R1](AUTH-B-READBACK-001-R1.md)，缺项见 [现场信息清单](B-ALG-002-FIELD-INFORMATION-CHECKLIST.md)。下面ECG-00保留为历史提案，标记SUPERSEDED_FOR_FIRST_READBACK，不能再据此执行。ECG-01/RESP-01是后续独立许可，仍未批准。

## AUTH-B-ECG-00：历史身份/完整备份窗口提案（已替代）

目的仅为填补ECG-01要求的今日UID/容量/options/Flash身份；需负责人同意分窗及逐项冻结后才能签发。当前 `DRAFT_INCOMPLETE_NOT_APPROVABLE`，不申请空白许可。

| 字段 | 当前值/必须补齐的内容 |
|---|---|
| 实际板 | 负责人确认STM32F407；完整后缀/板号/照片未知 |
| 当前状态 | J-Link当前接B（负责人最新更正）、CAN未接；供电/开关/BOOT0/模块线状态未知 |
| 源与导联 | 此窗口不启动模拟器、不接任何导联；当前是否已接线仍须确认 |
| 接口边界 | 仅B，排除A/C/云端；SWD接线图、引脚、VTref、参考地须冻结 |
| 工具 | 本地JLink V5.12 EXE已静态核SHA，见source-tool-sha256.json；DLL静态SHA亦已冻结；现场实际加载的版本组合待核定 |
| SWD速度 | 建议1000kHz，待实际工具/现场确认，不继承旧脚本4000kHz |
| 初始/末态 | 是否允许halt、reset、go、断电/上电及每次次数均未批准；必须填精确步骤 |
| 读取白名单 | UID12B、DBGMCU ID4B、容量2B；options精确范围待核定；容量正确后Flash双读各1048576B |
| 禁止 | 任何Flash/option/RDP写、候选安装、采集、源输出、CAN |
| 时限/次数 | 建议单次≤10分钟、无自动重试；具体起止和最大命令超时待签发 |
| 保存 | 受限目录，双读磁盘比较+独立恢复副本；公开仅脱敏摘要 |
| 停止 | 型号/容量/电气/保护异常、IO超时立即停止，不自动解锁或恢复 |
| 批准 | PI姓名/批准文本/精确卡SHA/有效起止：未提供 |

## AUTH-B-ECG-01：已知ECG输入、候选写入及采集

当前 `DRAFT_INCOMPLETE_NOT_APPROVABLE`。下表未知项任何一项未解决均不执行。ECG-00不能替代本卡；本卡不自动包括RESP阻抗验证。

| 必填字段 | 冻结值/状态 |
|---|---|
| 板/模块身份与照片 | STM32F407 family已回报；后缀/板号/模块版本/今日照片未知 |
| 真实供电/开关/BOOT/J-Link | J-Link当前接B（负责人最新更正）；其余未知 |
| UID/容量/options | 未读取；只保存在受限目录并以manifest SHA引用 |
| 当前完整Flash及恢复副本 | NOT_RUN；双读一致SHA、大小和副本核验均缺 |
| SKX机身/固件/附件 | 已到手；机身标识/固件/电极线附件照片未知 |
| 源电源及隔离 | 电池/充电USB/仪器/电脑各参考路径未知；电池不自动证明隔离 |
| RA/LA/RL通断 | 线缆两端触点编号/方向/照片及实测表缺；RL主动驱动兼容性缺 |
| 实际GPIO与跳帽 | 按B2-0映射逐项实物核验，J3/电源入口/地待确认 |
| 候选 | BIN 25284B，SHA438a8120…；完整SHA与本轮ELF/symbol SHA见profile.offline.json |
| 正常输入寄存器 | 01/E0/40/40/EC/F0/00/EA/03，GPIO按mask；今日回读缺 |
| 烧录工具/扇区 | EXE/DLL静态SHA见source-tool-sha256.json；精确命令及擦除行为证明缺；仅条件性sector0/1，不允许mass erase；具体恢复见恢复计划 |
| 采集工具/profile | 离线profile已冻结；真实BIO_V2采集后端未实现/未批准；真实UID/全Flash绑定缺 |
| 范围及次数 | 建议下述ECG矩阵；负责人须确认总窗口、reset/halt/go、读写和恢复精确次数 |
| 允许期限 | 未签发，无默认长期权限 |
| 失败处理 | STOP优先，保留所有轮次；禁止用改阈值或清flags消除失败 |
| 批准 | PI姓名/批准文本/完整卡SHA及起止时刻缺 |

断电通断记录草表：

| 模块信号 | 插头端触点/观察方向 | 模拟器端标记 | 仪表/阻值/证据 | 裁定 |
|---|---|---|---|---|
| ERA/RA | 未知 | RA拟核 | 未测 | UNKNOWN |
| ELA/LA | 未知 | LA拟核 | 未测 | UNKNOWN |
| RLD/RL | 未知 | RL是否容许主动RLD待证 | 未测 | BLOCKED |
| LL | 不属于本模块RA/LA/RL三线映射 | 不允许与RL短接 | 不适用 | DO_NOT_BRIDGE |

### 拟冻结ECG窗口及判据

全部数据 `ENGINEERING_NONHUMAN`。每档先独立预热30秒，再连续60秒稳态分析，共90秒×2；60/90/120 BPM合计6轮540秒，不含换档/准备/负例。参考先登记设定值、源误差依据、独立核频及不确定度；若没有任何可靠速率参考，保持REFERENCE_BLOCKED，不计算准确率。

建议工程稳态阈值|HR−参考|≤2BPM；源自身误差及纳入/排除规则需在采前冻结，不在采后调线。每轮同时报告有效覆盖、所有失效区间、原码完整性、单通道削顶、实际SPS及恢复耗时，不能只挑有效片段宣称PASS。无同步逐拍真值不计算逐峰敏感性/漏检率。预热也保留原码。固件5秒/10秒预热不替代台架30秒稳定观察。

负例建议单项≤15秒、一次一个因素，确切切换/断线对象、断电要求和恢复步骤必须补入卡；未批准前不做。普通ECG模式同步20bpm呼吸只登记耦合条件，不能作为B3结果。顶轨、强周期干扰、异常发热、供电越界/参考不明、身份或工具不符、尾段未确认均STOP/具名阻塞；不通过关闭MAINS/NO_CYCLES凑PASS。

## AUTH-B-RESP-01：独立动态阻抗验证

当前 `NOT_ELIGIBLE_ECG_NOT_VALIDATED`。ECG受审结果和实际动态阻抗证据出现后再提交，不申请提前批准。

必填：ECG受审run/hash；SKX动态阻抗实际电极对（须与CH1 RA–LA路径匹配）；基线Ω、ΔΩ及峰值/峰峰定义、实际频率及误差、测量仪器/方法/调制频率下复阻抗依据；源供电/隔离和主动RLD兼容；CH1真实寄存器、镜像/完整Flash/profile/工具SHA；一次只改一个因素；故障停止与逐项恢复；明确允许写入对象、窗口及PI签字。

建议12/18/24次/分，每档预热30秒+分析90秒，共120秒×2；尚未冻结为验收判据。电极对不匹配=`B3_BLOCKED_ELECTRODE_PAIR`，真值不明=`B3_BLOCKED_REFERENCE`。不把低频呼吸电压或静态DMM阻值当作动态阻抗证明，不猜接LL/RL。
