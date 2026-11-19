"""在真人录制上重放 HR 判据的若干改动，比较有效占比与数值。"""
import sys, math, statistics, random, datetime
from load import load, UV_PER_Y
from hr import Periods, NO_CYCLES, UNSTABLE, EXPIRED

class P2(Periods):
    """漏检容忍：间期约为当前中位数 2 倍（1.75–2.25）时视为漏检一拍，只移动锚点、不入窗、不破坏稳定。"""
    def accept(self, at):
        if self.anchored and self.count >= 3:
            e = at - self.anchor
            med = sorted(self.intervals[:self.count])[self.count // 2]
            if 1.75 * med <= e <= 2.25 * med and e <= self.maximum * 2:
                self.anchor = at; self.last_good = at; return
        if self.anchored and at - self.anchor > self.maximum and self.count >= 3:
            e = at - self.anchor
            med = sorted(self.intervals[:self.count])[self.count // 2]
            if 1.75 * med <= e <= 2.25 * med:
                self.anchor = at; self.last_good = at; return
        super().accept(at)

def replay(samples, mult=2.5, cls=Periods, required=5):
    per = cls(273, 2000, 4000, required)
    band, in_peak, peak, gate, above, peak_t = 0.0, False, 0.0, 0.0, 0, 0
    out = []
    for t, y in samples:
        band += .004 * (y * y - band); a = abs(y)
        thr = max(30.0, mult * math.sqrt(max(band, 0.0)))
        if not in_peak and a >= thr:
            in_peak, above, peak, peak_t, gate = True, t, a, t, thr
        elif in_peak:
            if a > peak: peak, peak_t = a, t
            if a < gate * .5 or t - above > 200:
                width = t - above; in_peak = False
                if 12 <= width <= 160 and peak >= gate * 1.05: per.accept(peak_t)
        per.expire(t)
        reason = per.reason | (NO_CYCLES if not per.rate else 0)
        out.append((t, reason == 0, per.rate if reason == 0 else 0))
    return out

def ms(h, m, s):
    tz = datetime.timezone(datetime.timedelta(hours=8))
    return int(datetime.datetime(2026, 11, 18, h, m, s, tzinfo=tz).timestamp() * 1000)

def main():
    ecg, *_ = load(sys.argv[1])
    human = [(int(t), mv * 1000 / UV_PER_Y) for t, mv, _, _ in ecg if ms(15, 4, 20) <= t < ms(15, 9, 30)]
    sim = [(int(t), mv * 1000 / UV_PER_Y) for t, mv, _, _ in ecg if t < ms(15, 0, 8)]
    off = [(int(t), mv * 1000 / UV_PER_Y) for t, mv, _, _ in ecg if ms(15, 0, 15) <= t < ms(15, 4, 0)]  # 导联断开/佩戴前
    rng = random.Random(7); noise = [(i * 4, rng.gauss(0, 150)) for i in range(250 * 300)]
    for name, mult, cls in [('C1 (2.5x, strict)', 2.5, Periods), ('gate 2.0x', 2.0, Periods), ('gate 1.8x', 1.8, Periods),
                            ('C1 + missed-beat tol', 2.5, P2), ('2.0x + missed-beat tol', 2.0, P2)]:
        row = [name]
        for seg in (human, sim, off, noise):
            r = replay(seg, mult, cls)
            v = [x[2] for x in r if x[1]]
            row.append(f'{100*len(v)/len(r):5.1f}% {statistics.median(v) if v else 0:5.0f}')
        print(' | '.join(row))
    print('columns: human 15:04:20-15:09:30 | simulator 60 | leads-off/attaching 15:00:15-15:04 | synthetic white noise')

if __name__ == "__main__":
    main()
