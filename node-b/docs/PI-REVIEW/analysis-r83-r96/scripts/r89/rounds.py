"""四轮真人采集同口径对比：PPG 锁定的 ECG 集合平均（波形形态与峰峰值）、带内噪声分带绝对值（uV）、单拍 SNR、缺样率。"""
import sys, json, numpy as np, statistics, bisect
sys.path.insert(0, '..')
from load import load, hms, UV_PER_Y
from variants import ms
CAP = '../../r83-capture/'
def ppg_peaks(path, A, B):
    ppg = []
    for l in open(path):
        r = json.loads(l)
        if r['topic'].endswith('NODE-A/telemetry/ppg'):
            p = json.loads(r['payload']); st = 1000 / p['sample_rate']
            ppg += [(p['timestamp'] + i * st, v) for i, v in enumerate(p['samples']) if A <= p['timestamp'] + i * st < B]
    ppg.sort()
    if len(ppg) < 200: return []
    t = np.array([x[0] for x in ppg]); v = np.array([x[1] for x in ppg], float)
    sm = v - np.convolve(v, np.ones(51) / 51, 'same'); thr = sm.std() * .5
    pk, last = [], -1e9
    for i in range(1, len(sm) - 1):
        if sm[i] > thr and sm[i] >= sm[i-1] and sm[i] > sm[i+1] and t[i] - last > 400: pk.append(t[i]); last = t[i]
    return pk
def bands(t, v):
    cut = np.where(np.diff(t) > 6)[0] + 1; P = np.zeros(4); n = 0
    B = [(0.5, 5), (5, 25), (25, 45), (45, 55)]
    for s in np.split(np.arange(len(t)), cut):
        x = v[s]
        for k in range(0, len(x) - 999, 1000):
            seg = x[k:k+1000] - x[k:k+1000].mean(); X = abs(np.fft.rfft(seg)) ** 2 * 2 / 1000 ** 2; f = np.fft.rfftfreq(1000, 1/250)
            P += [X[(f >= a) & (f < b)].sum() for a, b in B]; n += 1
    return np.sqrt(P / max(n, 1))
def run(name, path, A, B):
    ecg, *_ = load(CAP + path)
    t = np.array([x[0] for x in ecg]); v = np.array([x[1] * 1000 for x in ecg])   # uV
    m = (t >= A) & (t < B); tt, vv = t[m], v[m]
    pk = ppg_peaks(CAP + path, A, B)
    acc, n = np.zeros(250), 0
    for p in pk:
        i0 = bisect.bisect_left(t, p - 900)
        if i0 + 250 < len(t) and abs(t[i0 + 249] - (p - 900 + 996)) < 20: acc += v[i0:i0+250]; n += 1
    avg = acc / max(n, 1); avg -= np.median(avg)
    i = int(np.argmax(abs(avg)))
    shape = ' '.join(f'{avg[j]:+5.0f}' for j in range(max(0, i-10), min(250, i+16), 3))   # 每 12 ms
    b = bands(tt, vv); rms = vv.std()
    print(f'{name:22s} miss {100-100*len(tt)/((B-A)/4):4.0f}% | beats {n:3d} | QRS p-p {np.ptp(avg[max(0,i-25):i+25]):4.0f} uV peak {avg[i]:+5.0f} | band RMS {rms:4.0f} | 0.5-5 {b[0]:3.0f} 5-25 {b[1]:3.0f} 25-45 {b[2]:3.0f} 45-55 {b[3]:3.0f} uV | SNR {abs(avg[i])/rms:.2f}')
    print(f'{"":22s} shape around peak (12 ms step): {shape}')
run('R83 ankles', 'r83-20261118T065234Z-node-b.jsonl', ms(15,4,20), ms(15,9,30))
run('R85 wrists P1', 'r85-20261118T074904Z-node-ab.jsonl', ms(15,58,40), ms(16,3,40))
run('R87 P2 chest', 'r87-20261118T083445Z-node-ab.jsonl', ms(16,42,0), ms(16,47,51))
run('R89 S5 P2 chest', 'r89human-20261118T102758Z-node-ab.jsonl', ms(18,36,41), ms(18,43,30))
run('R89 S5 first 3 min', 'r89human-20261118T102758Z-node-ab.jsonl', ms(18,33,0), ms(18,36,31))
