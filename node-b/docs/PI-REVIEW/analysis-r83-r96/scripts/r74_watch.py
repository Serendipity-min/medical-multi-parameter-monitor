"""R74 真人采集监视：状态变化、录制断线/停写、NIBP 新值即时输出；每 30 s 输出一行标量摘要。只读。"""
import datetime, json, os, statistics, sys, time

path = sys.argv[1]
tz = datetime.timezone(datetime.timedelta(hours=8))
fmt = lambda t: datetime.datetime.fromtimestamp(t, tz).strftime('%H:%M:%S.%f')[:-5]
prev, last_row, stalled, nibp, bucket, bucket_start = None, time.time(), False, None, [], time.time()


def summary(rows):
    out = []
    for k in ('HR', 'RR', 'SPO2', 'PR', 'TEMP'):
        vals = [r['scalars'][k] for r in rows if k in r['scalars']]
        ok = [v[0] for v in vals if v[1] == 'VALID' and isinstance(v[0], (int, float))]
        if not vals:
            out.append(f'{k}=-'); continue
        if ok:
            out.append(f'{k}={statistics.median(ok):g}[{min(ok):g}-{max(ok):g}] v{len(ok)}/{len(vals)}')
        else:
            out.append(f'{k}=none v0/{len(vals)}')
    return ' '.join(out)


with open(path, encoding='utf-8') as f:
    f.seek(0, os.SEEK_END)
    while True:
        line = f.readline()
        if not line:
            if not stalled and time.time() - last_row > 10:
                print(f'{fmt(time.time())} RECORDER_STALL no rows for >10 s', flush=True); stalled = True
            time.sleep(0.5); continue
        last_row, stalled = time.time(), False
        r = json.loads(line)
        if 'error' in r:
            print(f"{fmt(r['t'])} RECORDER_ERROR {r['error'][:120]}", flush=True); continue
        state = (r.get('gw'), r.get('broker'), tuple(sorted((r.get('nodes') or {}).items())))
        if state != prev:
            print(f"{fmt(r['t'])} STATE gw={state[0]} broker={state[1]} " + ' '.join(f'{k[-1]}={v}' for k, v in state[2]), flush=True)
            prev = state
        cur = r['scalars'].get('NIBP')
        if cur and cur != nibp:
            print(f"{fmt(r['t'])} NIBP {cur}", flush=True)
            nibp = cur
        bucket.append(r)
        if r['t'] - bucket_start >= 30:
            if state[0] == 'ONLINE':
                print(f"{fmt(r['t'])} SUM30 {summary(bucket)}", flush=True)
            bucket, bucket_start = [], r['t']
