"""R126：R125 §5 模拟器验收判读（MQTT 原件）。在 r124_sim_eval 的四项之上加 R124 §3 三个问题的硬门槛；采集前提交，采集后只填 JSON。
用法：python3 -s -E r126_sim_eval.py <现场记录.json>（字段同 r124_sim_eval）。新增门槛：
  连续性（§3.1）：各 RESP 档开始 +45 s 到结束，ECG 样本丢失 ≤7%（C2 时期 2.0–6.5%），相邻缺口间隔落在 2.00±0.05 s 的比例 ≤5%（C2 0–1.4%，R1 首版 38–40%）；
  有效的 0（§3.2）：全程 HR、RR 的 VALID 帧中值为 0 或空的帧数 = 0；
  ECG 模式 RR（§3.3）：ECG 段开始到结束后 10 s（含断电前）RR 的 VALID 帧数 = 0。"""
import json, subprocess, sys, numpy as np
from r109_eval import get, frames
from r122_eval import at
from load2 import runs
if __name__ == '__main__':
    F = json.load(open(sys.argv[1], encoding='utf-8')); f = F['capture']; d = F['day']
    out = subprocess.run([sys.executable, '-s', '-E', 'r124_sim_eval.py', sys.argv[1]], capture_output=True, text=True, check=True).stdout
    print(out, end=''); ok_all = [out.rstrip().endswith('PASS（ECG、各档 RR、断开 ERA）') or out.rstrip().endswith('PASS（ECG、各档 RR）')]
    w, sc, _ = get(f)
    print('=== R124 §3 三项（R125 新增门槛）')
    for L in F['resp']:
        a, b = at(d, L['start']) + 45000, at(d, L['end'])
        s = [x for x in w['ecg'] if a <= x[0] < b]; seg = runs(s, 4.0)
        gaps = [(p[-1][0], q[0][0] - p[-1][0]) for p, q in zip(seg, seg[1:])]
        loss = sum(g for _, g in gaps) / (b - a); t = np.array([x[0] for x in gaps])
        per = float(np.mean(np.abs(np.diff(t) / 1000 - 2.0) <= .05)) if len(t) > 1 else 0.0
        ok = loss <= .07 and per <= .05; ok_all.append(ok)
        print(f'§3.1 连续性 {L["rate"]} 次/分档：ECG 丢失 {100 * loss:.1f}%（≤7%），缺口 {len(gaps)} 个，间隔≈2.00 s 占 {100 * per:.1f}%（≤5%）→ {"PASS" if ok else "FAIL"}')
    z = {k: [x for x in sc[k] if x[2] == 'VALID' and not x[1]] for k in ('hr', 'rr')}
    ok = not z['hr'] and not z['rr']; ok_all.append(ok)
    print(f'§3.2 有效的 0：HR {len(z["hr"])} 帧、RR {len(z["rr"])} 帧 → {"PASS" if ok else "FAIL"}')
    a, b = (at(d, x) for x in F['ecg']); b += 10000
    v = [x for x in frames(sc['rr'], a, b) if x[2] == 'VALID']; ok = not v; ok_all.append(ok)
    print(f'§3.3 ECG 模式 RR：{F["ecg"][0]} 起至结束后 10 s，RR VALID {len(v)} 帧，值 {sorted(set(x[1] for x in v))} → {"PASS" if ok else "FAIL"}')
    print(f'=== R125 §5 判定 → {"PASS" if all(ok_all) else "FAIL"}')
