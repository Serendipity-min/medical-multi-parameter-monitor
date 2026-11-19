"""候选 D（第一轮后新增）：窗内周期估计。y →（可选 50 Hz 梳状）→ 导数 → 平方 → 150 ms 积分 → 抽到 50 Hz；
每 1 s 对最近 W 秒包络做归一化自相关，取 273–2000 ms 范围最高峰；峰值 ≥θ 且最近 4 s 半窗在同一周期（±10%）也 ≥θ2 才有效。
半周期检查：若 lag/2 处自相关 ≥0.8×峰值，改取 lag/2（防倍周期）。"""
import numpy as np
from algos import Comb, GAP
class PeriodHR:
    def __init__(s, W=8.0, theta=.4, theta2=.3, comb=True):
        s.W, s.th, s.th2, s.use_comb = W, theta, theta2, comb
        s.comb = Comb(); s.x = [0.0] * 5; s.win = [0.0] * 38; s.sum = 0.0; s.k = 0; s.fill = 0
        s.dec = 0; s.buf = []; s.next = None; s.rate = 0; s.lastt = None
    def reset(s):
        s.comb.reset(); s.x = [0.0] * 5; s.win = [0.0] * 38; s.sum = 0.0; s.fill = 0
    @staticmethod
    def acf(e, lo, hi):
        e = e - e.mean(); v = (e * e).mean()
        if v <= 0: return None
        return np.array([(e[:-l] * e[l:]).mean() / v for l in range(lo, hi + 1)])
    def estimate(s):
        e = np.array(s.buf, float); lo, hi = 14, 100          # 50 Hz：280–2000 ms
        r = s.acf(e, lo, hi)
        if r is None: return 0
        i = int(np.argmax(r)); pk = r[i]; lag = lo + i
        h = lag // 2
        if h >= lo and r[h - lo] >= .8 * pk: lag, pk = h, r[h - lo]
        if pk < s.th or lag in (lo, hi): return 0
        # 最近一半窗内同一周期仍明显
        half = e[len(e) // 2:]; r2 = s.acf(half, max(lo, int(lag * .9)), min(hi, int(lag * 1.1) + 1))
        if r2 is None or r2.max() < s.th2: return 0
        # 抛物线插值细化周期
        j = lag - lo
        if 0 < j < len(r) - 1:
            a, b, c = r[j - 1], r[j], r[j + 1]; den = a - 2 * b + c
            off = .5 * (a - c) / den if den != 0 else 0.0
        else: off = 0.0
        return round(60000 / ((lag + off) * 20))
    def step(s, t, y):
        if s.lastt is not None and t - s.lastt > GAP:
            s.reset()
            # 缺段按缺失时长补零（板上无缺段，这里只为重放）
            s.buf += [0.0] * min(int((t - s.lastt) / 20), int(s.W * 50)); s.buf = s.buf[-int(s.W * 50):]
        s.lastt = t
        x = s.comb(y) if s.use_comb else y
        s.x = s.x[1:] + [x]
        d = (2 * s.x[4] + s.x[3] - s.x[1] - 2 * s.x[0]) / 8.0
        s.sum += d * d - s.win[s.k]; s.win[s.k] = d * d; s.k = (s.k + 1) % 38; s.fill += 1
        s.dec += 1
        if s.dec >= 5:
            s.dec = 0; s.buf.append(s.sum / 38.0 if s.fill >= 43 else 0.0); s.buf = s.buf[-int(s.W * 50):]
        if s.next is None: s.next = t + 1000
        if t >= s.next:
            s.next += 1000
            s.rate = s.estimate() if len(s.buf) >= int(s.W * 50) else 0
        return s.rate
def run_d(y, **kw):
    a = PeriodHR(**kw); return [(t, a.step(t, v)) for t, v in y]
