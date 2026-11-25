"""R125 补充：RR 参数变体的离线对比（只作决策依据，不改 R1）。9 个有真值的节拍段、丙 r123human 节拍 15 段、r123sim ECG 模式阴性段。
用法：python3 -s -E r125_rr_variants.py（在本目录运行，需 numpy）。"""
import sys, numpy as np
sys.path.insert(0, '.')
from r109_eval import get, ms, K
from r125_r1_equiv import PACED
def window(t, v, a, W, winsor, Q=.5, insearch=False):
    m = (t >= a) & (t < a + W)
    if m.sum() < W * 50 * .9: return None, 'coverage'
    tt = t[m]
    if np.diff(np.concatenate([[a], tt, [a + W]])).max() > 1.0: return None, 'gap'
    x = v[m].copy(); p5, p95 = np.percentile(x, [5, 95]); s = p95 - p5
    if x.max() - x.min() > 3 * s:
        if not winsor: return None, 'transient'
        med = np.median(x); x = np.clip(x, med - 1.5 * s, med + 1.5 * s)
    if s / 2 < 60: return None, 'amplitude'
    g = np.arange(a, a + W, .1); y = np.interp(g, tt, x); y = y - np.polyval(np.polyfit(g - a, y, 1), g - a); y *= np.hanning(len(y))
    X = abs(np.fft.rfft(y, 4096)) ** 2; f = np.fft.rfftfreq(4096, .1); band = (f >= .1) & (f <= .7)
    sb = (f > 9.5/60) & (f < 39/60) if insearch else band
    fp = f[sb][np.argmax(X[sb])]; rpm = 60 * fp
    if not (9.5 < rpm < 39): return None, 'edge'
    if X[abs(f - fp) <= .03].sum() / X[band].sum() < Q: return None, 'quality'
    return rpm, 'ok'
def run(t, v, ends, W, N=3, winsor=False, hold=0, Q=.5, insearch=False):
    out, hist, last, last_t = [], [], None, -1e9
    for c in ends:
        e, why = window(t, v, c - W, W, winsor, Q, insearch); hist = (hist + [e])[-N:]
        val = None
        if len(hist) == N and all(h is not None for h in hist) and max(hist) - min(hist) <= 2: val = float(np.median(hist)); last, last_t = val, c
        elif hold and last is not None and c - last_t <= hold and why in ('transient', 'gap'): val = last
        elif why not in ('transient', 'gap'): last = None
        out.append((c, val, why))
    return out
V = {'V0 基线 W32/3窗': dict(W=32), 'W24': dict(W=24), 'W20': dict(W=20), 'W32+削峰': dict(W=32, winsor=True),
     'W32/2窗': dict(W=32, N=2), 'W32+保持16s': dict(W=32, hold=16), 'Q0.40': dict(W=32, Q=.4), 'Q0.35': dict(W=32, Q=.35),
     'Q0.40+保持16s': dict(W=32, Q=.4, hold=16), 'Q0.40+2窗': dict(W=32, Q=.4, N=2)}
cache = {}
def series(f):
    if f not in cache:
        w, _, _ = get(f); cache[f] = (np.array([x[0] for x in w['resp']]) / 1000, np.array([x[1] * K for x in w['resp']]))
    return cache[f]
print('节拍段：评估窗末 ∈ [段起+40 s, 段末]；覆盖=有输出窗比例；准=±2 内比例；首出=段起到首个输出的秒数')
for name, kw in V.items():
    rows = []; tc = tv = tok = 0
    for seg, f, a, b, truth in PACED:
        t, v = series(f); ends = np.arange(a / 1000 + 6, b / 1000 + 1e-9, 2.0)
        o = run(t, v, ends, **kw); ev = [x for x in o if x[0] >= a / 1000 + 40]
        vals = [x[1] for x in ev if x[1] is not None]; ok = sum(abs(x - truth) <= 2 for x in vals)
        first = next((x[0] - a / 1000 for x in o if x[1] is not None), None)
        tc += len(ev); tv += len(vals); tok += ok
        rows.append(f'{seg[-4:]}:{len(vals)}/{len(ev)},{ok}/{len(vals)},{"-" if first is None else int(first)}')
    print(f'{name:18s} 覆盖 {tv}/{tc}={100*tv/tc:4.0f}%  准 {tok}/{tv}={100*tok/max(tv,1):4.0f}% | ' + ' '.join(rows))
# 阴性：r123sim ECG 模式段（无呼吸） + 断开 RA；r116/r119/r123human 全程 9.5–39 之外不计
t, v = series('r123sim-20261124T075651Z-node-ab.jsonl')
d = 24
for name, kw in V.items():
    ends = np.arange(ms(d,15,59,52) / 1000 + 6, ms(d,16,2,55) / 1000 + 10, 2.0); o = run(t, v, ends, **kw)
    bad = [round(x[1], 1) for x in o if x[1] is not None]
    e2 = np.arange(ms(d,16,10,10) / 1000, ms(d,16,10,41) / 1000, 2.0); o2 = run(t, v, np.arange(ms(d,16,9,0)/1000, ms(d,16,11,41)/1000, 2.0), **kw)
    era = [round(x[1], 1) for x in o2 if ms(d,16,10,10)/1000 <= x[0] <= ms(d,16,10,41)/1000 and x[1] is not None]
    rec = next((x[0] - ms(d,16,10,41)/1000 for x in o2 if x[0] > ms(d,16,10,41)/1000 and x[1] is not None), None)
    print(f'{name:18s} ECG 模式误出 {len(bad)} {sorted(set(bad))[:6]} | 断 RA 期间输出 {len(era)} {sorted(set(era))[:4]}')
print('=== 丙 r123human 节拍 15（16:35:00–16:40:15，真值约 15）：覆盖、±2 内、失效段长度（s）')
t, v = series('r123human-20261124T082448Z-node-ab.jsonl'); a, b = ms(24,16,35,0)/1000, ms(24,16,40,15)/1000
ends = np.arange(a + 6, b + 1e-9, 2.0)
for name, kw in V.items():
    o = run(t, v, ends, **kw); ev = [x for x in o if x[0] >= a + 40]; vals = [x[1] for x in ev if x[1] is not None]
    runs_, cur = [], 0
    for x in ev:
        if x[1] is None: cur += 2
        elif cur: runs_.append(cur); cur = 0
    if cur: runs_.append(cur)
    from collections import Counter
    why = Counter(x[2] for x in ev)
    print(f'{name:18s} 覆盖 {len(vals)}/{len(ev)}={100*len(vals)/len(ev):3.0f}% ±2 {sum(abs(x-15)<=2 for x in vals)}/{len(vals)} 失效段 {runs_} 判因 {dict(why)}')
