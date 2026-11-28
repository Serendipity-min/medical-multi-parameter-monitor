"""真人 RESP 在 R1 各道门上的拒绝分布（Python 参考 resp_r1，RPM_MIN=9.5 同固件）。上传缺口造成的 coverage/gap 单列，不算信号问题。
用法：在本目录运行 python3 -s -E bottleneck_resp.py；结果见 ../../results/bottleneck_resp.txt。"""
import numpy as np, collections
from r109_eval import get, ms, K
import resp_r1; resp_r1.RPM_MIN = 9.5
SEG = {'R108': ('r108human-20261120T061515Z-node-ab.jsonl', [(ms(20,14,41,21), ms(20,14,49,10)), (ms(20,14,54,30), ms(20,15,5,30))]),
       'R110 丙': ('r110human-20261120T073145Z-node-ab.jsonl', [(ms(20,15,39,55), None)]),
       'R112 丁': ('r112human-20261123T015825Z-node-ab.jsonl', [(ms(23,10,7,10), None)]),
       'R116 甲': ('r116human-20261123T085733Z-node-ab.jsonl', [(ms(23,17,5,28), None)]),
       'R119 甲': ('r119human-20261123T112630Z-node-ab.jsonl', [(ms(23,19,33,30), None)]),
       'R123 丙': ('r123human-20261124T082448Z-node-ab.jsonl', [(ms(24,16,29,7), None)]),
       'R125 丙': ('r125human-20261127T020900Z-node-ab.jsonl', [(ms(27,10,27,10), None)])}
tot = collections.Counter(); amps_all = []; qs_all = []
def stats(t, v, a):
    m = (t >= a) & (t < a + resp_r1.W); x = v[m]; p5, p95 = np.percentile(x, [5, 95])
    g = np.arange(a, a + resp_r1.W, .1); y = np.interp(g, t[m], x); y = y - np.polyval(np.polyfit(g - a, y, 1), g - a); y *= np.hanning(len(y))
    X = abs(np.fft.rfft(y, 4096)) ** 2; f = np.fft.rfftfreq(4096, .1); band = (f >= .1) & (f <= .7)
    fp = f[band][np.argmax(X[band])]
    lowf = X[(f >= .03) & (f < .1)].sum() / X[(f >= .03) & (f <= .7)].sum()
    return (p95 - p5) / 2, X[abs(f - fp) <= .03].sum() / X[band].sum(), 60 * fp, lowf
for name, (f, segs) in SEG.items():
    w, sc, _ = get(f); t = np.array([x[0] for x in w['resp']]) / 1000; v = np.array([x[1] * K for x in w['resp']])
    c = collections.Counter(); st = []
    for a1, b1 in segs:
        A = max(t[0], a1 / 1000); B = min(t[-1], b1 / 1000 if b1 else t[-1])
        for e in np.arange(A + resp_r1.W, B, resp_r1.STEP):
            est, why = resp_r1.window(t, v, e - resp_r1.W); c[why] += 1
            if why not in ('coverage', 'gap'): st.append(stats(t, v, e - resp_r1.W) + (why,))
    tot.update(c); n = sum(c[k] for k in c if k not in ('coverage', 'gap'))
    sig = '，'.join(f'{k} {100 * c[k] / max(n, 1):.0f}%' for k in ('ok', 'quality', 'transient', 'edge', 'amplitude') if c[k])
    print(f'{name:8s} 窗 {sum(c.values()):4d}，上传缺口 {c["coverage"] + c["gap"]:4d}；其余 {n:4d} 窗：{sig}'
          f' | 半幅中位 {np.median([s[0] for s in st]):5.0f} r，q 中位 {np.median([s[1] for s in st]):.2f}，<0.1 Hz 慢漂占比中位 {100 * np.median([s[3] for s in st]):.0f}%')
    amps_all += st
n = sum(tot[k] for k in tot if k not in ('coverage', 'gap'))
print('合计（剔除上传缺口）' + '，'.join(f'{k} {100 * tot[k] / n:.1f}%' for k in ('ok', 'quality', 'transient', 'edge', 'amplitude') if tot[k]) + f'，共 {n} 窗')
rej = [s for s in amps_all if s[4] == 'quality']; ok = [s for s in amps_all if s[4] == 'ok']
print(f'被 quality 拒的窗：q 中位 {np.median([s[1] for s in rej]):.2f}，主峰 {np.median([s[2] for s in rej]):.1f}/分，慢漂占比 {100*np.median([s[3] for s in rej]):.0f}%；'
      f'通过的窗：q 中位 {np.median([s[1] for s in ok]):.2f}，慢漂占比 {100*np.median([s[3] for s in ok]):.0f}%')
edge = [s[2] for s in amps_all if s[4] == 'edge']
print(f'被 edge 拒的窗 {len(edge)}：主峰 ≤9.5/分 {sum(r <= 9.5 for r in edge)}，≥39/分 {sum(r >= 39 for r in edge)}，主峰中位 {np.median(edge):.1f}/分')
# 模拟器参照
w, sc, _ = get('r125sim-20261126T115404Z-node-ab.jsonl'); t = np.array([x[0] for x in w['resp']]) / 1000; v = np.array([x[1] * K for x in w['resp']])
a = ms(26,20,3,0) / 1000; print('模拟器 R125 20 次/分参照：半幅 %.0f r，q %.2f' % stats(t, v, a)[:2])
