"""R100 判定：冻结版 PPG-RR（rr_frozen）按 R100 §4。时刻为标准时间（现场时钟 −30 s）。"""
import datetime, numpy as np
from load2 import load, runs
import rr_frozen
TZ = datetime.timezone(datetime.timedelta(hours=8))
def T(h, m, s): return datetime.datetime(2026, 11, 19, h, m, s, tzinfo=TZ).timestamp()
fmt = lambda s: datetime.datetime.fromtimestamp(s, TZ).strftime('%H:%M:%S')
SEG = [('N0', T(19,30,30), T(19,32,30), None), ('P10', T(19,32,30), T(19,34,0), 10), ('N1', T(19,34,0), T(19,35,0), None),
       ('P15', T(19,35,0), T(19,36,30), 15), ('N2', T(19,36,30), T(19,37,30), None), ('P20', T(19,37,30), T(19,39,0), 20),
       ('N3', T(19,39,0), T(19,40,0), None), ('H0', T(19,40,0), T(19,40,20), None), ('N4', T(19,40,20), T(19,41,20), None),
       ('H', T(19,41,20), T(19,41,50), None), ('N5', T(19,41,50), T(19,42,50), None)]
w, sc, _ = load('../../r83-capture/r100rr-20261119T112442Z-node-ab.jsonl')
A, B = T(19,29,30) * 1000, T(19,43,0) * 1000
o = rr_frozen.rr(w['ppg'], A, B)
cov_ppg = lambda a, b: sum(min(r[-1][0], b*1000) - max(r[0][0], a*1000) for r in runs([x for x in w['ppg'] if a*1000 <= x[0] < b*1000], 20) if len(r) > 1) / ((b - a) * 1000)
if __name__ == '__main__':
    passed = 0; bad_any = False; evaluated = 0
    for name, a, b, target in SEG:
        ws = [(c, v, p) for c, v, p, _ in o if c - 32 >= a + 10 and c <= b + 1e-6] if target else [(c, v, p) for c, v, p, _ in o if c - 32 >= a - 1e-6 and c <= b + 1e-6]
        outs = [v for _, v, _ in ws if v]
        pc = cov_ppg(a, b)
        line = f'{name:4s} {fmt(a)}-{fmt(b)} PPG continuous {100*pc:5.1f}% | windows {len(ws):2d} with output {len(outs):2d}'
        if outs: line += f' | values {np.round(sorted(outs),1).tolist()[:12]}{"…" if len(outs)>12 else ""}'
        if target:
            if pc < .6 or not ws: line += ' | NOT_EVALUATED'
            else:
                evaluated += 1
                within = sum(abs(v - target) <= 2 for v in outs); cov = len(outs) / len(ws); acc = within / len(outs) if outs else 0
                off = (len(outs) - within) / len(outs) if outs else 0
                ok = cov >= .6 and acc >= .9; passed += ok; bad_any |= off > .2
                line += f' | coverage {100*cov:.0f}% within±2 {100*acc:.0f}% off {100*off:.0f}% => {"PASS" if ok else "FAIL"}'
            # 各特征单独结果（诊断）
            for k, nm in ((1, 'RIFV'), (2, 'RIAV'), (3, 'RIIV')):
                fv = [p[k] for _, _, p in ws if k in p]
                if fv: line += f'\n      {nm}: peaks {np.round([x[0] for x in fv],1).tolist()[:10]} q {np.round([x[1] for x in fv],2).tolist()[:10]}'
        print(line)
    print(f'evaluated paced segments {evaluated}, passed {passed}, any segment >20% off: {bad_any} => overall', 'NOT_EVALUATED' if evaluated < 2 else ('PASS' if passed >= 2 and not bad_any else 'FAIL'))
