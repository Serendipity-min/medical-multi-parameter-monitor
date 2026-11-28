import datetime, numpy as np, statistics
from load2 import load
from ppg_rr import rr
TZ = datetime.timezone(datetime.timedelta(hours=8))
CAP = '../../r83-capture/'
def ms(d, h, m, s=0): return int(datetime.datetime(2026, 11, d, h, m, s, tzinfo=TZ).timestamp() * 1000)
SETS = [('R87 P2', 'r87-20261118T083445Z-node-ab.jsonl', ms(18,16,42), ms(18,16,47,51), None),
        ('R89 S5', 'r89human-20261118T102758Z-node-ab.jsonl', ms(18,18,36,41), ms(18,18,43,30), (ms(18,18,42,20), ms(18,18,43,20))),
        ('R91', 'r91human-20261119T072140Z-node-ab.jsonl', ms(19,15,36,41), ms(19,16,3,40), None),
        ('R94', 'r94human-20261119T090428Z-node-ab.jsonl', ms(19,17,8), ms(19,17,28), (ms(19,17,26,50), ms(19,17,27,50))),
        ('R85 wrist', 'r85-20261118T074904Z-node-ab.jsonl', ms(18,15,58,40), ms(18,16,3,40), None)]
fmt = lambda s: datetime.datetime.fromtimestamp(s, TZ).strftime('%H:%M:%S')
if __name__ == '__main__':
    for W in (32, 64):
        print(f'===== window {W} s')
        for name, f, A, B, metro in SETS:
            w, sc, _ = load(CAP + f)
            o = rr(w['ppg'], A, B, W=W)
            vals = [v for _, v, _, _ in o if v]
            feat_ok = {k: sum(1 for _, _, p, _ in o if k in p and p[k][1] >= .3) for k in (1, 2, 3)}
            line = f'{name:9s} windows {len(o):3d} output {len(vals):3d} ({100*len(vals)/max(1,len(o)):4.1f}%) values p10/50/90 {np.percentile(vals,[10,50,90]).round(1) if vals else "-"} | qualified RIFV/RIAV/RIIV {feat_ok[1]}/{feat_ok[2]}/{feat_ok[3]}'
            print(line)
            if metro:
                m0, m1 = metro[0] / 1000, metro[1] / 1000
                inside = [(c, v, p) for c, v, p, _ in o if c - W >= m0 - 4 and c <= m1 + 4]
                print(f'   metronome 12/min {fmt(m0)}-{fmt(m1)}: windows fully inside {len(inside)}; ' + '; '.join(f'{fmt(c)} out={v and round(v,1)} RIFV/RIAV/RIIV=' + '/'.join(f'{p[k][0]:.1f}({p[k][1]:.2f})' if k in p else '-' for k in (1,2,3)) for c, v, p in inside[:6]))
