"""R89 S4 RESP 定标：按已知 ΔR/呼吸率，对 RESP（r 单位）做正弦最小二乘拟合（不插值，抗缺段）与 30 s 窗带内 RMS；
再用同一口径计算 R87 P2 真人的带内 RMS，换算等效 ΔR。工程口径。"""
import sys, numpy as np
sys.path.insert(0, '..')
from load import load, hms, Y_PER_RESP_REL
from variants import ms
CAP = '../../r83-capture/'
def series(path):
    _, resp, _, rr = load(CAP + path)
    t = np.array([x[0] for x in resp]); v = np.array([x[1] * Y_PER_RESP_REL for x in resp])
    return t, v, rr
def fit(t, v, f):
    s = (t - t[0]) / 1000.0
    X = np.column_stack([np.sin(2*np.pi*f*s), np.cos(2*np.pi*f*s), np.ones_like(s), s])
    c, *_ = np.linalg.lstsq(X, v, rcond=None)
    res = v - X @ c
    return float(np.hypot(c[0], c[1])), float(res.std())
def band_rms(t, v, a, b, lo=0.1, hi=0.7):
    """30 s 窗：10 Hz 线性插值、去线性趋势、FFT 取 lo–hi Hz 的 RMS；同时给总 RMS 和主峰频率。"""
    out = []
    w = a
    while w + 30000 <= b:
        m = (t >= w) & (t < w + 30000)
        if m.sum() < 1000: w += 15000; continue
        g = np.arange(w, w + 30000, 100.0); x = np.interp(g, t[m], v[m])
        s = np.arange(len(x)); x = x - np.polyval(np.polyfit(s, x, 1), s)
        X = np.fft.rfft(x); f = np.fft.rfftfreq(len(x), 0.1)
        sel = (f >= lo) & (f <= hi)
        out.append((w, float(np.sqrt(2 * (abs(X[sel]) ** 2).sum()) / len(x)), float(x.std()), float(f[sel][np.argmax(abs(X[sel]))] * 60)))
        w += 15000
    return out
t, v, rr = series('r89cal-20261118T100701Z-node-ab.jsonl')
steps = [('20/min 1.5R', 1.5, 20, ms(18,11,0)), ('20/min 1.0R', 1.0, 20, ms(18,12,55)),
         ('20/min 0.5R', 0.5, 20, ms(18,14,45)), ('12/min 1.0R', 1.0, 12, ms(18,16,48))]
print('step         | window   | n     | sine amp (r) | p-p (r) | residual SD | amp/ΔR (r/Ω) | 30s band RMS (r) | peak /min')
rows = []
for name, dr, rpm, s0 in steps:
    for a, b, lab in ((s0 + 10000, s0 + 90000, '+10..90'), (s0 + 30000, s0 + 90000, '+30..90')):
        m = (t >= a) & (t < b)
        amp, res = fit(t[m], v[m], rpm / 60)
        br = band_rms(t, v, s0 + 30000, s0 + 90000)
        bs = ' '.join(f'{x[1]:.0f}' for x in br); pk = ' '.join(f'{x[3]:.0f}' for x in br)
        print(f'{name:12s} | {lab:8s} | {m.sum():5d} | {amp:12.0f} | {2*amp:7.0f} | {res:11.0f} | {amp/dr:12.0f} | {bs:16s} | {pk}')
        if lab == '+30..90': rows.append((dr, rpm, amp, br))
# 线性：20/min 三档振幅对 ΔR 过原点拟合
d = np.array([r[0] for r in rows if r[1] == 20]); A = np.array([r[2] for r in rows if r[1] == 20])
k = float((d @ A) / (d @ d)); k2 = np.polyfit(d, A, 1)
print(f'20/min amplitude vs ΔR: through-origin slope {k:.0f} r/Ω; free fit slope {k2[0]:.0f}, intercept {k2[1]:.0f} r')
# 真人 P2（R87）同口径带内 RMS
th, vh, _ = series('r87-20261118T083445Z-node-ab.jsonl')
hb = band_rms(th, vh, ms(16,41,40), ms(16,47,51))
hv = np.array([x[1] for x in hb])
print(f'R87 P2 human 30s band RMS (0.1–0.7 Hz): median {np.median(hv):.0f} r, range {hv.min():.0f}–{hv.max():.0f}; total SD median {np.median([x[2] for x in hb]):.0f}')
# 正弦：band RMS = amp/√2
print(f'human equivalent sinusoid amplitude: median {np.median(hv)*np.sqrt(2):.0f} r → ΔR ≈ {np.median(hv)*np.sqrt(2)/k:.2f} Ω (range {hv.min()*np.sqrt(2)/k:.2f}–{hv.max()*np.sqrt(2)/k:.2f}) using {k:.0f} r/Ω')
