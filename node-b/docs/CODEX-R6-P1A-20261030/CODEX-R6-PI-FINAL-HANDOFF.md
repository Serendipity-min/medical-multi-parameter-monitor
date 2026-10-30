# Codex R6 P1-A 交付与停止交接

`P1A_AUDIT_COMPLETE`：限定离线审查、必要主机候选补丁及Mock回归已完成。此状态不表示全部发现关闭，不表示P1-B、Gate F、B41012B安装或B5通过。

基线：`01864fb4c1ea35c9da38aa98b1e85790d2ed5415`。交付分支：`audit/codex-b5-r6-takeover-20261030`。交付提交为包含本报告的Git提交，完整SHA由提交/推送后的独立回执及最终答复给出，避免文件自引用。

## 可复核结果

- S0工作区和指定远端基线一致且干净；主合同两副本SHA一致。缺失前一份P1合同正文由负责人明确同意不阻断本轮，未假造路径或已读状态。
- 37个工具的基线/候选SHA和复用边界已列账；入口和SDK审查分别追踪COM、工人、云及原生API。G3 R6分派修正，默认Field仍无条件拒止；可信签署实现不在本轮启用。
- 151项隔离回归退出0；五种真实main入口经内存替身测试拒止，不产生现场token或驱动构造。历史R1-R5及只读API反例保留。
- 新独立Keil构建退出0，应用BIN41012B与归档一致，8个锚点唯一命中，实际编译输入及同次AXF/symbols/MAP/log均绑定；归档候选未覆盖。
- 14项旧清单全部与基线Git字节匹配；冻结review及三个R5 criteria字节保持不变。新主机候选的预期差异另列，不篡改旧清单。
- 三个R5完整review重放均精确保留原失败集合，进程真实退出3；没有把成功读取/采集当正式PASS。
- ECG WSS冻结集合独立复算：expected751、seen741、missing10；评价期内expected命中739，另1项非expected旧批次形成“740”；尾段新增2项expected，不能称740+1。
- CPU模型退出0，150000/150000模型帧、1200模型快照、0模型越界；结论严格为WCET_MODEL_ONLY。

## 技术审查门及未关闭事项

| 门/事项 | 本轮结论 | 下一阶段边界 |
|---|---|---|
| C-GATE-01入口分派/拒止 | CLOSED_OFFLINE_CANDIDATE | 不含300s联合成功流程或现场测试 |
| C-GATE-02签署互锁 | FAIL_CLOSED；所有R6 Field拒止 | 可信PI信任根、Git/制品/板卡绑定及nonce消费保持DESIGN_PROPOSED，不能自签 |
| C-GATE-03制品链 | 同次链已取得，BIN复现；差异定位为非加载.comment元数据与符号输出路径 | 新调试产物未自动替换旧Profile；PI需冻结一致链 |
| C-GATE-04 WCET | 模型证据完成，硬件证据OPEN | FrameFeed完整调用及串口无本地超时等待尚无实测最坏界 |
| C-GATE-05 ECG集合 | 口径纠正，有原件/集合SHA | 不改变741或历史NOT_PASS；ECG停顿底层根因UNKNOWN |
| 只读SDK连接/Close | P1-A审查完成，执行NOT_READY | 隐式CPU动作、旧ABI、温度只读Close异常路径、专用P1-B入口仍OPEN |
| 今日现场 | 最新负责人报告已登记 | 无照片/电子核验；USB反供电、接口类型、电脑端/VTref、具体SKX菜单UNKNOWN |
| RR菜单/1.5R及导联 | 已读真实说明书P5/P11，保留R5事实与今日L=LL报告 | 当前实物菜单未核；不能把周期字段/1.5R强行解释成载波/物理单位，不能推定CH2必无真实QRS；J3与额外导联不操作 |
| CPU ROM/独立冷启动/标定/故障注入 | 历史风险继续OPEN | 不为结束通信阶段而关闭 |

P1-A没有修复现场SDK恢复路径或实现签名基础设施，因为这将超出本合同的最小主机候选范围。修复选择和未知项已保留，不能据“151 passed”自动扩权。

## 交付索引

1. [接管事实](CODEX-B5-TAKEOVER-FACTS.md)
2. [工具复用矩阵](CODEX-R6-TOOL-REUSE-AND-SAFETY-MATRIX.md)
3. [真正入口](CODEX-R6-G3-ENTRYPOINT-CALLGRAPH.md)
4. [修改前审查](CODEX-R6-PATCH-PREIMPLEMENTATION.md) / [补丁及回归](CODEX-R6-MINIMAL-PATCH-AND-REGRESSION.md)
5. [同次构建身份](CODEX-R6-B41012-ARTIFACT-RECONCILIATION.md)
6. [P1-A现场/SDK准备](CODEX-R6-P1A-SITE-AND-READONLY-SDK-REVIEW.md)
7. [Node-B禁用申请](R6-P1B-BOARD-B-REQUEST.disabled.md) / [Gateway-C禁用申请](R6-P1B-BOARD-C-REQUEST.disabled.md)
8. [证据清单](CODEX-R6-EVIDENCE-HASHES.json)
9. [入口上下文](audit-context/ENTRY-DOSSIER.md) / [SDK上下文](audit-context/SDK-DOSSIER.md) / [WCET及WSS](audit-context/EVIDENCE-DOSSIER.md)
10. [阻断原因及具体解决方案](CODEX-R6-BLOCKER-RESOLUTION-PLAN.md)

原始运行日志、失败日志、执行命令、真实退出码、工具SHA和JSON回执在 `node-b/evidence/CODEX-R6-P1A-20261030/`。同次AXF、MAP、符号表、生成源码和编译输入原件保留在独立本机构建目录；清单和哈希已入交付包，不上传私有Flash/options/UID/原始采样与授权。

## 下一门申请与停止

向PI提交B/C两张**禁用申请**供分别审核；因工具入口/Close政策及当前现场证据未齐，不具备立即激活条件。需要PI先审本包，再按逐板工具、DLL、身份、现场状态、90s建议上限、一次新nonce/零重试和异常责任签发独立许可。未获另行许可不连接设备，也不为填未知而上电/改线。

```text
P1A_AUDIT                         = COMPLETE_WITH_OPEN_ITEMS
P1B_BOARD_B                       = NOT_AUTHORIZED / NOT_EXECUTED
P1B_BOARD_C                       = NOT_AUTHORIZED / NOT_EXECUTED
TRUSTED_PI_VERIFIER               = DESIGN_PROPOSED
R6_GATE_F                         = NOT_SIGNED
B41012B_INSTALL                   = NOT_AUTHORIZED / NOT_EXECUTED
R6_P2_THREE_WINDOWS               = NOT_AUTHORIZED / NOT_EXECUTED
REAL_SDK_OR_COM_SESSIONS           = 0
NEW_B5START_RESET_HALT_GO_FLASH    = 0
CLOUD_OR_SECURITY_GATE_CHANGES    = 0
R5_FORMAL                         = ALL_THREE_NOT_PASS_EXIT_3
B5_STAGE_CLOSURE                  = DENIED
NEXT_ACTION                       = STOP_AND_WAIT_FOR_PI_REVIEW
```

本轮仅按授权提交和推送此独立分支，不建PR、不合并、不继续下一阶段。
