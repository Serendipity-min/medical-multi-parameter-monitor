import sys, random, statistics
from load import load, UV_PER_Y
from hr import Periods, NO_CYCLES, UNSTABLE, EXPIRED
from variants import P2, replay, ms

class P3(P2):
    """漏检容忍 + 窗口容差放宽到 ±tol。"""
    tol = 0.30
    def accept(self, at):
        before = self.count
        super().accept(at)
        if self.reason == UNSTABLE and self.count >= self.required:
            s = sorted(self.intervals[:self.count]); m = s[self.count // 2]
            if max(abs(x - m) for x in s) <= self.tol * m:
                self.rate, self.reason = (60000 + m // 2) // m, 0

class P4(P2):
    """漏检容忍 + 相邻间期变化 ≤25%（取代“全部在中位数±20%”），速率取 5 拍中位数。"""
    def accept(self, at):
        super().accept(at)
        if self.reason == UNSTABLE and self.count >= self.required:
            seq = [self.intervals[(self.index - self.count + k) % 5] for k in range(self.count)]
            if all(abs(b - a) <= 0.25 * a for a, b in zip(seq, seq[1:])):
                m = sorted(seq)[len(seq) // 2]
                self.rate, self.reason = (60000 + m // 2) // m, 0

ecg, *_ = load(sys.argv[1])
seg = lambda a, b: [(int(t), mv * 1000 / UV_PER_Y) for t, mv, _, _ in ecg if a <= t < b]
human, sim, off = seg(ms(15,4,20), ms(15,9,30)), seg(0, ms(15,0,8)), seg(ms(15,0,15), ms(15,4,0))
rng = random.Random(7); noise = [(i * 4, rng.gauss(0, 150)) for i in range(250 * 300)]
for name, mult, cls in [('C1', 2.5, Periods), ('C1+tol', 2.5, P2), ('C1+tol+±30%', 2.5, P3), ('C1+tol+succ25%', 2.5, P4), ('2.0x+tol+±30%', 2.0, P3)]:
    row = [f'{name:16s}']
    for s in (human, sim, off, noise):
        r = replay(s, mult, cls); v = [x[2] for x in r if x[1]]
        row.append(f'{100*len(v)/len(r):5.1f}% {statistics.median(v) if v else 0:4.0f} [{min(v) if v else 0}-{max(v) if v else 0}]')
    print(' | '.join(row))
print('cols: human | simulator60 | leads-off/attaching | white noise')
