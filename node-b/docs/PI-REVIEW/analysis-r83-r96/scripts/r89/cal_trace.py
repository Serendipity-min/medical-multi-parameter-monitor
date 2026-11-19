"""S4 各档 2 s 粒度：RESP 均值/峰峰（r），RR 帧；用于查看扰动与漂移。"""
import sys, numpy as np
sys.path.insert(0, '..')
from load import load, hms, Y_PER_RESP_REL
from variants import ms
_, resp, _, rr = load('../../r83-capture/r89cal-20261118T100701Z-node-ab.jsonl')
t = np.array([x[0] for x in resp]); v = np.array([x[1] * Y_PER_RESP_REL for x in resp])
R = {int(a // 1000): (b, c) for a, b, c in rr}
a, b = ms(*map(int, sys.argv[1].split(':'))), ms(*map(int, sys.argv[2].split(':')))
for w in range(a, b, 2000):
    m = (t >= w) & (t < w + 2000)
    r = [R.get(s) for s in (w // 1000, w // 1000 + 1)]
    rs = ' '.join(f'{x[0]:.0f}' if x and x[1] == 'VALID' else ('inv' if x else '-') for x in r)
    print(hms(w)[:8], f'n {m.sum():3d}', f'mean {v[m].mean():9.0f} p-p {np.ptp(v[m]):8.0f}' if m.sum() else 'gap', '| RR', rs)
