"""R100 诊断（不影响判定）：节拍段整段（开始 10 s 后到段末，约 80 s）各信号在 0.05–0.7 Hz 的频谱，
报主峰、节拍频率处 ±0.02 Hz 的功率占比，以及该占比在 0.1–0.7 Hz 内的名次。信号：PPG 的 RIFV/RIAV/RIIV、PPG 原始低通基线、B 的 RESP。"""
import numpy as np, datetime
from load2 import load, runs, UV_PER_Y
from ppg_rr import beat_features
from r100_eval import SEG, w, fmt
def spec(t, v, fs):
    g = np.arange(t[0], t[-1], 1 / fs); x = np.interp(g, t, v); x = x - np.polyval(np.polyfit(g - g[0], x, 1), g - g[0])
    x *= np.hanning(len(x)); n = 8192; X = abs(np.fft.rfft(x, n)) ** 2; f = np.fft.rfftfreq(n, 1 / fs); return f, X
def rep(name, t, v, fs, target):
    if len(t) < 10: return f'{name}: -'
    f, X = spec(np.array(t), np.array(v), fs); band = (f >= .1) & (f <= .7)
    ft = target / 60; lobe = abs(f - ft) <= .02; share = X[lobe].sum() / X[band].sum()
    pk = f[band][np.argmax(X[band])] * 60
    # 名次：把 0.1–0.7 Hz 按 0.04 Hz 分箱，节拍箱的功率排第几
    edges = np.arange(.1, .72, .04); pw = [X[(f >= a) & (f < a + .04)].sum() for a in edges[:-1]]
    k = int((ft - .1) // .04); rank = 1 + sum(p > pw[k] for p in pw) if 0 <= k < len(pw) else None
    return f'{name}: peak {pk:4.1f}/min, share@target {100*share:4.1f}%, rank {rank}/{len(pw)}'
ppg = w['ppg']; resp = [(x[0], x[1] / 0.11920928955 * 1000) for x in w['resp']]
for name, a, b, target in SEG:
    if not target: continue
    A, B = (a + 10) * 1000, b * 1000
    beats = []
    for r in runs([x for x in ppg if A - 5000 <= x[0] < B + 5000], 20): beats += beat_features(r)
    beats = [x for x in beats if A / 1000 <= x[0] < B / 1000]
    out = [f'== {name} target {target}/min, {fmt(a+10)}-{fmt(b)}, PPG beats kept {len(beats)}']
    for k, nm in ((1, 'RIFV'), (2, 'RIAV'), (3, 'RIIV')):
        out.append('  ' + rep(nm, [x[0] for x in beats], [x[k] for x in beats], 4, target))
    p = [x for x in ppg if A <= x[0] < B]
    out.append('  ' + rep('PPG raw', [x[0] / 1000 for x in p], [x[1] for x in p], 10, target))
    rs = [x for x in resp if A <= x[0] < B]
    out.append('  ' + rep('B RESP', [x[0] / 1000 for x in rs], [x[1] for x in rs], 10, target))
    rr_b = [x for x in []]
    print('\n'.join(out))
# B 板上 RR/HR、A 的 PR 在各段
from r100_eval import sc
for name, a, b, target in SEG:
    rr = [x for x in sc['rr'] if a*1000 <= x[0] < b*1000]; hr = [x for x in sc['hr'] if a*1000 <= x[0] < b*1000]
    pr = [x[1] for x in sc['pr'] if a*1000 <= x[0] < b*1000 and x[2] == 'VALID']
    rv = [x[1] for x in rr if x[2] == 'VALID']; hv = [x[1] for x in hr if x[2] == 'VALID']
    print(f'{name:4s} B RR valid {len(rv)}/{len(rr)} {sorted(set(int(v) for v in rv))[:6]} | B HR valid {len(hv)}/{len(hr)} med {np.median(hv) if hv else 0} | A PR med {np.median(pr) if pr else 0}')
