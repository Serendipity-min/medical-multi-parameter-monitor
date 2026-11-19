"""R89 模拟器：断开/接回前后 HR 帧与 ECG 逐秒统计。"""
import sys, json, statistics, math
sys.path.insert(0, '.')
from load import load, hms, UV_PER_Y
ecg, resp, hr, rr = load(sys.argv[1])
A, B = int(sys.argv[2]), int(sys.argv[3])
H = {int(t // 1000): (v, s) for t, v, s in hr}
E = {}
for t, mv, ok, seq in ecg:
    if A <= t < B: E.setdefault(int(t // 1000), []).append((mv * 1000 / UV_PER_Y, ok, seq))
for s in range(A // 1000, B // 1000):
    e = E.get(s, [])
    ys = [y for y, _, _ in e]
    st = f'n {len(e):3d} valid {sum(o for _, o, _ in e):3d} min {min(ys):9.0f} max {max(ys):9.0f} rms {math.sqrt(statistics.fmean(y*y for y in ys)):8.0f}' if e else 'no ecg'
    print(hms(s * 1000)[:8], H.get(s, ('-', '-')), st)
