"""呼吸检测原型 R2：一阶高通去漂移（两级）+ 迟滞过零计数；间期 1.5–12 s，±30% 稳定窗，需 3 个间期。"""
import sys, math, statistics, collections, random
from load import load, hms, Y_PER_RESP_REL
from hr import Periods, NO_CYCLES, UNSTABLE
from variants import ms
from resp import replay_resp

class Tol(Periods):
    tol = 0.30
    def accept(self, at):
        super().accept(at)
        if self.reason == UNSTABLE and self.count >= self.required:
            s = sorted(self.intervals[:self.count]); m = s[self.count // 2]
            if max(abs(x - m) for x in s) <= self.tol * m:
                self.rate, self.reason = (60000 + m // 2) // m, 0

def replay_r2(samples, fs=50, fc=0.05, hyst=0.3, maximum=12000, timeout=15000, cls=Tol):
    a = 2 * math.pi * fc / fs
    per = cls(1500, maximum, timeout, 3)
    d1 = d2 = None; p = 0.0; state = 0; out = []; crossings = []
    for t, r in samples:
        d1 = r if d1 is None else d1 + a * (r - d1); x1 = r - d1
        d2 = x1 if d2 is None else d2 + a * (x1 - d2); x = x1 - d2
        p += (0.4 / fs) * (x * x - p)               # 约 2.5 s 平滑功率
        h = max(20.0, hyst * math.sqrt(max(p, 0.0)))
        if state <= 0 and x > h:
            if state < 0: per.accept(t); crossings.append(t)
            state = 1
        elif state >= 0 and x < -h:
            state = -1
        per.expire(t)
        reason = per.reason | (NO_CYCLES if not per.rate else 0)
        out.append((t, reason == 0, per.rate if reason == 0 else 0, reason))
    return out, crossings

def synth(period_s, cv, seconds=240, amp=1500, drift=1.0, seed=1, fs=50):
    rng = random.Random(seed); ph = 0.0; per = period_s; s = []
    for i in range(seconds * fs):
        t = i / fs; ph += 1 / fs / per
        if ph >= 1: ph -= 1; per = max(1.6, period_s * (1 + rng.gauss(0, cv)))
        v = amp * math.sin(2 * math.pi * ph) + drift * amp * (math.sin(2*math.pi*0.03*t) + 0.7*math.sin(2*math.pi*0.047*t+2))
        v += 0.25 * amp * math.sin(2 * math.pi * 0.35 * t + rng.random())   # 0.2–0.6 Hz 小波动
        s.append((int(t * 1000), v))
    return s

def summarize(out, start_ms=20000):
    o = [x for x in out if x[0] >= out[0][0] + start_ms]
    v = [x[2] for x in o if x[1]]
    return f'{100*len(v)/len(o):5.1f}% {statistics.median(v) if v else 0:4.0f}'

if __name__ == '__main__':
    _, resp, _, _ = load(sys.argv[1])
    s = [(int(t), v * Y_PER_RESP_REL) for t, v, _, _ in resp if ms(15, 4, 50) <= t < ms(15, 9, 30)]
    cases = [('human 15:04:50-15:09:30', s)] + [(f'synth {p}s cv{cv} drift{d}', synth(p, cv, drift=d)) for p, cv, d in
             [(5, .05, 0), (5, .05, 1.5), (8, .08, 1.0), (10, .08, 1.0), (3, .15, 0.5), (2, .1, 0)]]
    print(f'{"case":28s} | current algo | R2 fc0.05 h0.3 | R2 fc0.08 h0.3 | R2 fc0.05 h0.5')
    for name, seg in cases:
        cur, _ = replay_resp(seg)
        row = [f'{name:28s}', summarize(cur)]
        for fc, h in [(0.05, 0.3), (0.08, 0.3), (0.05, 0.5)]:
            o, cr = replay_r2(seg, fc=fc, hyst=h); row.append(summarize(o))
        print(' | '.join(row))
    o, cr = replay_r2(s)
    print('human R2 crossing intervals (s):', [round((b - a) / 1000, 1) for a, b in zip(cr, cr[1:])])
