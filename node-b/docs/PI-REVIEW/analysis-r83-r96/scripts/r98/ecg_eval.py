"""R98 阶段1 ECG 评测：修正时轴；有效率按整段观察时间逐秒计（无数据的秒计无效）；与 A 的 PR（±1 s）配对。"""
import sys, bisect, statistics, random, math, datetime
from load2 import load, UV_PER_Y
from ecg_cands import run
TZ = datetime.timezone(datetime.timedelta(hours=8))
CAP = '../../r83-capture/'
def ms(d, h, m, s=0): return int(datetime.datetime(2026, 11, d, h, m, s, tzinfo=TZ).timestamp() * 1000)
HUMAN = [('R87 P2', 'r87-20261118T083445Z-node-ab.jsonl', ms(18,16,42), ms(18,16,47,51)),
         ('R89 S5', 'r89human-20261118T102758Z-node-ab.jsonl', ms(18,18,33), ms(18,18,43,30)),
         ('R91', 'r91human-20261119T072140Z-node-ab.jsonl', ms(19,15,33,40), ms(19,16,3,40)),
         ('R94', 'r94human-20261119T090428Z-node-ab.jsonl', ms(19,17,8), ms(19,17,28)),
         ('R85 wrist', 'r85-20261118T074904Z-node-ab.jsonl', ms(18,15,58,40), ms(18,16,3,40)),
         ('R83 ankle', 'r83-20261118T065234Z-node-b.jsonl', ms(18,15,4,20), ms(18,15,9,30))]
NEG = [('R83 leads-off', 'r83-20261118T065234Z-node-b.jsonl', ms(18,15,0,15), ms(18,15,4,0)),
       ('R89 reconnect', 'r89sim-20261118T093511Z-node-ab.jsonl', ms(18,17,44,40), ms(18,17,45,40))]
POS = [('R83 sim60', 'r83-20261118T065234Z-node-b.jsonl', ms(18,14,59,21), ms(18,15,0,8)),
       ('R89 sim60', 'r89sim-20261118T093511Z-node-ab.jsonl', ms(18,17,41), ms(18,17,44,30)),
       ('R92 sim60', 'r92sim-20261119T082651Z-node-ab.jsonl', ms(19,16,31), ms(19,16,33,50))]
_c = {}
def data(f, A, B):
    if f not in _c: _c[f] = load(CAP + f)
    w, sc, _ = _c[f]
    return [(x[0], x[1] * 1000 / UV_PER_Y) for x in w['ecg'] if A - 20000 <= x[0] < B], [(t, v) for t, v, s in sc['pr'] if s == 'VALID' and v and A <= t < B]
def persec(o, A, B):
    d = {}
    for t, r in o:
        if A <= t < B: d[int(t // 1000)] = r
    return {s: d.get(s, 0) for s in range(A // 1000, B // 1000)}
def score(o, A, B, pr, ref=None):
    ps = persec(o, A, B); n = len(ps); v = [s for s, r in ps.items() if r]
    pt = [p[0] for p in pr]; pairs = []
    for s in v:
        if ref is not None: pairs.append((ps[s], ref)); continue
        i = bisect.bisect_left(pt, s * 1000)
        c = [pr[j] for j in (i - 1, i) if 0 <= j < len(pt) and abs(pt[j] - s * 1000) <= 1000]
        if c: pairs.append((ps[s], min(c, key=lambda z: abs(z[0] - s * 1000))[1]))
    ok = sum(abs(r - q) <= .1 * q for r, q in pairs)
    longest = cur = 0
    for s in sorted(ps): cur = cur + 1 if ps[s] else 0; longest = max(longest, cur)
    return 100 * len(v) / max(n, 1), ok, len(pairs), longest, sorted(set(ps[s] for s in v))
CANDS = sys.argv[1].split(',') if len(sys.argv) > 1 else ['C2', 'ALC+C2', 'NK', 'bSQI', 'bSQI+M', 'ALC+bSQI+M']
tot = {c: [0, 0, []] for c in CANDS}
print('=== human: coverage of observation seconds | PR-paired within ±10%')
for name, f, A, B in HUMAN:
    y, pr = data(f, A, B); row = [f'{name:9s}']
    for c in CANDS:
        cov, ok, n, _, _ = score(run(c, y), A, B, pr); tot[c][0] += ok; tot[c][1] += n
        row.append(f'{c} {cov:5.1f}% {ok}/{n}')
    print(' | '.join(row))
print('TOTAL PR agreement: ' + ' | '.join(f'{c} {100*tot[c][0]/max(1,tot[c][1]):.0f}% ({tot[c][0]}/{tot[c][1]})' for c in CANDS))
print('=== negatives (coverage, longest s, values) / positives (vs 60)')
for grp, ref in ((NEG, None), (POS, 60)):
    for name, f, A, B in grp:
        y, pr = data(f, A, B); row = [f'{name:13s}']
        for c in CANDS:
            cov, ok, n, lg, vals = score(run(c, y), A, B, pr, ref); row.append(f'{c} {cov:5.1f}% {lg}s {vals[:4]}' + (f' ok {ok}/{n}' if ref else ''))
        print(' | '.join(row))
