"""R98 阶段0：按网关协议恢复时间轴——波形批 timestamp 为批末样本时间：t[i] = ts - (N-1-i)*1000/fs，N 取该批实际样本数。
保留 seq、session_id、validity；按 (流, 会话) 分开，不跨会话拼接。"""
import json
UV_PER_Y = 0.11920928955 * 126877696 / 209715175
def load(path, end_stamp=True):
    w = {'ecg': [], 'resp': [], 'ppg': []}; sc = {'hr': [], 'rr': [], 'pr': [], 'spo2': []}; batches = []
    for line in open(path, encoding='utf-8'):
        r = json.loads(line); p = json.loads(r['payload']); k = r['topic'].rsplit('/', 1)[-1]
        if k in w:
            n = len(p['samples']); st = 1000.0 / p['sample_rate']
            t0 = p['timestamp'] - (n - 1) * st if end_stamp else p['timestamp']
            batches.append((k, p['timestamp'], n, p['seq'], p.get('session_id'), p['validity']))
            for i, v in enumerate(p['samples']):
                w[k].append((t0 + i * st, v, p['validity'] == 'VALID', p['seq'], p.get('session_id')))
        elif k in sc:
            sc[k].append((p['timestamp'], p['value'], p['validity']))
    for s in list(w.values()) + list(sc.values()): s.sort(key=lambda x: x[0])
    return w, sc, batches
def runs(series, step, tol=1.6):
    """连续段：相邻样本间隔 ≤ tol*step 且同会话；重叠（负间隔）也断开。"""
    out, cur = [], []
    for x in series:
        if cur and (x[0] - cur[-1][0] > tol * step or x[0] - cur[-1][0] <= 0 or x[4] != cur[-1][4]):
            out.append(cur); cur = []
        cur.append(x)
    if cur: out.append(cur)
    return out
