"""R103 离线检验：B 的 ADS1292R 实际采样率，以及 R94 工频残留起伏的来源（谐波混叠拍频 vs 工频频率漂过固定陷波）。
1) 采样率：网关只在相邻样本 tick 差恰为 4 ms 时续批，差 3 ms 时从该点重开新批、丢掉未满的批（seq 不跳）。
   因此批末差 399/400/401 ms 的相邻批之间正好 100 个 DRDY 间隔，用这些“连续链”估 fs；
   链内看不到被丢掉的批里的滑点，所以这是 fs 偏差的下限。另报网关实际出批率（丢批比例）。
   再用 MQTT 收包时间 ts_ms（服务器时钟）对批末时间戳做长程斜率，确认时间戳与服务器时钟同速。
2) 工频残留：按样本序号（数字频率）在 50 Hz 解调上传的 ECG（C2 滤波后 y），1 s 平滑得幅度 A(t)、相位 φ(t)，
   由 φ 斜率得残留相对数字 50 Hz 的频差 Δ(t)。
   - 混叠拍频假设：40–60 s 包络要求 |Δ| 约 3–5 mHz（拍频 = 5|Δ|）；
   - 陷波漂移假设：A ∝ |Δ|（窄陷波在中心附近幅频近似线性），A 近零处 Δ 过零、相位翻转。"""
import json, datetime, numpy as np
from load2 import load, runs
TZ = datetime.timezone(datetime.timedelta(hours=8))
CAP = '../../r83-capture/'
def T(d, h, m, s=0): return datetime.datetime(2026, 11, d, h, m, s, tzinfo=TZ).timestamp() * 1000
FILES = [('R92 sim', 'r92sim-20261119T082651Z-node-ab.jsonl', None), ('R89 human', 'r89human-20261118T102758Z-node-ab.jsonl', (T(18,18,33), T(18,18,43,30))),
         ('R91 human', 'r91human-20261119T072140Z-node-ab.jsonl', (T(19,15,33,40), T(19,16,3,40))),
         ('R94 human', 'r94human-20261119T090428Z-node-ab.jsonl', (T(19,17,8), T(19,17,28))),
         ('R100 human', 'r100rr-20261119T112442Z-node-ab.jsonl', None)]
F0 = 50.0; NOTCH_HALF_BW = F0 / 35 / 2   # C2 陷波 Q=35 的 -3 dB 半宽（Hz）

def rate(f):
    rows = [json.loads(l) for l in open(CAP + f, encoding='utf-8')]
    e = []
    for r in rows:
        if r['topic'].endswith('NODE-B/telemetry/ecg'):
            p = json.loads(r['payload']); e.append((p['seq'], p['timestamp'], len(p['samples']), r['ts_ms'], p.get('session_id')))
    e.sort()
    pairs = [(b[1] - a[1], a[2]) for a, b in zip(e, e[1:]) if b[0] == a[0] + 1 and b[4] == a[4] and b[2] == a[2]]
    G = np.array([g for g, _ in pairs], float); n = np.array([k for _, k in pairs], float)
    chain = abs(G - 4 * n) <= 1
    fs = 1000 * n[chain].sum() / G[chain].sum()
    kept = sum(x[2] for x in e) / (250 * (e[-1][1] - e[0][1]) / 1000)
    ts = np.array([x[1] for x in e], float); rx = np.array([x[3] for x in e], float)
    slope = np.polyfit(rx - rx[0], ts - ts[0], 1)[0]   # 批末时间戳 / 服务器收包时间
    return fs, int(chain.sum()), {g: int((G == g).sum()) for g in (399, 400, 401)}, slope, (rx[-1] - rx[0]) / 1000, kept

def line(f, span):
    w, _, _ = load(CAP + f)
    s = [x for x in w['ecg'] if span is None or span[0] <= x[0] < span[1]]
    A, D, Tm, Z = [], [], [], []
    for r in runs(s, 4):
        if len(r) < 250 * 6: continue
        y = np.array([x[1] * 1000 for x in r]); t = np.array([x[0] for x in r])   # µV
        z = y * np.exp(-2j * np.pi * F0 / 250 * np.arange(len(y)))
        z = np.convolve(z, np.ones(250) / 250, 'valid') * 2                       # 1 s 平滑：复振幅
        tz = t[125:125 + len(z)]
        ph = np.unwrap(np.angle(z))
        for i in range(250, len(z) - 250, 250):                                  # 每秒一个点，±1 s 求斜率
            A.append(abs(z[i])); D.append((ph[i + 250] - ph[i - 250]) / (2 * np.pi * 2.0)); Tm.append(tz[i]); Z.append(z[i])
    return np.array(A), np.array(D), np.array(Tm), np.array(Z)

def flips(A, D, Tm, Z):
    """A 的局部极小（±10 s 内最小且 <0.3×窗内最大、前后 3 s 同一连续段）处，扣除中位漂移后的相位跳变；与全部时刻对照。"""
    dm = np.median(D); jump = lambda i: abs(np.angle(Z[i + 3] * np.conj(Z[i - 3]) * np.exp(-2j * np.pi * dm * 6)))
    ok = [i for i in range(3, len(A) - 3) if abs(Tm[i + 3] - Tm[i - 3] - 6000) < 50]
    mins = [i for i in ok if A[i] == A[max(0, i - 10):i + 11].min() and A[i] < .3 * A[max(0, i - 10):i + 11].max()]
    big = lambda idx: np.mean([jump(i) > 3 * np.pi / 4 for i in idx]) if idx else float('nan')
    return len(mins), big(mins), big(ok)

print('=== 1. B 采样率（相邻批：批末时间差 / 100 点）')
for name, f, _ in FILES:
    fs, k, hist, slope, dur, kept = rate(f)
    print(f'{name:11s} 链 {k:5d} 对 gap399/400/401 {hist} | 出批率 {100*kept:.0f}% | fs ≥ {fs:.3f} SPS ({1e6*(fs/250-1):+.0f} ppm)'
          f' | 批末时间戳/收包时间 斜率 {slope:.6f}（{dur:.0f} s）| 数字频率下的电网 50 Hz = {F0*250/fs:.4f} Hz')
print('=== 2. 工频残留：按数字频率 50 Hz 解调（每秒一点；Δ>0 表示残留高于数字 50 Hz）')
for name, f, span in FILES[1:]:
    A, D, Tm, Z = line(f, span)
    if not len(A): print(name, 'no long runs'); continue
    big = A > np.percentile(A, 50)
    corr = np.corrcoef(A, abs(D))[0, 1]
    k = np.median(A[big] / np.maximum(abs(D[big]), 1e-4))   # µV/Hz
    lo = A < np.percentile(A, 10)
    flip = np.mean([np.sign(D[max(0, i - 3)]) != np.sign(D[min(len(D) - 1, i + 3)]) for i in np.where(lo)[0]])
    print(f'{name:11s} {len(A):4d} s | A p10/50/90 {np.percentile(A,[10,50,90]).round(1).tolist()} µV'
          f' | Δ p10/50/90 {np.percentile(D,[10,50,90]).round(4).tolist()} Hz | |Δ|<5 mHz 占 {100*np.mean(abs(D)<.005):.0f}%'
          f' | corr(A,|Δ|) {corr:.2f} | A 最低 10% 处前后 3 s Δ 变号 {100*flip:.0f}%')
    nm, fm, fa = flips(A, D, Tm, Z)
    print(f'{"":11s} A 局部极小 {nm} 处，扣除漂移后相位跳变 >135° 的比例 {100*fm:.0f}%（全部时刻 {100*fa:.0f}%）')
    if name.startswith('R94'):
        print('  R94 逐 10 s（A µV, Δ mHz）：')
        for i in range(0, len(A), 20):
            print('   ', datetime.datetime.fromtimestamp(Tm[i] / 1000, TZ).strftime('%T'), f'A {A[i]:6.1f}  Δ {1000*D[i]:+6.1f}')
