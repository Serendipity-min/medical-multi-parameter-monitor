"""R100 采集前的合成对照（冻结版 PPG-RR，见 rr_frozen.py）：
阴性：无呼吸调制的脉搏（HR 70，逐拍随机抖动 3%，幅度随机 5%，慢基线随机游走），20 个种子，各 300 s；
阳性：呼吸调制 6/10/15/20 次/分（幅度 ±10%、间期 ±5%、基线 ±5%），各 5 个种子。"""
import math, random, numpy as np
import rr_frozen
def synth(seed, rpm=None, seconds=300, fs=50):
    rng = random.Random(seed); t = 0.0; beats = []
    while t < seconds:
        rr = 60 / 70 * (1 + rng.gauss(0, .03))
        if rpm: rr *= 1 + .05 * math.sin(2 * math.pi * rpm / 60 * t)
        beats.append((t, 1 + rng.gauss(0, .05) + (.1 * math.sin(2 * math.pi * rpm / 60 * t) if rpm else 0))); t += rr
    out, drift, j = [], 0.0, 0
    for n in range(int(seconds * fs)):
        tt = n / fs; drift += rng.gauss(0, .002)
        while j + 1 < len(beats) and beats[j + 1][0] <= tt: j += 1
        ph = (tt - beats[j][0]) / (60 / 70); amp = beats[j][1]
        base = .05 * math.sin(2 * math.pi * rpm / 60 * tt) if rpm else 0
        v = amp * math.exp(-((ph - .2) / .08) ** 2) + .3 * amp * math.exp(-((ph - .45) / .1) ** 2) + drift + base + rng.gauss(0, .01)
        out.append((1000 * tt + 1e12, v, True, n // 50, 's'))
    return out
if __name__ == '__main__':
    A, B = 1e12, 1e12 + 300000
    neg = []
    for s in range(20):
        o = rr_frozen.rr(synth(s), A, B); neg.append(sum(1 for x in o if x[1]) / len(o))
    print(f'negative (no resp modulation) 20 seeds: windows with output mean {100*np.mean(neg):.2f}% max {100*max(neg):.2f}%')
    for rpm in (8, 10, 12, 15, 16, 20):
        cov, err = [], []
        for s in range(5):
            o = rr_frozen.rr(synth(100 + s, rpm), A, B); v = [x[1] for x in o if x[1]]
            cov.append(len(v) / len(o)); err += [abs(x - rpm) for x in v]
        print(f'positive {rpm:2d}/min: coverage {100*np.mean(cov):.0f}%, |err|<=2 {100*np.mean([e<=2 for e in err]) if err else 0:.0f}%, median err {np.median(err) if err else float("nan"):.2f}')
