"""C3 候选（浮点原型，便于消融）：
A 工频梳状（5 点滑动平均，零点 50/100 Hz）；
B Pan–Tompkins 式检测（导数、平方、150 ms 积分、SPKI/NPKI 双门限、回溯）；
C 判定：最近 8 个间期中位数，剔除偏离 >20% 的离群，剩余 ≥5 个才有效。
C2 原峰检/判据通过 drv.so 调用真实 C 代码。"""
import ctypes as C, statistics
_lib = C.CDLL('./drv.so')
_lib.D_Init.argtypes = [C.c_uint32]; _lib.D_Feed.argtypes = [C.c_float, C.c_uint32]; _lib.D_Feed.restype = C.c_uint32
_lib.D_Beat.argtypes = [C.c_uint32]; _lib.D_Tick.argtypes = [C.c_uint32]; _lib.D_Tick.restype = C.c_uint32
GAP = 20

class Comb:
    def __init__(s): s.buf = []
    def reset(s): s.buf = []
    def __call__(s, x):
        s.buf.append(x); s.buf = s.buf[-5:]; return sum(s.buf) / len(s.buf)

class PT:
    """流式 Pan–Tompkins 检测，返回本样本确认的心搏时刻列表。"""
    def __init__(s, refractory=273, learn=2000):
        s.ref, s.learn = refractory, learn
        s.x = [0.0] * 5; s.win = [0.0] * 38; s.sum = 0.0; s.k = 0; s.fill = 0
        s.spki = s.npki = None; s.lmax = []; s.t0 = None
        s.cand = None; s.last = None; s.rr = []; s.noisepk = None
    def reset(s, t):
        s.x = [0.0] * 5; s.win = [0.0] * 38; s.sum = 0.0; s.fill = 0; s.cand = None
    def thr1(s): return s.npki + .25 * (s.spki - s.npki)
    def qrs(s, t, p, back=False):
        if s.last is not None:
            rr = t - s.last
            if 273 <= rr <= 2000: s.rr = (s.rr + [rr])[-8:]
        s.spki = (.25 if back else .125) * p + (.75 if back else .875) * s.spki
        s.last = t; s.noisepk = None
        return t
    def step(s, t, y):
        out = []
        if s.t0 is None: s.t0 = t
        s.x = s.x[1:] + [y]
        d = (2 * s.x[4] + s.x[3] - s.x[1] - 2 * s.x[0]) / 8.0
        sq = d * d
        s.sum += sq - s.win[s.k]; s.win[s.k] = sq; s.k = (s.k + 1) % 38; s.fill += 1
        if s.fill < 43: return out
        m = s.sum / 38.0
        if s.spki is None:                      # 学习期
            s.lmax.append(m)
            if t - s.t0 >= s.learn:
                s.spki = .25 * max(s.lmax); s.npki = .5 * statistics.fmean(s.lmax)
            return out
        # 局部峰：候选在 200 ms 内未被超过、或回落到一半即确认
        if s.cand is None or m > s.cand[1]: s.cand = (t, m)
        elif t - s.cand[0] >= 200 or m < .5 * s.cand[1]:
            pt, p = s.cand; s.cand = None
            if s.last is None or pt - s.last >= s.ref:
                if p > s.thr1(): out.append(s.qrs(pt, p))
                else:
                    s.npki = .125 * p + .875 * s.npki
                    if s.noisepk is None or p > s.noisepk[1]: s.noisepk = (pt, p)
        # 回溯：超过 1.66 倍平均 RR 仍无心搏，取期间最大噪声峰（> 半门限）
        if s.last is not None and len(s.rr) >= 2 and s.noisepk:
            avg = sum(s.rr) / len(s.rr)
            if t - s.last > 1.66 * avg and s.noisepk[1] > .5 * s.thr1() and s.noisepk[0] - s.last >= s.ref:
                pt, p = s.noisepk; out.append(s.qrs(pt, p, back=True))
        return out

class Med8:
    def __init__(s, keep=8, need=5, tol=.2, timeout=4000):
        s.keep, s.need, s.tol, s.timeout = keep, need, tol, timeout; s.iv = []; s.last = None; s.rate = 0
    def beat(s, t):
        if s.last is not None:
            e = t - s.last
            if e > 2000: s.iv = []
            elif e >= 273: s.iv = (s.iv + [e])[-s.keep:]
        s.last = t
        s.rate = 0
        if len(s.iv) >= s.need:
            m = statistics.median(s.iv); inl = [x for x in s.iv if abs(x - m) <= s.tol * m]
            if len(inl) >= s.need: s.rate = round(60000 / statistics.median(inl))
    def tick(s, t):
        if s.last is not None and t - s.last > s.timeout: s.iv = []; s.rate = 0; s.last = None
        return s.rate

def run(name, y):
    """返回 [(t, hr 或 0)]。name：C2 | A+C2 | B+C2 | B+C | A+B+C"""
    out = []
    if name in ('C2', 'A+C2'):
        _lib.D_Init(y[0][0] & 0xffffffff); comb = Comb(); prev = None
        for t, v in y:
            if prev is not None and t - prev > GAP: comb.reset()
            prev = t
            x = comb(v) if name == 'A+C2' else v
            out.append((t, _lib.D_Feed(x, t & 0xffffffff)))
        return out
    use_a = name.startswith('A+'); det = PT(); comb = Comb(); prev = None
    if name.endswith('+C2'): _lib.D_Init(y[0][0] & 0xffffffff)
    rule = Med8() if name.endswith('+C') else None
    for t, v in y:
        if prev is not None and t - prev > GAP: comb.reset(); det.reset(t)
        prev = t
        x = comb(v) if use_a else v
        for b in det.step(t, x):
            if rule: rule.beat(b)
            else: _lib.D_Beat(b & 0xffffffff)
        out.append((t, rule.tick(t) if rule else _lib.D_Tick(t & 0xffffffff)))
    return out
