# R6 P1-A 构建与冻结 WSS 证据上下文

执行模式：`READONLY_OFFLINE_RECOUNT / WCET_MODEL_ONLY`。审查基线为 `01864fb4c1ea35c9da38aa98b1e85790d2ed5415`。本报告仅阅读源码与历史 EFS 原件；未构建、未加载 SDK、未连接设备、未接云端。补丁与新构建由主执行流程分别记录。本报告的行号均指上述基线，不能把后续主机补丁的行号混为历史来源。

## 1. 构建器及八个协作点

`node-b/tools/build_b4_arm.py:28-31` 校验冻结源输入；`:43-49` 在唯一 `BioV2_Process(...)` 锚点后加入 `BCan_Sample(...)` 和 `CanOpen_Task(...)`；`:50-75` 进行八处 R6 文本替换。基线只对原始 Bio hook 有唯一命中断言，八处 R6 替换没有逐项唯一命中断言。使用 AST 读取基线构建器中 `if args.candidate_r6` 的八次 `text.replace`，在真实冻结 `HARDWARE/hr_page.c` 中逐项计数，结果如下；读取和计数的真实进程退出码为 **0**。

| 构建器基线行 | 锚点 | 冻结源命中数 | 新增 FrameFeed 次数 |
|---|---|---:|---:|
| 53 | `StateTxt(HP_TXT_HR_ST, st_hr);` | 1 | 1 |
| 56 | `StateTxt(HP_TXT_RR_ST, st_rr);` | 1 | 1 |
| 59 | `ProbeRefresh(now_ms);` | 1 | 1 |
| 62 | `if (s_cur == HP_SCR_PROBE) { ProbePageRefresh(now_ms); }` | 1 | 1 |
| 65 | `QualityRefresh();` 后紧跟周期分支结束 | 1 | 1 |
| 68 | `MinuteTick();` 后紧跟周期分支结束 | 1 | 1 |
| 71 | `ReadRTC();` 后紧跟周期分支结束 | 1 | 1 |
| 74 | `ScanControls();` 后紧跟周期分支结束 | 1 | 1 |

基线构建器 `:76-78` 将注入后的候选源码写到既有 `node-b/evidence/B5-R6-PATCH01/hr_page.candidate.c`。这使历史候选输出路径成为可覆盖路径；本轮重建必须先在主机候选补丁中改为新构建目录输出，不能直接运行旧构建器覆盖归档候选。

原始两次构建回执 `b4-arm-20261030T062335164483Z/receipt.json` 与 `b4-arm-20261030T065438840092Z/receipt.json` 均记录 BIN 41012B、SHA256 `1dbbf27177caa429f037ac72c43581a519e8ff70ac6224411c9c4ffe9529432d`；AXF 分别为 `e11219c4...` 与 `3e9d4d32...`，symbols 分别为 `07e2166e...` 与 `bbc978f3...`。两个 symbols 文件记录长度均为 **108998B**，并非报告表格的 44101B。BIN 相同不能证明 AXF/symbols 同一，差异具体成因在本报告中保持 `UNKNOWN`，不能未经比较就归因调试路径。单一新构建链及 MAP 由主流程另行生成并登记。

## 2. FrameFeed 的真实调用及时间预算边界

| 位置（均为基线） | 真实行为 | 现有模型未建立的约束 |
|---|---|---|
| `HARDWARE/hr_page.c:286-321` | `while (ADS1292_ReadFrame(f) != 0)` 排空累积 FIFO；保留 IRQ sampleMs/sequence，调用 `BioV2_Process` | 一次调用可处理多帧；不是固定单帧或零成本函数 |
| 构建器 `:43-49` | 每帧继续调用 `BCan_Sample`、`CanOpen_Task` | 模型未运行这些真实 C 实现 |
| `HARDWARE/bio_v2.c:198` | 双通道算法状态推进 | 数据相关最坏耗时未在本次实板测得 |
| `node-b/canopen/b_canopen_app.c:62-78` | 入通信队列、固定点转换、资格/序列更新 | 队列满、有效性与ISR交互不是零成本 |
| 同文件 `:142-166` | 温度任务、CANopen 处理、最多8轮推进 | 多个协议处理子路径及 IRQ 抢占耗时未被现有 Python 模型执行 |
| `node-b/temperature/b_temperature.c:39-48` | 每轮最多消费32个 UART 字节 | UART异步相位、接收环和解析路径须计入完整调用预算 |
| `HARDWARE/hr_page.c:56-57,305-319` | Home/run状态下每4帧ECG及每8帧RESP写波形 | 每第8帧可能同时发送两路图形命令；屏幕状态改变调用成本 |
| `SCREEN/hmi_driver.c:1223-1236` | `GraphChannelDataAdd` 通过命令头/尾和逐字节发送完成整条命令 | 波形发送同样是同步阻塞，不能漏算 |
| `SCREEN/hmi_user_uart.c:82-87` | 每字节等待 TXE，发送后再等待 TC | 这两处 while 没有本地超时；单靠理论波特率没有建立故障时的有限上界 |
| `HARDWARE/hr_page.c:398-445` | 两路值/状态、多个文本、报警及 ProbeRefresh | 各原子输出字节数、报警变化和页面路径影响切片长度 |
| `HARDWARE/hr_page.c:818-850` | 主循环以及1s/10s/30s/60s/200ms周期任务 | 任务重合必须包含任务内部调用和 FrameFeed 本身的完整耗时 |

`test_timing_simulation.py:128-132` 的 `feed_frames()` 只出队并赋值时间；`:160` 的切片时长为预设 `(4.0,4.0,4.0,5.4)`；`:318-326` 的另一个压力模型使用预设 `(3.5,3.5,4.5,1.2,2.5,0.8,1.5)`，均非从实际编译 C 函数运行自动测得。模型的 150000/150000 仅证明模型事件数。其结果不能证明实际 CPU 完整 FrameFeed `<45us`、真实最坏源龄或实板零丢帧。

因此该证据的正确等级是 **`WCET_MODEL_ONLY`**。保留原 250SPS/50SPS、真实IRQ时标和 `[-10,2500]ms` 判据。完整 C 调用成本、FIFO多帧情况下的屏幕写负载、ISR抢占及错误路径耗时保持 **OPEN/NOT_MEASURED_ON_TARGET**；本合同不允许以连接实板来填补这些缺口。

## 3. ECG WSS 统计规则与独立原件复算

复算原件为 R5 ECG60 `owner-observed-ECG60-R5-55d99a50/joint` 的 `cloud-events-private.jsonl`、`T0.json`、`ARM_ATTEMPT.json` 和 B `blocks-private.bin/jsonl`。公开报告仅保留上述原件别名、字节数及 SHA；不复制载荷、UID、凭据或完整 Flash。

冻结联评器 `b5_channel_review.py:94-119` 先筛选 ARM 后、非 retained 的 Broker 消息，以 `telemetry_key=(node_id,stream,session_id,seq,timestamp)` 去重，保留与评价区间有源点交叠的波形批次，并调用 `b5_g3_review.match_batch` 用真实 B 原码/CAN 队列验证。`b5_channel_review.py:163-168` 的 seen 集合允许 WSS `server_time` 在 **`[start,end+15000)`**，要求 VALID 与 Broker 原载荷值/样本完全一致；`:207` 输出的是 `len(expected & seen)`。评价快照覆盖检查与波形 seen 检查采用不同窗口，不能混为同一计数。

真实进程命令为 PowerShell 单引号 here-string Python 输入后接 `python -X utf8 -B -`；两次只读复算进程退出码均为 **0**。第一次按冻结逻辑调用 `old.reconstruct`、`g.can_utc_points` 和 `old.match_batch` 完整验证 expected；第二次补充分界统计。未运行联评器 CLI，未调用其 `g.save` 或写回历史结果。输出见同目录 `WSS-RECOUNT.json`，包含工具/输入SHA、集合SHA和尾段新增键的SHA摘要。

| 集合/口径 | 原件复算 |
|---|---:|
| ARM后非retained去重Broker消息 | 2867 |
| 通过源原码/CAN匹配的冻结 expected ECG keys | **751** |
| 其中批次末点 timestamp 在评价区间内 | 750 |
| 其中批次末点在评价终点之后、但批次内仍有评价源点 | 1 |
| 评价期内 observed∩expected | **739** |
| 评价期内另外观察到的非expected ECG key | 1 |
| 评价期内全部观察到的 ECG keys | **740** |
| 原冻结规则（含15s尾段）的 observed∩expected | **741** |
| 尾段新增 expected keys | **2** |
| 原冻结规则缺失 keys | **10 = 751−741** |
| source mapping errors | 0 |

边界核对：首个 expected 批次末点位于 start+230ms，最后一个 expected 末点位于 end+213ms；评价期额外观察到但不属于 expected 的旧批次末点为 start−170ms。尾段两项新增 expected 键首次观察时刻分别为 end+40ms、end+544ms。完整15s尾段还有继续产生的非expected实时批次，不能把 tail 中全部ECG keys当作评价expected集合。

所以“750理论批次、评价期740、尾段+1”的报告算术**不是冻结联评器的集合规则**。正式 JSON 的 **741** 和 **NOT_PASS/exit3** 原样保留；缺失10项仍成立，但应按 **751−741** 解释，不能删除边界批次、改规则或据此追认PASS。已有`750−740=10`仅是不同口径凑巧同值。

### 可复算核心代码

下面的代码是上述两次实际运行代码的合并版本；只读原件，调用冻结重建/匹配函数，不保存到 EFS。`FOLDER`须由操作者在离线环境中设为已登记的 ECG R5 joint 目录。本轮真正执行的目录即上一段记录的原件别名。

```python
import collections, json, sys
from pathlib import Path
sys.path.insert(0, str(Path.cwd() / 'node-b/tools'))
import b5_g3_review as old
import b5_g3_contract as g

def recount(FOLDER):
    folder = Path(FOLDER)
    t0 = json.loads((folder/'T0.json').read_text())
    arm = json.loads((folder/'ARM_ATTEMPT.json').read_text())
    start, end = t0['evaluation_UTC_ms']
    raw, can, clocks, _ = old.reconstruct(folder)
    index = g.can_utc_points(can, clocks)
    events = [json.loads(x) for x in (folder/'cloud-events-private.jsonl').read_text().splitlines()]
    messages, expected, errors = {}, set(), collections.Counter()
    for row in events:
        if row['kind'] != 'BROKER_RAW' or row['monotonic'] < arm['monotonic'] or row['data']['retain']:
            continue
        x = row['data']
        m = old.decode_mqtt(x['topic'], bytes.fromhex(x['payload_hex'])).model_dump()
        key = g.telemetry_key(m)
        if key in messages:
            assert messages[key] == m
            continue
        messages[key] = m
        if m['node_id'] != 'NODE-B' or m['stream'] not in ('ECG','RESP'):
            continue
        rate, count = (250,100) if m['stream'] == 'ECG' else (50,50)
        assert m['sample_rate'] == rate and len(m['samples']) == count
        if m['timestamp'] < start or m['timestamp']-(count-1)*(1000//rate) >= end:
            continue
        try:
            old.match_batch(m,index,can,raw)
            if m['stream'] == 'ECG': expected.add(key)
        except ValueError as error:
            errors[str(error)] += 1
    seen_eval, seen_tail = set(), set()
    for row in events:
        if row['kind'] != 'WSS_RAW': continue
        when = row['data']['server_time']
        for m in row['data'].get('streams',[]):
            key = g.telemetry_key(m)
            original = messages.get(key)
            if original and m['stream'] == 'ECG' and m['validity'] == 'VALID' and m['value'] == original['value'] and m['samples'] == original['samples']:
                if start <= when < end: seen_eval.add(key)
                if start <= when < end+15000: seen_tail.add(key)
    return {'expected':len(expected), 'evaluation_matching':len(expected & seen_eval),
            'evaluation_all_ecg':len(seen_eval), 'frozen_matching':len(expected & seen_tail),
            'frozen_missing':len(expected-seen_tail), 'mapping_errors':dict(errors)}
```

## 4. 仍未证明的事项

1. `REAL_CPU_WCET = NOT_MEASURED_ON_TARGET`；P1-A 不授予硬件测时权限。
2. `PHYSICAL_CAUSE_OF_ECG_GAP = UNKNOWN`；计数/集合核对不能确定空口、AT或CPU根因。
3. `R6_SINGLE_NEW_BUILD_CHAIN` 由主流程另行产出；此处不从旧两次产物拼装一个假身份。
4. 此复算只解释 ECG WSS 统计边界，不改变 R5正式失败，也不授权 P1-B、Gate F、候选安装或P2。
