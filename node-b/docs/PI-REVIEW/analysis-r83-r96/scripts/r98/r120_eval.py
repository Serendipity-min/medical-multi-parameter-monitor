"""R120：R119（志愿者甲复测，手臂静止 + 手臂位置交替）评估，复用 r109_eval、r111_eval 的函数；MQTT 原件含无效批波形。
时刻为现场报告值（误差约 ±3 s），每段开头 10 s 不计。QRS 幅度 = qrs_polarity 的正峰中位（30 s 窗），噪声 = bands 的 5–25 Hz。
现场偏离：交替时双臂一起移动、放在桌上（不是左臂放扶手），段名按实际记录。20 次/分为 4 个 30 s 段计数 10+11+12+10=43。"""
import numpy as np
from r109_eval import get, ms, K, frames, ecg_arrays, human_row, bands, hr_metrics
from r111_eval import resp_peak
from qrs_polarity import polarity
import resp_r1
R119 = 'r119human-20261123T112630Z-node-ab.jsonl'
T0 = ms(23,19,33,30)
def qrs(a, b):
    t, v = ecg_arrays(R119, a, b); out = []
    for s in range(a, b - 29999, 30000):
        m = (t >= s) & (t < s + 30000)
        if m.sum() > 5000: out.append(polarity(list(zip(t[m], v[m] / 1000)))[2])
    return float(np.median(out)) if out else float('nan')
def noise(a, b): return float(bands(R119, a, b)[1])
SEG = [('S5 静止全程', T0 + 10000, ms(23,19,41,30)), ('S5 早段 +1–3 分', ms(23,19,34,30), ms(23,19,36,30)),
       ('S5 晚段 +6–8 分', ms(23,19,39,30), ms(23,19,41,30)), ('屏气后—交替前', ms(23,19,41,40), ms(23,19,43,10)),
       ('间隔 45:20–46:10', ms(23,19,45,20), ms(23,19,46,10)), ('交替后 48:15–51:00', ms(23,19,48,25), ms(23,19,51,0)),
       ('节拍20', ms(23,19,51,10), ms(23,19,53,0))]
ARM = [('P0 腿上（S5 末 60 s）', ms(23,19,40,30), ms(23,19,41,30)), ('P1 双臂桌上', ms(23,19,43,10), ms(23,19,44,10)),
       ('P2 双臂腿上', ms(23,19,44,20), ms(23,19,45,20)), ('P3 双臂桌上', ms(23,19,46,10), ms(23,19,47,10)),
       ('P4 双臂腿上', ms(23,19,47,15), ms(23,19,48,15))]
if __name__ == '__main__':
    w, sc, _ = get(R119)
    print('=== 模拟器心电核对（绿→RA、黄→LA、红→RL）')
    t, v = ecg_arrays(R119, ms(23,19,29,40), ms(23,19,30,30)); n, p, mp, mn = polarity(list(zip(t, v / 1000)))
    print(f'19:29:40–19:30:30 峰 {n}，主峰正向 {p:.1f}%，正峰中位 {mp:.0f} µV')
    print('=== 逐 30 s：HR 有效、QRS 正峰中位、5–25 Hz（T0 = 19:33:30）')
    for s in range(T0, ms(23,19,53,30), 30000):
        nv, nh, ok, n, med = hr_metrics(R119, s, s + 30000); t, v = ecg_arrays(R119, s, s + 30000)
        pn, pp, mp, mn = polarity(list(zip(t, v / 1000))) if len(t) > 5000 else (0, float('nan'), 0, 0)
        hh = (s // 1000 + 8 * 3600) % 86400
        print(f'{hh // 3600:02d}:{hh // 60 % 60:02d}:{hh % 60:02d} HR {nv:2d}/{nh:2d} 中位 {med:5.1f} PR±10% {ok}/{n} | 正峰 {mp:4.0f} 负峰 {mn:4.0f} µV 正向 {pp:5.1f}% | 5–25 Hz {noise(s, s + 30000):4.0f} µV')
    print('=== 分段（MQTT 全部批，含无效批）')
    for name, a, b in SEG: human_row(name, R119, a, b)
    human_row('R116 甲 贴片后头 3 分钟', 'r116human-20261123T085733Z-node-ab.jsonl', ms(23,17,5,30), ms(23,17,8,0))
    print('=== §6.2 静止段自发衰减（晚 ÷ 早）')
    qe, qa = qrs(*SEG[1][1:]), qrs(*SEG[2][1:]); ne, na = noise(*SEG[1][1:]), noise(*SEG[2][1:])
    print(f'QRS 早 {qe:.0f} 晚 {qa:.0f} µV → {qa / qe:.2f}；噪声 早 {ne:.0f} 晚 {na:.0f} µV → {na / ne:.2f}')
    print('=== §6.3 手臂位置（每段开头 10 s 不计）')
    Q = []
    for name, a, b in ARM:
        a += 10000; q = qrs(a, b) if b - a >= 30000 else float('nan'); t, v = ecg_arrays(R119, a, b)
        pn, pp, mp, mn = polarity(list(zip(t, v / 1000))); nv, nh, *_ = hr_metrics(R119, a, b); Q.append(mp)
        print(f'{name:16s} HR 有效 {nv}/{nh} | 50 s 正峰中位 {mp:4.0f} µV 负峰 {mn:4.0f} 正向 {pp:5.1f}% | 5–25 Hz {noise(a, b):4.0f} µV')
    print(f'桌上效应 P1/avg(P0,P2) {Q[1] / ((Q[0] + Q[2]) / 2):.2f}，P3/avg(P2,P4) {Q[3] / ((Q[2] + Q[4]) / 2):.2f}；'
          f'腿上三段 max/min {max(Q[0], Q[2], Q[4]) / min(Q[0], Q[2], Q[4]):.2f}；P2/P0 {Q[2] / Q[0]:.2f}，P4/P0 {Q[4] / Q[0]:.2f}')
    print('=== §6.4 节拍 20 次/分（只记录；真值 43/2 = 21.5）')
    rt = np.array([x[0] for x in w['resp']]); rv = np.array([x[1] * K for x in w['resp']])
    a, b = ms(23,19,51,0), ms(23,19,53,0)
    r, q, pp = resp_peak(rt, rv, a + 10000, b); m = (rt >= a - 40000) & (rt < b)
    o = [x for x in resp_r1.run(rt[m] / 1000, rv[m], (a - 36000) / 1000, b / 1000) if x[0] * 1000 - resp_r1.W * 1000 >= a - 1]
    vals = [round(x[1], 1) for x in o if x[1] is not None]; ok = sum(abs(x - 21.5) <= 2 for x in vals)
    rr = frames(sc['rr'], a + 10000, b); bv = [x[1] for x in rr if x[2] == 'VALID']
    print(f'频谱主峰 {r:.1f}/min 集中度 {q:.2f}；R1 窗 {len(o)}，有输出 {len(vals)}（{100 * len(vals) / max(len(o), 1):.0f}%），±2 内 {ok}/{len(vals)}；值 {vals}')
    print(f'板上 RR 有效 {len(bv)}/{len(rr)} 值 {sorted(set(bv))}')
