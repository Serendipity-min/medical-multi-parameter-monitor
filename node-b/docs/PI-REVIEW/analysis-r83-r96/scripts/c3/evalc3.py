"""C3 评测：有效率、与 PR 一致率、阴/阳性对照。"""
import sys, bisect, statistics
from data import HUMAN, NEG, POS, seg, noise, artifact
from algos import run
ALGOS = sys.argv[1].split(',') if len(sys.argv) > 1 else ['C2', 'A+C2', 'B+C2', 'B+C', 'A+B+C']
def score(o, d):
    w = [(t, r) for t, r in o if d['A'] <= t < d['B']]
    valid = 100 * sum(1 for _, r in w if r) / max(1, len(w))
    sec = {}
    for t, r in w:
        if r: sec[t // 1000] = r
    pt = [p[0] for p in d['pr']]; pairs = []
    for s, r in sec.items():
        i = bisect.bisect_left(pt, s * 1000)
        c = [d['pr'][j] for j in (i - 1, i) if 0 <= j < len(pt) and abs(pt[j] - s * 1000) <= 1000]
        if c: q = min(c, key=lambda z: abs(z[0] - s * 1000))[1]; pairs.append((r, q))
    ok = sum(abs(r - q) <= .1 * q for r, q in pairs)
    longest = cur = 0; lastt = None
    for t, r in w:
        cur = cur + (t - lastt if lastt is not None and r else 0) if r else 0; lastt = t; longest = max(longest, cur)
    vals = sorted(set(r for _, r in w if r))
    return valid, pairs, ok, longest, vals
print('=== human (valid% | paired within ±10% | median abs err)')
tot = {a: [0, 0, []] for a in ALGOS}
for name, (p, A, B) in HUMAN.items():
    d = seg(p, A, B); row = [f'{name:10s}']
    for a in ALGOS:
        v, pairs, ok, _, _ = score(run(a, d['y']), d)
        tot[a][0] += ok; tot[a][1] += len(pairs); tot[a][2] += [abs(r - q) for r, q in pairs]
        row.append(f'{a:6s} {v:5.1f}% {ok:3d}/{len(pairs):3d}')
    print(' | '.join(row))
print('TOTAL agree: ' + ' | '.join(f'{a} {100*tot[a][0]/max(1,tot[a][1]):.0f}% med|err| {statistics.median(tot[a][2]) if tot[a][2] else 0}' for a in ALGOS))
print('=== negatives / positives (valid% , longest valid ms, values)')
for grp in (NEG, POS):
    for name, (p, A, B) in grp.items():
        d = seg(p, A, B); row = [f'{name:14s}']
        for a in ALGOS:
            v, _, _, lg, vals = score(run(a, d['y']), d); row.append(f'{a} {v:5.1f}% {lg:5d} {vals[:3]}{"…" if len(vals)>3 else ""}')
        print(' | '.join(row))
