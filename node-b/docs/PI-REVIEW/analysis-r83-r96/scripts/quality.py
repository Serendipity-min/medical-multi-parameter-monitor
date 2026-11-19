"""比较两轮录制的 ECG 质量：带内 RMS、|y| 包络自相关在心率周期处的峰值、PR 参照。"""
import sys, json, math, statistics, datetime
from load import load, UV_PER_Y, hms
tz = datetime.timezone(datetime.timedelta(hours=8))
def ms(h, m, s): return int(datetime.datetime(2026, 11, 18, h, m, s, tzinfo=tz).timestamp() * 1000)
def pr_series(path):
    out = []
    for l in open(path):
        r = json.loads(l)
        if r['topic'].endswith('NODE-A/telemetry/pr'):
            p = json.loads(r['payload'])
            if p['validity'] == 'VALID': out.append((p['timestamp'], p['value']))
    return out
def env_autocorr(seg, fs=250):
    # |y| 平滑包络，降到 25 Hz，自相关 0.4–1.5 s
    x = [abs(v) for _, v in seg]; e = [sum(x[i:i+10]) / 10 for i in range(0, len(x) - 10, 10)]
    m = statistics.fmean(e); e = [v - m for v in e]; den = sum(v * v for v in e) or 1
    best = (0, 0)
    for lag in range(10, 38):
        c = sum(e[i] * e[i + lag] for i in range(len(e) - lag)) / den
        if c > best[0]: best = (c, lag / 25)
    return best
for path, label, wins in [
    ('../r83-capture/r83-20261118T065234Z-node-b.jsonl', 'R83 ankles', [((15,7,10),(15,8,10)), ((15,8,10),(15,9,10))]),
    ('../r83-capture/r85-20261118T074904Z-node-ab.jsonl', 'R85 P1 wrists', [((15,58,40),(15,59,40)), ((15,59,40),(16,0,40)), ((16,0,40),(16,1,40)), ((16,1,40),(16,2,40)), ((16,2,40),(16,3,40))])]:
    ecg, *_ = load(path); prs = pr_series(path)
    for a, b in wins:
        seg = [(t, mv * 1000) for t, mv, _, _ in ecg if ms(*a) <= t < ms(*b)]  # µV
        if not seg: continue
        vals = [v for _, v in seg]; rms = math.sqrt(statistics.fmean(v * v for v in vals))
        p99 = sorted(abs(v) for v in vals)[int(len(vals) * .99)]
        c, lag = env_autocorr(seg)
        pr = [v for t, v in prs if ms(*a) <= t < ms(*b)]
        print(f'{label:14s} {hms(ms(*a))[:8]} | band RMS {rms:6.1f} uV | |y| p99 {p99:6.0f} uV | p99/RMS {p99/rms:4.1f} | '
              f'envelope autocorr peak {c:.2f} at {lag:.2f} s ({60/lag if lag else 0:.0f}/min) | A PR median {statistics.median(pr) if pr else float("nan"):.0f}')
