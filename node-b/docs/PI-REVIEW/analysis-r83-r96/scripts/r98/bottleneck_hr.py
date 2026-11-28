"""色标改正后（R108 起）全部真人录制按 20 s 分窗：板上 HR 有效率 vs 信号质量。冻结版 BIO_V2_ALC=0，上传 ECG 即板上心搏检测所见波形。
信号质量：PPG 峰锁定的 QRS 集合平均（r109_eval.ensemble）峰峰值与稳健单拍 SNR（|集合峰|/10 s 块标准差中位数）；
5–25 Hz、45–55 Hz（陷波后工频残留）RMS。只读录制，输出汇总。
用法：在本目录运行 python3 -s -E bottleneck_hr.py；结果见 ../../results/bottleneck_hr.txt。"""
import sys, numpy as np
from r109_eval import get, ensemble, bands, ms
# 电极贴到人身上之后的时段（各报告现场时刻）；之前是模拟器心电核对，B 显示 60 而 A 是真人
SEG = {'R108': [(ms(20,14,41,21), ms(20,14,49,10)), (ms(20,14,54,30), ms(20,15,5,30))], 'R110 丙': [(ms(20,15,39,55), 1e15)],
       'R112 丁': [(ms(23,10,7,10), 1e15)], 'R116 甲': [(ms(23,17,5,28), 1e15)], 'R119 甲': [(ms(23,19,33,30), 1e15)],
       'R123 丙': [(ms(24,16,29,7), 1e15)], 'R125 丙': [(ms(27,10,27,10), 1e15)]}
CAPS = [('R108', 'r108human-20261120T061515Z-node-ab.jsonl'), ('R110 丙', 'r110human-20261120T073145Z-node-ab.jsonl'),
        ('R112 丁', 'r112human-20261123T015825Z-node-ab.jsonl'), ('R116 甲', 'r116human-20261123T085733Z-node-ab.jsonl'),
        ('R119 甲', 'r119human-20261123T112630Z-node-ab.jsonl'), ('R123 丙', 'r123human-20261124T082448Z-node-ab.jsonl'),
        ('R125 丙', 'r125human-20261127T020900Z-node-ab.jsonl')]
W = 20000
rows = []
for name, f in CAPS:
    w, sc, _ = get(f)
    hr = sc['hr']; pr = [x for x in sc['pr'] if x[2] == 'VALID' and x[1]]
    if not hr or not pr: continue
    A0 = max(hr[0][0], pr[0][0]); B0 = min(hr[-1][0], pr[-1][0])
    for a1, b1 in SEG[name]:
     A, B = max(A0, a1), min(B0, b1)
     for s in range(int(A), int(B) - W, W):
         fr = [x for x in hr if s <= x[0] < s + W]; p = [x[1] for x in pr if s <= x[0] < s + W]
         if len(fr) < 15 or len(p) < 15: continue
         e = ensemble(f, s, s + W)
         if not e: continue
         b = bands(f, s, s + W); v = [x for x in fr if x[2] == 'VALID']; prm = float(np.median(p))
         agree = sum(abs(x[1] - prm) <= .1 * prm for x in v)
         rows.append(dict(sess=name, valid=len(v) / len(fr), nv=len(v), agree=agree, pp=e[1], snr=e[5], sign=e[4], inband=b[1], mains=b[2], pr=prm))
R = rows
print(f'窗口数 {len(R)}（20 s，需同时有 B 的 HR 帧与 A 的有效 PR / PPG）')
def summ(sel, tag):
    if not sel: print(f'{tag}: 0 窗'); return
    q = lambda k: np.percentile([r[k] for r in sel], [25, 50, 75])
    nv = sum(r['nv'] for r in sel); ag = sum(r['agree'] for r in sel)
    print(f'{tag}: {len(sel):3d} 窗 | QRS p-p 中位 {q("pp")[1]:4.0f} µV（四分位 {q("pp")[0]:.0f}–{q("pp")[2]:.0f}） | SNR {q("snr")[1]:.2f}（{q("snr")[0]:.2f}–{q("snr")[2]:.2f}）'
          f' | 5–25 Hz {q("inband")[1]:4.0f} µV | 工频残留 {q("mains")[1]:5.1f} µV（{q("mains")[0]:.1f}–{q("mains")[2]:.1f}） | 有效帧与 PR±10% {ag}/{nv}')
print('\n=== 按板上 HR 有效率分组')
summ([r for r in R if r['valid'] >= .8], 'HR 有效 ≥80%')
summ([r for r in R if .2 <= r['valid'] < .8], 'HR 有效 20–80%')
summ([r for r in R if r['valid'] < .2], 'HR 有效 <20%')
print('\n=== 按信号 SNR 分组：板上 HR 有效率（窗均值）与有效帧准确率')
for lo, hi in ((0, 1.5), (1.5, 2), (2, 2.5), (2.5, 3), (3, 4), (4, 99)):
    sel = [r for r in R if lo <= r['snr'] < hi]
    if not sel: continue
    nv = sum(r['nv'] for r in sel); ag = sum(r['agree'] for r in sel)
    print(f'SNR {lo:>3}–{hi:<3}: {len(sel):3d} 窗，HR 有效率 {100 * np.mean([r["valid"] for r in sel]):5.1f}%，有效帧与 PR±10% {100 * ag / max(nv, 1):5.1f}%（{ag}/{nv}）'
          f'，QRS p-p 中位 {np.median([r["pp"] for r in sel]):4.0f} µV，工频残留中位 {np.median([r["mains"] for r in sel]):5.1f} µV')
print('\n=== 按工频残留分组（陷波后 45–55 Hz RMS）')
for lo, hi in ((0, 5), (5, 15), (15, 40), (40, 1e9)):
    sel = [r for r in R if lo <= r['mains'] < hi]
    if not sel: continue
    print(f'工频 {lo:>3}–{hi if hi < 1e8 else "∞":<4} µV: {len(sel):3d} 窗，HR 有效率 {100 * np.mean([r["valid"] for r in sel]):5.1f}%，SNR 中位 {np.median([r["snr"] for r in sel]):.2f}')
print('\n=== 各次录制')
for name, _ in CAPS:
    sel = [r for r in R if r['sess'] == name]
    if not sel: print(f'{name}: 无可用窗'); continue
    nv = sum(r['nv'] for r in sel); ag = sum(r['agree'] for r in sel)
    print(f'{name:8s} {len(sel):3d} 窗 | HR 有效 {100 * np.mean([r["valid"] for r in sel]):5.1f}% | 与 PR±10% {100 * ag / max(nv, 1):5.1f}% | QRS p-p {np.median([r["pp"] for r in sel]):4.0f} µV'
          f' | SNR {np.median([r["snr"] for r in sel]):.2f} | 5–25 Hz {np.median([r["inband"] for r in sel]):4.0f} µV | 工频 {np.median([r["mains"] for r in sel]):5.1f} µV'
          f' | 主峰正向 {100 * np.mean([r["sign"] > 0 for r in sel]):.0f}%')
print('\n=== 疑似算法问题的窗')
miss = [r for r in R if r['snr'] >= 3 and r['valid'] < .2]
wrong = [r for r in R if r['nv'] >= 5 and r['agree'] < .5 * r['nv']]
print(f'信号好（SNR≥3）但 HR 有效 <20%：{len(miss)}/{sum(r["snr"] >= 3 for r in R)} 窗 ' + str([(r['sess'], round(r['snr'], 2), round(r['mains'], 1)) for r in miss][:8]))
print(f'HR 有效但多数与 PR 不符：{len(wrong)} 窗 ' + str([(r['sess'], round(r['snr'], 2), r['nv'], r['agree']) for r in wrong][:8]))
