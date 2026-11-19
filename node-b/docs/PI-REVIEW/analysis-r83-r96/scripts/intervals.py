"""人体段（15:04:20–15:09:30）逐个心搏：B 判据接受的间期、被拒候选，以及间期相对局部中位数的比值分布。"""
import sys, math, statistics, collections
from load import load, hms, UV_PER_Y
ecg, *_ = load(sys.argv[1])
lo, hi = int(sys.argv[2]), int(sys.argv[3])
band, in_peak, peak, gate, above, peak_t = 0.0, False, 0.0, 0.0, 0, 0
cands = []   # (peak_t, width, peak, gate, ok)
for t, mv, _, _ in ecg:
    t = int(t); y = mv * 1000.0 / UV_PER_Y
    band += .004 * (y * y - band); a = abs(y)
    thr = max(30.0, 2.5 * math.sqrt(max(band, 0.0)))
    if not in_peak and a >= thr:
        in_peak, above, peak, peak_t, gate = True, t, a, t, thr
    elif in_peak:
        if a > peak: peak, peak_t = a, t
        if a < gate * .5 or t - above > 200:
            width = t - above; in_peak = False
            if lo <= peak_t < hi:
                cands.append((peak_t, width, peak, gate, 12 <= width <= 160 and peak >= gate * 1.05))
ok = [c for c in cands if c[4]]
print('candidates', len(cands), 'pass width/amp', len(ok))
print('reject reasons: width>160', sum(c[1] > 160 for c in cands), 'width<12', sum(c[1] < 12 for c in cands),
      'amp<1.05gate', sum(c[2] < c[3] * 1.05 for c in cands))
# 不应期 273 ms 后的被接受间期序列（模拟 accept 中 anchor 逻辑）
anchor, iv = None, []
for c in ok:
    if anchor is None: anchor = c[0]; continue
    e = c[0] - anchor
    if e < 273: continue
    iv.append((c[0], e)); anchor = c[0]
vals = [e for _, e in iv if e <= 2000]
med = statistics.median(vals)
print(f'accepted intervals {len(vals)}, median {med} ms ({60000/med:.1f} bpm), p10 {sorted(vals)[len(vals)//10]}, p90 {sorted(vals)[len(vals)*9//10]}')
ratio = collections.Counter()
for i, (t, e) in enumerate(iv):
    local = statistics.median([x for _, x in iv[max(0, i-4):i+5]])
    r = e / local
    bucket = '<0.6 extra' if r < 0.6 else '0.6-0.8' if r < 0.8 else '0.8-1.2 normal' if r <= 1.2 else '1.2-1.6' if r < 1.6 else '>=1.6 missed'
    ratio[bucket] += 1
print('interval / local median:', dict(ratio))
print('first 40 intervals (ms):', [e for _, e in iv[:40]])
amp = [c[2] * UV_PER_Y for c in ok]
print(f'accepted peak amplitude median {statistics.median(amp):.0f} uV, gate median {statistics.median([c[3]*UV_PER_Y for c in ok]):.0f} uV')
