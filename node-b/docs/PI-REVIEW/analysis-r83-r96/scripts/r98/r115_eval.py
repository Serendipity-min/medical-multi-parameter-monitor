"""R115：R114（志愿者丙，先躺后坐）评估。判定逻辑按 R114 §8 补记在采集前写定并提交，采集后只填现场记录 JSON，不改本文件。
用法：python3 -s -E r115_eval.py <现场记录.json>。JSON 字段（北京时间 hh:mm:ss，现场报告值，误差约 ±3 s）：
  capture、day、sim、offcard 同 r122_eval；t0  平躺贴好、两臂放好的时刻；sit  坐好的时刻；
  paced    同 r122_eval；没做写 {}（记 NOT_RUN）。
平躺窗 L = T0+2:10–T0+4:00，坐姿窗 S = 坐好+1:10–坐好+3:00（各自开头 10 s 不计）。"""
import json, sys
from r109_eval import ms, human_row, bands
from r122_eval import at, sim_check, r1_paced
REF_SIT = 268   # R111 丙静坐 5–25 Hz（µV）
if __name__ == '__main__':
    F = json.load(open(sys.argv[1], encoding='utf-8')); f = F['capture']; d = F['day']
    sim_check(F)
    T0, SIT = at(d, F['t0']), at(d, F['sit'])
    L, S = (T0 + 130000, T0 + 240000), (SIT + 70000, SIT + 180000)
    print('=== §8.4 平躺 / 坐姿（MQTT 全部批，含无效批）')
    human_row('平躺稳定（只记录）', f, T0 + 10000, T0 + 120000)
    human_row('平躺窗 L', f, *L); human_row('坐姿窗 S', f, *S)
    bl, bs = bands(f, *L), bands(f, *S)
    lo, ratio = bs[0] / bl[0], bl[1] / bs[1]
    hit = [x for x in F['offcard'] if L[0] - 10000 <= at(d, x) <= L[1] or S[0] - 10000 <= at(d, x) <= S[1]]
    print(f'接触核对：0.5–5 Hz 坐 ÷ 躺 {lo:.2f}（>2.0 或 <0.5 判接触变化）{"；窗内卡外动作 " + "、".join(hit) if hit else ""}')
    if hit or lo > 2.0 or lo < 0.5: verdict = 'NOT_EVALUABLE'
    elif ratio <= .5: verdict = '支持胸壁肌电主导' if bs[1] >= .7 * REF_SIT else '躺下降噪，但坐姿低于丙既往水平：部分支持，需复测'
    elif ratio <= .8: verdict = '部分支持，需复测'
    else: verdict = '不支持，噪声另有来源'
    print(f'5–25 Hz 躺 {bl[1]:.0f} µV、坐 {bs[1]:.0f} µV（R111 丙静坐 {REF_SIT}，×0.7 = {.7 * REF_SIT:.0f}）；躺 ÷ 坐 {ratio:.2f} → {verdict}')
    P = sorted(F['paced'].items(), key=lambda kv: int(kv[0]))
    if not P: print('=== 节拍呼吸 NOT_RUN'); sys.exit()
    print('=== 节拍各段 HR（只记录，每段开头 10 s 不计）')
    for k, c in P: a = at(d, c['start']); human_row(f'节拍{k}', f, a + 10000, a + 120000)
    r1_paced(F, P)
