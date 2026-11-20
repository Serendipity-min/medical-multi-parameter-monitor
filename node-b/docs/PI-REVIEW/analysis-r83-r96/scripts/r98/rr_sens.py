"""事后敏感性（非冻结）：主峰须落在 8–39 次/分，排除带边慢漂移后重算 PPG-RR。"""
import numpy as np
import ppg_rr
from load2 import load
from rr_eval import SETS, CAP, fmt
_est = ppg_rr.est
def est2(g, v, A, W):
    e = _est(g, v, A, W)
    return (e[0], 0.0) if e and not (8 <= e[0] <= 39) else e
ppg_rr.est = est2
if __name__ == '__main__':
    for name, f, A, B, metro in SETS:
        w, sc, _ = load(CAP + f); o = ppg_rr.rr(w['ppg'], A, B, W=32)
        vals = [v for _, v, _, _ in o if v]
        print(f'{name:9s} output {len(vals)}/{len(o)} ({100*len(vals)/len(o):.1f}%) p10/50/90 {np.percentile(vals,[10,50,90]).round(1) if vals else "-"}')
        if metro:
            ins = [(c, v, p) for c, v, p, _ in o if c - 32 >= metro[0]/1000 - 4 and c <= metro[1]/1000 + 4]
            print('   metronome:', '; '.join(f'{fmt(c)} out={v and round(v,1)} ' + '/'.join(f'{p[k][0]:.1f}({p[k][1]:.2f})' if k in p else '-' for k in (1,2,3)) for c, v, p in ins))
