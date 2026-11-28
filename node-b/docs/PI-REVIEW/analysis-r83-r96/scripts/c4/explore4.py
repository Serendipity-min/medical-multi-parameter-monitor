"""R118 §3 探索（运行后追加，不参与门槛）：C2 口径下把系数 k 从 2.0 扫到 3.5，看 2.5 是否在峰值附近。"""
import statistics
from eval4 import HUMAN, NEG, RECON, seg, run, score
for k in (2.0, 2.25, 2.5, 2.75, 3.0, 3.5):
    c = (f'K{k}', 0, k); tv = tn = 0; ok = n = 0; row = []
    for name, (p, A, B) in HUMAN.items():
        d = seg(p, A, B); v, pairs, _, m = score(run(c, d['y']), d); tv += v * m; tn += m
        ok += sum(abs(r - q) <= .1 * q for r, q in pairs); n += len(pairs); row.append(f'{v:5.1f}')
    neg = [score(run(c, seg(p, A, B)['y']), seg(p, A, B)) for p, A, B in list(NEG.values()) + list(RECON.values())]
    print(f'k={k:4.2f} 合计有效 {tv / tn:5.1f}% 一致 {100 * ok / max(1, n):4.1f}% | 各段 {" ".join(row)} | 导联断开 {neg[0][0]:.1f}% 接回 {neg[1][0]:.1f}% {neg[1][2]}')
