# 工具复用、审查修正与复现

先读基线工具并形成两个context dossier，再执行原始C回放；没有跳过审查直接调阈值。审查对象为 b9b17a7 的 `b5_rr15_causal_replay.py`；本轮修正保留既有格式/算法调用，增加专项只读观察，没有另造调试器/采样工具链。

| 基线问题 | 本轮处理 / 状态 |
|---|---|
| 只有whole binary SHA，无index pin | CLI额外要求RR/ECG index SHA，逐块offset/hash/尾部和整体SHA仍核验 |
| 未保留IRQ cycles/status清单、epoch与缺口 | 帧增加原cycles/status；统计seq/ms/cycles/flags，序号重启/回绕拒止，不拼接不同boot |
| 允许95%样本频谱并压缩缺样相位 | 250个完整连续序号与1..8ms IRQ间距，否则拒止；相位用原IRQ ms |
| 暖机直接比较绝对ms，回绕错误 | 使用uint32相对时间，时间值本身不改写，定向wrap测试通过 |
| last_cycle_ms语义错误 | 明确为last_accepted_peak_timestamp_ms；额外只读C桥取真实intervals/峰宽，不把时间戳当周期 |
| 输出仅排除repo、host库位于OS临时目录 | CLI用既有PRIVATE/EFS属性验证；真实/派生数据与库放EFS并保留，不借OS temp存真实数据 |
| 未完整记录compiler/header/库hash | 绑定C/header SHA，保留编译命令/版本/二进制SHA、stdout/stderr和各host库实际SHA |
| Python sizeof120不等于C ABI验证 | 编译附加ABI桥，执行前核验C sizeof与全部offsetof；不改公开C/header |
| 单Process回放忽略getter/Tick和初态 | 逐seq对应真实诊断；做+0/+1/+4ms敏感性，承认实际调用时刻缺失，不伪造精确调度 |
| 没有正反例/留出的执行证据 | 7份真实ECG（含当前新ECG）+独立R5 RR、40组合成数据及65项既有C回归；保留两项挑战限制 |

新增 `b5_rr15_causal_analysis.py` 复用上述封存读取、host编译和原冻结 `reconstruct` 纯读取函数，提供只读C内部状态、逐帧120B等价、逐seq对齐、频谱/周期证据和EFS工程波形。调用冻结重建函数不等于重跑或修改正式联评器。

新增 `run_rr15_causal_corpus.py` 驱动相同纯host库：读取已封存重建CSV、独立R5留出，执行固定seed/相位的合成QRS与非QRS输入，保留原seq/ms/flags。原C、header、采样/队列/固件及真实输入没有更改。该脚本最后仅修正了历史index中继承的 `HELD_OUT_NOT_REPLAYED` 显示标签，原执行脚本/结果仍封存，数据及数值结果不变，没有第二次留出回放。

## 复现入口

在本机仓库根目录，工具单元测试（17项，合成原件/假host库）可以直接运行：

```powershell
python -B -X utf8 node-b/tests/test_rr15_causal_replay.py
$testExit = $LASTEXITCODE
exit $testExit
```

真实数据复现只在受限EFS使用。当期路径和显式SHA由忽略的 `node-b/build/codex-RR15-causal-current-pointer.json` → `inputs-private.json` 定位。`final-replay-process-private.json` 保留完整实际命令；不要把其私有输入复制到Git。CLI需要：

```text
python -X utf8 node-b/tools/b5_rr15_causal_replay.py
  --rr-joint <EFS RR joint> --rr-blocks-sha256 <sealed SHA> --rr-index-sha256 <sealed index SHA>
  --ecg-joint <EFS ECG joint> --ecg-blocks-sha256 <sealed SHA> --ecg-index-sha256 <sealed index SHA>
  --baseline-source <bio_v2.c> --baseline-source-sha256 <3adca55c...full SHA>
  --baseline-header-sha256 <76198016...full SHA>
  --out-private <NEW path in existing EFS directory>
```

若未来真有候选，`--candidate-source`必须同时给候选C/header SHA；本轮没有使用候选算法。编译输出目录和回执独占创建，新运行不能复用/覆盖本轮目录。`--out-private`必须为已有EFS父目录下的新文件。

完整因果分析与图：`b5_rr15_causal_analysis.py --inputs-private <EFS inputs>`，图为随后 `--render-existing`；输出目录已存在时拒止，不应为复现删除原件。锁定语料入口为 `run_rr15_causal_corpus.py --inputs-private <EFS inputs> --corpus-sha256 <aea6e071...full SHA>`，并要求预先存在不改算法的开发决定。所有真实库是本地编译的纯C数学库，非J-Link/设备SDK。

进入真实语料的main有EFS门；低层解析/统计函数用于合成单元测试时可读取测试进程临时目录，不提供现场/网络能力。C回放进程exit0仅指成功完成诊断，不能把RR HR有效样本仍存在或挑战覆盖不足改写为算法PASS。
