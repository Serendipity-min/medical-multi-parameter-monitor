"""C1/C2 真实 C 代码在真人录制上的 HR 重放（跳过滤波），对照 R88 的 Python 原型数字。"""
import sys, ctypes as C, random, statistics
sys.path.insert(0, '/home/claudedev/workspaces/mmpm-review/node-b/build/r83-analysis')
from load import load, UV_PER_Y
from variants import ms
CAP = '/home/claudedev/workspaces/mmpm-review/node-b/build/r83-capture/'
libs = {}
for k in ('c1', 'c2'):
    l = C.CDLL(f'./replay_{k}.so'); l.Replay_Init.argtypes = [C.c_uint32]
    l.Replay_Feed.argtypes = [C.c_float, C.c_uint32]; l.Replay_Feed.restype = C.c_uint32; libs[k] = l
def run(lib, y):
    lib.Replay_Init(y[0][0] & 0xffffffff)
    return [(t, lib.Replay_Feed(v, t & 0xffffffff)) for t, v in y]
def stat(o, a=None, b=None):
    o = [x for x in o if a is None or a <= x[0] < b]; v = [r for _, r in o if r]
    return f'{100*len(v)/len(o):5.1f}% {statistics.median(v) if v else 0:4.0f} [{min(v) if v else 0}-{max(v) if v else 0}]'
e87, *_ = load(CAP + 'r87-20261118T083445Z-node-ab.jsonl')
e83, *_ = load(CAP + 'r83-20261118T065234Z-node-b.jsonl')
e85, *_ = load(CAP + 'r85-20261118T074904Z-node-ab.jsonl')
Y = lambda e, a, b: [(int(t), mv * 1000 / UV_PER_Y) for t, mv, _, _ in e if a <= t < b]
rng = random.Random(7); noise = [(i * 4, rng.gauss(0, 150)) for i in range(250 * 300)]
sets = [('P2 chest R87', Y(e87, ms(16,41,40), ms(16,47,51)), ms(16,42,0), ms(16,47,51)),
        ('ankles R83', Y(e83, ms(15,4,0), ms(15,9,30)), ms(15,4,20), ms(15,9,30)),
        ('wrists R85', Y(e85, ms(15,58,20), ms(16,3,40)), ms(15,58,40), ms(16,3,40)),
        ('simulator R83', Y(e83, 0, ms(15,0,8)), None, None),
        ('leads-off R83', Y(e83, ms(15,0,15), ms(15,4,0)), None, None),
        ('white noise 150', noise, None, None)]
print(f'{"set":16s} | C1 (C code)            | C2 (C code)')
res = {}
for name, y, a, b in sets:
    res[name] = {k: run(l, y) for k, l in libs.items()}
    print(f'{name:16s} | ' + ' | '.join(stat(res[name][k], a, b) for k in libs))
print('P2 per minute (C1 | C2):')
for m in range(42, 48):
    A, B = ms(16, m, 0), min(ms(16, m + 1, 0), ms(16, 47, 51))
    print(f'  16:{m}', ' | '.join(stat(res['P2 chest R87'][k], A, B) for k in libs))
