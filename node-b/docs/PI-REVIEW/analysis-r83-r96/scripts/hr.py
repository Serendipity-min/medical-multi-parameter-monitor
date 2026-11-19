"""R83 HR 离线复盘：
1) 把 bio_v2.c 的 heartbeat()/accept_cycle()/expire() 逐行移植，在录到的滤波 ECG 上重放，重建每秒 H 原因码；
2) 用与 B 无关的简单 R 峰检测作独立参照，判断 B 的 HR 是否倍频/漏检。
预热、工频、削顶三类原因依赖原始码，无法从滤波波形重建，结果中不含 1/32/64 位。"""
import sys, math, collections, statistics
from load import load, hms, UV_PER_Y

NO_CYCLES, UNSTABLE, EXPIRED = 2, 4, 8


class Periods:
    def __init__(self, minimum, maximum, timeout, required):
        self.minimum, self.maximum, self.timeout, self.required = minimum, maximum, timeout, required
        self.forget(1)

    def forget(self, reason):
        self.count = self.index = self.rate = 0
        self.anchored = False
        self.last_good = 0
        self.intervals = [0] * 5
        self.reason = reason

    def expire(self, now):
        if (self.count and now - self.last_good > self.timeout) or (self.anchored and now - self.anchor > self.maximum):
            self.forget(EXPIRED)

    def accept(self, at):
        self.expire(at)
        if not self.anchored:
            self.anchor, self.anchored, self.reason = at, True, NO_CYCLES
            return
        elapsed = at - self.anchor
        if elapsed < self.minimum:
            return
        if elapsed > self.maximum:
            self.forget(EXPIRED); self.anchor, self.anchored = at, True
            return
        self.anchor = self.last_good = at
        self.intervals[self.index] = elapsed; self.index = (self.index + 1) % 5
        self.count = min(self.count + 1, 5)
        self.rate, self.reason = 0, NO_CYCLES
        if self.count < self.required:
            return
        s = sorted(self.intervals[:self.count]) if self.count < 5 else sorted(self.intervals)
        median = s[self.count // 2]
        largest = max(abs(x - median) for x in s)
        if largest * 100 > median * 20:
            self.reason = UNSTABLE
            return
        self.rate, self.reason = (60000 + median // 2) // median, 0


def replay_heart(ecg, required):
    per = Periods(273, 2000, 4000, required)
    band, in_peak, peak, gate, above, peak_t = 0.0, False, 0.0, 0.0, 0, 0
    out = []                    # (t, valid, rate, reason)
    for t, mv, _, _ in ecg:
        t = int(t)
        y = mv * 1000.0 / UV_PER_Y
        band += .004 * (y * y - band)
        a = abs(y)
        thr = max(30.0, 2.5 * math.sqrt(max(band, 0.0)))
        if not in_peak and a >= thr:
            in_peak, above, peak, peak_t, gate = True, t, a, t, thr
        elif in_peak:
            if a > peak:
                peak, peak_t = a, t
            if a < gate * .5 or t - above > 200:
                width = t - above
                in_peak = False
                if 12 <= width <= 160 and peak >= gate * 1.05:
                    per.accept(peak_t)
        per.expire(t)
        reason = per.reason | (NO_CYCLES if not per.rate else 0)
        out.append((t, reason == 0, per.rate if reason == 0 else 0, reason))
    return out


def reference_beats(ecg):
    """独立参照：|y| 超过前 3 s 滑动最大值的 45%，不应期 300 ms，取局部峰。"""
    beats, window, last = [], collections.deque(), -10_000
    for t, mv, _, _ in ecg:
        a = abs(mv)
        window.append((t, a))
        while window[0][0] < t - 3000:
            window.popleft()
        if len(window) < 250:
            continue
        top = max(v for _, v in window)
        if a >= 0.45 * top and t - last > 300:
            beats.append(t); last = t
    return beats


def per_window(series, start, end, step=10000):
    t = start
    while t < end:
        yield t, [x for x in series if t <= x[0] < t + step]
        t += step


if __name__ == '__main__':
    ecg, resp, hr, rr = load(sys.argv[1])
    t0 = int(sys.argv[2]) if len(sys.argv) > 2 else int(ecg[0][0])
    c1 = replay_heart(ecg, 5)
    ref = reference_beats(ecg)
    hr_by_sec = {int(t // 1000): (v, s) for t, v, s in hr}
    # 每 10 s 汇总：B 实际 HR、重放 HR、重建 H 分布、独立参照心率
    print('window     | B HR valid/median        | replay valid/median | replay H codes             | ref HR (median RR)')
    for w, rows in per_window(c1, t0, int(ecg[-1][0])):
        if not rows:
            continue
        secs = range(w // 1000, (w + 10000) // 1000)
        b = [hr_by_sec[s] for s in secs if s in hr_by_sec]
        bv = [v for v, s in b if s == 'VALID']
        rv = [r[2] for r in rows if r[1]]
        codes = collections.Counter(r[3] for r in rows)
        rb = [x for x in ref if w <= x < w + 10000]
        rr_ms = [b2 - b1 for b1, b2 in zip(rb, rb[1:]) if 300 < b2 - b1 < 2000]
        refhr = 60000 / statistics.median(rr_ms) if rr_ms else float('nan')
        print(f'{hms(w)} | {len(bv):2d}/{len(b):2d} {statistics.median(bv) if bv else 0:6.1f}            '
              f'| {100*sum(r[1] for r in rows)/len(rows):5.1f}% {statistics.median(rv) if rv else 0:5.1f}   '
              f'| {" ".join(f"{k}:{100*v/len(rows):.0f}%" for k, v in codes.most_common(3)):26s} '
              f'| {refhr:6.1f} ({len(rb)} beats)')
