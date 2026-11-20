"""R100 探索（非冻结，不作判定）：B 的阻抗 RESP（滤波后 r）用 32 s 窗谱峰估计呼吸率，逐窗与节拍对照。
窗口与 R100 §4 相同（节拍段开始 10 s 后，完全落在段内）；主峰限 8–39 次/分；报占比 q。"""
import numpy as np
from load2 import runs
from r100_eval import SEG, w, fmt
resp = [(x[0] / 1000, x[1] / 0.11920928955 * 1000) for x in w['resp']]
t = np.array([x[0] for x in resp]); v = np.array([x[1] for x in resp])
def est(a, W=32):
    m = (t >= a) & (t < a + W)
    if m.sum() < W * 50 * .8: return None
    g = np.arange(a, a + W, .1); x = np.interp(g, t[m], v[m]); x = x - np.polyval(np.polyfit(g - a, x, 1), g - a); x *= np.hanning(len(x))
    X = abs(np.fft.rfft(x, 4096)) ** 2; f = np.fft.rfftfreq(4096, .1); band = (f >= 8 / 60) & (f <= 39 / 60)
    j = np.argmax(X[band]); fp = f[band][j]; q = X[abs(f - fp) <= .03].sum() / X[(f >= .1) & (f <= .7)].sum()
    return 60 * fp, q
for name, a, b, target in SEG:
    cs = [c for c in np.arange(a + 10 + 32, b + 1e-6, 2)] if target else [c for c in np.arange(a + 32, b + 1e-6, 2)]
    e = [est(c - 32) for c in cs]; e = [x for x in e if x]
    if not e: print(f'{name:4s} -'); continue
    vals = [round(x[0], 1) for x in e]; qs = [round(x[1], 2) for x in e]
    s = f'{name:4s} {fmt(a)}-{fmt(b)} windows {len(e)} median {np.median(vals):.1f}/min'
    if target: s += f' | within±2 of {target}: {sum(abs(x-target)<=2 for x in vals)}/{len(vals)} | with q≥0.5: {sum(1 for x,q in zip(vals,qs) if q>=.5)} of which within±2 {sum(1 for x,q in zip(vals,qs) if q>=.5 and abs(x-target)<=2)}'
    s += f'\n      values {vals[:14]}\n      q      {qs[:14]}'
    print(s)
