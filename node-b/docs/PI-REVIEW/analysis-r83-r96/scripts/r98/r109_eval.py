"""R109：R108 按正确色标的复测评估（MQTT 原件，load2 批末时间轴）。
A RESP 重新定标：各档正弦最小二乘（同 R89 cal.py 的 fit），r 单位 = resp × 1000/0.1192；板上 RR 有效率。
B 模拟器心电核对：QRS 极性。
C 真人：B 的 HR 有效率（逐帧）、与 A 的 PR 配对（±1 s）±10% 一致率、QRS 极性、PPG 锁定的集合平均 QRS 峰峰值与单拍 SNR（同 R94 快照口径）、
  分带 RMS；同一函数计算 R87 P2、R94 作对照。
D RR：板上 RR 有效率；R102 的 R1 在节拍段只记录。时刻为现场报告值（误差约 ±3 s），每段开头 10 s 不计。"""
import bisect, datetime, numpy as np
from load2 import load
from qrs_polarity import polarity
import resp_r1
TZ = datetime.timezone(datetime.timedelta(hours=8))
CAP = '../../r83-capture/'
K = 1000 / 0.11920928955
def ms(d, h, m, s=0): return int(datetime.datetime(2026, 11, d, h, m, s, tzinfo=TZ).timestamp() * 1000)
_c = {}
def get(f):
    if f not in _c: _c[f] = load(CAP + f)
    return _c[f]
def fit(t, v, f, order=1):
    s = (t - t[0]) / 1000.0
    X = np.column_stack([np.sin(2 * np.pi * f * s), np.cos(2 * np.pi * f * s)] + [s ** k for k in range(order + 1)])
    c, *_ = np.linalg.lstsq(X, v, rcond=None)
    return float(np.hypot(c[0], c[1])), float((v - X @ c).std())
def frames(sc, A, B):
    return [x for x in sc if A <= x[0] < B]
def hr_metrics(f, A, B):
    w, sc, _ = get(f)
    hr = frames(sc['hr'], A, B); pr = [x for x in sc['pr'] if x[2] == 'VALID' and x[1]]
    v = [x for x in hr if x[2] == 'VALID']; pt = [x[0] for x in pr]; ok = n = 0
    for t, h, _ in v:
        i = bisect.bisect_left(pt, t); c = [pr[j] for j in (i - 1, i) if 0 <= j < len(pr) and abs(pr[j][0] - t) <= 1000]
        if c: n += 1; q = min(c, key=lambda z: abs(z[0] - t))[1]; ok += abs(h - q) <= .1 * q
    return len(v), len(hr), ok, n, (np.median([x[1] for x in v]) if v else 0)
def ecg_arrays(f, A, B):
    w, _, _ = get(f); e = [x for x in w['ecg'] if A <= x[0] < B]
    return np.array([x[0] for x in e]), np.array([x[1] * 1000 for x in e])   # ms, µV
def ensemble(f, A, B):
    """PPG 峰锁定的 ECG 集合平均（R94 快照口径）：QRS 峰峰值、单拍 SNR（|峰|/窗内 ECG 标准差）、相对 PPG 峰的时刻。"""
    w, _, _ = get(f); t, v = ecg_arrays(f, A - 1000, B + 1000)
    p = [x for x in w['ppg'] if A <= x[0] < B]
    if len(p) < 500 or len(t) < 2500: return None
    pt = np.array([x[0] for x in p]); pv = np.array([x[1] for x in p], float)
    sm = pv - np.convolve(pv, np.ones(51), 'same') / np.convolve(np.ones_like(pv), np.ones(51), 'same'); thr = .5 * sm.std(); last = -1e9
    acc = np.zeros(250); n = 0
    for i in range(1, len(sm) - 1):
        if sm[i] > thr and sm[i] >= sm[i - 1] and sm[i] > sm[i + 1] and pt[i] - last > 400:
            last = pt[i]; i0 = bisect.bisect_left(t, pt[i] - 900)
            if i0 + 250 < len(t) and abs(t[i0 + 249] - (pt[i] - 900 + 996)) < 20: acc += v[i0:i0 + 250]; n += 1
    if n < 10: return None
    a = acc / n; a -= np.median(a); k = int(np.argmax(abs(a))); me = (t >= A) & (t < B)
    # 稳健分母：10 s 块标准差的中位数，不受少数大幅伪迹段左右
    blk = [v[(t >= s) & (t < s + 10000)].std() for s in range(A, B - 9999, 10000) if ((t >= s) & (t < s + 10000)).sum() > 2000]
    return n, float(np.ptp(a[max(0, k - 25):k + 25])), float(abs(a[k]) / v[me].std()), k * 4 - 900, float(np.sign(a[k])), (float(abs(a[k]) / np.median(blk)) if blk else float('nan'))
def bands(f, A, B):
    t, v = ecg_arrays(f, A, B); out = []
    for s in range(A, B - 9999, 10000):
        x = v[(t >= s) & (t < s + 10000)]
        if len(x) < 2000: continue
        x = x[:len(x) // 250 * 250]; fr = np.fft.rfftfreq(len(x), 1 / 250); X = abs(np.fft.rfft(x - x.mean())) ** 2 * 2 / len(x) ** 2
        out.append([np.sqrt(X[(fr >= a) & (fr < b)].sum()) for a, b in [(0.5, 5), (5, 25), (45, 55)]])
    return np.median(out, axis=0) if out else [np.nan] * 3
def human_row(name, f, A, B):
    nv, nh, ok, n, med = hr_metrics(f, A, B); t, v = ecg_arrays(f, A, B)
    pn, pp, mp, mn = polarity(list(zip(t, v / 1000)))   # polarity 内部再 ×1000
    e = ensemble(f, A, B); b = bands(f, A, B)
    es = f'集合 {e[0]:3d} 拍 QRS p-p {e[1]:4.0f} µV SNR {e[2]:.2f}（稳健 {e[5]:.2f}）主峰{"正" if e[4] > 0 else "负"}' if e else '集合 不足'
    print(f'{name:22s} {(B - A) / 1000:5.0f} s | HR 有效 {nv:3d}/{nh:3d} ({100 * nv / max(nh, 1):4.0f}%) 中位 {med:5.1f} | PR±10% {ok:3d}/{n:3d} ({100 * ok / max(n, 1):4.0f}%)'
          f' | 主峰正向 {pp:5.1f}% | {es} | 0.5–5/5–25/45–55 Hz {b[0]:4.0f}/{b[1]:4.0f}/{b[2]:4.0f} µV')
R108 = 'r108human-20261120T061515Z-node-ab.jsonl'
if __name__ == '__main__':
    w, sc, _ = get(R108)
    rt = np.array([x[0] for x in w['resp']]); rv = np.array([x[1] * K for x in w['resp']])
    print('=== A RESP 重新定标（接法 绿→RA、黄→LL、红→RL；每档自开始 +15 s 至下一档开始）')
    levels = [('20/min 1.5R', 1.5, 20, ms(20,14,26,30), ms(20,14,28,38)), ('20/min 1.0R', 1.0, 20, ms(20,14,28,38), ms(20,14,30,42)),
              ('20/min 0.5R', 0.5, 20, ms(20,14,30,42), ms(20,14,32,45)), ('12/min 1.0R', 1.0, 12, ms(20,14,32,45), ms(20,14,34,40))]
    k, k2 = [], []
    for name, dr, rpm, a, b in levels:
        a += 15000; m = (rt >= a) & (rt < b); amp, res = fit(rt[m], rv[m], rpm / 60)
        rr = frames(sc['rr'], a, b); val = [x[1] for x in rr if x[2] == 'VALID']
        print(f'{name}: {(b - a) / 1000:.0f} s, n {m.sum()}, 正弦幅值 {amp:.0f} r（p-p {2 * amp:.0f}），残差 SD {res:.0f}，SNR {amp / res:.1f}，幅值/ΔR {amp / dr:.0f} r/R'
              f' | 板上 RR 有效 {len(val)}/{len(rr)} 值 {sorted(set(val))}')
        if rpm == 20: k.append((dr, amp))
        # 稳健：逐 10 s 块正弦拟合取中位数；块内 p95−p5 超过本档中位数 2 倍的块（调档、菜单操作瞬变）剔除
        blk = [(s0, (rt >= s0) & (rt < s0 + 10000)) for s0 in range(a, b - 9999, 10000)]
        blk = [(s0, mm) for s0, mm in blk if mm.sum() > 300]
        spread = np.array([np.subtract(*np.percentile(rv[mm], [95, 5])) for _, mm in blk]); keep = spread <= 2 * np.median(spread)
        fits = [fit(rt[mm], rv[mm], rpm / 60) for (_, mm), kp in zip(blk, keep) if kp]
        amp2 = float(np.median([x[0] for x in fits])); res2 = float(np.median([x[1] for x in fits]))
        print(f'   稳健（10 s 块拟合中位数，保留 {keep.sum()}/{len(keep)} 块）：幅值 {amp2:.0f} r（p-p {2 * amp2:.0f}），块内残差 SD {res2:.0f}，SNR {amp2 / res2:.1f}，幅值/ΔR {amp2 / dr:.0f} r/R')
        if rpm == 20: k2.append((dr, amp2))
    d = np.array([x[0] for x in k2]); Am = np.array([x[1] for x in k2])
    print(f'稳健口径 20/min 三档过原点斜率 {float(d @ Am / (d @ d)):.0f} r/R；线性 斜率/截距 {np.round(np.polyfit(d, Am, 1), 1).tolist()}')
    d = np.array([x[0] for x in k]); Am = np.array([x[1] for x in k])
    print(f'20/min 三档过原点斜率 {float(d @ Am / (d @ d)):.0f} r/R；线性拟合 斜率/截距 {np.round(np.polyfit(d, Am, 1), 1).tolist()}（R91 旧值约 330 r/R，旧接线，作废）')
    print('=== B 模拟器心电核对（绿→RA、黄→LA、红→RL）')
    t, v = ecg_arrays(R108, ms(20,14,19,45), ms(20,14,22,0)); print('14:19:45–14:22:00', polarity(list(zip(t, v / 1000))))
    print('=== C 真人（同一名志愿者；R87、R94 用同一函数作对照）')
    rows = [('R108-1 静坐', ms(20,14,42,20), ms(20,14,45,20)), ('R108-1 挪动', ms(20,14,45,20), ms(20,14,46,20)),
            ('R108-1 重新静坐', ms(20,14,46,30), ms(20,14,48,30)), ('R108-1 屏气', ms(20,14,48,40), ms(20,14,49,0)),
            ('R108-1 合计', ms(20,14,42,20), ms(20,14,49,0)),
            ('R108-2 戴夹至静坐前', ms(20,14,54,40), ms(20,14,59,7)), ('R108-2 静坐与观察', ms(20,14,59,17), ms(20,15,0,18)),
            ('R108-2 屏气', ms(20,15,0,28), ms(20,15,1,51)), ('R108-2 正常呼吸', ms(20,15,2,1), ms(20,15,2,14)),
            ('R108-2 屏气2', ms(20,15,2,24), ms(20,15,3,18)), ('R108-2 节拍12', ms(20,15,3,28), ms(20,15,4,48)),
            ('R108-2 末段', ms(20,15,4,58), ms(20,15,5,19)), ('R108-2 合计', ms(20,14,54,40), ms(20,15,5,19))]
    for name, a, b in rows: human_row(name, R108, a, b)
    human_row('R87 P2（旧色标）', 'r87-20261118T083445Z-node-ab.jsonl', ms(18,16,42), ms(18,16,47,51))
    human_row('R94（旧色标，乙）', 'r94human-20261119T090428Z-node-ab.jsonl', ms(19,17,8), ms(19,17,28))
    print('=== D RR')
    for name, a, b in [('R108-1 合计', ms(20,14,42,20), ms(20,14,49,0)), ('R108-2 合计', ms(20,14,54,40), ms(20,15,5,19))]:
        rr = frames(sc['rr'], a, b); print(f'{name} 板上 RR 有效 {sum(x[2] == "VALID" for x in rr)}/{len(rr)}')
    A, B = ms(20,15,3,18), ms(20,15,4,48); m = (rt >= A - 40000) & (rt < B)
    o = [x for x in resp_r1.run(rt[m] / 1000, rv[m], (A - 36000) / 1000, B / 1000) if x[0] * 1000 - resp_r1.W * 1000 >= A - 1]
    print('R1 节拍 12 段（只记录，节拍真值 12，人工计数未报）：', [(round(x[0] * 1000 - A) // 1000, x[1] and round(x[1], 1), x[3]) for x in o])
