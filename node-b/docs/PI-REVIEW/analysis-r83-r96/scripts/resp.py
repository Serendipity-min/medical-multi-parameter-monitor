"""RESP 离线复盘：滤波呼吸波形的幅度、主周期（自相关）以及移植 respiration()+accept_cycle 的重放原因码。"""
import sys, math, statistics, collections
from load import load, hms, Y_PER_RESP_REL
from hr import Periods, NO_CYCLES
from variants import ms

def replay_resp(samples, maximum=10000, timeout=12000, required=3, tol=None):
    per = Periods(1500, maximum, timeout, required)
    band, prev, prev2, trough, trough_t, armed = 0.0, 0.0, 0.0, 0.0, 0, False
    out, peaks = [], []
    for t, r in samples:
        band += .02 * (r * r - band)          # 原算法 .004/样本@250Hz；50Hz 下等效 .02
        gate = max(20.0, .6 * math.sqrt(max(band, 0.0)))
        if prev2 > prev and prev <= r and (not armed or prev < trough):
            trough, trough_t, armed = prev, t, True
        if prev2 < prev and prev >= r and armed and prev - trough > 2 * gate and t - trough_t >= 300:
            armed = False; peaks.append(t); per.accept(t)
        prev2, prev = prev, r
        per.expire(t)
        reason = per.reason | (NO_CYCLES if not per.rate else 0)
        out.append((t, reason == 0, per.rate if reason == 0 else 0, reason))
    return out, peaks

def dominant_period(xs, fs=50, lo=3.0, hi=14.0):
    m = statistics.fmean(xs); x = [v - m for v in xs]
    e = sum(v * v for v in x) or 1
    best = (0, 0)
    for lag in range(int(lo * fs), int(hi * fs)):
        c = sum(x[i] * x[i + lag] for i in range(0, len(x) - lag, 2)) / e * 2
        if c > best[0]: best = (c, lag / fs)
    return best

if __name__ == '__main__':
    _, resp, _, rr = load(sys.argv[1])
    s = [(int(t), v * Y_PER_RESP_REL) for t, v, _, _ in resp]
    t0 = ms(15, 4, 0)
    print('window   | p2p r  | std r | dominant period (corr) | replay R codes | peaks: intervals ms')
    out, peaks = replay_resp(s)
    for w in range(t0, s[-1][0], 30000):
        seg = [v for t, v in s if w <= t < w + 30000]
        if len(seg) < 500: continue
        corr, per_s = dominant_period(seg)
        codes = collections.Counter(x[3] for x in out if w <= x[0] < w + 30000)
        pk = [p for p in peaks if w <= p < w + 30000]
        ivs = [b - a for a, b in zip(pk, pk[1:])]
        print(f'{hms(w)[:8]} | {max(seg)-min(seg):6.0f} | {statistics.pstdev(seg):5.0f} | {per_s:5.1f} s ({corr:.2f})        | '
              f'{" ".join(f"{k}:{100*v/sum(codes.values()):.0f}%" for k, v in codes.most_common(3)):18s} | {ivs}')
