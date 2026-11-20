"""R111：R110（志愿者丙，正确色标胸前）评估，复用 r109_eval 的函数；MQTT 原件含无效批波形。
时刻为现场报告值（误差约 ±3 s），每段开头 10 s 不计。节拍段没有人工计数，RR 只记录、不判定。"""
import numpy as np
from r109_eval import get, ms, K, frames, ecg_arrays, human_row
from qrs_polarity import polarity
import resp_r1
R110 = 'r110human-20261120T073145Z-node-ab.jsonl'
SEG = [('丙 质量关期间', ms(20,15,40,5), ms(20,15,47,0)), ('丙 静坐', ms(20,15,47,10), ms(20,15,49,0)),
       ('丙 正常呼吸', ms(20,15,49,40), ms(20,15,51,30)), ('丙 节拍15', ms(20,15,51,40), ms(20,15,53,0)),
       ('丙 节拍20', ms(20,15,53,30), ms(20,15,55,15)), ('丙 合计', ms(20,15,40,5), ms(20,15,55,25))]
def resp_peak(rt, rv, a, b):
    m = (rt >= a) & (rt < b); g = np.arange(a, b, 100.0); x = np.interp(g, rt[m], rv[m])
    x = x - np.polyval(np.polyfit(g - a, x, 1), g - a); x *= np.hanning(len(x))
    X = abs(np.fft.rfft(x, 4096)) ** 2; f = np.fft.rfftfreq(4096, .1); bd = (f >= .1) & (f <= .7); fp = f[bd][np.argmax(X[bd])]
    return 60 * fp, X[abs(f - fp) <= .03].sum() / X[bd].sum(), float(np.subtract(*np.percentile(rv[m], [95, 5])))
if __name__ == '__main__':
    w, sc, _ = get(R110)
    print('=== 模拟器心电核对（绿→RA、黄→LA、红→RL）')
    t, v = ecg_arrays(R110, ms(20,15,36,10), ms(20,15,37,0)); n, p, mp, mn = polarity(list(zip(t, v / 1000)))
    print(f'15:36:10–15:37:00 峰 {n}，主峰正向 {p:.1f}%，正峰中位 {mp:.0f} µV')
    print('=== 志愿者丙 胸前（MQTT 全部批，含无效批）')
    for name, a, b in SEG: human_row(name, R110, a, b)
    print('=== RESP（r 单位；R109 定标约 310 r/R）与 RR')
    rt = np.array([x[0] for x in w['resp']]); rv = np.array([x[1] * K for x in w['resp']])
    for name, a, b in SEG:
        r, q, pp = resp_peak(rt, rv, a, b); rr = frames(sc['rr'], a, b)
        print(f'{name:10s} 主峰 {r:4.1f}/min 集中度 {q:.2f} | p95−p5 {pp:6.0f} r ≈ {pp / 2 / 310:.1f} R | 板上 RR 有效 {sum(x[2] == "VALID" for x in rr)}/{len(rr)}')
    for name, a, b, nominal in [('节拍15', ms(20,15,51,40), ms(20,15,53,0), 15), ('节拍20', ms(20,15,53,30), ms(20,15,55,15), 20)]:
        m = (rt >= a - 40000) & (rt < b)
        o = [x for x in resp_r1.run(rt[m] / 1000, rv[m], (a - 36000) / 1000, b / 1000) if x[0] * 1000 - resp_r1.W * 1000 >= a - 1]
        vals = [round(x[1], 1) for x in o if x[1] is not None]
        print(f'R1 {name}（节拍设定 {nominal}，人工计数缺）：窗 {len(o)}，有输出 {len(vals)}，值 {vals}，单窗原因 {dict((k, sum(1 for x in o if x[3] == k)) for k in set(x[3] for x in o))}')
