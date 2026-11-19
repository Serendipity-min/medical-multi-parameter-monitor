"""R94 实时副本：10 s 粒度 ECG 幅度/分带、PPG 锁定 QRS（30 s 窗）、B 板 HR 帧，看“贴好后短暂有效、随后无效”的原因。"""
import sys, json, numpy as np, bisect, datetime
sys.path.insert(0, '..')
from load import load
TZ = datetime.timezone(datetime.timedelta(hours=8))
def ms(h, m, s=0): return int(datetime.datetime(2026, 11, 19, h, m, s, tzinfo=TZ).timestamp() * 1000)
P = sys.argv[1]
ecg, resp, hr, rr = load(P)
t = np.array([x[0] for x in ecg]); v = np.array([x[1] * 1000 for x in ecg]); ok = np.array([x[2] for x in ecg])
ppg = []
for l in open(P):
    r = json.loads(l)
    if r['topic'].endswith('NODE-A/telemetry/ppg'):
        p = json.loads(r['payload']); st = 1000 / p['sample_rate']; ppg += [(p['timestamp'] + i * st, x) for i, x in enumerate(p['samples'])]
ppg.sort(); pt = np.array([x[0] for x in ppg]); pv = np.array([x[1] for x in ppg], float)
def band(x):
    f = np.fft.rfftfreq(len(x), 1/250); X = abs(np.fft.rfft(x - x.mean())) ** 2 * 2 / len(x) ** 2
    return [np.sqrt(X[(f >= a) & (f < b)].sum()) for a, b in [(0.5, 5), (5, 25), (25, 45), (45, 55)]]
H = {int(x[0] // 1000): (x[1], x[2]) for x in hr}
print('10s    n   inv%  p1     p99    rms  | 0.5-5 5-25 25-45 45-55 | B HR')
for s in range(ms(17, 7, 30), int(t[-1]), 10000):
    m = (t >= s) & (t < s + 10000)
    if m.sum() < 500: print(datetime.datetime.fromtimestamp(s/1000, TZ).strftime('%T'), 'few', m.sum()); continue
    x = v[m]; b = band(x[:len(x)//250*250])
    hs = ''.join(('H' if H.get(k, (0, ''))[1] == 'VALID' else '.') for k in range(s // 1000, s // 1000 + 10))
    vals = sorted(set(int(H[k][0]) for k in range(s // 1000, s // 1000 + 10) if k in H and H[k][1] == 'VALID'))
    print(datetime.datetime.fromtimestamp(s/1000, TZ).strftime('%T'), f'{m.sum():4d} {100*(1-ok[m].mean()):4.0f} {np.percentile(x,1):6.0f} {np.percentile(x,99):6.0f} {x.std():6.0f} | {b[0]:5.0f} {b[1]:4.0f} {b[2]:5.0f} {b[3]:5.0f} | {hs} {vals}')
def ens(A, B):
    m = (pt >= A) & (pt < B); tt, vv = pt[m], pv[m]
    sm = vv - np.convolve(vv, np.ones(51), 'same') / np.convolve(np.ones_like(vv), np.ones(51), 'same'); thr = sm.std() * .5; last = -1e9
    acc = np.zeros(250); n = 0
    for i in range(1, len(sm) - 1):
        if sm[i] > thr and sm[i] >= sm[i-1] and sm[i] > sm[i+1] and tt[i] - last > 400:
            last = tt[i]; i0 = bisect.bisect_left(t, tt[i] - 900)
            if i0 + 250 < len(t) and abs(t[i0+249] - (tt[i] - 900 + 996)) < 20: acc += v[i0:i0+250]; n += 1
    if n < 10: return n, float('nan'), float('nan'), 0
    a = acc / n; a -= np.median(a); k = int(np.argmax(abs(a))); me = (t >= A) & (t < B)
    return n, np.ptp(a[max(0, k-25):k+25]), abs(a[k]) / v[me].std(), k * 4 - 900
for A in range(ms(17, 8, 0), int(t[-1]) - 20000, 30000):
    n, pp, snr, lag = ens(A, A + 30000)
    print('ensemble', datetime.datetime.fromtimestamp(A/1000, TZ).strftime('%T'), f'beats {n} QRS p-p {pp:.0f} uV SNR {snr:.2f} lag {lag}')
