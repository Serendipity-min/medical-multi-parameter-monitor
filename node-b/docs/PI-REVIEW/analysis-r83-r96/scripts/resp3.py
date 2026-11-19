import sys, statistics, collections
from load import load, Y_PER_RESP_REL, hms
from variants import ms
from resp import replay_resp
from resp2 import replay_r2, synth, summarize

def smooth(seg, win_s, fs=50):
    n = max(1, int(win_s * fs)); out = []; acc = 0.0; q = collections.deque()
    for t, v in seg:
        q.append(v); acc += v
        if len(q) > n: acc -= q.popleft()
        out.append((t, acc / len(q)))
    return out

_, resp, _, _ = load(sys.argv[1])
segs = {'human 15:04:50-15:07:00': [(int(t), v * Y_PER_RESP_REL) for t, v, _, _ in resp if ms(15,4,50) <= t < ms(15,7,0)],
        'human 15:07:00-15:09:30 (8s?)': [(int(t), v * Y_PER_RESP_REL) for t, v, _, _ in resp if ms(15,7,0) <= t < ms(15,9,30)]}
for p, cv, d in [(5,.05,1.0),(8,.08,1.0),(10,.08,1.0),(3,.15,0.5),(2,.1,0)]:
    segs[f'synth {p}s cv{cv} drift{d}'] = synth(p, cv, drift=d)
print(f'{"case":30s} | current | R2 | R2+MA1.0s | R2+MA1.5s | R2+MA2.0s')
for name, seg in segs.items():
    row = [f'{name:30s}', summarize(replay_resp(seg)[0]), summarize(replay_r2(seg, fc=0.08)[0])]
    for w in (1.0, 1.5, 2.0):
        row.append(summarize(replay_r2(smooth(seg, w), fc=0.08)[0]))
    print(' | '.join(row))
o, cr = replay_r2(smooth(segs['human 15:07:00-15:09:30 (8s?)'], 1.5), fc=0.08)
print('human 15:07-15:09:30 R2+MA1.5 crossing intervals (s):', [round((b - a) / 1000, 1) for a, b in zip(cr, cr[1:])])
