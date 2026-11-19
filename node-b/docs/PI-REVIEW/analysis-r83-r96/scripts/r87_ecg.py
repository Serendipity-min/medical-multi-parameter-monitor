"""R87 ECG 分段：PPG 锁定集合平均 QRS、带内 RMS、B 检出的心搏间期分类（漏检/多检/节律变化），C1 与 C2 重放有效率，HR-PR 10 s 中位数差。"""
import sys, json, math, bisect, statistics, collections
from load import load, hms, UV_PER_Y
from hr import Periods
from variants import ms, replay
from hr import UNSTABLE
from variants import P2
class P3(P2):
    """C2：漏检容忍 + ±30%（同 variants2.P3；该文件导入即运行，故此处复制）。"""
    def accept(self, at):
        super().accept(at)
        if self.reason == UNSTABLE and self.count >= self.required:
            s = sorted(self.intervals[:self.count]); m = s[self.count // 2]
            if max(abs(x - m) for x in s) <= 0.30 * m:
                self.rate, self.reason = (60000 + m // 2) // m, 0
path = sys.argv[1]
ppg = []
for l in open(path):
    r = json.loads(l)
    if r['topic'].endswith('NODE-A/telemetry/ppg'):
        p = json.loads(r['payload']); step = 1000 / p['sample_rate']
        for i, v in enumerate(p['samples']): ppg.append((p['timestamp'] + i * step, v))
ppg.sort()
ecg, _, hr, _ = load(path)
pr = []
for l in open(path):
    r = json.loads(l)
    if r['topic'].endswith('NODE-A/telemetry/pr'):
        p = json.loads(r['payload'])
        if p['validity'] == 'VALID': pr.append((p['timestamp'], p['value']))
def ppg_peaks(a, b):
    seg = [(t, v) for t, v in ppg if a <= t < b]
    if len(seg) < 100: return []
    vals = [v for _, v in seg]
    sm = [vals[i] - statistics.fmean(vals[max(0, i - 25): i + 25]) for i in range(len(vals))]
    thr = statistics.pstdev(sm) * 0.5; peaks, last = [], -1e9
    for i in range(1, len(sm) - 1):
        if sm[i] > thr and sm[i] >= sm[i - 1] and sm[i] > sm[i + 1] and seg[i][0] - last > 400:
            peaks.append(seg[i][0]); last = seg[i][0]
    return peaks
def detector(seg, mult=2.5):
    """B 的峰检（与 replay 相同门限），返回 (峰时刻, 峰值/门限)。"""
    band, in_peak, out = 0.0, False, []
    for t, y in seg:
        band += .004 * (y * y - band); a = abs(y)
        thr = max(30.0, mult * math.sqrt(max(band, 0.0)))
        if not in_peak and a >= thr: in_peak, above, peak, pt, gate = True, t, a, t, thr
        elif in_peak:
            if a > peak: peak, pt = a, t
            if a < gate * .5 or t - above > 200:
                in_peak = False
                if 12 <= t - above <= 160 and peak >= gate * 1.05: out.append((pt, peak / gate))
    return out
y_all = [(int(t), mv * 1000 / UV_PER_Y) for t, mv, _, _ in ecg]
c1 = replay(y_all, 2.5, Periods); c2 = replay(y_all, 2.5, P3)
wins = [((16,41,0),(16,41,40)), ((16,42,0),(16,43,0)), ((16,43,0),(16,44,0)), ((16,44,0),(16,45,0)), ((16,45,0),(16,46,0)), ((16,46,0),(16,47,0)), ((16,47,0),(16,47,51))]
print('window        | PPG HR | n  | QRS p-p uV | band RMS uV | B HR valid | HR-PR med | C1 replay | C2 replay | beats pk/thr med | intervals: ok / ~2x missed / <0.7 extra / RSA>20%')
for a, b in wins:
    A, B = ms(*a), ms(*b)
    seg_uv = [(t, v * UV_PER_Y) for t, v in y_all if A <= t < B]
    rms = math.sqrt(statistics.fmean(v * v for _, v in seg_uv))
    pk = ppg_peaks(A, B); qrs, n, phr = float('nan'), 0, float('nan')
    if len(pk) > 10:
        phr = 60000 / statistics.median([y - x for x, y in zip(pk, pk[1:])])
        ts = [t for t, _ in seg_uv]; vs = [v for _, v in seg_uv]; L = 250; acc = [0.0] * L
        for p in pk:
            i0 = bisect.bisect_left(ts, p - 800)
            if i0 + L >= len(ts) or abs(ts[i0 + L - 1] - (p - 800 + 996)) > 20: continue
            for k in range(L): acc[k] += vs[i0 + k]
            n += 1
        if n: avg = [x / n for x in acc]; qrs = max(avg) - min(avg)
    hb = [x for x in hr if A <= x[0] < B]; hv = [x for x in hb if x[2] == 'VALID']
    diffs = []
    for w in range(A, B, 10000):
        h = [x[1] for x in hv if w <= x[0] < w + 10000]; q = [v for t, v in pr if w <= t < w + 10000]
        if h and q: diffs.append(abs(statistics.median(h) - statistics.median(q)) / statistics.median(q) * 100)
    r1 = [x for x in c1 if A <= x[0] < B]; r2 = [x for x in c2 if A <= x[0] < B]
    det = detector([(t, v) for t, v in y_all if A - 5000 <= t < B]); det = [d for d in det if d[0] >= A]
    ivs = [y[0] - x[0] for x, y in zip(det, det[1:])]
    cls = collections.Counter()
    for i, iv in enumerate(ivs):
        ref = statistics.median(ivs[max(0, i - 4): i + 5])
        r = iv / ref
        cls['missed' if r > 1.6 else 'extra' if r < 0.7 else 'rsa' if abs(r - 1) > 0.2 else 'ok'] += 1
    tot = sum(cls.values()) or 1
    print(f'{hms(A)[:8]}-{hms(B)[3:8]} | {phr:5.1f} | {n:3d} | {qrs:6.0f} | {rms:6.1f} | {len(hv):2d}/{len(hb):2d} | '
          f'{statistics.median(diffs) if diffs else float("nan"):4.1f}% ({len(diffs)}) | {100*sum(x[1] for x in r1)/len(r1):5.1f}% | {100*sum(x[1] for x in r2)/len(r2):5.1f}% | '
          f'{statistics.median(d[1] for d in det):.2f} | ' + ' / '.join(f'{100*cls[k]/tot:.0f}%' for k in ('ok', 'missed', 'extra', 'rsa')))
