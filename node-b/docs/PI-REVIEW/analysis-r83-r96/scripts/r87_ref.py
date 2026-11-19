"""R87 呼吸参照：A 的 PPG 基线（呼吸致强度变化）和 PPG 心搏间期（RSA）在 0.05–0.7 Hz 的主峰，与 B RESP 主峰逐窗对比。"""
import sys, json, math, cmath, statistics
from load import load, hms, Y_PER_RESP_REL
from variants import ms
path = sys.argv[1]
ppg, rates = [], set()
for l in open(path):
    r = json.loads(l)
    if r['topic'].endswith('NODE-A/telemetry/ppg'):
        p = json.loads(r['payload']); step = 1000 / p['sample_rate']; rates.add(p['sample_rate'])
        for i, v in enumerate(p['samples']): ppg.append((p['timestamp'] + i * step, v))
ppg.sort()
print('ppg rates', rates, len(ppg))
def grid(s, step=100):
    T0, T1 = int(s[0][0]) // step * step + step, int(s[-1][0]) // step * step
    g, j = [], 0
    for t in range(T0, T1, step):
        while s[j + 1][0] < t: j += 1
        (ta, a), (tb, b) = s[j], s[j + 1]
        g.append((t, a + (b - a) * (t - ta) / (tb - ta) if tb > ta else a))
    return g
def spec(x, fs=10):
    n = len(x); mx = (n - 1) / 2; my = statistics.fmean(x)
    b = sum((i - mx) * (y - my) for i, y in enumerate(x)) / sum((i - mx) ** 2 for i in range(n))
    x = [(y - my - b * (i - mx)) * (0.5 - 0.5 * math.cos(2 * math.pi * i / (n - 1))) for i, y in enumerate(x)]
    return [(k * fs / n, abs(sum(x[i] * cmath.exp(-2j * math.pi * k * i / n) for i in range(n))) ** 2) for k in range(1, int(0.8 * n / fs) + 1)]
def top(x):
    if len(x) < 200: return "      -       "
    sp = [z for z in spec(x) if 0.05 <= z[0] <= 0.7]; tot = sum(p for _, p in sp) or 1
    f, p = max(sp, key=lambda z: z[1]); return f'{60*f:4.1f}/min {100*p/tot:3.0f}%'
# PPG 基线：1 s 滑动均值后 10 Hz
pg = grid(ppg)
base = [(t, statistics.fmean(v for _, v in pg[max(0, i - 5): i + 5])) for i, (t, _) in enumerate(pg)]
# PPG 心搏：去 1 s 均值后找峰
pk, last = [], -1e9
d = [(t, v - b) for (t, v), (_, b) in zip(pg, base)]
for i in range(1, len(d) - 1):
    thr = statistics.pstdev(x for _, x in d[max(0, i - 50): i + 50]) * 0.5 if i % 1 == 0 else 0
    if d[i][1] > thr and d[i][1] >= d[i-1][1] and d[i][1] > d[i+1][1] and d[i][0] - last > 400:
        pk.append(d[i][0]); last = d[i][0]
ibi = [(b, b - a) for a, b in zip(pk, pk[1:]) if 400 < b - a < 1500]
ig = grid(ibi)
_, resp, _, _ = load(path)
rg = grid([(t, v * Y_PER_RESP_REL) for t, v, _, _ in resp])
print('win(30s)  | B RESP         | PPG baseline   | PPG IBI (RSA)')
w = ms(16, 41, 0)
while w + 30000 <= ms(16, 47, 52):
    sel = lambda g: [v for t, v in g if w <= t < w + 30000]
    print(f'{hms(w)[:8]} | {top(sel(rg))} | {top(sel(base))} | {top(sel(ig))}')
    w += 15000
