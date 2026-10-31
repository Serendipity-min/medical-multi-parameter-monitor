# 工具复用与Scope差异（只审查，不改旧入口）

现有工具当前SHA见[复用工具索引](../../evidence/CODEX-M0-MULTIRATE-20261031/reused-tools-current-hashes.json)，历史实际执行版本则取[逐窗登记](../../evidence/CODEX-M0-MULTIRATE-20261031/historical-evidence-register.json)及原profile，二者不能互换。本轮工具源未改，不为M0重建工具链。

| 既有组件 | 可复用能力 | 新矩阵差异/保持禁用原因 |
|---|---|---|
| B2 `capture_b.py` / `analyze_capture_b.py` | 稳定槽重建、120B诊断/原码、冻结C回放/名义率 | 旧25284B ABI/地址及92s/30+60判据，不是B41012/165s入口；不重用旧卡 |
| E3 `resp_matrix_b.py` / supervisor / analyzer | 独立格、profile/source/card/tool哈希、原码连续性/周期/原生退出 | 固定137s=45+90+2，周期20、旧ABI、旧单次RESET/HALT/GO上界；不能改常量后冒称旧授权仍可用 |
| `b4_runtime.py` / B4当前采集/decoder | B41012诊断/ADC/CAN/TEMP、受限读取及原始时戳 | 新165s单板采集、CPU/SDK/Open/Close预算、独立冷启动和输出管理需新Scope薄适配；原生副作用仍UNKNOWN |
| `b5_codex_p1b_readonly.py` | 已审只读库结构、Mock签署/nonce负例可参考 | 生产CLI默认拒止、信任根未配置、历史B40928目标；不能靠OFFLINE_MOCK或填字段开放真实DLL/B41012 |
| `b5_channel_profiles.py` / joint / review | 独立ECG60/TEMP/RR15业务、冻结评测器与旧卡消费 | 旧Scope只认原目标/时限/一次START；不能把ECG60改90/120、RR15改R12后追认正式PASS |
| `b5_rr15_causal_replay.py` / analysis / corpus | 已验收原C因果及正负例非盲回归 | 本轮不调算法、不回放、不重复65+17；缺独立源真值不能从旧失败窗拟合门限 |
| `run_b4_bench.py`中的纯Host组件 | 资源策略和RAM-MMIO ACK/FAIL/STOP | 只提取三个已有相关用例执行，B4_CAPTURE_SERIAL不等于C49132原MP_B5构建，结果不关闭SDK风险 |
| `run_b4.py` / 实际OD/Router/Hub | 纯文件/模拟总线集成框架 | 旧b4_backend夹具要求TEMP无效，与当前温度路径有代际差异；完整T0先修审夹具再另批，不盲跑宣称三板通过 |

未来M1薄入口最小工作：绑定同次构建的B41012 BIN/AXF/symbols/地址；复用已审采集/槽解码，独立实现本提案固定165s/120槽工程评价及真实错误退出，不扩展旧scope；在真实加载SDK前验证新可信签署/不可复用nonce、逐次允许动作、当前现场、Open/Close预算和停止责任。Mock仅验证控制流程/拒止，不证明SDK原生安全；必须保留DLL原生返回、短读、超时、Close及监督器强杀差异。

目前没有上述新执行器/评测器，不向现有CLI传本轮JSON，不用临时脚本绕过门禁。工具实现、Mock及新现场卡签发的权限需下一轮具体确认；M0只是准备可审查差异，不以“已准备24卡”宣称24场可立即开跑。
