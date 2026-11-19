"""R87 vs R89 S5：ECG（滤波后，uV）连续段频谱分带占比、TP 段噪声（PPG 无关，用 B 峰检锚点后 550–800 ms）。"""
import sys, numpy as np, math
sys.path.insert(0, '..')
from load import load, hms, UV_PER_Y
from variants import ms
CAP = '../../r83-capture/'
def run(name, path, A, B):
    ecg, _, hr, _ = load(CAP + path)
    t = np.array([x[0] for x in ecg]); v = np.array([x[1] * 1000 / UV_PER_Y * UV_PER_Y for x in ecg])  # uV
    m = (t >= A) & (t < B); t, v = t[m], v[m]
    # 连续段（相邻 ≤6 ms）≥4 s 才做谱
    cut = np.where(np.diff(t) > 6)[0] + 1; segs = np.split(np.arange(len(t)), cut)
    bands = [(0.5, 5), (5, 15), (15, 25), (25, 45), (45, 55), (55, 125)]
    P = np.zeros(len(bands)); tot = 0
    for s in segs:
        if len(s) < 1000: continue
        x = v[s][:len(s) // 1000 * 1000]
        for k in range(0, len(x), 1000):
            seg = x[k:k + 1000] - x[k:k + 1000].mean(); X = abs(np.fft.rfft(seg * np.hanning(1000))) ** 2; f = np.fft.rfftfreq(1000, 1 / 250)
            tot += X[f >= .5].sum(); P += [X[(f >= a) & (f < b)].sum() for a, b in bands]
    print(f'{name}: ' + ' | '.join(f'{a}-{b} Hz {100*p/tot:4.1f}%' for (a, b), p in zip(bands, P)))
run('R87 P2', 'r87-20261118T083445Z-node-ab.jsonl', ms(16,42,0), ms(16,47,51))
run('R89 S5 all', 'r89human-20261118T102758Z-node-ab.jsonl', ms(18,33,0), ms(18,43,30))
for a in range(33, 44):
    run(f'  R89 18:{a}', 'r89human-20261118T102758Z-node-ab.jsonl', ms(18,a,0), ms(18,a+1,0))
