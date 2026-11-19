"""R89 模拟器断开/接回段：C1/C2 真实 C 代码重放，逐秒有效值；并列出 C2 峰检候选时刻与间期。"""
import sys, ctypes as C, math
sys.path.insert(0, '..')
from load import load, hms, UV_PER_Y
ecg, *_ = load(sys.argv[1]); A, B = int(sys.argv[2]), int(sys.argv[3])
y = [(int(t), mv * 1000 / UV_PER_Y) for t, mv, _, _ in ecg if A - 60000 <= t < B]
out = {}
for k in ('c1', 'c2'):
    l = C.CDLL(f'./replay_{k}.so'); l.Replay_Init.argtypes = [C.c_uint32]
    l.Replay_Feed.argtypes = [C.c_float, C.c_uint32]; l.Replay_Feed.restype = C.c_uint32
    l.Replay_Init(y[0][0] & 0xffffffff); sec = {}
    for t, v in y:
        r = l.Replay_Feed(v, t & 0xffffffff)
        if t >= A: sec.setdefault(t // 1000, set()).add(r)
    out[k] = sec
for s in sorted(out['c1']):
    a, b = sorted(out['c1'][s] - {0}), sorted(out['c2'][s] - {0})
    if a or b: print(hms(s * 1000)[:8], 'C1', a, '| C2', b)
# 峰检候选（与固件同门限）
band, inp, peaks = 0.0, False, []
for t, v in y:
    band += .004 * (v * v - band); a = abs(v); thr = max(30.0, 2.5 * math.sqrt(band))
    if not inp and a >= thr: inp, above, pk, pt, gate = True, t, a, t, thr
    elif inp:
        if a > pk: pk, pt = a, t
        if a < gate * .5 or t - above > 200:
            inp = False
            if 12 <= t - above <= 160 and pk >= gate * 1.05 and A <= pt < B: peaks.append((pt, pk / gate, t - above))
prev = None
for pt, ratio, w in peaks:
    print('peak', hms(pt), f'iv {pt - prev if prev else 0:5d} ms', f'peak/gate {ratio:4.2f} width {w}')
    prev = pt
