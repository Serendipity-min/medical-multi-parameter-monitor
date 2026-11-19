import sys, math, cmath
from load import load, hms, Y_PER_RESP_REL
from variants import ms
_, resp, _, _ = load(sys.argv[1])
s = [(int(t), v * Y_PER_RESP_REL) for t, v, _, _ in resp]
def band_power(x, fs, f1, f2):
    n = len(x); m = sum(x) / n; x = [v - m for v in x]
    p = 0.0; k1, k2 = int(f1 * n / fs), int(f2 * n / fs) + 1
    for k in range(max(1, k1), k2):
        z = sum(x[i] * cmath.exp(-2j * math.pi * k * i / n) for i in range(0, n, 1))
        p += abs(z) ** 2
    return p
for a, b in [((15,5,0),(15,6,0)), ((15,6,0),(15,7,0)), ((15,7,0),(15,8,0)), ((15,8,0),(15,9,0))]:
    x = [v for t, v in s if ms(*a) <= t < ms(*b)][::5]      # 降到 10 Hz，足够看 0–5 Hz
    fs = 10
    br = band_power(x, fs, 0.07, 0.2); lo = band_power(x, fs, 0.2, 0.6); ca = band_power(x, fs, 1.2, 2.2); vl = band_power(x, fs, 0.01, 0.07)
    tot = br + lo + ca + vl
    print(f'{hms(ms(*a))[:5]} breathing 0.07–0.2Hz {100*br/tot:4.1f}% | 0.2–0.6Hz {100*lo/tot:4.1f}% | cardiac 1.2–2.2Hz {100*ca/tot:4.1f}% | drift 0.01–0.07Hz {100*vl/tot:4.1f}%')
