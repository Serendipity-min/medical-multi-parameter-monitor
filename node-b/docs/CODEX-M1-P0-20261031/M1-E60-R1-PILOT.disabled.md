# M1-E60-R1：ECG60首场试采执行卡（默认禁用）

状态 **NOT_AUTHORIZED**；允许现场会话0；当前不执行任何操作。机器原件：[M1-E60-R1-PILOT.disabled.json](M1-E60-R1-PILOT.disabled.json)。本卡直接绑定M0的M1-E60-R1原卡及唯一矩阵，不把24张卡作为一张现场批量许可。

| 对象 | 固定提案/绑定 | 尚需PI独立签发 |
|---|---|---|
| B镜像 | BIN41012B `1dbbf27177caa429f037ac72c43581a519e8ff70ac6224411c9c4ffe9529432d` | 当期实际板与历史身份/full/options匹配，非新刷写 |
| 调试链 | 原安装同次AXF `e11219c4…`、symbols `07e2166e…`，9处RAM符号已核验 | 绑定完整SHA及实际工具/签署commit/tree，不混用后来同BIN的另一AXF |
| 刺激 | 正常ECG60bpm、1mV名义幅值，R→RA/L→LA/F→RL | 当前只知“心电波形/L在LA”；率值/幅值/源电源隔离和安全拓扑待核对 |
| 冷启动 | 一次新的独立B冷启动事实、run/boot标识及源记录 | 当前已上电不满足本场证明；不得用run_id/新目录代替冷启动，不由工具自动RESET |
| 采集 | 45s预热+120s评价，原码窗165000ms | 一次会话、新目录、新nonce，零重试；仅批准本卡才执行 |
| 数据 | CH1/CH2全250Hz ADC、seq/flags/IRQ cycles/ms；RESP50按seq%5派生 | 不插值、不修时戳；模组原始帧/诊断完整留EFS |
| 评价 | 固定120个1Hz槽、最早原生观察；至少118正确有效、任一有效HR超±2失败 | 不改旧G3或正式Criteria；初次成功且PI接受后计入E60三次中的R1 |
| 预算 | 预检75s、采集165s、收尾20s，总260s；监督265s；native普通读5s/full读45s/Close5s；SDK20000并留64次收尾 | 这是本卡待批上界，不是现场WCET证明；native阻塞按心跳杀唯一worker，不补跑 |
| Close | 全窗口成功且末态Flash健康才设置正常Close续跑；异常不发Go/Reset/重连 | PI承认原生副作用仍未证实，指定人工停止/断电责任；Close后UNKNOWN |
| 外部范围 | 不需要C双CAN、C串口/身份/RESET/B5START/云 | 单板隔离方案须明确；当前B/C均上电不自动成为准入条件 |

真实工具入口为 `node-b/tools/b5_m1_entry.py`。P0固定PI信任根未配置，`--execute`/`--worker`均在SDK构造前拒止exit2；`--plan`只输出设计。生产代码已具备签署/绑定→nonce→独立worker→监督/采集路径，但不能靠改JSON布尔、非空签名、旧G3授权、OFFLINE_MOCK或测试公钥启用。信任根选定及当期授权必须先由PI独立审批、固定工具新SHA。

仅在将来获批之后，才由当场批准的调用方基于新现场记录生成受限授权，绑定scope/run/plan/commit/tree/tools/DLL/bundle/site/cold_start/output/责任人；父进程原子消耗nonce，worker另做一次不可复用claim。Open前失败也不退款/换目录自动重试。对构造/部分Open失败可能无法完成native Close，保存原件、停止并由人工负责，不能宣称SDK风险已关闭。

如试采失败，本卡原件/已用nonce/原始数据保留；不以失败试采补成R1 PASS、不拿R2掩盖，不自动进入E90或RR批次。需要新尝试只能由PI另签。RR15真值与三板准备均不在本卡批准范围。
