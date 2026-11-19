"""R89 S5 与 R87 P2 对比：C1/C2 真实 C 代码重放、峰检幅度、TP 段噪声、全信号 RMS、缺样率、分钟级。"""
import sys, ctypes as C, math, statistics, bisect
sys.path.insert(0, '..')
from load import load, hms, UV_PER_Y
from variants import ms
CAP = '../../r83-capture/'
libs = {}
for k in ('c1', 'c2'):
    l = C.CDLL(f'./replay_{k}.so'); l.Replay_Init.argtypes = [C.c_uint32]
    l.Replay_Feed.argtypes = [C.c_float, C.c_uint32]; l.Replay_Feed.restype = C.c_uint32; libs[k] = l
def replay(l, y):
    l.Replay_Init(y[0][0] & 0xffffffff); return [(t, l.Replay_Feed(v, t & 0xffffffff)) for t, v in y]
def detector(y):
    band, inp, out = 0.0, False, []
    for t, v in y:
        band += .004 * (v * v - band); a = abs(v); thr = max(30.0, 2.5 * math.sqrt(band))
        if not inp and a >= thr: inp, above, pk, pt, gate = True, t, a, t, thr
        elif inp:
            if a > pk: pk, pt = a, t
            if a < gate * .5 or t - above > 200:
                inp = False
                if 12 <= t - above <= 160 and pk >= gate * 1.05: out.append((pt, pk))
    return out
def report(name, path, A, B, excl=None):
    ecg, _, hr, _ = load(CAP + path)
    y = [(int(t), mv * 1000 / UV_PER_Y) for t, mv, _, _ in ecg if A - 20000 <= t < B]
    ys = [(t, v) for t, v in y if A <= t < B and not (excl and excl[0] <= t < excl[1])]
    print(f'== {name}: samples {len(ys)} / expected {(B-A)//4} ({100*len(ys)/((B-A)/4):.0f}%)')
    rs = {k: replay(l, y) for k, l in libs.items()}
    for m0 in range(A, B, 60000):
        m1 = min(m0 + 60000, B)
        seg = [v * UV_PER_Y for t, v in ys if m0 <= t < m1]
        if not seg: continue
        rms = math.sqrt(statistics.fmean(x * x for x in seg))
        det = [d for d in detector(y) if m0 <= d[0] < m1]
        ivs = [b[0] - a[0] for a, b in zip(det, det[1:])]
        pk = statistics.median(d[1] * UV_PER_Y for d in det) if det else 0
        rp = ' '.join(f'{k} {100*sum(1 for t,v in r if m0<=t<m1 and v)/max(1,sum(1 for t,v in r if m0<=t<m1)):5.1f}%' for k, r in rs.items())
        bh = [x for x in hr if m0 <= x[0] < m1]
        bv = [x[1] for x in bh if x[2] == 'VALID']
        print(f'  {hms(m0)[:5]} rms {rms:5.0f} uV  peaks {len(det):3d} peak|y| {pk:5.0f} uV  iv med {statistics.median(ivs) if ivs else 0:5.0f} ms  | replay {rp} | board {len(bv)}/{len(bh)} {sorted(set(int(x) for x in bv))[:6]}')
report('R87 P2 (C1 on board)', 'r87-20261118T083445Z-node-ab.jsonl', ms(16,42,0), ms(16,47,51))
report('R89 S5 P2 (C2 on board)', 'r89human-20261118T102758Z-node-ab.jsonl', ms(18,33,0), ms(18,43,30), (ms(18,36,31), ms(18,36,41)))
