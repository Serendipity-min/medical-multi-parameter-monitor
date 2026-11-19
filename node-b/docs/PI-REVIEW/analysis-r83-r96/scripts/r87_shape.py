"""R87：以 B 峰检锚点（负向主峰）对齐的 QRS 形态，-200..+500 ms，看双相波两叶的幅度和间距、T 波。"""
import sys, bisect, statistics
exec(open('r87_extra.py').read().split("for path, A, B in")[0])
ecg, *_ = load('../r83-capture/r87-20261118T083445Z-node-ab.jsonl')
A, B = ms(16,42,0), ms(16,47,51)
y = [(int(t), mv * 1000 / UV_PER_Y) for t, mv, _, _ in ecg if A - 5000 <= t < B]
det = [d for d in detector(y) if d[0] >= A and d[2] < 0]
ts = [t for t, _ in y]; vs = [v * UV_PER_Y for _, v in y]
acc = [0.0] * 175; n = 0
for d in det:
    i0 = bisect.bisect_left(ts, d[0] - 200)
    if i0 + 175 < len(ts) and abs(ts[i0 + 174] - (d[0] + 496)) <= 12:
        for k in range(175): acc[k] += vs[i0 + k]
        n += 1
avg = [a / n for a in acc]
print('beats', n)
print(' '.join(f'{(k*4-200):+d}:{avg[k]:.0f}' for k in range(0, 175, 3)))
