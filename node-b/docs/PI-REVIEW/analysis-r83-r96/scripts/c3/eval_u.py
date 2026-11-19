"""并联：C2 有效时用 C2，否则用 D2（看能否保住 R87 同时拿到低 SNR 的增益）。"""
import evalc3_lib as L
from algo_d2 import run_d2
from algos import run
def union(y, **kw):
    a, b = run('C2', y), run_d2(y, **kw)
    return [(t, r1 if r1 else r2) for (t, r1), (_, r2) in zip(a, b)]
CFG = [dict(name='C2'), dict(name='C2∪D2 θ.4', theta=.4, theta2=.3), dict(name='C2∪D2 θ.45', theta=.45, theta2=.35)]
def go(c, y):
    if c['name'] == 'C2': return run('C2', y)
    return union(y, **{k: v for k, v in c.items() if k != 'name'})
L.report(CFG, go, extra_noise=False)
