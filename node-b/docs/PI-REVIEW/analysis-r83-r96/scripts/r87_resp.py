"""R87 RESP：10 Hz 重采样（缺段线性插值），每 30 s 窗去线性趋势后 DFT，给 0.05–0.7 Hz 主峰与各频段占比；并打印 0.5 s 均值序列。"""
import sys, math, cmath, statistics
from load import load, hms, Y_PER_RESP_REL
from variants import ms
_, resp, _, rr = load(sys.argv[1])
s = [(t, v * Y_PER_RESP_REL) for t, v, _, _ in resp]
T0, T1 = int(s[0][0]) // 100 * 100 + 100, int(s[-1][0]) // 100 * 100
g, j = [], 0
for t in range(T0, T1, 100):           # 10 Hz 线性插值
    while s[j + 1][0] < t: j += 1
    (ta, a), (tb, b) = s[j], s[j + 1]
    g.append((t, a + (b - a) * (t - ta) / (tb - ta) if tb > ta else a))
def spec(x, fs=10):
    n = len(x); xs = range(n); mx = (n - 1) / 2; my = statistics.fmean(x)
    b = sum((i - mx) * (y - my) for i, y in zip(xs, x)) / sum((i - mx) ** 2 for i in xs)
    x = [(y - my - b * (i - mx)) * (0.5 - 0.5 * math.cos(2 * math.pi * i / (n - 1))) for i, y in enumerate(x)]
    return [(k * fs / n, abs(sum(x[i] * cmath.exp(-2j * math.pi * k * i / n) for i in range(n))) ** 2) for k in range(1, int(2.2 * n / fs) + 1)]
bands = [(0.01, 0.07), (0.07, 0.15), (0.15, 0.25), (0.25, 0.6), (0.6, 2.2)]
print('win(30s)  | peak 0.05–0.7 Hz (/min) | ' + ' | '.join(f'{a}-{b}' for a, b in bands))
w = ms(*map(int, sys.argv[2].split(':'))) if len(sys.argv) > 2 else T0
while w + 30000 <= T1:
    x = [v for t, v in g if w <= t < w + 30000]
    sp = spec(x); tot = sum(p for f, p in sp if 0.01 <= f < 2.2) or 1
    pk = max(((f, p) for f, p in sp if 0.05 <= f <= 0.7), key=lambda z: z[1])
    print(f'{hms(w)[:8]} | {pk[0]:.3f} Hz ({60*pk[0]:4.1f}) {100*pk[1]/tot:4.0f}% | ' + ' | '.join(f'{100*sum(p for f,p in sp if a<=f<b)/tot:5.1f}' for a, b in bands))
    w += 15000
