"""阶段0 对照：旧（批首）与新（批末）时间展开下的 PPG 连续性、峰间隔、ECG–PPG 延迟、PPG 锁定 QRS 集合平均。"""
import sys, numpy as np, bisect, datetime
from load2 import load, runs
TZ = datetime.timezone(datetime.timedelta(hours=8))
CAP = '../../r83-capture/'
def ms(d, h, m, s=0): return int(datetime.datetime(2026, 11, d, h, m, s, tzinfo=TZ).timestamp() * 1000)
SETS = [('R87', 'r87-20261118T083445Z-node-ab.jsonl', ms(18,16,42), ms(18,16,47,51)),
        ('R89', 'r89human-20261118T102758Z-node-ab.jsonl', ms(18,18,36,41), ms(18,18,43,30)),
        ('R91a', 'r91human-20261119T072140Z-node-ab.jsonl', ms(19,15,39), ms(19,15,48)),
        ('R94', 'r94human-20261119T090428Z-node-ab.jsonl', ms(19,17,8,20), ms(19,17,28))]
def ppg_peaks(ppg, A, B):
    pk = []
    for r in runs([x for x in ppg if A <= x[0] < B], 20):
        if len(r) < 100: continue
        t = np.array([x[0] for x in r]); v = np.array([x[1] for x in r], float)
        sm = v - np.convolve(v, np.ones(51), 'same') / np.convolve(np.ones_like(v), np.ones(51), 'same')
        thr = sm.std() * .5; last = -1e9
        for i in range(1, len(sm) - 1):
            if sm[i] > thr and sm[i] >= sm[i-1] and sm[i] > sm[i+1] and t[i] - last > 400: pk.append(t[i]); last = t[i]
    return pk
def ensemble(ecg, pk, lo=-1200, n=375):
    t = np.array([x[0] for x in ecg]); v = np.array([x[1] * 1000 for x in ecg]); acc = np.zeros(n); k = 0
    for p in pk:
        i0 = bisect.bisect_left(t, p + lo)
        if i0 + n < len(t) and abs(t[i0 + n - 1] - (p + lo + (n - 1) * 4)) < 20: acc += v[i0:i0+n]; k += 1
    a = acc / max(k, 1); a -= np.median(a); j = int(np.argmax(abs(a)))
    return k, np.ptp(a[max(0, j-25):j+25]), lo + j * 4, a
for name, f, A, B in SETS:
    for mode in (False, True):
        w, sc, bt = load(CAP + f, end_stamp=mode)
        ecg = [x for x in w['ecg'] if A - 2000 <= x[0] < B + 2000]
        ppg = w['ppg']; pr = runs([x for x in ppg if A <= x[0] < B], 20)
        overl = sum(1 for a, b in zip(ppg, ppg[1:]) if A <= a[0] < B and b[0] - a[0] <= 0)
        pk = ppg_peaks(ppg, A, B); iv = np.diff(pk)
        k, pp, lag, _ = ensemble(ecg, pk)
        e = np.array([x[1] * 1000 for x in ecg if A <= x[0] < B]); snr = (pp / 2) / e.std()
        print(f'{name:5s} {"END " if mode else "HEAD"} ppg runs {len(pr):3d} overlaps {overl:3d} | peaks {len(pk)} iv p10/50/90 {np.percentile(iv,[10,50,90]).round()} | beats {k} QRS p-p {pp:4.0f} uV at {lag:+5d} ms vs PPG peak | p-p/2÷RMS {snr:.2f}')
