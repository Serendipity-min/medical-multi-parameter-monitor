"""R103：主线 bio_v2.c 在 BIO_V2_ALC=0/1 下的纯噪声阴性对照扩种子（与主机用例 c1_noise_mains 同一发生器，180 s/种子）。
主机用例门槛：心率有效样本 ≤2%。这里看 ALC 是否系统性抬高噪声误报，而不是只看 6 个种子。"""
import ctypes as C, math, random, subprocess, tempfile, pathlib
SRC = pathlib.Path(__file__).resolve().parents[5] / 'firmware/biov2/实验固件/HARDWARE/bio_v2.c'
SEEDS = range(1, 101)
tmp = pathlib.Path(tempfile.mkdtemp())
def lib(alc):
    so = tmp / f'bio_{alc}.so'
    subprocess.run(['gcc', '-std=c99', '-O2', '-ffp-contract=off', '-shared', '-fPIC', f'-DBIO_V2_ALC={alc}', str(SRC), '-o', str(so), '-lm'], check=True)
    L = C.CDLL(str(so)); L.BioV2_Init.argtypes = [C.c_uint32]; L.BioV2_Process.argtypes = [C.c_int32, C.c_int32, C.c_uint32, C.c_uint32, C.c_uint8]
    return L
OFF_HR_VALID = 14   # BioV2Diag 中 hr_valid 的 uint32 序号（8 个计数 + 4 个波形 + hr、rpm 之后）
def run(L, seed, amplitude):
    noise = random.Random(seed); L.BioV2_Init(1000); base = C.addressof(C.c_uint32.in_dll(L, 'g_bio_v2'))
    hv = C.c_uint32.from_address(base + 4 * OFF_HR_VALID); n = 0
    for i in range(180 * 250):
        t = i / 250
        h = int(round(200000 + noise.gauss(0, 2000) + amplitude * math.sin(2 * math.pi * 50 * t))); r = int(round(640000 + noise.gauss(0, 2000)))
        L.BioV2_Process(h, r, (1000 + i * 4) & 0xffffffff, i + 1, 0); n += hv.value != 0
    return 100 * n / (180 * 250)
for amplitude in (0, 70000):
    res = {alc: [run(lib(alc), s, amplitude) for s in SEEDS] for alc in (0, 1)}
    for alc, v in res.items():
        print(f'mains {amplitude:6d} ALC={alc}: 种子 {len(v)} | 平均有效 {sum(v)/len(v):.3f}% | 有任何有效的种子 {sum(x > 0 for x in v)} | >2% 的种子 {sum(x > 2 for x in v)} | 最大 {max(v):.2f}%（种子 {1 + v.index(max(v))}）| 种子5 {v[4]:.2f}%')
# 配对比较：再取种子 101–400（无工频；上面两档工频结果相同，陷波已把 70000 码工频滤净）
L0, L1 = lib(0), lib(1)
p = [(run(L0, s, 0), run(L1, s, 0)) for s in range(101, 401)]
a, b = [x for x, _ in p], [y for _, y in p]
print(f'配对 300 种子：ALC=0 平均 {sum(a)/300:.3f}% >2% {sum(x > 2 for x in a)} | ALC=1 平均 {sum(b)/300:.3f}% >2% {sum(y > 2 for y in b)}'
      f' | ALC 更高 {sum(y > x for x, y in p)} / 更低 {sum(y < x for x, y in p)} / 相同 {sum(y == x for x, y in p)}')
