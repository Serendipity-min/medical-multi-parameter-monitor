import evalc3_lib as L
from algo_d2 import run_d2
from algos import run
CFG = [dict(name='C2'), dict(name='D2 θ.4', theta=.4, theta2=.3), dict(name='D2 θ.45', theta=.45, theta2=.35),
       dict(name='D2 θ.4 p3', theta=.4, theta2=.3, persist=3)]
def go(c, y):
    if c['name'] == 'C2': return run('C2', y)
    return run_d2(y, **{k: v for k, v in c.items() if k != 'name'})
L.report(CFG, go)
