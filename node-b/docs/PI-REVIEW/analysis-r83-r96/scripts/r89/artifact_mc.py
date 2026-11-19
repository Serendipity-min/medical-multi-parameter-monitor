"""伪迹尖峰序列（准周期，中心间期 m、相对均匀抖动 ±j）喂入 C1/C2 心搏判据，比较误判有效占比。只作对照，不代表真实伪迹统计。"""
import ctypes as C, random, math
libs = {}
for k in ('c1', 'c2'):
    l = C.CDLL(f'./replay_{k}.so'); l.Replay_Init.argtypes = [C.c_uint32]
    l.Replay_Feed.argtypes = [C.c_float, C.c_uint32]; l.Replay_Feed.restype = C.c_uint32; libs[k] = l
def train(m, j, seconds, rng):
    t, out = 500.0, []
    while t < seconds * 1000: out.append(t); t += m * (1 + rng.uniform(-j, j))
    return out
def run(lib, beats, seconds, rng):
    lib.Replay_Init(1000); valid = 0; i = 0
    for n in range(seconds * 250):
        t = n * 4; y = rng.gauss(0, 60)
        while i < len(beats) and beats[i] < t - 40: i += 1
        for b in beats[i:i + 2]:
            y += 1500 * math.exp(-.5 * ((t - b) / 10) ** 2)
        valid += lib.Replay_Feed(y, 1000 + t) != 0
    return 100 * valid / (seconds * 250)
print('m(ms) jitter | C1 valid% | C2 valid%   (20 runs x 30 s each)')
for m in (400, 820):
    for j in (.10, .20, .25, .30, .40):
        res = {}
        for k, l in libs.items():
            rng = random.Random(11); tot = 0
            for r in range(20): tot += run(l, train(m, j, 30, rng), 30, rng)
            res[k] = tot / 20
        print(f'{m:5d} ±{int(j*100):2d}%     | {res["c1"]:8.1f} | {res["c2"]:8.1f}')
