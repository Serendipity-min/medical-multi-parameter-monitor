import sys, math, random, statistics, collections
from load import load, UV_PER_Y
from hr import Periods, NO_CYCLES
from variants import P2, ms
from variants2 import P3

def replay(samples, mult=2.5, cls=Periods, wmin=12, margin=1.05, required=5):
    per = cls(273, 2000, 4000, required)
    band, in_peak, peak, gate, above, peak_t = 0.0, False, 0.0, 0.0, 0, 0
    out = []
    for t, y in samples:
        band += .004 * (y * y - band); a = abs(y)
        thr = max(30.0, mult * math.sqrt(max(band, 0.0)))
        if not in_peak and a >= thr: in_peak, above, peak, peak_t, gate = True, t, a, t, thr
        elif in_peak:
            if a > peak: peak, peak_t = a, t
            if a < gate * .5 or t - above > 200:
                w = t - above; in_peak = False
                if wmin <= w <= 160 and peak >= gate * margin: per.accept(peak_t)
        per.expire(t)
        reason = per.reason | (NO_CYCLES if not per.rate else 0)
        out.append((t, reason == 0, per.rate if reason == 0 else 0, reason))
    return out

if __name__ == '__main__':
    ecg, *_ = load(sys.argv[1])
    seg = lambda a, b: [(int(t), mv * 1000 / UV_PER_Y) for t, mv, _, _ in ecg if a <= t < b]
    human, sim, off = seg(ms(15,4,20), ms(15,9,30)), seg(0, ms(15,0,8)), seg(ms(15,0,15), ms(15,4,0))
    noises = []
    for sd in (1, 2, 3):
        rng = random.Random(sd); noises.append([(i * 4, rng.gauss(0, 150)) for i in range(250 * 300)])
    for name, kw in [('C1', dict()), ('C1 tol ±30%', dict(cls=P3)), ('tol ±30% w>=8', dict(cls=P3, wmin=8)),
                     ('tol ±30% w>=8 m1.0', dict(cls=P3, wmin=8, margin=1.0)), ('tol ±30% w>=4 m1.0', dict(cls=P3, wmin=4, margin=1.0))]:
        row = [f'{name:20s}']
        for s in (human, sim, off):
            r = replay(s, **kw); v = [x[2] for x in r if x[1]]
            row.append(f'{100*len(v)/len(r):5.1f}% {statistics.median(v) if v else 0:4.0f}')
        nf = [100 * sum(x[1] for x in replay(n, **kw)) / len(n) for n in noises]
        row.append('noise ' + '/'.join(f'{x:.1f}%' for x in nf))
        r = replay(human, **kw)
        row.append('human codes ' + ' '.join(f'{k}:{100*v/len(r):.0f}%' for k, v in collections.Counter(x[3] for x in r).most_common(3)))
        print(' | '.join(row))
    print('cols: human | simulator60 | leads-off | white noise x3 | human reason mix')
