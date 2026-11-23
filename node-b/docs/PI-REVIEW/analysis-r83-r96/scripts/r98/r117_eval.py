"""R117：R116（志愿者甲，正确色标胸前，坐姿完整流程 + 坐—躺—坐）评估，复用 r109_eval、r111_eval 的函数；MQTT 原件含无效批波形。
时刻为现场报告值（误差约 ±3 s），每段开头 10 s 不计。R87（甲，旧色标）用同一函数对照。
RR 真值为人工计数 ÷ 段长（12 段 24、15 段 30、20 段约 42——11-23 负责人补报，为约数）；S7 三段各 60 s 计数只记录。"""
import numpy as np
from r109_eval import get, ms, K, frames, ecg_arrays, human_row, bands
from r111_eval import resp_peak
from qrs_polarity import polarity
import resp_r1
R116 = 'r116human-20261123T085733Z-node-ab.jsonl'
R87 = 'r87-20261118T083445Z-node-ab.jsonl'
SEG = [('甲 贴片后未戴指夹', ms(23,17,5,40), ms(23,17,12,10)), ('甲 静坐（S6.1）', ms(23,17,12,25), ms(23,17,14,15)),
       ('甲 正常呼吸', ms(23,17,14,35), ms(23,17,16,25)), ('甲 节拍12', ms(23,17,17,10), ms(23,17,19,0)),
       ('甲 节拍15', ms(23,17,19,40), ms(23,17,21,30)), ('甲 节拍20', ms(23,17,22,10), ms(23,17,24,0)),
       ('甲 S6 合计', ms(23,17,12,25), ms(23,17,24,15))]
S7 = [('甲 坐姿A', ms(23,17,24,40), ms(23,17,26,30)), ('甲 平躺静息', ms(23,17,28,40), ms(23,17,30,30)),
      ('甲 平躺延长', ms(23,17,30,40), ms(23,17,32,30)), ('甲 坐姿B', ms(23,17,33,40), ms(23,17,35,30))]
PACED = [('节拍12', ms(23,17,17,0), ms(23,17,19,0), 24 / 2), ('节拍15', ms(23,17,19,30), ms(23,17,21,30), 30 / 2),
         ('节拍20', ms(23,17,22,0), ms(23,17,24,0), 42 / 2)]
if __name__ == '__main__':
    w, sc, _ = get(R116)
    print('=== 模拟器心电核对（绿→RA、黄→LA、红→RL）')
    t, v = ecg_arrays(R116, ms(23,17,0,40), ms(23,17,1,30)); n, p, mp, mn = polarity(list(zip(t, v / 1000)))
    print(f'17:00:40–17:01:30 峰 {n}，主峰正向 {p:.1f}%，正峰中位 {mp:.0f} µV')
    print('=== 志愿者甲 胸前（MQTT 全部批，含无效批）')
    for name, a, b in SEG + S7: human_row(name, R116, a, b)
    human_row('R87 P2（甲，旧色标）', R87, ms(18,16,42), ms(18,16,47,51))
    print('=== 坐—躺—坐 5–25 Hz 噪声比（R116 §5.4）')
    nb = {name: bands(R116, a, b)[1] for name, a, b in S7}
    sa = nb['甲 坐姿A']
    print(f'平躺 ÷ 坐姿A {nb["甲 平躺静息"] / sa:.2f}；平躺延长 ÷ 坐姿A {nb["甲 平躺延长"] / sa:.2f}；坐姿B ÷ 坐姿A {nb["甲 坐姿B"] / sa:.2f}')
    print('=== RESP（r 单位；R109 定标约 310 r/R）与板上 RR')
    rt = np.array([x[0] for x in w['resp']]); rv = np.array([x[1] * K for x in w['resp']])
    for name, a, b in SEG[1:6] + S7:
        r, q, pp = resp_peak(rt, rv, a, b); rr = frames(sc['rr'], a, b); val = [x[1] for x in rr if x[2] == 'VALID']
        print(f'{name:10s} 主峰 {r:4.1f}/min 集中度 {q:.2f} | p95−p5 {pp:6.0f} r ≈ {pp / 2 / 310:.1f} R'
              f' | 板上 RR 有效 {len(val)}/{len(rr)} 值 {sorted(set(val))}')
    print('=== R1 判定（覆盖率 ≥40%；有输出窗 ≥90% 在真值 ±2/min 内）')
    for name, a, b, truth in PACED:
        m = (rt >= a - 40000) & (rt < b)
        o = [x for x in resp_r1.run(rt[m] / 1000, rv[m], (a - 36000) / 1000, b / 1000) if x[0] * 1000 - resp_r1.W * 1000 >= a - 1]
        vals = [round(x[1], 1) for x in o if x[1] is not None]; cov = len(vals) / max(len(o), 1)
        rr = frames(sc['rr'], a + 10000, b); bv = [x[1] for x in rr if x[2] == 'VALID']
        if truth is None:
            print(f'R1 {name}（人工计数缺 → NOT_EVALUATED）：窗 {len(o)}，有输出 {len(vals)}（{100 * cov:.0f}%）；值 {vals}')
            print(f'   板上 RR：有效 {len(bv)}/{len(rr)}，值 {sorted(set(bv))}')
            continue
        ok = sum(abs(x - truth) <= 2 for x in vals); acc = ok / max(len(vals), 1); bok = sum(abs(x - truth) <= 2 for x in bv)
        print(f'R1 {name}（真值 {truth:.1f}）：窗 {len(o)}，有输出 {len(vals)}（{100 * cov:.0f}%），±2 内 {ok}/{len(vals)}（{100 * acc:.0f}%）'
              f' → {"PASS" if cov >= .4 and acc >= .9 else "FAIL"}；值 {vals}')
        print(f'   板上 RR：有效 {len(bv)}/{len(rr)}（{100 * len(bv) / max(len(rr), 1):.0f}%），±2 内 {bok}/{len(bv)}')
