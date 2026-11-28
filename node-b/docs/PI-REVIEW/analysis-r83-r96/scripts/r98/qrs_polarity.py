"""R106：检测带 ECG 的 QRS 主峰极性（判据写定后不改）。
记录的 ECG = 滤波后的 (ELA − ERA)：原理图 ELA→R15→IN2P、ERA→R4→IN2N，固件符号扩展、上传换算均为正系数。
峰：连续段（≥5 s）内 |y| 超过段内 p99 的 0.6 倍的局部极大，间隔 ≥300 ms；统计正、负主峰比例和幅度中位数。
用法：无参数时跑既有录制；`qrs_polarity.py <文件> <名称> <起 ms> <止 ms> ...` 跑指定窗口（每 4 个参数一组）。"""
import contextlib, io, sys, numpy as np
from load2 import load, runs
CAP = '../../r83-capture/'
def polarity(y):
    pos, neg = [], []
    for r in runs([(t, v, 1, 0, 0) for t, v in y], 4):
        if len(r) < 1250: continue
        v = np.array([x[1] for x in r]) * 1000   # µV（load2 的波形值为 mV）
        a = abs(v); thr = .6 * np.percentile(a, 99); last = -10 ** 9
        for i in range(1, len(v) - 1):
            if a[i] > thr and a[i] >= a[i - 1] and a[i] > a[i + 1] and i - last >= 75:
                last = i; (pos if v[i] > 0 else neg).append(a[i])
    n = len(pos) + len(neg)
    return n, (100 * len(pos) / n if n else float('nan')), (np.median(pos) if pos else 0.0), (np.median(neg) if neg else 0.0)
def show(name, y):
    n, p, mp, mn = polarity(y)
    print(f'{name:22s} 峰 {n:5d} | 主峰正向 {p:5.1f}% | 正峰中位 {mp:5.0f} µV | 负峰中位 {mn:5.0f} µV')
_c = {}
def ecg(f, A, B):
    if f not in _c: _c[f] = load(CAP + f)[0]['ecg']
    return [(x[0], x[1]) for x in _c[f] if A <= x[0] < B]
if __name__ == '__main__':
    if len(sys.argv) > 1:
        a = sys.argv[1:]
        for i in range(0, len(a), 4): show(a[i + 1], ecg(a[i], int(a[i + 2]), int(a[i + 3])))
    else:
        with contextlib.redirect_stdout(io.StringIO()):
            from ecg_eval import HUMAN, POS
        notes = {'R83 ankle': '厂家样例：红右踝 黄左踝 绿右腕', 'R85 wrist': '红右腕 黄左腕 绿右踝', 'R87 P2': '红右锁骨下 黄左下胸 绿右下腹',
                 'R89 S5': '同 P2', 'R91': '同 P2', 'R94': '同 P2（志愿者乙）'}
        print('=== 既有录制（检测带 ECG；模拟器接线均为 R红→RA、L黄→LA、F绿→RL）')
        for name, f, A, B in HUMAN + POS:
            show(name, ecg(f, A, B)); print(f'{"":22s} 贴法：{notes.get(name, "模拟器 R→RA L→LA F→RL")}')
