"""R91 复测逐分钟：缺样率、INVALID 批占比、削顶迹象（|y| 极大）、分带绝对 RMS、PPG 锁定 QRS 峰峰与单拍 SNR、B 板上 HR 有效与 A PR。"""
import sys, json, numpy as np, bisect, datetime
sys.path.insert(0, '..')
from load import load, UV_PER_Y
TZ = datetime.timezone(datetime.timedelta(hours=8))
def ms(h, m, s=0): return int(datetime.datetime(2026, 11, 19, h, m, s, tzinfo=TZ).timestamp() * 1000)
P = '../../r83-capture/r91human-20261119T072140Z-node-ab.jsonl'
ecg, resp, hr, rr = load(P)
t = np.array([x[0] for x in ecg]); v = np.array([x[1] * 1000 for x in ecg]); ok = np.array([x[2] for x in ecg])
ppg, pr = [], []
for l in open(P):
    r = json.loads(l)
    if r['topic'].endswith('NODE-A/telemetry/ppg'):
        p = json.loads(r['payload']); st = 1000 / p['sample_rate']
        ppg += [(p['timestamp'] + i * st, x) for i, x in enumerate(p['samples'])]
    elif r['topic'].endswith('NODE-A/telemetry/pr'):
        p = json.loads(r['payload']); pr.append((p['timestamp'], p['value'], p['validity']))
ppg.sort(); pt = np.array([x[0] for x in ppg]); pv = np.array([x[1] for x in ppg], float)
def peaks(A, B):
    m = (pt >= A) & (pt < B)
    if m.sum() < 200: return []
    tt, vv = pt[m], pv[m]; sm = vv - np.convolve(vv, np.ones(51), 'same') / np.convolve(np.ones_like(vv), np.ones(51), 'same'); thr = sm.std() * .5  # 滑动均值两端按实际点数归一，避免补零抬高阈值
    out, last = [], -1e9
    for i in range(1, len(sm) - 1):
        if sm[i] > thr and sm[i] >= sm[i-1] and sm[i] > sm[i+1] and tt[i] - last > 400: out.append(tt[i]); last = tt[i]
    return out
def bands(tt, vv):
    cut = np.where(np.diff(tt) > 6)[0] + 1; Pw = np.zeros(4); n = 0
    for s in np.split(np.arange(len(tt)), cut):
        x = vv[s]
        for k in range(0, len(x) - 499, 500):
            seg = x[k:k+500] - x[k:k+500].mean(); X = abs(np.fft.rfft(seg)) ** 2 * 2 / 500 ** 2; f = np.fft.rfftfreq(500, 1/250)
            Pw += [X[(f >= a) & (f < b)].sum() for a, b in [(0.5, 5), (5, 25), (25, 45), (45, 55)]]; n += 1
    return np.sqrt(Pw / max(n, 1))
print('min    miss inv%  max|y|uV  rms   0.5-5 5-25 25-45 45-55 | beats QRSpp  SNR | B HR valid | A PR valid med')
for a in range(ms(15,28), ms(16,4,30), 60000):
    b = a + 60000; m = (t >= a) & (t < b)
    lab = datetime.datetime.fromtimestamp(a / 1000, TZ).strftime('%H:%M')
    if m.sum() < 500: print(lab, 'too few ecg', m.sum()); continue
    tt, vv = t[m], v[m]; bd = bands(tt, vv); rms = vv.std()
    pk = peaks(a, b); acc, n = np.zeros(250), 0
    for p in pk:
        i0 = bisect.bisect_left(t, p - 900)
        if i0 + 250 < len(t) and abs(t[i0 + 249] - (p - 900 + 996)) < 20: acc += v[i0:i0+250]; n += 1
    if n >= 10:
        avg = acc / n; avg -= np.median(avg); i = int(np.argmax(abs(avg))); qpp = np.ptp(avg[max(0, i-25):i+25]); snr = abs(avg[i]) / rms
    else: qpp = snr = float('nan')
    bh = [x for x in hr if a <= x[0] < b]; ap = [x[1] for x in pr if a <= x[0] < b and x[2] == 'VALID']
    print(f'{lab}  {100-100*m.sum()/15000:3.0f}% {100*(1-ok[m].mean()):4.0f}% {abs(vv).max():8.0f} {rms:5.0f}  {bd[0]:5.0f} {bd[1]:4.0f} {bd[2]:5.0f} {bd[3]:5.0f} | {n:4d} {qpp:5.0f} {snr:4.2f} | {sum(x[2]=="VALID" for x in bh):2d}/{len(bh):2d} | {len(ap):2d} {np.median(ap) if ap else 0:4.0f}')
