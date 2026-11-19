"""干净段正弦拟合：只用目视无瞬变的连续区段。"""
import sys, numpy as np
sys.path.insert(0, '..')
from load import load, Y_PER_RESP_REL
from variants import ms
exec(open('cal.py').read().split('t, v, rr = series')[0].split('def band_rms')[0])
t, v, rr = series('r89cal-20261118T100701Z-node-ab.jsonl')
segs = [('20/min 1.5R', 1.5, 20, (18,11,30), (18,12,30)), ('20/min 1.0R', 1.0, 20, (18,13,14), (18,13,44)),
        ('20/min 0.5R', 0.5, 20, (18,15,40), (18,16,16)), ('12/min 1.0R', 1.0, 12, (18,17,18), (18,18,18))]
k = []
for name, dr, rpm, a, b in segs:
    m = (t >= ms(*a)) & (t < ms(*b)); amp, res = fit(t[m], v[m], rpm / 60)
    vv = [x for x in rr if ms(*a) <= x[0] < ms(*b)]
    print(f'{name}: {b[1]*60+b[2]-a[1]*60-a[2]} s, n {m.sum()}, amp {amp:.0f} r, p-p {2*amp:.0f}, residual SD {res:.0f}, SNR(amp/res) {amp/res:.1f}, amp/ΔR {amp/dr:.0f} r/Ω, RR valid {sum(x[2]=="VALID" for x in vv)}/{len(vv)}')
    if rpm == 20: k.append((dr, amp))
d = np.array([x[0] for x in k]); A = np.array([x[1] for x in k])
print('through-origin slope', round(float(d @ A / (d @ d))), 'r/Ω; free', np.round(np.polyfit(d, A, 1), 1))
