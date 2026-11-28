"""R98 阶段1 ECG 候选（参数在看真人结果前冻结）：
C2      ：真实 C2 代码（drv.so）。
ALC+C2  ：50 Hz 自适应工频抵消（NLMS 正余弦参考，按时间戳求相位，|e|>3σ 时冻结更新，μ=0.01）后接 C2。
NK      ：NeuroKit2 'neurokit' 检测器（按连续段离线批处理，非因果）→ 8 间期判据。
bSQI    ：NK 与 'elgendi2010'（第一轮用 pantompkins1985，因模拟器上漏拍而更换）两检测器在最近 10 s 内的 F1≥0.9 才放行 → 8 间期判据。
bSQI+M  ：再要求最近 10 s 内各拍与窗内中位模板的相关 ≥0.8 的比例 ≥80%。
ALC+bSQI+M：前置 ALC。
8 间期判据：最近 8 个间期（同一连续段、≤2000 ms），中位数 ±20% 内 ≥5 个才有效；最后一拍后 4 s 失效。"""
import ctypes as C, math, statistics, bisect, numpy as np, warnings
import neurokit2 as nk
from load2 import runs
warnings.filterwarnings('ignore')
_lib = C.CDLL('./drv.so')
_lib.D_Init.argtypes = [C.c_uint32]; _lib.D_Feed.argtypes = [C.c_float, C.c_uint32]; _lib.D_Feed.restype = C.c_uint32

def alc(y):
    """y: [(t_ms, v)]，返回同长度去工频序列。"""
    a = b = 0.0; mu = .01; var = None; out = []; prev = None
    for t, v in y:
        if prev is not None and t - prev > 20: a = b = 0.0; var = None
        prev = t
        ph = 2 * math.pi * 50.0 * t / 1000.0; c, s = math.cos(ph), math.sin(ph)
        e = v - (a * c + b * s)
        var = e * e if var is None else var + .002 * (e * e - var)
        if e * e <= 9 * var:
            a += mu * e * c; b += mu * e * s
        out.append((t, e))
    return out

def c2(y):
    _lib.D_Init(int(y[0][0]) & 0xffffffff)
    return [(t, _lib.D_Feed(v, int(t) & 0xffffffff)) for t, v in y]

def beats(y, method):
    out = []
    for r in runs([(t, v, True, 0, 0) for t, v in y], 4):
        if len(r) < 1250: continue
        sig = np.array([x[1] for x in r]); tt = np.array([x[0] for x in r])
        try:
            _, info = nk.ecg_peaks(sig, sampling_rate=250, method=method, correct_artifacts=False)
            idx = np.asarray(info['ECG_R_Peaks'], int)
        except Exception:
            idx = np.array([], int)
        out.append((tt, sig, idx))
    return out   # 每段：时间、信号、峰索引

def med8(times, now):
    iv = [b - a for a, b in zip(times, times[1:]) if b - a <= 2000][-8:]
    if not times or now - times[-1] > 4000 or len(iv) < 5: return 0
    m = statistics.median(iv); inl = [x for x in iv if abs(x - m) <= .2 * m]
    return round(60000 / statistics.median(inl)) if len(inl) >= 5 else 0

def f1(ta, tb, tol=150):
    if not ta or not tb: return 0.0
    j = m = 0
    for x in ta:
        while j < len(tb) and tb[j] < x - tol: j += 1
        if j < len(tb) and abs(tb[j] - x) <= tol: m += 1; j += 1
    return 2 * m / (len(ta) + len(tb))

def gated(y, use_bsqi, use_morph, second='elgendi2010'):
    """跨连续段保留心搏历史；跨缺口的间期不计入（med8 只用同段相邻心搏的间期）。"""
    segs_a = beats(y, 'neurokit'); segs_b = beats(y, second) if use_bsqi else []
    ta, run_id, win = [], [], []
    for k, (tt, sig, ia) in enumerate(segs_a):
        for i in ia:
            ta.append(tt[i]); run_id.append(k)
            win.append(sig[i-12:i+13] if 12 <= i < len(sig) - 13 else None)
    tb = sorted(float(tt[i]) for tt, _, ib in segs_b for i in ib)
    if not segs_a: return []
    outs = []
    for s in range(int(y[0][0] // 1000) + 1, int(y[-1][0] // 1000) + 1):
        now = s * 1000; n = bisect.bisect_right(ta, now)
        iv = [ta[j] - ta[j-1] for j in range(1, n) if run_id[j] == run_id[j-1] and ta[j] - ta[j-1] <= 2000][-8:]
        r = 0
        if n and now - ta[n-1] <= 4000 and len(iv) >= 5:
            m = statistics.median(iv); inl = [x for x in iv if abs(x - m) <= .2 * m]
            if len(inl) >= 5: r = round(60000 / statistics.median(inl))
        if r and use_bsqi:
            wa = [x for x in ta[:n] if x > now - 10000]; wb = [x for x in tb if now - 10000 < x <= now]
            if f1(wa, wb) < .9: r = 0
        if r and use_morph:
            W = [win[j] for j in range(n) if ta[j] > now - 10000 and win[j] is not None]
            if len(W) < 5: r = 0
            else:
                W = np.array(W); tpl = np.median(W, axis=0)
                cs = [np.corrcoef(w, tpl)[0, 1] for w in W]
                if np.mean(np.array(cs) >= .8) < .8: r = 0
        outs.append((now, r))
    return outs

def run(name, y):
    if name == 'C2': return c2(y)
    if name == 'ALC+C2': return c2(alc(y))
    if name == 'NK': return gated(y, False, False)
    if name == 'bSQI': return gated(y, True, False)
    if name == 'bSQI+M': return gated(y, True, True)
    if name == 'ALC+bSQI+M': return gated(alc(y), True, True)
    raise ValueError(name)
