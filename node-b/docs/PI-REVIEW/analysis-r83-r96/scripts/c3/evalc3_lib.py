"""C3 评测：有效率、与 PR 一致率、阴/阳性对照。"""
import sys, bisect, statistics
from data import HUMAN, NEG, POS, seg, noise, artifact
from algos import run
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

def report(CFG, go, extra_noise=True):
    names=[c['name'] for c in CFG]; tot={n:[0,0,[]] for n in names}
    print('=== human (valid% | paired within ±10%)')
    for name,(p,A,B) in HUMAN.items():
        d=seg(p,A,B); row=[f'{name:10s}']
        for c in CFG:
            v,pairs,ok,_,_=score(go(c,d['y']),d); n=c['name']
            tot[n][0]+=ok; tot[n][1]+=len(pairs); tot[n][2]+=[abs(r-q) for r,q in pairs]
            row.append(f'{n} {v:5.1f}% {ok}/{len(pairs)}')
        print(' | '.join(row))
    print('TOTAL agree: '+' | '.join(f'{n} {100*tot[n][0]/max(1,tot[n][1]):.0f}% ({tot[n][0]}/{tot[n][1]}) med|err| {statistics.median(tot[n][2]) if tot[n][2] else 0}' for n in names))
    print('=== negatives / positives (valid%, longest ms, values)')
    for grp in (NEG,POS):
        for name,(p,A,B) in grp.items():
            d=seg(p,A,B); row=[f'{name:14s}']
            for c in CFG:
                v,_,_,lg,vals=score(go(c,d['y']),d); row.append(f"{c['name']} {v:5.1f}% {lg} {vals[:3]}")
            print(' | '.join(row))
    if extra_noise:
        for c in CFG:
            vs=[];lgs=[]
            for sd in range(1,11):
                d=noise(sd,120); v,_,_,lg,_=score(go(c,d['y']),d); vs.append(v); lgs.append(lg)
            print(f"white noise x10 {c['name']}: mean {statistics.fmean(vs):.2f}% max {max(vs):.2f}% longest {max(lgs)} ms")
