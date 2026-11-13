# ECG60单次入场门：closing STOP最小整改与待签包

2026-10-31，Asia/Shanghai。**TARGETED_STOP_GUARD_PATCH_OFFLINE_COMPLETE；M1-E60-R1仍NOT_AUTHORIZED / NOT_RUN。** 父提交 `37630aee2ef0af5bee9b13b827d21b38351d2445`；独立分支 `codex/b5-m1-ecg60-stop-gate-20261031`。[本轮合同原件](contracts/MPM-B5-M1-P0-PI-REVIEW-AND-ECG60-ONE-SHOT-GATE-R1.md)按相同字节保存，未将其当作可执行签名或现场令牌。

## 最小改动及反例

实现只改 `M1Link.gate()` 一处条件：去掉 `phase=='closing'` 的STOP豁免。原19项测试方法保持原AST不变，增加两个定向测试；评测器、Mock运行器、finally Close、采集/预算、算法、旧卡/Criteria、T0及三板代码均未修改。

新增测试直接调用真实 `M1Link.gate`，只替换传输边界和时钟；不复制待测条件、不加载设备SDK。第一个在closing的最终状态首读之前创建STOP，第二个在末态/前缀/身份读取完成、准备设置 `SetRestartOnClose` 之前创建STOP。

| 指定注入点 | 修补前 | 修补后 |
|---|---|---|
| 最终状态首读前 | capture exit0；STOP后普通读26次、续跑策略1次 | capture exit4/M1_OPERATOR_STOP；STOP后普通读0、续跑策略0 |
| SetRestartOnClose前 | capture exit0；STOP后续跑策略1次 | capture exit4/M1_OPERATOR_STOP；STOP后普通读0、续跑策略0 |

修补后两种情形的Mock均只进入一次原finally Close，close_resume未开启，Close后状态仍UNKNOWN，native_side_effects仍UNRESOLVED。补丁前只跑新增两项，得到2个预期失败、进程真实exit1；补丁后完整21项（原19+新2）通过，真实exit0。原失败、原源码、事件序列与所有SHA均保留：[反例对照](../../evidence/CODEX-M1-E60-ONE-SHOT-GATE-20261031/STOP-before-after.json)、[最小改动与原19保留证明](../../evidence/CODEX-M1-E60-ONE-SHOT-GATE-20261031/minimal-diff-and-regression-preservation.json)。

这个结论只覆盖主机检查和上述注入点；不能撤销已在途的SDK动作，也不证明原生Close无暂停/复位、MCU已停止或Close后仍运行。仅允许原受审finally的关闭路径，不为恢复退出码0发Halt/Go/Reset/Flash或重连。

## 首场独立签署材料

[首场禁用卡](M1-E60-R1-ONE-SHOT.disabled.md)及[JSON](M1-E60-R1-ONE-SHOT.disabled.json)重新绑定工具SHA，仍 `enabled=false / sessions=0 / PI_signature=null / nonce=null`。提议仅一次M1-E60-R1，其他23场为零授权。[待签清单](FIRST-SIGNING-READINESS.disabled.json)登记四项现场阻断：

1. **TRUST**：固定PI根仍None；尚未收到PI可信渠道选定的公钥/指纹。需要PI提供受控Ed25519原始32B公钥并独立核对其SHA256指纹。Codex没有创建生产PI根或代签权限；原19项回归中的临时密钥仅是离线测试fixture，不进入本卡/生产配置。根变更后代码SHA会变，须重新冻结实际commit/tree、全部工具及负例再签，不能沿用本稿哈希自动放行。
2. **SITE**：B-only电气图、C电源/USB/CAN/反供电及探针隔离证据、SKX正常ECG60/1mV和充电USB断开、导联/人员STOP条件均待当期批准后核定。最近B/C同时上电、USB在C、J-Link在B、L在LA的历史自述不当作新证据；本轮没有新查询或指挥现场动作。
3. **COLD**：独立物理冷启动及真实BOOT epoch未建立，不能由uptime≤120s、目录或nonce推导。任何冷态操作须先取得具体许可，不能现在为补材料改线/上电。
4. **SDK**：OpenEx/Device/Connect/Close及强杀原生风险保持UNRESOLVED，PI知情接受有限风险与人工停止/保全/断电责任尚未签署。Mock不关闭此风险。

同次B41012的BIN/AXF/symbols与历史identity/full/options六份原件本轮重新验hash一致，见[历史参考核对](../../evidence/CODEX-M1-E60-ONE-SHOT-GATE-20261031/B41012-historical-reference-check.json)。这是离线旧参考核对，**不是今天已读板**。未来唯一许可内先比对当前B身份/完整Flash/options/同次制品，采前失败即停，不先另行偷偷连接排查。B-only不等待C双CAN、MQTT或云就绪，但其电气隔离证据不能省略。

保持原45s预热+120s评价、120个1Hz槽、≥118正确有效及每条有效HR为60±2、原码完整性和合法STOP/Close要求；250Hz CH1/CH2与依原seq派生RESP50不变。capture exit0不等于工程PASS；review exit0且field_scope_PASS=true才可申请M1_E60_R1_ENGINEERING_PASS。当前该场仍NOT_RUN，旧RR15 NOT_PASS/exit3及SOURCE_UNKNOWN/ROOT_CAUSE_UNRESOLVED不变。

## 回执和停止

[执行账本](../../evidence/CODEX-M1-E60-ONE-SHOT-GATE-20261031/execution-ledger.json)、[工具与未变更项](../../evidence/CODEX-M1-E60-ONE-SHOT-GATE-20261031/frozen-tools-and-scope.json)、[制品SHA清单](EVIDENCE-HASHES.json)可复算。Codex独立重算了被验收父提交18项登记文件的Git字节SHA/大小；这不是声称PI曾重算全部SHA。

所有新Mock原件/日志/执行副本留新EFS目录，忽略指针 `node-b/build/m1-ecg60-stop-gate-pointer.json` 可定位。旧失败和原参考未覆盖；没有生产PI私钥、真实UID或完整镜像进入Git。源码检查仅合同授权范围，不运行安全扫描。

本轮真实目标SDK/COM/探针枚举、上电/改线、RESET/HALT/GO、B5START、Flash、云端与现场采集均0。签署资料只是待PI填写/核定的禁用材料，不是已发许可。提交推送并复核远端SHA后停止，等待PI审核补丁和上述待签项；首场真正执行必须另取仅一次有效现场授权，其他23场和T1/T2/T3不开放。
