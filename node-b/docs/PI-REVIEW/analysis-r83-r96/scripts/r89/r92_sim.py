"""R92 模拟器链路自检：按现场时刻分段，计算检测带 p1/p99、RMS、分带残留、HR 有效与恢复时间。µV 口径同 R89 S3。"""
import sys, json, numpy as np, datetime
sys.path.insert(0, '..')
from load import load
TZ = datetime.timezone(datetime.timedelta(hours=8))
def ms(d, h, m, s=0): return int(datetime.datetime(2026, 11, d, h, m, s, tzinfo=TZ).timestamp() * 1000)
def stats(t, v, A, B):
    m = (t >= A) & (t < B); x = v[m]
    if len(x) < 500: return None
    cut = np.where(np.diff(t[m]) > 6)[0] + 1; P = np.zeros(4); n = 0; f = np.fft.rfftfreq(500, 1/250)
    for s in np.split(np.arange(len(x)), cut):
        y = x[s]
        for k in range(0, len(y) - 499, 500):
            z = y[k:k+500] - y[k:k+500].mean(); X = abs(np.fft.rfft(z)) ** 2 * 2 / 500 ** 2
            P += [X[(f >= a) & (f < b)].sum() for a, b in [(0.5, 5), (5, 25), (25, 45), (45, 55)]]; n += 1
    b = np.sqrt(P / max(n, 1))
    return dict(n=len(x), miss=100 - 100 * len(x) / ((B - A) / 4), p1=np.percentile(x, 1), p99=np.percentile(x, 99), rms=x.std(), b=b)
def hrv(hr, A, B):
    h = [x for x in hr if A <= x[0] < B]; v = [x[1] for x in h if x[2] == 'VALID']
    return len(v), len(h), sorted(set(int(x) for x in v))
e89, *_ = load('../../r83-capture/r89sim-20261118T093511Z-node-ab.jsonl')
e92, _, hr92, _ = load('../../r83-capture/r92sim-20261119T082651Z-node-ab.jsonl')
T = lambda e: (np.array([x[0] for x in e]), np.array([x[1] * 1000 for x in e]))
t89, v89 = T(e89); t, v = T(e92)
def row(name, s, h=None):
    if not s: print(f'{name:34s} too few samples'); return
    hs = f'| HR valid {h[0]}/{h[1]} {h[2][:4]}' if h else ''
    print(f'{name:34s} miss {s["miss"]:3.0f}% p1/p99 {s["p1"]:+6.0f}/{s["p99"]:+6.0f} rms {s["rms"]:6.1f} | 0.5-5 {s["b"][0]:6.1f} 5-25 {s["b"][1]:6.1f} 25-45 {s["b"][2]:5.1f} 45-55 {s["b"][3]:5.1f} {hs}')
row('R89 S3 sim baseline 17:42-44', stats(t89, v89, ms(18,17,42), ms(18,17,44)))
D = 19
segs = [('S2 baseline 16:31:10-16:33:00', (16,31,10), (16,33,0)),
        ('pre-S3 16:33:00-16:34:00', (16,33,0), (16,34,0)),
        ('RA wiggle 16:34:00-20', (16,34,0), (16,34,20)), ('after RA +10..+60 s', (16,34,30), (16,35,20)),
        ('LA wiggle 16:35:50-36:10', (16,35,50), (16,36,10)), ('after LA +10..+40 s', (16,36,20), (16,36,50)),
        ('RL wiggle 16:36:50-37:10', (16,36,50), (16,37,10)), ('after RL +10..+60 s', (16,37,20), (16,38,10)),
        ('S4/S5 16:38:10-16:42:00', (16,38,10), (16,42,0)),
        ('RL off 16:42:10-16:42:50', (16,42,10), (16,42,50)), ('RL back +20 s 16:43:10-30', (16,43,10), (16,43,30))]
for name, a, b in segs:
    A, B = ms(D, *a), ms(D, *b); row(name, stats(t, v, A, B), hrv(hr92, A, B))
# 恢复：每次操作结束后首个有效 HR 帧与之后连续有效
for name, end in [('RA', (16,34,20)), ('LA', (16,36,10)), ('RL', (16,37,10)), ('RL reattach', (16,42,50))]:
    E = ms(D, *end); after = [x for x in hr92 if x[0] >= E]
    first = next((x for x in after if x[2] == 'VALID'), None)
    print(f'{name:12s} end {datetime.datetime.fromtimestamp(E/1000,TZ).strftime("%T")} first valid HR at +{(first[0]-E)/1000 if first else float("nan"):.1f} s value {first[1] if first else "-"}; next 30 s valid {sum(1 for x in after if x[0]<E+30000 and x[2]=="VALID")}/{sum(1 for x in after if x[0]<E+30000)}')
# 逐 10 s 有效 HR 时间线（16:31-16:43:30）
line = []
for s in range(ms(D,16,31), ms(D,16,43,30), 10000):
    h = [x for x in hr92 if s <= x[0] < s + 10000]; line.append(f'{datetime.datetime.fromtimestamp(s/1000,TZ).strftime("%M:%S")} {sum(x[2]=="VALID" for x in h)}/{len(h)}')
print(' | '.join(line))
