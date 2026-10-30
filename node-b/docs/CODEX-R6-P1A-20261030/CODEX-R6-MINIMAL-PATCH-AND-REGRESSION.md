# R6 最小候选补丁与回归

状态：CANDIDATE_OFFLINE。仅改变G3分派、R6上下文拒止、构建器断言/输出路径、对应测试和新审计工具。修改前已形成 [缺陷/变更/拒止/回滚表](CODEX-R6-PATCH-PREIMPLEMENTATION.md)。

## 实际变更

1. g.validate新增显式执行上下文和R6分派。默认Field拒绝R6以及任何带OFFLINE_MOCK的现场调用。
2. Profile不再用非空pi_signature解释冻结，R6只接受显式离线调用上下文及Mock声明。真实签署机制保持DESIGN_PROPOSED。
3. 构建器8处替换逐一要求恰一次命中；源码另存新构建目录，保持归档候选不变；同次回执包含实际输入、AXF/BIN/symbols/MAP/log指纹。
4. 原36项Profile测试只将两项R6离线用例迁到G3显式Mock入口；新增14项用例，覆盖真正main五入口、假签名/旧卡/重复nonce/错误ABI、3601s与86400s、旧R1-R5分派和缺失/重复锚点。

## 真实回执

命令和全部运行记录见证据目录 `execution-ledger.json`；stdout/stderr均保留在同名.log。

| 运行 | 真实退出码与结果 | 范围 |
|---|---|---|
| mock-regression-01 | 1，导入阶段被子进程护栏拒止 | 依赖platform.system尝试本机版本查询；未生成成功回执 |
| mock-regression-02 | 0；151项、0失败/错误/跳过 | Mock回归；护栏仅发生3次有意自检，无实际设备/网络/子进程 |
| arm-build-01 | 0；Keil 0 error / 0 warning | 独立新目录，未下载 |
| integrity-01 | 1，相对路径与绝对路径不能relative_to | 审计工具入口修正；失败日志保留 |
| integrity-02/03 | 0；基线14/14，review及三criteria字节不变 | 新/旧工具身份分开登记 |
| r5-replay-01 | 1；护栏拒止stdlib ctypes首次系统DLL初始化 | 调整标准库初始化顺序，J-Link从未加载 |
| r5-replay-02/03 | 3；三窗原正式失败全部复现 | 原冻结review，失败集合与正式原件一致，不重写原件 |
| model-01/02 | 0，PASS_SYNTHETIC | 150000模型帧、1200模型快照、0模型越界，WCET_MODEL_ONLY |
| artifact-file-comparison-02/03 | 1→0 | 先保留注释顺序差异，再定位非加载元数据；原始制品不改 |
| whitespace-full-01 / whitespace-code-01 | 2 / 0 | 原样合同的Markdown双空格和原生编译日志尾空白被全量检查检出；普通源码/交付文稿检查通过，原始附件/日志不格式化 |

R5 ECG五项失败、TEMP一项、RR三项失败均原样保留。151项中既有只读API测试覆盖负返回/正短读、HALT/ROM/超时及禁止控制API；这是替身拒止证据，不是原生SDK行为或真实CPU结果。

R1-R5原规则/身份/criteria不改；新拒止仅额外阻断把Mock声明送入默认Field。旧R5的86400秒例外未延伸给R6。冻结review和criteria的原始SHA见integrity回执。

尚未执行真实300s联合成功Mock、真实Broker/Backend/WSS、目标测时或P1-B。不得把上述回归数量或模型帧数作为现场验收。
