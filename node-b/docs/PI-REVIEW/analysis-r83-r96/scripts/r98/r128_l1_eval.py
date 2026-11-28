"""R128：R127 一小时长测判读（MQTT 原件，可选 C 串口原件）。判定口径在采集前写定并提交，采集后只填现场记录 JSON，不改本文件。
用法：python3 -s -E r128_l1_eval.py <现场记录.json>。JSON 字段（北京时间 hh:mm:ss，现场报告值，误差约 ±3 s）：
  capture  MQTT 原件文件名（r83-capture/ 下，须含 NODE-A/B/D/E 全部主题）；day 日；window [开始, 结束]（约 60 min）；
  ecg      [[开始, 结束], ...] 模拟器 ECG 60 bpm 段；resp [{"rate": 次/分, "start": 开始, "end": 结束}, ...] 模拟器 RESP 段（1.0R）；
  power    [["NODE-B", 时刻], ...] 现场人为断电或复位（含换接线断电）；nibp [{"time": 结果出现时刻, "sys": , "dia": }, ...] 屏上读数；
  serial   C 串口原件文件名（可为 null）；serial_index 对应的接收时刻索引（可为 null）。
判据（R127 §4）：
  G1 节点不意外重启：窗口内各节点会话（session_id 的 boot 段）变化，只允许出现在 power 所列时刻 ±60 s 内；
  G2 断链自恢复：任一遥测主题的 MQTT 收包间隔 >5 s 计一次中断；每次都须在 ≤180 s 内自行恢复，合计中断 ≤5% 窗口时长；
  G3 标量覆盖：窗口按 2 s 分格，剔除 G2 中断（前后各 5 s）和本节点 power 时刻 ±60 s，统计含该流帧（telemetry 或 replay）的格数比例：
     SPO2、PR、TEMP ≥99%；B 的 HR、RR ≥90%（R125 两份录制的基线为 93–95%，B 标量存在 2 s 以上空洞，原因未查明，列为已知限制）。
     按 seq 计的完整率只记录（C 先递增 seq 再丢弃未授时帧，seq 缺号不等于传输丢失）；
  G4 模拟器数值：ECG 段 +60 s 起 HR 有效 ≥90% 且全部在 60±2；RESP 段 +45 s 起 RR 有效 ≥80% 且全部在设定值 ±1；
  G5 无错误有效值：ECG 段开始到结束后 10 s 内 RR 有效帧 = 0；全程 HR、RR、SPO2、PR、TEMP 有效帧中值为 0 或空 = 0；
  G6 波形：各模拟器段 +10 s 起，本段信号（ECG 段看 ECG，RESP 段看 RESP）样本 VALID ≥95%；ECG 段与 RESP 段 +45 s 起、剔除 G2 中断（前后各 5 s）后，
     ECG 丢失 ≤7%，缺口 ≥20 个时相邻缺口间隔 2.00±0.05 s 的比例 ≤5%（不足 20 个只记录）；
  G7 NIBP 链路：nibp 所列每次读数在其时刻 ±120 s 内有 MQTT NIBP 有效帧，SYS/DIA 与屏上一致（±1 mmHg）。
只记录：SpO₂/PR/TEMP 有效率与分位数、NIBP 次数、语音下行帧数、各次中断起止、C 串口覆盖范围与中断前后 ±30 s 的日志行。
修订 2（采集前）：通配订阅会收到 voice/broadcast 的 MPB1 二进制帧，解析时跳过并计数；判据不变。"""
import json, sys, numpy as np
from collections import defaultdict
from r122_eval import at, hhmmss
CAP = '../../r83-capture/'
def load(path):
    """(node, stream) -> [(收包 ms, timestamp, seq, session, validity, value, source, samples, sample_rate)]；status 另存。"""
    d = defaultdict(list); load.voice = 0
    for line in open(path, encoding='utf-8'):
        r = json.loads(line); parts = r['topic'].split('/')
        if len(parts) < 5: continue
        if parts[3] == 'voice': load.voice += 1; continue   # MPB1 二进制下行帧（R127 修订 2），只计数
        node, kind = parts[3], parts[4]; stream = parts[5] if len(parts) > 5 else kind
        p = json.loads(r['payload'])
        d[(node, stream if kind in ('telemetry', 'replay') else kind)].append(
            (r['ts_ms'], p['timestamp'], p['seq'], p.get('session_id'), p['validity'], p.get('value'), p.get('source'),
             p.get('samples'), p.get('sample_rate'), kind))
    for v in d.values(): v.sort(key=lambda x: x[1])
    return d
def gaps_of(ts, limit):
    ts = sorted(ts); return [(a, b - a) for a, b in zip(ts, ts[1:]) if b - a > limit]
def wave_points(rows):
    pts = []
    for r in rows:
        if not r[7] or not r[8]: continue
        st = 1000.0 / r[8]; t0 = r[1] - (len(r[7]) - 1) * st
        pts += [(t0 + i * st, r[4] == 'VALID') for i in range(len(r[7]))]
    pts.sort(); return pts
if __name__ == '__main__':
    F = json.load(open(sys.argv[1], encoding='utf-8')); d = F['day']; D = load(CAP + F['capture'])
    A, B = (at(d, x) for x in F['window']); ok = {}
    tele = [r for (n, s), v in D.items() if s not in ('status', 'event') for r in v if r[9] == 'telemetry']
    print(f'=== 窗口 {F["window"][0]}–{F["window"][1]}（{(B - A) / 60000:.1f} min）；主题 {sorted(set(f"{n}/{s}" for n, s in D))}')
    # G2 断链
    rx = [r[0] for r in tele if A <= r[0] <= B]; out = gaps_of([A] + rx + [B], 5000)
    total = sum(g for _, g in out); g2 = all(g <= 180000 for _, g in out) and total <= .05 * (B - A); ok['G2'] = g2
    print(f'G2 断链：{len(out)} 次，' + '，'.join(f'{hhmmss(int(a))} 起 {g / 1000:.1f} s' for a, g in out) + f'；合计 {total / 1000:.1f} s（≤{.05 * (B - A) / 1000:.0f} s）→ {"PASS" if g2 else "FAIL"}')
    outs = [(a - 5000, a + g + 5000) for a, g in out]
    # G1 节点重启
    pw = [(n, at(d, t)) for n, t in F.get('power', [])]; bad = []
    for node in ('NODE-A', 'NODE-B', 'NODE-D', 'NODE-E'):
        rows = sorted((r[0], r[3].rsplit('-', 1)[-1]) for (n, s), v in D.items() if n == node and s != 'status' for r in v if r[9] == 'telemetry' and r[3] and A <= r[0] <= B)
        ch = [t for (t, b0), (_, b1) in zip(rows, rows[1:]) if b0 != b1]
        un = [t for t in ch if not any(n == node and abs(t - p) <= 60000 for n, p in pw)]
        bad += un; print(f'G1 {node}：会话变化 {len(ch)} 次，其中未登记 {len(un)} 次 {[hhmmss(int(t)) for t in un]}')
    ok['G1'] = not bad; print(f'G1 → {"PASS" if ok["G1"] else "FAIL"}')
    # G3 标量覆盖
    g3 = True
    for node, s, need in (('NODE-B', 'hr', .9), ('NODE-B', 'rr', .9), ('NODE-A', 'spo2', .99), ('NODE-A', 'pr', .99), ('NODE-D', 'temp', .99)):
        rows = [r for r in D.get((node, s), []) if A <= r[1] < B]; ts = np.array([r[1] for r in rows])
        excl = outs + [(p - 60000, p + 60000) for n, p in pw if n == node]
        keep = [x for x in range(A, B - 1999, 2000) if not any(o0 <= x < o1 for o0, o1 in excl)]
        hit = sum(bool(((ts >= x) & (ts < x + 2000)).any()) for x in keep) if len(ts) else 0
        c = hit / len(keep) if keep else 0; g3 &= c >= need
        seqs = defaultdict(set)
        for r in rows: seqs[r[3]].add(r[2])
        have = sum(len(x) for x in seqs.values()); want = sum(max(x) - min(x) + 1 for x in seqs.values())
        print(f'G3 {node}/{s}：2 s 格覆盖 {hit}/{len(keep)}（{100 * c:.1f}%，≥{100 * need:.0f}%）；seq 完整 {have}/{want}（只记录）')
    ok['G3'] = g3; print(f'G3 → {"PASS" if g3 else "FAIL"}')
    # G4、G5、G6
    def frames(node, s, a, b): return [r for r in D.get((node, s), []) if a <= r[1] < b]
    g4 = g5 = g6 = True
    for a0, b0 in ([at(d, x), at(d, y)] for x, y in F['ecg']):
        fr = frames('NODE-B', 'hr', a0 + 60000, b0); v = [r[5] for r in fr if r[4] == 'VALID']
        c = bool(fr) and len(v) >= .9 * len(fr) and all(58 <= x <= 62 for x in v); g4 &= c
        print(f'G4 ECG 段 {hhmmss(a0)}–{hhmmss(b0)}：HR 有效 {len(v)}/{len(fr)}，值 {sorted(set(v))} → {"PASS" if c else "FAIL"}')
        rr = [r for r in frames('NODE-B', 'rr', a0, b0 + 10000) if r[4] == 'VALID']; g5 &= not rr
        print(f'G5 ECG 段 RR 有效 {len(rr)} 帧 {sorted(set(r[5] for r in rr))}')
    for L in F['resp']:
        a0, b0 = at(d, L['start']), at(d, L['end']); fr = frames('NODE-B', 'rr', a0 + 45000, b0); v = [r[5] for r in fr if r[4] == 'VALID']
        c = bool(fr) and len(v) >= .8 * len(fr) and all(abs(x - L['rate']) <= 1 for x in v); g4 &= c
        print(f'G4 RESP {L["rate"]} 次/分 {hhmmss(a0)}–{hhmmss(b0)}：RR 有效 {len(v)}/{len(fr)}，值 {sorted(set(v))} → {"PASS" if c else "FAIL"}')
    for node, s in (('NODE-B', 'hr'), ('NODE-B', 'rr'), ('NODE-A', 'spo2'), ('NODE-A', 'pr'), ('NODE-D', 'temp')):
        z = [r for r in D.get((node, s), []) if A <= r[1] <= B and r[4] == 'VALID' and not r[5]]; g5 &= not z
        if z: print(f'G5 {node}/{s} 有效的 0：{len(z)} 帧')
    ok['G4'], ok['G5'] = g4, g5; print(f'G4 → {"PASS" if g4 else "FAIL"}；G5 → {"PASS" if g5 else "FAIL"}')
    segs = [('ecg', at(d, x), at(d, y)) for x, y in F['ecg']] + [('resp', at(d, L['start']), at(d, L['end'])) for L in F['resp']]
    ecg_pts = wave_points(D.get(('NODE-B', 'ecg'), []))
    for k, a0, b0 in segs:
        p = [x for x in wave_points(D.get(('NODE-B', k), [])) if a0 + 10000 <= x[0] < b0]; vf = sum(x[1] for x in p)
        c1 = bool(p) and vf >= .95 * len(p)
        t = np.array([x[0] for x in ecg_pts if a0 + 45000 <= x[0] < b0 and not any(o0 <= x[0] < o1 for o0, o1 in outs)])
        span = (b0 - a0 - 45000) - sum(max(0, min(o1, b0) - max(o0, a0 + 45000)) for o0, o1 in outs)
        gp = [(u, w - u) for u, w in zip(t, t[1:]) if w - u > 6 and not any(o0 <= u < o1 or o0 <= w < o1 or (u < o0 and w > o1) for o0, o1 in outs)]
        loss = sum(g - 4 for _, g in gp) / span if span > 0 else 1.0
        gt = np.array([u for u, _ in gp]); per = float(np.mean(np.abs(np.diff(gt) / 1000 - 2.0) <= .05)) if len(gt) > 1 else 0.0
        c2 = loss <= .07 and (len(gp) < 20 or per <= .05); g6 &= c1 and c2
        print(f'G6 {k.upper()} 段 {hhmmss(a0)}–{hhmmss(b0)}：本段波形 VALID {vf}/{len(p)}（{100 * vf / max(len(p), 1):.1f}%）；ECG 丢失 {100 * loss:.1f}%，缺口 {len(gp)}，'
              f'2 s 周期 {100 * per:.1f}%{"（不足 20 个，只记录）" if len(gp) < 20 else ""} → {"PASS" if c1 and c2 else "FAIL"}')
    ok['G6'] = g6; print(f'G6 → {"PASS" if g6 else "FAIL"}')
    # G7 NIBP
    nb = [r for r in D.get(('NODE-E', 'nibp'), []) if r[4] == 'VALID' and isinstance(r[5], list)]; g7 = True
    for m in F.get('nibp', []):
        t = at(d, m['time']); hit = [r for r in nb if abs(r[1] - t) <= 120000 and abs(r[5][0] - m['sys']) <= 1 and abs(r[5][1] - m['dia']) <= 1]
        g7 &= bool(hit); print(f'G7 NIBP {m["time"]} 屏 {m["sys"]}/{m["dia"]}：MQTT {"一致 " + hhmmss(int(hit[0][1])) if hit else "未找到"}')
    ok['G7'] = g7 and bool(F.get('nibp')); print(f'G7 → {"PASS" if ok["G7"] else ("NOT_RUN" if not F.get("nibp") else "FAIL")}；MQTT NIBP 有效结果共 {len(set((r[1], tuple(r[5])) for r in nb if A <= r[1] <= B))} 次')
    # 只记录
    print('=== 只记录')
    print(f'语音下行 MPB1 帧（voice/broadcast）：{load.voice} 条')
    for node, s in (('NODE-A', 'spo2'), ('NODE-A', 'pr'), ('NODE-D', 'temp')):
        fr = [r for r in D.get((node, s), []) if A <= r[1] <= B and r[9] == 'telemetry']; v = [r[5] for r in fr if r[4] == 'VALID']
        q = np.percentile(v, [5, 50, 95]).round(1).tolist() if v else []
        print(f'{node}/{s}：有效 {len(v)}/{len(fr)}（{100 * len(v) / max(len(fr), 1):.0f}%），5/50/95 分位 {q}')
    if F.get('serial'):
        raw = open(CAP + F['serial'], 'rb').read(); idx = [json.loads(x) for x in open(CAP + F['serial_index'], encoding='utf-8')] if F.get('serial_index') else []
        if idx:
            tt = [x['utc_ms'] for x in idx]; sg = gaps_of(tt, 10000)
            print(f'C 串口：{len(raw)} B，接收 {hhmmss(int(tt[0]))}–{hhmmss(int(tt[-1]))}，>10 s 无数据 {len(sg)} 次；窗口覆盖 {100 * max(0, min(tt[-1], B) - max(tt[0], A)) / (B - A):.0f}%')
            for a, g in out:
                near = [x for x in idx if a - 30000 <= x['utc_ms'] <= a + g + 30000]
                text = b''.join(raw[x['offset']:x['offset'] + x['bytes']] for x in near).decode('utf-8', 'replace').replace('\r', '')
                print(f'  中断 {hhmmss(int(a))} 前后 ±30 s 日志：' + (' | '.join(l for l in text.split('\n') if l)[:1500] or '无'))
        else: print(f'C 串口：{len(raw)} B，无接收时刻索引')
    else: print('C 串口：NOT_RUN')
    gates = ['G1', 'G2', 'G3', 'G4', 'G5', 'G6', 'G7']
    print(f'=== R127 判定 → {"PASS" if all(ok[g] for g in gates) else "FAIL"}（' + '，'.join(f'{g} {"PASS" if ok[g] else "FAIL"}' for g in gates) + '）')
