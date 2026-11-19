import sys, math, cmath, statistics, datetime
from load import load, hms
tz = datetime.timezone(datetime.timedelta(hours=8))
def ms(h, m, s): return int(datetime.datetime(2026, 11, 18, h, m, s, tzinfo=tz).timestamp() * 1000)
bands = [(0.5, 5), (5, 15), (15, 30), (30, 45), (45, 55), (55, 80), (80, 125)]
def spec(vals, fs=250, n=1024):
    acc = [0.0] * (n // 2)
    segs = 0
    for s in range(0, len(vals) - n, n // 2):
        x = vals[s:s + n]; m = sum(x) / n
        w = [(x[i] - m) * (0.5 - 0.5 * math.cos(2 * math.pi * i / n)) for i in range(n)]
        for k in range(1, n // 2):
            z = sum(w[i] * cmath.exp(-2j * math.pi * k * i / n) for i in range(0, n, 2)) # 粗略：抽半点
            acc[k] += abs(z) ** 2
        segs += 1
        if segs >= 6: break
    return [(k * fs / n, a) for k, a in enumerate(acc)]
for path, label, a, b in [
    ('../r83-capture/r83-20261118T065234Z-node-b.jsonl', 'R83 simulator', (14,59,30), (15,0,5)),
    ('../r83-capture/r83-20261118T065234Z-node-b.jsonl', 'R83 ankles', (15,7,10), (15,8,10)),
    ('../r83-capture/r85-20261118T074904Z-node-ab.jsonl', 'R85 P1 wrists', (16,0,40), (16,1,40))]:
    ecg, *_ = load(path)
    vals = [mv * 1000 for t, mv, _, _ in ecg if ms(*a) <= t < ms(*b)]
    sp = spec(vals); tot = sum(p for f, p in sp if 0.5 <= f < 125) or 1
    rms = math.sqrt(statistics.fmean(v * v for v in vals))
    print(f'{label:14s} RMS {rms:6.1f} uV | ' + ' '.join(f'{lo}-{hi}Hz {100*sum(p for f,p in sp if lo<=f<hi)/tot:4.1f}%' for lo, hi in bands))
