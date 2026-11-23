"""R113：R112（志愿者丁，正确色标胸前，坐姿）评估，复用 r109_eval、r111_eval 的函数；MQTT 原件含无效批波形。
时刻为现场报告值（误差约 ±3 s），每段开头 10 s 不计。平躺、肢体 II 未做。
RR 真值为人工计数 ÷ 2 min（12 段 24±3、15 段 30±3、20 段 40±5），按 R110 §5.3 / R112 §5.4 判定 R1。"""
import numpy as np
from r109_eval import get, ms, K, frames, ecg_arrays, human_row
from r111_eval import resp_peak
from qrs_polarity import polarity
import resp_r1
R112 = 'r112human-20261123T015825Z-node-ab.jsonl'
SEG = [('丁 质量关期间', ms(23,10,9,40), ms(23,10,13,10)), ('丁 静坐', ms(23,10,15,40), ms(23,10,17,30)),
       ('丁 节拍12', ms(23,10,17,55), ms(23,10,19,45)), ('丁 节拍15', ms(23,10,20,40), ms(23,10,22,30)),
       ('丁 节拍20', ms(23,10,23,40), ms(23,10,25,30)), ('丁 S6 合计', ms(23,10,15,40), ms(23,10,25,50)),
       ('丁 合计（含质量关）', ms(23,10,9,40), ms(23,10,25,50))]
PACED = [('节拍12', ms(23,10,17,45), ms(23,10,19,45), 24 / 2), ('节拍15', ms(23,10,20,30), ms(23,10,22,30), 30 / 2),
         ('节拍20', ms(23,10,23,30), ms(23,10,25,30), 40 / 2)]
if __name__ == '__main__':
    w, sc, _ = get(R112)
    print('=== 模拟器心电核对（绿→RA、黄→LA、红→RL）')
    t, v = ecg_arrays(R112, ms(23,10,1,10), ms(23,10,2,0)); n, p, mp, mn = polarity(list(zip(t, v / 1000)))
    print(f'10:01:10–10:02:00 峰 {n}，主峰正向 {p:.1f}%，正峰中位 {mp:.0f} µV')
    print('=== 志愿者丁 胸前（MQTT 全部批，含无效批）')
    for name, a, b in SEG: human_row(name, R112, a, b)
    print('=== RESP（r 单位；R109 定标约 310 r/R）与板上 RR')
    rt = np.array([x[0] for x in w['resp']]); rv = np.array([x[1] * K for x in w['resp']])
    for name, a, b in SEG[:5]:
        r, q, pp = resp_peak(rt, rv, a, b); rr = frames(sc['rr'], a, b); val = [x[1] for x in rr if x[2] == 'VALID']
        print(f'{name:10s} 主峰 {r:4.1f}/min 集中度 {q:.2f} | p95−p5 {pp:6.0f} r ≈ {pp / 2 / 310:.1f} R'
              f' | 板上 RR 有效 {len(val)}/{len(rr)} 值 {sorted(set(val))}')
    print('=== R1 判定（覆盖率 ≥40%；有输出窗 ≥90% 在真值 ±2/min 内）')
    for name, a, b, truth in PACED:
        m = (rt >= a - 40000) & (rt < b)
        o = [x for x in resp_r1.run(rt[m] / 1000, rv[m], (a - 36000) / 1000, b / 1000) if x[0] * 1000 - resp_r1.W * 1000 >= a - 1]
        vals = [round(x[1], 1) for x in o if x[1] is not None]; ok = sum(abs(x - truth) <= 2 for x in vals)
        cov = len(vals) / max(len(o), 1); acc = ok / max(len(vals), 1)
        rr = frames(sc['rr'], a + 10000, b); bv = [x[1] for x in rr if x[2] == 'VALID']; bok = sum(abs(x - truth) <= 2 for x in bv)
        print(f'R1 {name}（真值 {truth:.1f}）：窗 {len(o)}，有输出 {len(vals)}（{100 * cov:.0f}%），±2 内 {ok}/{len(vals)}（{100 * acc:.0f}%）'
              f' → {"PASS" if cov >= .4 and acc >= .9 else "FAIL"}；值 {vals}')
        print(f'   板上 RR：有效 {len(bv)}/{len(rr)}（{100 * len(bv) / max(len(rr), 1):.0f}%），±2 内 {bok}/{len(bv)}')
