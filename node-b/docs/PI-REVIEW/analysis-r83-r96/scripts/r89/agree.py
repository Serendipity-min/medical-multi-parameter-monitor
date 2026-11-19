"""C1/C2 重放 HR 与 A 的 PR（VALID）一致性：逐秒配对（PR 取 ±1 s 内最近值）与每 10 s 中位数。"""
import json, bisect, statistics
exec(open('replay_rec.py').read().split("e87, *_")[0])
path = CAP + 'r87-20261118T083445Z-node-ab.jsonl'
pr = []
for l in open(path):
    r = json.loads(l)
    if r['topic'].endswith('NODE-A/telemetry/pr'):
        p = json.loads(r['payload'])
        if p['validity'] == 'VALID' and p['value']: pr.append((p['timestamp'], p['value']))
pr.sort(); pt = [t for t, _ in pr]
e87, *_ = load(path)
A, B = ms(16, 42, 0), ms(16, 47, 51)
y = [(int(t), mv * 1000 / UV_PER_Y) for t, mv, _, _ in e87 if ms(16, 41, 40) <= t < B]
for k, l in libs.items():
    o = [x for x in run(l, y) if A <= x[0] < B]
    sec = {}
    for t, v in o:
        if v: sec[t // 1000] = v
    pairs = []
    for s, v in sec.items():
        i = bisect.bisect_left(pt, s * 1000)
        c = [pr[j] for j in (i - 1, i) if 0 <= j < len(pr) and abs(pr[j][0] - s * 1000) <= 1000]
        if c: pairs.append((v, min(c, key=lambda z: abs(z[0] - s * 1000))[1]))
    within = sum(abs(v - q) <= 0.1 * q for v, q in pairs)
    ad = statistics.median(abs(v - q) for v, q in pairs)
    win = []
    for w in range(A, B, 10000):
        bv = [v for t, v in o if w <= t < w + 10000 and v]; pv = [q for t, q in pr if w <= t < w + 10000]
        if bv and pv: win.append(100 * abs(statistics.median(bv) - statistics.median(pv)) / statistics.median(pv))
    print(f'{k}: valid-seconds {len(sec)}, paired {len(pairs)}, within±10% {within} ({100*within/len(pairs):.0f}%), '
          f'median|diff| {ad} bpm, 10s-window median diff {min(win):.1f}-{max(win):.1f}% (n {len(win)}, >10%: {sum(x>10 for x in win)})')
