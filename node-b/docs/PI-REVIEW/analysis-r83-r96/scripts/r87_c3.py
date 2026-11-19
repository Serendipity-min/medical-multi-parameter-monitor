"""R87 离线：C1 / C2（漏检容忍+±30%）/ C3（C2 + 120 ms 内双相叶合并取大者）重放有效率；模拟器(R83)、导联开路(R83)、白噪声对照。"""
import sys, random, statistics
exec(open('r87_extra.py').read().split("for path, A, B in")[0])
from hr import Periods, UNSTABLE
from variants import P2
class P3(P2):
    def accept(self, at):
        super().accept(at)
        if self.reason == UNSTABLE and self.count >= self.required:
            s = sorted(self.intervals[:self.count]); m = s[self.count // 2]
            if max(abs(x - m) for x in s) <= 0.30 * m:
                self.rate, self.reason = (60000 + m // 2) // m, 0
def run(y, cls, merge):
    det = detector(y)
    if merge:   # 120 ms 内的相邻候选视为同一 QRS 的两叶，只保留幅度大者
        m = []
        for d in det:
            if m and d[0] - m[-1][0] <= 120:
                if d[1] > m[-1][1]: m[-1] = d
            else: m.append(d)
        det = m
    per = cls(273, 2000, 4000, 5); out, i = [], 0
    for t, _ in y:
        while i < len(det) and det[i][0] <= t: per.accept(det[i][0]); i += 1
        per.expire(t)
        out.append((t, per.reason == 0 and per.rate > 0, per.rate))
    return out
def stat(o, a=None, b=None):
    o = [x for x in o if (a is None or a <= x[0] < b)]
    v = [x[2] for x in o if x[1]]
    return f'{100*len(v)/len(o):5.1f}% {statistics.median(v) if v else 0:4.0f}'
e87, *_ = load('../r83-capture/r87-20261118T083445Z-node-ab.jsonl')
e83, *_ = load('../r83-capture/r83-20261118T065234Z-node-b.jsonl')
e85, *_ = load('../r83-capture/r85-20261118T074904Z-node-ab.jsonl')
Y = lambda e, a, b: [(int(t), mv * 1000 / UV_PER_Y) for t, mv, _, _ in e if a <= t < b]
rng = random.Random(7); noise = [(i * 4, rng.gauss(0, 150)) for i in range(250 * 300)]
sets = [('P2 chest 16:42-47:51', Y(e87, ms(16,41,40), ms(16,47,51)), ms(16,42,0), ms(16,47,51)),
        ('ankles R83', Y(e83, ms(15,4,0), ms(15,9,30)), ms(15,4,20), ms(15,9,30)),
        ('wrists R85', Y(e85, ms(15,58,20), ms(16,3,40)), ms(15,58,40), ms(16,3,40)),
        ('simulator R83', Y(e83, 0, ms(15,0,8)), None, None),
        ('leads-off R83', Y(e83, ms(15,0,15), ms(15,4,0)), None, None),
        ('white noise', noise, None, None)]
print(f'{"set":22s} | C1            | C2            | C3 (C2+merge)')
for name, y, a, b in sets:
    print(f'{name:22s} | ' + ' | '.join(stat(run(y, cls, mg), a, b) for cls, mg in [(Periods, False), (P3, False), (P3, True)]))
print('P2 per minute:')
for a in range(42, 48):
    A, B = ms(16, a, 0), min(ms(16, a + 1, 0), ms(16, 47, 51))
    y = sets[0][1]
    print(f'  16:{a}', ' | '.join(stat(run(y, cls, mg), A, B) for cls, mg in [(Periods, False), (P3, False), (P3, True)]))
