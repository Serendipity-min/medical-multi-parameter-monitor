import sys, statistics, json
import evalc3_lib as L
from algo_d import run_d
from algos import run
CFG = [dict(name='C2'), dict(name='D comb θ.4', comb=True, theta=.4, theta2=.3),
       dict(name='D comb θ.5', comb=True, theta=.5, theta2=.4), dict(name='D nocomb θ.4', comb=False, theta=.4, theta2=.3)]
def go(c, y):
    if c['name'] == 'C2': return run('C2', y)
    kw = {k: v for k, v in c.items() if k != 'name'}; return run_d(y, **kw)
L.report(CFG, go)
