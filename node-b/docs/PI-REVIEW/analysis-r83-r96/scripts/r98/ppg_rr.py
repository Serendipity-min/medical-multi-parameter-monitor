"""R98 阶段1 RR：A 的 PPG 逐拍呼吸调制（RIAV/RIIV/RIFV）+ 质量 + 融合。参数在看结果前冻结：
带通 0.5–5 Hz 检峰（距离 ≥0.33 s，显著性 ≥0.3σ）；逐拍剔除：间期不在 0.33–2 s 或偏离 11 拍中位数 >30%、幅度偏离中位数 >3 MAD；
特征 4 Hz 重采样，拍间 >2 s 不插值；窗 32 s（另报 64 s），步长 2 s；0.1–0.7 Hz 内主峰占带内功率 ≥0.30 才算合格；
≥2 个合格特征相差 ≤3 次/分才输出（取均值）。离线非因果，仅作可行性筛选。"""
import numpy as np
from scipy.signal import butter, filtfilt, find_peaks
from load2 import runs
FS = 50.0
def beat_features(run):
    t = np.array([x[0] for x in run]) / 1000.0; v = np.array([x[1] for x in run], float)
    if len(v) < FS * 20: return []
    b, a = butter(2, [0.5 / (FS / 2), 5 / (FS / 2)], 'band'); bp = filtfilt(b, a, v)
    bl, al = butter(2, 5 / (FS / 2)); lp = filtfilt(bl, al, v)
    pk, _ = find_peaks(bp, distance=int(.33 * FS), prominence=.3 * bp.std())
    out = []
    for k in range(1, len(pk)):
        i0, i1 = pk[k - 1], pk[k]
        tr = i0 + int(np.argmin(lp[i0:i1 + 1]))
        out.append((t[i1], t[i1] - t[i0], lp[i1] - lp[tr], (lp[i1] + lp[tr]) / 2))
    if len(out) < 11: return []
    arr = np.array(out); keep = []
    for k in range(len(arr)):
        lo, hi = max(0, k - 5), min(len(arr), k + 6)
        mi = np.median(arr[lo:hi, 1]); ma = np.median(arr[lo:hi, 2]); mad = np.median(abs(arr[lo:hi, 2] - ma)) + 1e-12
        if .33 <= arr[k, 1] <= 2 and abs(arr[k, 1] - mi) <= .3 * mi and abs(arr[k, 2] - ma) <= 3 * mad * 1.4826: keep.append(k)
    return [tuple(arr[k]) for k in keep]
def series(beats, which):
    """which: 1=RIFV 2=RIAV 3=RIIV；返回 4 Hz 网格段列表 [(t0, values)]"""
    segs, cur = [], []
    for b in beats:
        if cur and b[0] - cur[-1][0] > 2.0: segs.append(cur); cur = []
        cur.append(b)
    if cur: segs.append(cur)
    out = []
    for s in segs:
        if len(s) < 8: continue
        tt = np.array([x[0] for x in s]); vv = np.array([x[which] for x in s])
        g = np.arange(tt[0], tt[-1], .25); out.append((g, np.interp(g, tt, vv)))
    return out
def est(g, v, A, W):
    m = (g >= A) & (g < A + W)
    if m.sum() < W * 4 * .9: return None
    x = v[m] - np.polyval(np.polyfit(g[m] - A, v[m], 1), g[m] - A); x *= np.hanning(len(x))
    n = 4096; X = abs(np.fft.rfft(x, n)) ** 2; f = np.fft.rfftfreq(n, .25)
    band = (f >= .1) & (f <= .7)
    if X[band].sum() <= 0: return None
    j = np.argmax(X[band]); fpk = f[band][j]
    lob = (f >= fpk - .03) & (f <= fpk + .03)
    q = X[lob].sum() / X[band].sum()
    return 60 * fpk, q
def rr(ppg, A, B, W=32, step=2, qmin=.30, agree=3.0):
    beats = []
    for r in runs([x for x in ppg if A - W * 1000 <= x[0] < B], 20): beats += beat_features(r)
    beats.sort()
    feats = {k: series(beats, k) for k in (1, 2, 3)}
    out = []
    for c in np.arange(A / 1000 + W, B / 1000 + .001, step):
        a0 = c - W; per = {}
        for k, segs in feats.items():
            for g, v in segs:
                e = est(g, v, a0, W)
                if e: per[k] = e
        ok = {k: e for k, e in per.items() if e[1] >= qmin}
        val = None
        ks = sorted(ok, key=lambda k: -ok[k][1])
        for i in range(len(ks)):
            for j in range(i + 1, len(ks)):
                if abs(ok[ks[i]][0] - ok[ks[j]][0]) <= agree and val is None:
                    val = (ok[ks[i]][0] + ok[ks[j]][0]) / 2
        out.append((c, val, per, len(beats)))
    return out
