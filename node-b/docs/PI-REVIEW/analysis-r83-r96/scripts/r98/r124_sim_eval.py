"""R124：R123 §5 模拟器验收判读（MQTT 原件）。判定口径在采集前写定并提交，采集后只填现场记录 JSON，不改本文件。
用法：python3 -s -E r124_sim_eval.py <现场记录.json>。JSON 字段（北京时间 hh:mm:ss，现场报告值，误差约 ±3 s）：
  capture、day 同 r122_eval；ecg  [开始, 结束]（60 bpm）；
  resp     [{"rate": 20, "start": 开始, "end": 结束}, ...]（1.0R）；era  [断开, 接回, 结束]，没做写 null。
口径（R123 §5.5 的数值化）：
  ECG：开始 +60 s 到结束，HR 帧 VALID ≥90%，有效值全部在 60±2；
  RR：每档开始 +45 s 到结束，RR 帧 VALID ≥80%，有效值全部在设定值 ±1；
  断开 ERA：断开到接回之间，VALID 帧的值不得偏离断开前那一档 ±1 以外；接回后只记录；
  连续性（只记录）：ECG、RESP 样本流相邻间隔 > 1.6 个采样周期的次数与总缺口时长。"""
import json, sys, numpy as np
from r109_eval import get, K, frames
from r122_eval import at, hhmmss
from load2 import runs
import resp_r1
def ratio(fr, lo, hi):
    v = [x[1] for x in fr if x[2] == 'VALID']
    return len(v), len(fr), sum(lo <= x <= hi for x in v), sorted(set(v))
if __name__ == '__main__':
    F = json.load(open(sys.argv[1], encoding='utf-8')); f = F['capture']; d = F['day']
    w, sc, _ = get(f); ok_all = []
    a, b = (at(d, x) for x in F['ecg'])
    nv, n, good, vals = ratio(frames(sc['hr'], a + 60000, b), 58, 62)
    ok = n and nv >= .9 * n and good == nv; ok_all.append(ok)
    print(f'=== ECG 60 bpm（{F["ecg"][0]}+60 s–{F["ecg"][1]}）HR VALID {nv}/{n}，在 58–62 内 {good}/{nv}，值 {vals} → {"PASS" if ok else "FAIL"}')
    rt = np.array([x[0] for x in w['resp']]); rv = np.array([x[1] * K for x in w['resp']])
    print('=== RR（1.0R；开始 +45 s 到结束）')
    for L in F['resp']:
        a, b = at(d, L['start']), at(d, L['end']); r = L['rate']
        nv, n, good, vals = ratio(frames(sc['rr'], a + 45000, b), r - 1, r + 1)
        ok = n and nv >= .8 * n and good == nv; ok_all.append(ok)
        m = (rt >= a - 40000) & (rt < b)
        o = [x for x in resp_r1.run(rt[m] / 1000, rv[m], (a - 36000) / 1000, b / 1000) if x[0] * 1000 - resp_r1.W * 1000 >= a - 1]
        ov = [round(x[1], 1) for x in o if x[1] is not None]
        print(f'{r} 次/分 {L["start"]}–{L["end"]}：板上 RR VALID {nv}/{n}（{100 * nv / max(n, 1):.0f}%），在 ±1 内 {good}/{nv}，值 {vals} → {"PASS" if ok else "FAIL"}'
              f' | 离线 R1 窗 {len(o)} 有输出 {len(ov)}，值 {sorted(set(ov))}')
    if F.get('era'):
        off, on, end = (at(d, x) for x in F['era']); prev = [L['rate'] for L in F['resp'] if at(d, L['start']) < off][-1]
        nv, n, good, vals = ratio(frames(sc['rr'], off, on), prev - 1, prev + 1)
        ok = good == nv; ok_all.append(ok)
        nv2, n2, _, vals2 = ratio(frames(sc['rr'], on, end), 0, 99)
        print(f'=== 断开 ERA {F["era"][0]}–{F["era"][1]}：RR VALID {nv}/{n}，值 {vals}（只允许 {prev}±1）→ {"PASS" if ok else "FAIL"}；'
              f'接回后（只记录）VALID {nv2}/{n2}，值 {vals2}')
    else: print('=== 断开 ERA：NOT_RUN')
    print('=== 连续性（只记录）')
    for k, step in (('ecg', 4.0), ('resp', 20.0)):
        seg = runs(w[k], step); gaps = [s[0][0] - p[-1][0] for p, s in zip(seg, seg[1:])]
        print(f'{k}：连续段 {len(seg)}，缺口 {len(gaps)} 个，合计 {sum(gaps) / 1000:.1f} s，最大 {max(gaps, default=0) / 1000:.2f} s；'
              f'录制 {hhmmss(int(w[k][0][0]))}–{hhmmss(int(w[k][-1][0]))}')
    print(f'=== §5 判定 → {"PASS" if all(ok_all) else "FAIL"}（ECG、各档 RR{"、断开 ERA" if F.get("era") else ""}）')
