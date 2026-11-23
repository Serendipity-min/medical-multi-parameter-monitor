"""R118 C4 评测：在正确色标真人录制上比较心搏峰检门限口径（R118 §1 预先写定）。
数据用 r98/load2（批末时间轴）；y 为 B 检测带内部码（与固件同量纲）。时刻为北京时间，段定义见 R109/R111/R113/R117。
用法：在本目录先编译 gcc -std=c99 -O2 -ffp-contract=off -shared -fPIC -I. drv4.c -o drv4.so -lm，再 python3 -s -E eval4.py"""
import sys, bisect, statistics, random, ctypes as C
sys.path.insert(0, '../r98')
from load2 import load, UV_PER_Y
from r109_eval import ms
CAP = '../../r83-capture/'
L = C.CDLL('./drv4.so')
L.V_Init.argtypes = [C.c_uint32, C.c_int, C.c_float]
for f in (L.V_Feed, L.C2_Feed): f.argtypes = [C.c_float, C.c_uint32]; f.restype = C.c_uint32
CFG = [('C2', 0, 2.5), ('K2.0', 0, 2.0), ('N3.5', 1, 3.5), ('N3.0', 1, 3.0)]
# 正确色标真人（主判据）；旧色标真人只记录
HUMAN = {
    'R108 乙 1':  ('r108human-20261120T061515Z-node-ab.jsonl', ms(20,14,42,20), ms(20,14,48,30)),
    'R108 乙 2':  ('r108human-20261120T061515Z-node-ab.jsonl', ms(20,14,59,17), ms(20,15,5,19)),
    'R110 丙':    ('r110human-20261120T073145Z-node-ab.jsonl', ms(20,15,40,5), ms(20,15,55,25)),
    'R112 丁':    ('r112human-20261123T015825Z-node-ab.jsonl', ms(23,10,9,40), ms(23,10,25,50)),
    'R116 甲':    ('r116human-20261123T085733Z-node-ab.jsonl', ms(23,17,12,25), ms(23,17,35,30)),
}
OLD = {
    'R87 甲旧':   ('r87-20261118T083445Z-node-ab.jsonl', ms(18,16,42), ms(18,16,47,51)),
    'R94 乙旧':   ('r94human-20261119T090428Z-node-ab.jsonl', ms(19,17,8), ms(19,17,28)),
}
NEG = {
    'R83 导联断开': ('r83-20261118T065234Z-node-b.jsonl', ms(18,15,0,15), ms(18,15,4,0)),
}
RECON = {'R89 接回伪迹': ('r89sim-20261118T093511Z-node-ab.jsonl', ms(18,17,44,40), ms(18,17,45,40))}
SIM = {
    'R108 sim': ('r108human-20261120T061515Z-node-ab.jsonl', ms(20,14,19,45), ms(20,14,22,0)),
    'R110 sim': ('r110human-20261120T073145Z-node-ab.jsonl', ms(20,15,36,10), ms(20,15,37,0)),
    'R112 sim': ('r112human-20261123T015825Z-node-ab.jsonl', ms(23,10,1,10), ms(23,10,2,0)),
    'R116 sim': ('r116human-20261123T085733Z-node-ab.jsonl', ms(23,17,0,40), ms(23,17,1,30)),
    'R92 sim':  ('r92sim-20261119T082651Z-node-ab.jsonl', ms(19,16,31), ms(19,16,33,50)),
}
_c = {}
def rec(p):
    if p not in _c:
        w, sc, _ = load(CAP + p)
        _c[p] = ([(int(t), v * 1000 / UV_PER_Y) for t, v, *_ in w['ecg']], [(t, v) for t, v, s in sc['pr'] if s == 'VALID' and v],
                 [(t, v, s) for t, v, s in sc['hr']])
    return _c[p]
def seg(p, A, B, lead=20000):
    y, pr, hr = rec(p)
    return dict(y=[x for x in y if A - lead <= x[0] < B], A=A, B=B, pr=[x for x in pr if A <= x[0] < B], hr=[x for x in hr if A <= x[0] < B])
def run(cfg, y, raw=False):
    L.V_Init(y[0][0] & 0xffffffff, cfg[1], cfg[2]); f = L.C2_Feed if raw else L.V_Feed
    return [(t, f(v, t & 0xffffffff)) for t, v in y]
def score(o, d):
    w = [(t, r) for t, r in o if d['A'] <= t < d['B']]
    valid = 100 * sum(1 for _, r in w if r) / max(1, len(w))
    sec = {}
    for t, r in w:
        if r: sec[t // 1000] = r
    pt = [p[0] for p in d['pr']]; pairs = []
    for s, r in sec.items():
        i = bisect.bisect_left(pt, s * 1000)
        c = [d['pr'][j] for j in (i - 1, i) if 0 <= j < len(pt) and abs(pt[j] - s * 1000) <= 1000]
        if c: pairs.append((r, min(c, key=lambda z: abs(z[0] - s * 1000))[1]))
    vals = sorted(set(r for _, r in w if r))
    return valid, pairs, vals, len(w)
def noise(seed, seconds=180, sd=2000.0):
    g = random.Random(seed); return dict(y=[(i * 4, g.gauss(0, sd)) for i in range(seconds * 250)], A=0, B=seconds * 1000, pr=[])
if __name__ == '__main__':
    print('=== 夹具核对：mode 0、k=2.5 与原样 C2 逐点一致；回放 C2 与板上 HR 有效率')
    for name, (p, A, B) in HUMAN.items():
        d = seg(p, A, B); a = run(CFG[0], d['y']); b = run(CFG[0], d['y'], raw=True)
        board = 100 * sum(x[2] == 'VALID' for x in d['hr']) / max(1, len(d['hr']))
        print(f'{name:10s} 逐点一致 {a == b} | 回放 C2 {score(a, d)[0]:5.1f}% | 板上 {board:5.1f}%')
    print('=== 真人（有效率 | 与 PR ±10% | 误差中位）')
    tot = {c[0]: [0, 0, [], 0.0, 0] for c in CFG}
    for grp, title in ((HUMAN, '正确色标（判据）'), (OLD, '旧色标（只记录）')):
        print(f'--- {title}')
        for name, (p, A, B) in grp.items():
            d = seg(p, A, B); row = [f'{name:10s}']
            for c in CFG:
                v, pairs, _, n = score(run(c, d['y']), d); ok = sum(abs(r - q) <= .1 * q for r, q in pairs)
                err = statistics.median([abs(r - q) for r, q in pairs]) if pairs else float('nan')
                if grp is HUMAN: t = tot[c[0]]; t[0] += ok; t[1] += len(pairs); t[2] += [abs(r - q) for r, q in pairs]; t[3] += v * n; t[4] += n
                row.append(f'{c[0]} {v:5.1f}% {ok}/{len(pairs)} ({100 * ok / max(1, len(pairs)):3.0f}%) e{err:.0f}')
            print(' | '.join(row))
    print('合计（正确色标）：' + ' | '.join(f'{k} 有效 {t[3] / t[4]:.1f}% 一致 {100 * t[0] / max(1, t[1]):.1f}% ({t[0]}/{t[1]}) 误差中位 {statistics.median(t[2]) if t[2] else 0}' for k, t in tot.items()))
    print('=== 阴性对照（有效率、报出的值）')
    for name, (p, A, B) in NEG.items():
        d = seg(p, A, B); print(f'{name:12s} ' + ' | '.join(f'{c[0]} {score(run(c, d["y"]), d)[0]:5.1f}% {score(run(c, d["y"]), d)[2][:4]}' for c in CFG))
    for c in CFG:
        vs = [score(run(c, nd['y']), nd)[0] for nd in (noise(s) for s in range(1, 11))]
        print(f'白噪声 ×10 {c[0]}: 平均 {statistics.fmean(vs):.2f}% 最大 {max(vs):.2f}%')
    print('=== 接回伪迹（模拟器 60；报出值须在 54–66）')
    for name, (p, A, B) in RECON.items():
        d = seg(p, A, B); print(f'{name:12s} ' + ' | '.join(f'{c[0]} {score(run(c, d["y"]), d)[0]:5.1f}% {score(run(c, d["y"]), d)[2]}' for c in CFG))
    print('=== 模拟器 60 bpm（有效率、报出的值）')
    for name, (p, A, B) in SIM.items():
        d = seg(p, A, B); print(f'{name:10s} ' + ' | '.join(f'{c[0]} {score(run(c, d["y"]), d)[0]:5.1f}% {score(run(c, d["y"]), d)[2]}' for c in CFG))
