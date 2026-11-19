"""D2：在 D 基础上加 (1) 连续两次估计相差 ≤5% 才报有效；(2) 周期范围 333–1500 ms（40–180 bpm）。"""
from algo_d import PeriodHR
import numpy as np
class PeriodHR2(PeriodHR):
    def __init__(s, persist=2, lo=17, hi=75, **kw):
        super().__init__(**kw); s.persist, s.lo, s.hi = persist, lo, hi; s.hist = []
    def estimate(s):
        e = np.array(s.buf, float); lo, hi = s.lo, s.hi
        r = s.acf(e, lo, hi)
        if r is None: return 0
        i = int(np.argmax(r)); pk = r[i]; lag = lo + i
        h = lag // 2
        if h >= lo and r[h - lo] >= .8 * pk: lag, pk = h, r[h - lo]
        if pk < s.th or lag in (lo, hi): return 0
        half = e[len(e) // 2:]; r2 = s.acf(half, max(lo, int(lag * .9)), min(hi, int(lag * 1.1) + 1))
        if r2 is None or r2.max() < s.th2: return 0
        j = lag - lo
        a, b, c = (r[j-1], r[j], r[j+1]) if 0 < j < len(r) - 1 else (0, 1, 0)
        den = a - 2 * b + c; off = .5 * (a - c) / den if den != 0 and 0 < j < len(r) - 1 else 0.0
        return round(60000 / ((lag + off) * 20))
    def step(s, t, y):
        prev = s.next
        r = super().step(t, y)
        if s.next != prev:                     # 本样本刚做过一次估计
            s.hist = (s.hist + [r])[-s.persist:]
            ok = len(s.hist) == s.persist and all(s.hist) and max(s.hist) <= 1.05 * min(s.hist)
            s.rate = r if ok else 0
        return s.rate
def run_d2(y, **kw):
    a = PeriodHR2(**kw); return [(t, a.step(t, v)) for t, v in y]
