"""C3 数据集：真人（含 A 的 PR 参照）、阴性对照、阳性对照。y 为 B 检测带内部码（与固件 y 同量纲）。"""
import sys, json, random, math, datetime
sys.path.insert(0, '..')
from load import load, UV_PER_Y
TZ = datetime.timezone(datetime.timedelta(hours=8))
CAP = '../../r83-capture/'
def ms(d, h, m, s=0): return int(datetime.datetime(2026, 11, d, h, m, s, tzinfo=TZ).timestamp() * 1000)
_cache = {}
def rec(path):
    if path not in _cache:
        ecg, *_ = load(CAP + path)
        pr = []
        for l in open(CAP + path):
            r = json.loads(l)
            if r['topic'].endswith('NODE-A/telemetry/pr'):
                p = json.loads(r['payload'])
                if p['validity'] == 'VALID' and p['value']: pr.append((p['timestamp'], p['value']))
        _cache[path] = ([(int(t), mv * 1000 / UV_PER_Y) for t, mv, _, _ in ecg], sorted(pr))
    return _cache[path]
def seg(path, A, B, lead=20000):
    y, pr = rec(path)
    return dict(y=[x for x in y if A - lead <= x[0] < B], A=A, B=B, pr=[p for p in pr if A <= p[0] < B])
HUMAN = {
    'R87 P2':   ('r87-20261118T083445Z-node-ab.jsonl', ms(18,16,42), ms(18,16,47,51)),
    'R89 S5':   ('r89human-20261118T102758Z-node-ab.jsonl', ms(18,18,33), ms(18,18,43,30)),
    'R91':      ('r91human-20261119T072140Z-node-ab.jsonl', ms(19,15,33,40), ms(19,16,3,40)),
    'R94':      ('r94human-20261119T090428Z-node-ab.jsonl', ms(19,17,8), ms(19,17,28)),
    'R85 wrist':('r85-20261118T074904Z-node-ab.jsonl', ms(18,15,58,40), ms(18,16,3,40)),
    'R83 ankle':('r83-20261118T065234Z-node-b.jsonl', ms(18,15,4,20), ms(18,15,9,30)),
}
NEG = {
    'R83 leads-off': ('r83-20261118T065234Z-node-b.jsonl', ms(18,15,0,15), ms(18,15,4,0)),
    'R89 reconnect': ('r89sim-20261118T093511Z-node-ab.jsonl', ms(18,17,44,40), ms(18,17,45,40)),
}
POS = {
    'R83 sim60': ('r83-20261118T065234Z-node-b.jsonl', ms(18,14,59,21), ms(18,15,0,8)),
    'R89 sim60': ('r89sim-20261118T093511Z-node-ab.jsonl', ms(18,17,41), ms(18,17,44,30)),
    'R92 sim60': ('r92sim-20261119T082651Z-node-ab.jsonl', ms(19,16,31), ms(19,16,33,50)),
}
def noise(seed, seconds=180, sd=2000.0):
    rng = random.Random(seed); return dict(y=[(i * 4, rng.gauss(0, sd)) for i in range(seconds * 250)], A=0, B=seconds * 1000, pr=[])
def artifact(m, j, seed, seconds=30):
    """R90 式准周期尖峰：中心间期 m ms、相对抖动 ±j，叠加白噪声（内部码）。"""
    rng = random.Random(seed); t, beats = 500.0, []
    while t < seconds * 1000: beats.append(t); t += m * (1 + rng.uniform(-j, j))
    y, i = [], 0
    for n in range(seconds * 250):
        tt = n * 4; v = rng.gauss(0, 800)
        while i < len(beats) and beats[i] < tt - 40: i += 1
        for b in beats[i:i+2]: v += 20000 * math.exp(-.5 * ((tt - b) / 10) ** 2)
        y.append((tt, v))
    return dict(y=y, A=0, B=seconds * 1000, pr=[])
