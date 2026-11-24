"""R122：R121（志愿者甲短流程）评估。判定逻辑按 R121 §5 在采集前写定并提交，采集后只填现场记录 JSON，不改本文件。
用法：python3 -s -E r122_eval.py <现场记录.json>。JSON 字段（时刻为北京时间 hh:mm:ss，现场报告值，误差约 ±3 s）：
  capture  MQTT 原件文件名（放在 r83-capture/）；day  11 月的日期；
  sim      模拟器核对窗 [起, 止]；t0  两臂放好的时刻；
  paced    {"12"|"15"|"20": {"start": 节拍器开始时刻, "counts30": 30/60/90/120 s 累计数，缺失写 null}}；
  offcard  卡外动作时刻列表（站起、换姿势、碰电极或导联线），没有写 []。
复用 r109_eval、r111_eval 的函数；R1 判定与 R117 相同（R121 §5.2 不改）。"""
import json, sys, numpy as np
from r109_eval import get, ms, K, frames, ecg_arrays, human_row, bands, hr_metrics
from r111_eval import resp_peak
from qrs_polarity import polarity
import resp_r1
def at(day, s): h, m, x = map(int, s.split(':')); return ms(day, h, m, x)
def hhmmss(t): s = (t // 1000 + 8 * 3600) % 86400; return f'{s // 3600:02d}:{s // 60 % 60:02d}:{s % 60:02d}'
if __name__ == '__main__':
    F = json.load(open(sys.argv[1], encoding='utf-8')); f = F['capture']; d = F['day']
    w, sc, _ = get(f)
    print('=== 模拟器心电核对（绿→RA、黄→LA、红→RL）')
    a, b = (at(d, x) for x in F['sim']); t, v = ecg_arrays(f, a, b); n, p, mp, mn = polarity(list(zip(t, v / 1000)))
    print(f'{F["sim"][0]}–{F["sim"][1]} 峰 {n}，主峰正向 {p:.1f}%，正峰中位 {mp:.0f} µV')
    T0 = at(d, F['t0']); A, B = T0 + 10000, T0 + 180000
    print(f'=== §5.1 HR 判定窗 T0+10 s–T0+3:00（T0 = {F["t0"]}）逐 30 s（首段从 T0+10 s 起）')
    for s in range(T0, B, 30000):
        s0 = max(s, A); nv, nh, ok, n, med = hr_metrics(f, s0, s + 30000); t, v = ecg_arrays(f, s0, s + 30000)
        pn, pp, mp, mn = polarity(list(zip(t, v / 1000))) if len(t) > 3000 else (0, float('nan'), 0, 0)
        print(f'{hhmmss(s0)} HR {nv:2d}/{nh:2d} 中位 {med:5.1f} PR±10% {ok}/{n} | 正峰 {mp:4.0f} 负峰 {mn:4.0f} µV 正向 {pp:5.1f}%'
              f' | 5–25 Hz {bands(f, s0, s + 30000)[1]:4.0f} µV')
    human_row('S5 判定窗', f, A, B)
    nv, nh, ok, n, _ = hr_metrics(f, A, B); eff, agr = nv / max(nh, 1), ok / max(n, 1)
    hit = [x for x in F['offcard'] if T0 <= at(d, x) <= B]
    verdict = 'NOT_EVALUABLE' if hit else ('PASS' if eff >= .8 and n and agr >= .8 else 'FAIL')
    print(f'HR 有效率 {nv}/{nh}（{100 * eff:.0f}%，门槛 80%）；与 PR ±10% {ok}/{n}（{100 * agr:.0f}%，门槛 80%，无配对帧不满足）'
          f'{"；窗内卡外动作 " + "、".join(hit) if hit else ""} → {verdict}')
    print('=== S6 各段 HR（只记录，每段开头 10 s 不计）')
    P = sorted(F['paced'].items(), key=lambda kv: int(kv[0]))
    for k, c in P: a = at(d, c['start']); human_row(f'节拍{k}', f, a + 10000, a + 120000)
    print('=== §5.2 R1 判定（覆盖率 ≥40%；有输出窗 ≥90% 在真值 ±2/min 内；三段各自满足为 PASS）')
    rt = np.array([x[0] for x in w['resp']]); rv = np.array([x[1] * K for x in w['resp']]); res = []
    for k, c in P:
        a = at(d, c['start']); b = a + 120000; cnt = c['counts30']
        truth = cnt[3] / 2 if len(cnt) == 4 and cnt[3] is not None else None
        m = (rt >= a - 40000) & (rt < b)
        o = [x for x in resp_r1.run(rt[m] / 1000, rv[m], (a - 36000) / 1000, b / 1000) if x[0] * 1000 - resp_r1.W * 1000 >= a - 1]
        vals = [round(x[1], 1) for x in o if x[1] is not None]; cov = len(vals) / max(len(o), 1)
        rr = frames(sc['rr'], a + 10000, b); bv = [x[1] for x in rr if x[2] == 'VALID']
        r, q, pp = resp_peak(rt, rv, a + 10000, b)
        print(f'节拍{k} 计数 {cnt}；频谱主峰 {r:.1f}/min 集中度 {q:.2f}')
        if truth is None:
            res.append('NOT_EVALUATED')
            print(f'R1 节拍{k}（人工计数缺 → NOT_EVALUATED）：窗 {len(o)}，有输出 {len(vals)}（{100 * cov:.0f}%）；值 {vals}')
        else:
            ok = sum(abs(x - truth) <= 2 for x in vals); acc = ok / max(len(vals), 1); res.append('PASS' if cov >= .4 and acc >= .9 else 'FAIL')
            print(f'R1 节拍{k}（真值 {truth:.1f}）：窗 {len(o)}，有输出 {len(vals)}（{100 * cov:.0f}%），±2 内 {ok}/{len(vals)}（{100 * acc:.0f}%）'
                  f' → {res[-1]}；值 {vals}')
            if k == '20': print(f'   §5.3 计数核对（只记录）：计数 {truth:.1f} − 主峰 {r:.1f} = {truth - r:+.1f}/min{"，超过 3，需分析" if abs(truth - r) > 3 else ""}')
        bok = sum(abs(x - truth) <= 2 for x in bv) if truth is not None else '—'
        print(f'   板上 RR：有效 {len(bv)}/{len(rr)}（{100 * len(bv) / max(len(rr), 1):.0f}%），±2 内 {bok}/{len(bv)}，值 {sorted(set(bv))}')
    allr = 'PASS' if res == ['PASS'] * 3 else ('NOT_EVALUATED' if 'NOT_EVALUATED' in res and 'FAIL' not in res else 'FAIL')
    print(f'R1 三段 {dict(zip([k for k, _ in P], res))} → {allr}')
