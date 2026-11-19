"""以 A 的 PPG 峰为心搏时标，对 B 的 ECG 做集合平均，估计真实 QRS 幅度与噪声。"""
import sys, json, math, statistics, datetime
from load import load, hms
tz = datetime.timezone(datetime.timedelta(hours=8))
def ms(h, m, s): return int(datetime.datetime(2026, 11, 18, h, m, s, tzinfo=tz).timestamp() * 1000)
path = sys.argv[1]
ppg = []
for l in open(path):
    r = json.loads(l)
    if r['topic'].endswith('NODE-A/telemetry/ppg'):
        p = json.loads(r['payload']); step = 1000 / p['sample_rate']
        for i, v in enumerate(p['samples']): ppg.append((p['timestamp'] + i * step, v))
ppg.sort()
print('ppg samples', len(ppg), hms(ppg[0][0]) if ppg else '-', '→', hms(ppg[-1][0]) if ppg else '-')
ecg, *_ = load(path)
def ppg_peaks(a, b):
    seg = [(t, v) for t, v in ppg if a <= t < b]
    if len(seg) < 100: return []
    vals = [v for _, v in seg]
    # 去趋势：减 1 s 滑动均值
    sm = []
    for i in range(len(vals)):
        w = vals[max(0, i - 25): i + 25]; sm.append(vals[i] - sum(w) / len(w))
    thr = statistics.pstdev(sm) * 0.5
    peaks, last = [], -1e9
    for i in range(1, len(sm) - 1):
        if sm[i] > thr and sm[i] >= sm[i - 1] and sm[i] > sm[i + 1] and seg[i][0] - last > 400:
            peaks.append(seg[i][0]); last = seg[i][0]
    return peaks
for a, b in [((15,58,40),(16,0,40)), ((16,0,40),(16,2,40)), ((16,2,40),(16,4,10))]:
    A, B = ms(*a), ms(*b)
    pk = ppg_peaks(A, B)
    if len(pk) < 20: print(hms(A)[:8], 'too few ppg peaks', len(pk)); continue
    hr = 60000 / statistics.median([y - x for x, y in zip(pk, pk[1:])])
    seg = [(t, mv * 1000) for t, mv, _, _ in ecg if A - 1000 <= t < B + 1000]
    ts = [t for t, _ in seg]; vs = [v for _, v in seg]
    import bisect
    L = 250  # 1 s 窗：峰前 800 ms 到峰后 200 ms，250 Hz
    acc = [0.0] * L; n = 0
    for p in pk:
        i0 = bisect.bisect_left(ts, p - 800)
        if i0 + L >= len(ts) or abs(ts[i0 + L - 1] - (p - 800 + 996)) > 20: continue
        for k in range(L): acc[k] += vs[i0 + k]
        n += 1
    avg = [x / n for x in acc]
    pp = max(avg) - min(avg); imax = max(range(L), key=lambda k: abs(avg[k]))
    noise = math.sqrt(statistics.fmean(v * v for v in vs))
    print(f'{hms(A)[:8]}-{hms(B)[:8]} | PPG HR {hr:5.1f} | beats averaged {n} | ensemble QRS p-p {pp:6.0f} uV at {(imax*4-800)} ms before PPG peak | raw band RMS {noise:6.1f} uV | expected single-beat SNR (pk/RMS) {max(abs(x) for x in avg)/noise:.2f}')
