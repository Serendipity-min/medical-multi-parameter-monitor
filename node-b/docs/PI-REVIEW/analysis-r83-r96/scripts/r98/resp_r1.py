"""R102 候选 R1：B 阻抗 RESP（滤波后 r，50 Hz）窗内谱峰 RR。参数见 R102 §1，写定后不改。"""
import numpy as np
W, STEP, AMP_MIN, Q_MIN, AGREE = 32.0, 2.0, 60.0, .50, 2.0
RPM_MIN = 8.0   # R125 固件改为 9.5；默认保持 R102 冻结值
def window(t, v, a):
    m = (t >= a) & (t < a + W)
    if m.sum() < W * 50 * .9: return None, 'coverage'
    tt = t[m]
    if np.diff(np.concatenate([[a], tt, [a + W]])).max() > 1.0: return None, 'gap'
    x = v[m]; p5, p95 = np.percentile(x, [5, 95])
    if x.max() - x.min() > 3 * (p95 - p5): return None, 'transient'
    if (p95 - p5) / 2 < AMP_MIN: return None, 'amplitude'
    g = np.arange(a, a + W, .1); y = np.interp(g, tt, x); y = y - np.polyval(np.polyfit(g - a, y, 1), g - a); y *= np.hanning(len(y))
    X = abs(np.fft.rfft(y, 4096)) ** 2; f = np.fft.rfftfreq(4096, .1); band = (f >= .1) & (f <= .7)
    fp = f[band][np.argmax(X[band])]; rpm = 60 * fp
    if not (RPM_MIN < rpm < 39): return None, 'edge'
    q = X[abs(f - fp) <= .03].sum() / X[band].sum()
    if q < Q_MIN: return None, 'quality'
    return rpm, 'ok'
def run(t, v, A, B):
    """t 秒、v r；返回 [(窗末时刻, 输出或 None, 单窗估计或 None, 原因)]"""
    out, hist = [], []
    for c in np.arange(A + W, B + 1e-9, STEP):
        e, why = window(t, v, c - W)
        hist = (hist + [e])[-3:]
        val = None
        if len(hist) == 3 and all(h is not None for h in hist) and max(hist) - min(hist) <= AGREE:
            val = float(np.median(hist))
        out.append((c, val, e, why))
    return out
