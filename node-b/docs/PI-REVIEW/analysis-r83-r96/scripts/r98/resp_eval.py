"""R102 评测（门槛见 R102 §3）。"""
import datetime, random, numpy as np
from scipy.signal import butter, lfilter
from load2 import load
import resp_r1
TZ = datetime.timezone(datetime.timedelta(hours=8))
CAP = '../../r83-capture/'
def T(d, h, m, s=0): return datetime.datetime(2026, 11, d, h, m, s, tzinfo=TZ).timestamp()
K = 1000 / 0.11920928955
_c = {}
def resp(f):
    if f not in _c:
        w, sc, _ = load(CAP + f); _c[f] = (np.array([x[0] / 1000 for x in w['resp']]), np.array([x[1] * K for x in w['resp']]))
    return _c[f]
def summ(o, truth=None, tol=None):
    vals = [x[1] for x in o if x[1] is not None]; n = len(o)
    why = {}
    for x in o: why[x[3]] = why.get(x[3], 0) + 1
    s = f'windows {n:3d} output {len(vals):3d} ({100*len(vals)/max(1,n):5.1f}%)'
    ok = None
    if vals: s += f' values p10/50/90 {np.percentile(vals,[10,50,90]).round(1).tolist()}'
    if truth is not None and vals:
        ok = sum(abs(v - truth) <= tol for v in vals) / len(vals); s += f' | within±{tol} {100*ok:.0f}%'
    return s + f' | single-window reasons {why}', (len(vals) / max(1, n)), ok
CAL = 'r89cal-20261118T100701Z-node-ab.jsonl'
POS = [('sim 1.5R@20', CAL, T(18,18,11,30), T(18,18,12,30), 20, True), ('sim 1.0R@20', CAL, T(18,18,13,14), T(18,18,13,44), 20, True),
       ('sim 1.0R@12', CAL, T(18,18,17,18), T(18,18,18,18), 12, True), ('sim 0.5R@20', CAL, T(18,18,15,40), T(18,18,16,16), 20, False)]
NEG = [('R92 ECG-mode rest', 'r92sim-20261119T082651Z-node-ab.jsonl', T(19,16,31), T(19,16,33,50)),
       ('R92 wiggle/pull', 'r92sim-20261119T082651Z-node-ab.jsonl', T(19,16,33,50), T(19,16,42)),
       ('R83 leads-off', 'r83-20261118T065234Z-node-b.jsonl', T(18,15,0,15), T(18,15,4,0)),
       ('R89cal transient 1', CAL, T(18,18,12,40), T(18,18,13,14)), ('R89cal transient 2', CAL, T(18,18,14,30), T(18,18,15,40))]
R100 = 'r100rr-20261119T112442Z-node-ab.jsonl'
DEV = [('R100 P10', T(19,19,32,40), T(19,19,34,0), 10), ('R100 P15', T(19,19,35,10), T(19,19,36,30), 15), ('R100 P20', T(19,19,37,40), T(19,19,39,0), 20)]
NAT = [('R87 P2', 'r87-20261118T083445Z-node-ab.jsonl', T(18,16,42), T(18,16,47,51)), ('R89 S5', 'r89human-20261118T102758Z-node-ab.jsonl', T(18,18,33), T(18,18,43,30)),
       ('R91', 'r91human-20261119T072140Z-node-ab.jsonl', T(19,15,33,40), T(19,16,3,40)), ('R94', 'r94human-20261119T090428Z-node-ab.jsonl', T(19,17,8), T(19,17,28)),
       ('R100 N0', R100, T(19,19,30,30), T(19,19,32,30)), ('R100 N1-N5', R100, T(19,19,34,0), T(19,19,42,50))]
def lead(A): return A - resp_r1.W - 2 * resp_r1.STEP   # 让第一个评估窗之前已有 2 个历史窗，与板上连续运行一致
def inwin(o, A, B): return [x for x in o if x[0] - resp_r1.W >= A - 1e-6 and x[0] <= B + 1e-6]
gate = True
print('=== positives (simulator, truth known)')
for name, f, A, B, truth, gated in POS:
    t, v = resp(f); o = inwin(resp_r1.run(t, v, lead(A), B), A, B); s, cov, ok = summ(o, truth, 1)
    g = cov >= .8 and ok == 1.0
    if gated: gate &= g
    print(f'{name:18s} {s} => {("PASS" if g else "FAIL") if gated else "record"}')
print('=== negatives (must be 0%)')
for name, f, A, B in NEG:
    t, v = resp(f); o = resp_r1.run(t, v, A, B); s, cov, _ = summ(o); g = cov == 0; gate &= g
    print(f'{name:18s} {s} => {"PASS" if g else "FAIL"}')
b, a = butter(2, .8 / 25); covs = []
for seed in range(20):
    rng = np.random.default_rng(seed); x = lfilter(b, a, rng.normal(0, 1, 300 * 50)); x *= 200 / x.std()
    t = np.arange(len(x)) / 50.0; o = resp_r1.run(t, x, 0, 300); covs.append(sum(1 for y in o if y[1] is not None) / len(o))
g = np.mean(covs) <= .01; gate &= g
print(f'synthetic noise 20 seeds: output mean {100*np.mean(covs):.2f}% max {100*max(covs):.2f}% => {"PASS" if g else "FAIL"}')
print('=== dev set R100 (seen before; not independent)')
for name, A, B, truth in DEV:
    t, v = resp(R100); o = inwin(resp_r1.run(t, v, lead(A), B), A, B); s, cov, ok = summ(o, truth, 2)
    g = cov >= .6 and (ok or 0) >= .9
    if truth != 10: gate &= g
    print(f'{name:18s} {s} => {("PASS" if g else "FAIL") if truth != 10 else "record"}')
print('=== natural breathing (no truth; report only)')
for name, f, A, B in NAT:
    t, v = resp(f); o = resp_r1.run(t, v, A, B); s, _, _ = summ(o); print(f'{name:18s} {s}')
print('OVERALL R102 offline gate:', 'PASS' if gate else 'FAIL')
