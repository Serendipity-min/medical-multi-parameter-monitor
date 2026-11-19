"""R87 阶段定位：RESP 每 2 s 的去趋势幅度（屏气 = 低幅平台）和缺段。"""
import sys, statistics
from load import load, hms, gaps, Y_PER_RESP_REL
ecg, resp, hr, rr = load(sys.argv[1])
print('ECG gaps', [(hms(t)[:12], int(d)) for t, d in gaps(ecg, 4)][:60])
print('RESP gaps', [(hms(t)[:12], int(d)) for t, d in gaps(resp, 20)][:60])
s = [(t, v * Y_PER_RESP_REL) for t, v, _, _ in resp]
t0 = s[0][0]
w = t0 - t0 % 2000
line = []
while w < s[-1][0]:
    seg = [v for t, v in s if w <= t < w + 2000]
    if len(seg) > 20:
        n = len(seg); xs = range(n); mx = (n - 1) / 2; my = statistics.fmean(seg)
        b = sum((x - mx) * (y - my) for x, y in zip(xs, seg)) / sum((x - mx) ** 2 for x in xs)
        res = [y - my - b * (x - mx) for x, y in zip(xs, seg)]
        line.append(f'{hms(w)[3:8]} {statistics.pstdev(res):5.0f} {my:8.0f}')
    w += 2000
for i in range(0, len(line), 5): print(' | '.join(line[i:i+5]))
