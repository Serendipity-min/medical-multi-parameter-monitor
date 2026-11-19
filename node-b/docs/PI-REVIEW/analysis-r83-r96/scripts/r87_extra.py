"""R87：B 峰检“多检”来源——短间期分布、峰极性；以及 TP 段（R 后 550–800 ms）噪声 RMS。踝部 R83 对照。"""
import sys, math, statistics, collections, bisect
from load import load, UV_PER_Y
from variants import ms
def detector(seg, mult=2.5):
    """B 的峰检（与 replay 相同门限），返回 (峰时刻, 峰值/门限)。"""
    band, in_peak, out = 0.0, False, []
    for t, y in seg:
        band += .004 * (y * y - band); a = abs(y)
        thr = max(30.0, mult * math.sqrt(max(band, 0.0)))
        if not in_peak and a >= thr: in_peak, above, peak, pt, gate, sign = True, t, a, t, thr, (1 if y > 0 else -1)
        elif in_peak:
            if a > peak: peak, pt, sign = a, t, (1 if y > 0 else -1)
            if a < gate * .5 or t - above > 200:
                in_peak = False
                if 12 <= t - above <= 160 and peak >= gate * 1.05: out.append((pt, peak / gate, sign))
    return out

for path, A, B in [('../r83-capture/r87-20261118T083445Z-node-ab.jsonl', ms(16,42,0), ms(16,47,51)),
                   ('../r83-capture/r83-20261118T065234Z-node-b.jsonl', ms(15,4,20), ms(15,9,30)),
                   ('../r83-capture/r85-20261118T074904Z-node-ab.jsonl', ms(15,58,40), ms(16,3,40))]:
    ecg, *_ = load(path)
    y = [(int(t), mv * 1000 / UV_PER_Y) for t, mv, _, _ in ecg if A - 5000 <= t < B]
    det = [d for d in detector(y) if d[0] >= A]
    ivs = [(x, b[0] - x[0], b) for x, b in zip(det, det[1:])]
    med = statistics.median(iv for _, iv, _ in ivs)
    short = [iv for _, iv, _ in ivs if iv < 0.7 * med]
    h = collections.Counter(min(iv // 100 * 100, 900) for iv in short)
    pol = collections.Counter(d[2] for d in det)
    # 短间期对：第一峰与第二峰极性
    pairs = collections.Counter((x[2], b[2]) for x, iv, b in ivs if iv < 0.7 * med)
    ts = [t for t, _ in y]; vs = [v * UV_PER_Y for _, v in y]
    tp = []
    for (x, iv, b) in ivs:
        if iv > 850:
            i0, i1 = bisect.bisect_left(ts, x[0] + 550), bisect.bisect_left(ts, x[0] + 800)
            if i1 - i0 > 55: tp.extend(vs[i0:i1])
    tprms = math.sqrt(statistics.fmean(v * v for v in tp)) if tp else float('nan')
    pk_uv = statistics.median(abs(vs[bisect.bisect_left(ts, d[0])]) for d in det)
    print(path.split('/')[-1][:3], f'det {len(det)} median iv {med:.0f} ms | short<0.7x {len(short)} ({100*len(short)/len(ivs):.0f}%) by 100ms bin {sorted(h.items())} | polarity {dict(pol)} | short pairs (sign1,sign2) {dict(pairs)} | detected peak |y| median {pk_uv:.0f} uV | TP-seg RMS {tprms:.0f} uV (n {len(tp)})')

print('--- after 273 ms refractory (as Periods.accept), anchor sequence:')
import json
for path, A, B in [('../r83-capture/r87-20261118T083445Z-node-ab.jsonl', ms(16,42,0), ms(16,47,51)),
                   ('../r83-capture/r83-20261118T065234Z-node-b.jsonl', ms(15,4,20), ms(15,9,30))]:
    ecg, *_ = load(path)
    y = [(int(t), mv * 1000 / UV_PER_Y) for t, mv, _, _ in ecg if A - 5000 <= t < B]
    det = [d for d in detector(y) if d[0] >= A]
    anc = []
    for d in det:
        if not anc or d[0] - anc[-1][0] >= 273: anc.append(d)
    ivs = [b[0] - a[0] for a, b in zip(anc, anc[1:])]
    sw = collections.Counter((a[2], b[2]) for a, b in zip(anc, anc[1:]))
    cls = collections.Counter(); win_fail = collections.Counter()
    for i in range(len(ivs)):
        w = ivs[max(0, i - 4): i + 1]
        if len(w) < 5: continue
        m = sorted(w)[2]; dev = max(abs(x - m) for x in w) / m
        has_missed = any(x > 1.6 * m for x in w); has_extra = any(x < 0.6 * m for x in w)
        same_pol = len(set(anc[j][2] for j in range(max(0, i - 4), i + 2))) == 1
        k = 'ok' if dev <= .2 else 'missed' if has_missed else 'extra' if has_extra else 'rsa/jitter'
        cls[k] += 1
        if k == 'rsa/jitter': win_fail['mixed-polarity' if not same_pol else 'same-polarity'] += 1
    tot = sum(cls.values())
    print(path.split('/')[-1][:3], f'anchors {len(anc)} | 5-interval windows: ' + ', '.join(f'{k} {100*v/tot:.0f}%' for k, v in cls.most_common()), '| rsa/jitter windows by anchor polarity', dict(win_fail), '| anchor polarity transitions', dict(sw))
