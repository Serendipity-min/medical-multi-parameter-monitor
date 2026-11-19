import sys, math, statistics, datetime
from load import load, UV_PER_Y, hms
from variants import ms
ecg, *_ = load(sys.argv[1])
lo, hi = ms(15, 4, 20), ms(15, 9, 30)
band, in_peak, peak, gate, above, peak_t = 0.0, False, 0.0, 0.0, 0, 0
beats = []
for t, mv, _, _ in ecg:
    t = int(t); y = mv * 1000 / UV_PER_Y
    band += .004 * (y * y - band); a = abs(y); thr = max(30.0, 2.5 * math.sqrt(max(band, 0.0)))
    if not in_peak and a >= thr: in_peak, above, peak, peak_t, gate = True, t, a, t, thr
    elif in_peak:
        if a > peak: peak, peak_t = a, t
        if a < gate * .5 or t - above > 200:
            w = t - above; in_peak = False
            if 12 <= w <= 160 and peak >= gate * 1.05 and lo <= peak_t < hi:
                if not beats or peak_t - beats[-1] >= 273: beats.append(peak_t)
iv = [(b2, b2 - b1) for b1, b2 in zip(beats, beats[1:])]
# 去掉漏检（约 2 倍）后，看正常间期的 5 拍窗口最大偏差
norm = [(t, e) for t, e in iv if 350 <= e <= 900]
dev = []
for i in range(4, len(norm)):
    w = [e for _, e in norm[i-4:i+1]]; m = sorted(w)[2]
    dev.append(max(abs(x - m) for x in w) / m)
dev.sort()
print('normal intervals', len(norm), 'min/median/max', min(e for _, e in norm), statistics.median(e for _, e in norm), max(e for _, e in norm))
print('5-beat window max deviation: p50 %.0f%% p75 %.0f%% p90 %.0f%%; share within 20%%: %.0f%%, within 30%%: %.0f%%' %
      (100*dev[len(dev)//2], 100*dev[len(dev)*3//4], 100*dev[len(dev)*9//10], 100*sum(d <= .2 for d in dev)/len(dev), 100*sum(d <= .3 for d in dev)/len(dev)))
succ = sorted(abs(b - a) / a for (_, a), (_, b) in zip(norm, norm[1:]))
print('successive change: p50 %.0f%% p90 %.0f%%, share <=15%%: %.0f%%' % (100*succ[len(succ)//2], 100*succ[len(succ)*9//10], 100*sum(s <= .15 for s in succ)/len(succ)))
# 每 2 s 的瞬时心率，看是否随慢呼吸周期起伏
print('instantaneous HR every beat 15:07:10-15:08:10:')
print(' '.join(f'{60000/e:.0f}' for t, e in norm if ms(15,7,10) <= t < ms(15,8,10)))
