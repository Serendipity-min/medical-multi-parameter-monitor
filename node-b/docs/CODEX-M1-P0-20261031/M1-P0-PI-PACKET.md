# M1-P0 独立B多速率离线工具与首卡交付

2026-10-31，Asia/Shanghai。**M1_P0_OFFLINE_PREPARED；ECG60_PILOT_FIELD_NOT_AUTHORIZED。** 基线 `025839a2fc272232141b557bfce8aa10952ca682`；独立分支 `codex/b5-m1-p0-offline-entry-20261031`。PI接受的T0交付与历史R5/R6结果均保留；本轮不扩展T0，不实施A/C双CAN集成，也不以C未就绪阻塞B独立试采准备。

## 已完成

- [M1独立入口](../../tools/b5_m1_entry.py)：复用BLink的Open/只读原生返回/Close、b4_runtime快照与assess、原G3槽格式；M1子类单独限制地址、调用次数和阶段预算，不运行或修改旧业务CLI。现场入口先检查固定PI信任根，再验签/绑定、原子消耗nonce、独立worker claim；父进程监督唯一worker。当前固定根未配置，现场CLI立即exit2，任何旧G3卡、自填布尔/非空签名或OFFLINE_MOCK参数不能开启。
- [M1工程评测器](../../tools/b5_m1_review.py)：复用既有稳定原码解码；165秒原码窗、前45秒预热、后120秒评价、固定120个1Hz槽，最早原生观察选点，不按valid挑值。≥118/120正确有效且任何原生有效量值不得超HR±2/RR±1。ADC/seq/IRQ/flags/时序/启动变化单独判完整性；保留全部250Hz CH1/CH2原码，并以原seq%5导出RESP50，不重采样、不改原时戳。
- [首张ECG60禁用试采卡](M1-E60-R1-PILOT.disabled.md)、[JSON](M1-E60-R1-PILOT.disabled.json)和[固定计划](M1-E60-R1.plan.json)：绑定原安装B41012B、同次AXF/symbols、历史身份/full/options及工具哈希。当前允许次数0、签署/nonce/有效期/新现场与独立冷启动证据均未建立。
- [分批计划](M1-BATCH-PLAN.disabled.json)：直接引用并验hash的M0原24张禁用卡/矩阵，不复制改写旧卡。按本次PI指令先E60-R1，再E90/120首轮与RR12/15/18/24/30首轮，再补齐各三次；仅在首场前调整未来分批次序，无旧结果或判据变更。
- [SDK及制品审查](audit-context/SDK-AND-MAPPING.md)：现有同次BIN41012、AXF811816、symbols108998字节实物文件及9个RAM映射已离线核验。历史安装前/后身份相同，完整Flash/options旧参考hash一致；它们不是本轮的新读板证据。必要参考副本新存EFS，真实UID/完整镜像不进Git。

## 验证与真实退出码

最终19个unittest方法（含多组子负例）PASS_MOCK/exit0，SDK/DLL/COM、子进程和socket保护钩子没有被测试调用触发。测试直接调用新入口/评测器和原BLink负读/短读方法；165秒虚拟时钟采集经真实稳定槽解码完成120槽评价，并检验事后改动输入会被拒绝。签名、公钥及原件哈希独立保存，评测重新核验签名；信任根未配置时只输出离线指标，field_scope_PASS=false。它不代表真实ADC时钟、SDK副作用、临床精度或现场PASS。

覆盖：信任根/坏签名/篡改/旧Scope/过期/次数、nonce不可复用及失败不退款、构造/OpenEx/Device/Connect、身份/固件/冷启动漂移、ROM/HALT、负读/正短读、Close失败/超时、STOP/会话硬停、监督器故障强杀与原生退出码、缺样/乱序/IRQ不推进/flags/ADC错误、120槽最早观察选择、118槽边界及额外有效超差、RR中HR真实valid保持和SOURCE_UNKNOWN。

保留两次失败：mock-01 exit1，保护钩子误拦Windows ctypes初始化kernel32（没有触及J-Link）；改为先完成标准库初始化后仍严格阻止SDK加载。mock-02 exit1，三个断言把原BLink的ValueError错写成RuntimeError，修正测试预期，未改旧库异常语义。后续针对新增计划/原件封存、生产监督路径、签名存档/重验及坏签名CLI退出码的回归均exit0，最终mock-release为19项。没有隐去失败或将Mock当原生副作用已解决。

完整[退出码和回归证据](../../evidence/CODEX-M1-P0-20261031/mock-and-execution-ledger.json)、[同次制品映射](../../evidence/CODEX-M1-P0-20261031/b41012-mapping-and-reuse.json)、[历史参考链](../../evidence/CODEX-M1-P0-20261031/reference-chain-check.json)、[工具绑定](../../evidence/CODEX-M1-P0-20261031/tool-reuse-bindings.json)和[EVIDENCE-HASHES.json](EVIDENCE-HASHES.json)可复算。执行脚本/日志、合成夹具和参考原件留新EFS job，忽略指针为 `node-b/build/m1-p0-pointer.json`；临时合成测试目录生命周期结束后清理，不是删除现场原始数据。

## 当前现场与首场待PI批准项

用户最新报告：USB连接C，J-Link连接B，B/C已上电，连接心电波形，L在LA，其余不变。本轮只登记为负责人自述，没有枚举/连接任何目标。**ECG是否60bpm/1mV、SKX充电USB隔离、M1单板拓扑、新独立冷启动和当期SDK会话安全条件仍UNKNOWN/未确认。** 本报告不指挥现在改线、上电或按RESET。

首场独立批准需冻结：生产PI公钥指纹、此交付工具/commit/tree、新签署/nonce/有效期与输出目录；本场源/单B电气拓扑和安全停止责任；一次独立冷启动事实及启动标识（当前已上电自述不是本场冷启动证明）；SDK原生风险与正常/异常Close策略。固定信任根当前为None，不能从授权来件、测试临时密钥或非空签名自取。PI选择信任根并批准现场调用方/worker之前，P0 CLI保持拒止，不用临时脚本绕过。

B-only不依赖C身份、双CAN、C串口、B5START或云UTC。原始IRQ ms/cycles/seq可独立评价；CAN/温度/时钟诊断照实保留，不能为配合单板试验改固件或伪造字段。停止/退出预算及代码边界见[M1工具与准入说明](M1-ENTRY-REVIEW-AND-EXIT-CONTRACT.md)。

Open/Device/Connect/Close的原生内部动作、Close后目标状态、部分Open/构造失败资源状态、冷启动ROM机制和真实WCET仍UNKNOWN。M1只禁止显式Reset/Halt/Go/Flash/目标写；不据此声称原生内部从未暂停/复位。必要时保存现场并停在STOP_TARGET，不自动恢复/重连/重试。

RR15 SOURCE_UNKNOWN/ROOT_CAUSE_UNRESOLVED、旧正式NOT_PASS/exit3不变；RESP中的HR仅表征，不强制屏蔽、不伪造Lead-Off。旧冻结评测器/BIO/ABI/采样代码、M0卡、T0、A/C及云代码均未改。提交推送后停止，申请PI单独审核 **M1-E60-R1首场ECG60试采**；其余23场及三板T1/T2/T3仍零授权。
