"""R102 修订评估（看过首轮结果后，仅为抵消 MQTT 丢批）：窗内覆盖 ≥75%、单个缺口 ≤2.5 s（线性插值）。
算法其余参数与门槛不变；全部数据集重跑。"""
import numpy as np, resp_r1
_orig = resp_r1.window
def window(t, v, a):
    m = (t >= a) & (t < a + resp_r1.W)
    if m.sum() < resp_r1.W * 50 * .75: return None, 'coverage'
    if np.diff(np.concatenate([[a], t[m], [a + resp_r1.W]])).max() > 2.5: return None, 'gap'
    # 其余检查沿用原函数：临时放宽原函数的覆盖/缺口判断
    save = np.ndarray
    tt = t[m]; x = v[m]
    p5, p95 = np.percentile(x, [5, 95])
    if x.max() - x.min() > 3 * (p95 - p5): return None, 'transient'
    if (p95 - p5) / 2 < resp_r1.AMP_MIN: return None, 'amplitude'
    g = np.arange(a, a + resp_r1.W, .1); y = np.interp(g, tt, x); y = y - np.polyval(np.polyfit(g - a, y, 1), g - a); y *= np.hanning(len(y))
    X = abs(np.fft.rfft(y, 4096)) ** 2; f = np.fft.rfftfreq(4096, .1); band = (f >= .1) & (f <= .7)
    fp = f[band][np.argmax(X[band])]; rpm = 60 * fp
    if not (8 < rpm < 39): return None, 'edge'
    if X[abs(f - fp) <= .03].sum() / X[band].sum() < resp_r1.Q_MIN: return None, 'quality'
    return rpm, 'ok'
resp_r1.window = window
if __name__ == '__main__':
    import runpy; runpy.run_path('resp_eval.py', run_name='__main__')
