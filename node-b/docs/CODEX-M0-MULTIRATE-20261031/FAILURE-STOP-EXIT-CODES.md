# 失败、停止与退出码：历史原生和未来提案分开

## 已有真实退出语义（本轮不改）

| 对象 | 既有语义/本轮处理 |
|---|---|
| E3 capture worker | 0完整采集/导出，1停止，2导出失败；supervisor 0/1单列 |
| E3单格分析 | 0全通过，2输入完整性失败，3周期/稳态/覆盖不通过，1异常 |
| E3矩阵 | 0六格通过，2完整性失败，3工程不通过，1缺格/重复/异常；旧六格均0，不重跑 |
| 当前R6正式review | ECG60/TEMP各0，RR15为3；不能用collector/supervisor 0覆盖review3 |
| 本轮证据收集 | 初版exit1为旧摘要缺EFS属性；保留原件，副本新EFS+SHA复核后修订exit0；不是算法失败 |
| 本轮三板源比对 | 初版exit1为CRLF/LF字节不同；分开登记磁盘和Git SHA后exit0；不冒称原字节相同 |
| 路径发现 | rg无匹配/错误路径的1/2属于查询结果/路径问题，按真实返回登记，不能作目标/测量裁定 |
| 本轮Host组件 | 三次compile及三次run各0，runner0；只是组件，不是实板或完整T0 |

精确操作与SHA见[执行账本](../../evidence/CODEX-M0-MULTIRATE-20261031/M0-execution-ledger.json)。Git commit/push后才能记录其真实码，不在提交前预言成功。

## 新M1评测器建议退出码（尚未实施/执行）

| 拟议码/状态 | 触发 | 必须保留和后续动作 |
|---|---|---|
| 0 / ENGINEERING_RATE_SUBFUNCTION_PASS | 新窗口原件/采样门通过且目标量值/覆盖通过 | 只限签署对象；RESP仍带HR_TRUTH_UNKNOWN，不升级整窗PASS |
| 1 / TOOL_OR_NATIVE_ERROR | 异常原生返回、SDK/Close错误、工具异常 | 原生日志/退出码/时间预算；不能当板故障；停止该run和后续，不自动恢复 |
| 2 / INTEGRITY_OR_AUTHORIZATION_REJECT | 哈希、签署/nonce/工具/目标/BOOT/原码完整性不符 | 入口拒绝应发生在SDK前；若运行中出现，STOP_TARGET保留失败，不改分母/补点 |
| 3 / ENGINEERING_NOT_PASS | 有效率覆盖不足、任一有效量值超差、采样/传播工程门不通过 | 所有失败项与区间原件；不得删除失败、追加重跑、改判据或挑最后有效值 |
| 4 / STOP_TARGET_OPERATOR_OR_BUDGET | 人工STOP、原生超时/预算耗尽、监督器终止、身份漂移/CPU状态未知 | 分别记录worker原生码、监督器码和termination reason，不把OS kill改写为4或0；4仅拟议上层分类 |
| 无进程 / NOT_RUN | 未授权、前格失败或前置项未满足 | exit_code=null，不能填0；不消费不存在的现场次数 |

上述映射只供下一轮评测器设计，不能说已存在的CLI实现这些码。采集、分析、监督器、SDK返回和最终scope verdict必须各自记录；只有输入/原生检查/工程判据都满足才有该scope PASS。

HALT/ROM/Fault/LOCKUP、异常复位、Flash/options/身份漂移、供电/接线/源不符、意外接地/主动RLD异常、SDK超时及无资格UTC均按所批阶段停止并保全原件；无自动RESET/GO/重连/重刷。下一张卡必须指定负责人和允许的退出/冷态隔离方式，当前不指挥任何物理动作。

云端/串流有效位、来源/epoch错配、REPLAY续活、无理由丢弃等在M2/T0各适用标准覆盖范围单独失败；M1不执行的C/云阶段只能NOT_RUN，不能报零错误PASS。A+B实板、生产云更改、Security Gate均未授权。
