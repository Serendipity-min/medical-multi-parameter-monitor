"""厂家（凌智 F103/F429 例程）心率算法 vs 板上 BIO_V2；厂家思路补的呼吸率 vs 板上 R1。纯离线，只读 MQTT 录制。
输入限制：MQTT 上的 ECG 是 BIO_V2 检测带（陷波 + 5–25 Hz）波形，RESP 是 0.8 Hz 低通、50 Hz 抽取后的波形，均非 ADC 原始码。
厂家链路在其上原样运行（offset-binary → 129 抽头 FIR → 三点峰检），等于给厂家一个比它自己前端更干净的输入（偏向厂家的最好情况）。
板上数值（HR/RR 帧）是实机冻结固件的真实输出，不重放。
用法：在本目录运行 python3 -s -E vendor_cmp.py（需 numpy、scipy；录制放在 ../../r83-capture/，不入库）。结果见 ../../results/vendor_cmp.txt。"""
import bisect, datetime, json, sys, numpy as np
from scipy.signal import lfilter

CAP = '../../r83-capture/'
TZ = datetime.timezone(datetime.timedelta(hours=8))

def at(day, s):
    h, m, x = map(int, s.split(':'))
    return int(datetime.datetime(2026, 11, day, h, m, x, tzinfo=TZ).timestamp() * 1000)

def coeffs(name):
    """从厂家 F103 usart 例程 main.c 取系数（GB18030 编码）。"""
    src = open('../../../../../../ADS1292R模块资料V4.1_ECG/测试程序/STM32F103/STM32F103_FIR_ADS1292_usart/User/main.c',
               encoding='gb18030').read()
    body = src.split(name + '[NumTaps]')[1].split('{', 1)[1].split('}', 1)[0]
    c = np.array([float(x) for x in body.replace('\n', ' ').split(',') if x.strip()])
    assert len(c) == 129, len(c)
    return c

BPF = coeffs('BPF_5Hz_40Hz'); LPF = coeffs('LPF_2Hz')
UV_PER_CODE = 0.11920928955 * 126877696 / 209715175   # 检测带码 → µV（ecg_units.h）
K_RESP = 1000 / 0.11920928955                            # RESP 显示量 → 滤波域码（r109_eval.K）

def load(path):
    """返回 waves{'ecg','resp'}: [(t_ms, v)]，scal{'hr','rr','pr'}: [(t_ms, value, VALID?)]；按 (流, 会话, seq) 去重（含断网保留补发）。"""
    w = {'ecg': [], 'resp': []}; sc = {'hr': [], 'rr': [], 'pr': []}; seen = set()
    for line in open(path, encoding='utf-8'):
        r = json.loads(line); parts = r['topic'].split('/')
        if len(parts) < 5 or parts[3] not in ('NODE-A', 'NODE-B'): continue
        k = parts[-1]
        if k not in w and k not in sc: continue
        try: p = json.loads(r['payload'])
        except (ValueError, TypeError): continue
        key = (k, p.get('session_id'), p['seq'])
        if key in seen: continue
        seen.add(key)
        if k in w:
            n = len(p['samples']); st = 1000.0 / p['sample_rate']; t0 = p['timestamp'] - (n - 1) * st
            w[k] += [(t0 + i * st, v) for i, v in enumerate(p['samples'])]
        else:
            sc[k].append((p['timestamp'], p['value'], p['validity'] == 'VALID'))
    for s in list(w.values()) + list(sc.values()): s.sort(key=lambda x: x[0])
    return w, sc

def gaps(ts, step):
    """相邻样本间隔 > 1.6 步长的缺口 [(起, 止)]。"""
    d = np.diff(ts); i = np.nonzero(d > 1.6 * step)[0]
    return [(ts[j], ts[j + 1]) for j in i]

def vendor_peaks(t, y, refresh, refractory=0, integer=True):
    """厂家 main.c 三点峰检逐行复刻：u32 截断、阈值 max[0]-Peak/3、每 refresh 点刷新极值；point_cnt*4 用时间戳差代替（无缺口时相同）。
    Peak/BPM_LH 在厂家源码中未初始化，这里取 0（开头 refresh 点内任何局部极大都算峰，与厂家行为一致或更好）。
    refractory>0 仅用于“厂家思路呼吸”的改良版。返回 [(检出时刻, 速率/分, 间期起点)]。"""
    mn = [0xFFFFFFFF, 0xFFFFFFFF]; mx = [0, 0]; peak = 0; L = [0, 0, 0]; pnum = 0; last = None; out = []
    for tk, yk in zip(t, y):
        q = int(yk) if integer else float(yk)
        if mn[1] > yk: mn[1] = q
        if mx[1] < yk: mx[1] = q
        L[0], L[1], L[2] = L[1], L[2], q
        thr = (mx[0] - peak // 3) % (1 << 32) if integer else mx[0] - peak / 3
        if L[0] < L[1] and L[1] > thr and L[2] < L[1]:
            if last is None:
                last = tk                      # 厂家首个峰用的是开机以来的计数，这里不计入
            elif tk - last >= refractory:
                out.append((tk, 60000.0 / (tk - last), last)); last = tk
        pnum += 1
        if pnum > refresh:
            mn[0], mx[0] = mn[1], mx[1]; mn[1], mx[1] = 0xFFFFFFFF, 0
            peak = (mx[0] - mn[0]) % (1 << 32) if integer else mx[0] - mn[0]; pnum = 0
    return out

def held(events, instants, gap_list, cap=None):
    """厂家输出是“最近一次算出的值一直保持”。在每个评分时刻取当前值；若该值的间期跨过 MQTT 缺口则标记 None（板上无此缺口，不能算厂家的错）。"""
    et = [e[0] for e in events]; res = []
    for x in instants:
        i = bisect.bisect_right(et, x) - 1
        if cap is not None:   # LCD 版：BPM ≥ cap 不刷新显示，退回到上一个 < cap 的值
            while i >= 0 and events[i][1] >= cap: i -= 1
        if i < 0: res.append(('none', None)); continue
        a, b = events[i][2], events[i][0]
        if any(g0 < b and g1 > a for g0, g1 in gap_list): res.append(('gap', None)); continue
        res.append(('ok', events[i][1]))
    return res

def run_vendor_hr(w):
    t = np.array([x[0] for x in w['ecg']]); code = np.array([x[1] * 1000 for x in w['ecg']]) / UV_PER_CODE
    y = lfilter(BPF, 1.0, (code + 8388608).astype(np.float32).astype(np.float64)).astype(np.float32)
    return t, vendor_peaks(t, y, 2000), gaps(t, 4.0)

_rr_cache = {}
def run_vendor_rr(w, refresh, refractory):
    key = (id(w), refresh, refractory)
    if key not in _rr_cache: _rr_cache[key] = _run_vendor_rr(w, refresh, refractory)
    return _rr_cache[key]
def _run_vendor_rr(w, refresh, refractory):
    """呼吸基线是我们按厂家思路补的，不是厂家代码：厂家 2 Hz 低通 + 同一套三点峰检。
    与厂家不同处（均为避免数值伪影）：float64、不加 0x800000 偏置（float32 在 840 万附近分辨率为 1 码，慢变呼吸波 97% 相邻点相等，三点比较全部落在平顶上）；
    ≤2.5 s 的上传缺口在 50 Hz 点上线性插值补齐（RESP 已 0.8 Hz 低通），更长缺口不插值，跨它的间期在评分时剔除。"""
    t50 = np.array([x[0] for x in w['resp']]); v50 = np.array([x[1] * K_RESP for x in w['resp']])
    gl = [g for g in gaps(t50, 20.0) if g[1] - g[0] > 2500]
    cuts = [t50[0]] + [g[1] for g in gl]; ends = [g[0] for g in gl] + [t50[-1]]
    t = np.concatenate([np.arange(a, b + 1e-6, 4.0) for a, b in zip(cuts, ends)])
    y = lfilter(LPF, 1.0, np.interp(t, t50, v50))
    return vendor_peaks(t, y, refresh, refractory, integer=False), gl

def score(instants_vals, ok):
    n = len(instants_vals); out = [v for s, v in instants_vals if s == 'ok']
    g = sum(1 for s, _ in instants_vals if s == 'gap')
    good = sum(1 for v in out if ok(v))
    return n, len(out), g, good

def board(sc, k, a, b):
    return [x for x in sc[k] if a <= x[0] < b]

def pct(x, n): return f'{100 * x / n:5.1f}%' if n else '  —  '

def sim_rows(name, f, day, ecg, resp):
    _rr_cache.clear()   # 键里的 id(w) 在对象回收后会被复用
    w, sc = load(CAP + f); print(f'\n### {name}（{f.split("-")[0]}）')
    t, hr_ev, hr_gap = run_vendor_hr(w)
    a, b = at(day, ecg[0]) + 60000, at(day, ecg[1])
    fr = board(sc, 'hr', a, b); inst = [x[0] for x in fr]
    bv = [x for x in fr if x[2]]; bg = sum(58 <= x[1] <= 62 for x in bv)
    vv = held(hr_ev, inst, hr_gap); n, no, ng, vg = score(vv, lambda v: 58 <= v <= 62)
    lv = held(hr_ev, inst, hr_gap, cap=200); _, lo, _, lg = score(lv, lambda v: 58 <= v <= 62)
    beats = [e[1] for e in hr_ev if a <= e[0] < b and not any(g0 < e[0] and g1 > e[2] for g0, g1 in hr_gap)]
    bb = sum(58 <= x <= 62 for x in beats)
    print(f'HR 60 bpm，{ecg[0]}+60 s–{ecg[1]}，评分时刻 {len(inst)}（板上 HR 帧，1 Hz）')
    print(f'  BIO_V2 板上：有效 {len(bv)}/{len(fr)}（{pct(len(bv), len(fr))}），有效值在 58–62 {bg}/{len(bv)}（{pct(bg, len(bv))}）；值 {sorted(set(x[1] for x in bv))}')
    print(f'  厂家 usart 版：有值 {no}/{n - ng}（剔除跨缺口 {ng}），在 58–62 {vg}/{no}（{pct(vg, no)}）；'
          f'逐拍 BPM {len(beats)} 次，在 58–62 {bb}（{pct(bb, len(beats))}），中位 {np.median(beats) if beats else 0:.1f}，'
          f'分位 5/95 {np.percentile(beats, 5) if beats else 0:.1f}/{np.percentile(beats, 95) if beats else 0:.1f}')
    print(f'  厂家 LCD 版（BPM<200 才刷新）：在 58–62 {lg}/{lo}（{pct(lg, lo)}）')
    res = {'hr': (len(fr), len(bv), bg, n - ng, no, vg, lo, lg)}
    # ECG 段 RR 误报（模拟器 ECG 模式无呼吸）
    a0, b0 = at(day, ecg[0]), at(day, ecg[1]) + 10000
    fr = board(sc, 'rr', a0, b0); inst = [x[0] for x in fr]; brv = [x for x in fr if x[2]]
    print(f'ECG 段（无呼吸）RR 误报：板上 R1 有效 {len(brv)}/{len(fr)}', end='')
    for tag, refresh, refr in (('厂家思路·原样', 2000, 0), ('厂家思路·改良', 8000, 1500)):
        ev, gl = run_vendor_rr(w, refresh, refr); vv = held(ev, inst, gl); n, no, ng, _ = score(vv, lambda v: True)
        vals = [v for s, v in vv if s == 'ok']
        print(f'；{tag} 有值 {no}/{n - ng}（中位 {np.median(vals) if vals else 0:.1f}/分）', end='')
    print()
    for L in resp:
        a, b = at(day, L['start']) + 45000, at(day, L['end']); r = L['rate']
        fr = board(sc, 'rr', a, b); inst = [x[0] for x in fr]; brv = [x for x in fr if x[2]]; bg = sum(abs(x[1] - r) <= 1 for x in brv)
        print(f'RR {r} 次/分，{L["start"]}+45 s–{L["end"]}，评分时刻 {len(inst)}')
        print(f'  R1 板上：有效 {len(brv)}/{len(fr)}（{pct(len(brv), len(fr))}），±1 内 {bg}/{len(brv)}（{pct(bg, len(brv))}）；值 {sorted(set(x[1] for x in brv))}')
        res[f'rr{r}'] = [(len(fr), len(brv), bg)]
        for tag, refresh, refr in (('厂家思路·原样', 2000, 0), ('厂家思路·改良', 8000, 1500)):
            ev, gl = run_vendor_rr(w, refresh, refr); vv = held(ev, inst, gl); n, no, ng, vg = score(vv, lambda v: abs(v - r) <= 1)
            vals = [v for s, v in vv if s == 'ok']
            br = [e[1] for e in ev if a <= e[0] < b]
            print(f'  {tag}：有值 {no}/{n - ng}，±1 内 {vg}/{no}（{pct(vg, no)}），中位 {np.median(vals) if vals else 0:.1f}；'
                  f'逐次 {len(br)} 个，±1 内 {pct(sum(abs(x - r) <= 1 for x in br), len(br))}')
            res[f'rr{r}'].append((n - ng, no, vg))
    return res

def human_rows(name, f, day, t0, paced, paced_dur, truth, rr_from, note):
    _rr_cache.clear()   # 键里的 id(w) 在对象回收后会被复用
    w, sc = load(CAP + f); print(f'\n### {name}（{f.split("-")[0]}）')
    t, hr_ev, hr_gap = run_vendor_hr(w)
    pr = [x for x in sc['pr'] if x[2] and x[1]]; pt = [x[0] for x in pr]
    def ref(x):
        i = bisect.bisect_left(pt, x); c = [pr[j] for j in (i - 1, i) if 0 <= j < len(pr) and abs(pr[j][0] - x) <= 1000]
        return min(c, key=lambda z: abs(z[0] - x))[1] if c else None
    T0 = at(day, t0)
    hr_all = sc['hr']
    for tag, a, b in (('验收窗 T0+10 s–T0+180 s', T0 + 10000, T0 + 180000),
                      ('全程（板上 HR 帧所在全部时段，只记录）', hr_all[0][0], hr_all[-1][0] + 1)):
        fr = board(sc, 'hr', a, b); inst = [x[0] for x in fr]
        bv = [x for x in fr if x[2]]; bp = [(x[1], ref(x[0])) for x in bv]; bp = [p for p in bp if p[1]]
        bg = sum(abs(h - q) <= .1 * q for h, q in bp)
        vv = held(hr_ev, inst, hr_gap); vp = [(v, ref(x)) for x, (s, v) in zip(inst, vv) if s == 'ok']; vp = [p for p in vp if p[1]]
        vg = sum(abs(h - q) <= .1 * q for h, q in vp); ng = sum(1 for s, _ in vv if s == 'gap'); no = sum(1 for s, _ in vv if s == 'ok')
        lv = held(hr_ev, inst, hr_gap, cap=200); lp = [(v, ref(x)) for x, (s, v) in zip(inst, lv) if s == 'ok']; lp = [p for p in lp if p[1]]
        lg = sum(abs(h - q) <= .1 * q for h, q in lp)
        print(f'HR {tag}，评分时刻 {len(inst)}（{(b - a) / 1000:.0f} s）')
        print(f'  BIO_V2 板上：有效 {len(bv)}/{len(fr)}（{pct(len(bv), len(fr))}），与 PR ±10% {bg}/{len(bp)}（{pct(bg, len(bp))}）')
        print(f'  厂家 usart 版：有值 {no}/{len(inst) - ng}（剔除跨缺口 {ng}），与 PR ±10% {vg}/{len(vp)}（{pct(vg, len(vp))}），'
              f'中位 {np.median([p[0] for p in vp]) if vp else 0:.1f} vs PR 中位 {np.median([p[1] for p in vp]) if vp else 0:.1f}')
        print(f'  厂家 LCD 版：与 PR ±10% {lg}/{len(lp)}（{pct(lg, len(lp))}）')
    a, b = at(day, paced) + rr_from * 1000, at(day, paced) + paced_dur * 1000; r = truth
    fr = board(sc, 'rr', a, b); inst = [x[0] for x in fr]; brv = [x for x in fr if x[2]]; bg = sum(abs(x[1] - r) <= 2 for x in brv)
    print(f'RR 真值 {truth} 次/分（{note}），{paced}+{rr_from} s 起 {paced_dur - rr_from} s，评分时刻 {len(inst)}')
    print(f'  R1 板上：有效 {len(brv)}/{len(fr)}（{pct(len(brv), len(fr))}），±2 内 {bg}/{len(brv)}（{pct(bg, len(brv))}）；值 {sorted(set(x[1] for x in brv))}')
    for tag, refresh, refr in (('厂家思路·原样', 2000, 0), ('厂家思路·改良', 8000, 1500)):
        ev, gl = run_vendor_rr(w, refresh, refr); vv = held(ev, inst, gl); n, no, ng, vg = score(vv, lambda v: abs(v - r) <= 2)
        vals = [v for s, v in vv if s == 'ok']
        print(f'  {tag}：有值 {no}/{n - ng}，±2 内 {vg}/{no}（{pct(vg, no)}），中位 {np.median(vals) if vals else 0:.1f}')

if __name__ == '__main__':
    f = lambda x: 20 * np.log10(abs(np.polyval(BPF[::-1], np.exp(-1j * 2 * np.pi * x / 250))) + 1e-12)
    print(f'厂家 BPF：DC 增益 {BPF.sum():.4f}，10/50 Hz {f(10):.1f}/{f(50):.1f} dB；LPF DC 增益 {LPF.sum():.4f}')
    sim_rows('模拟器 R123', 'r123sim-20261124T075651Z-node-ab.jsonl', 24, ['15:59:52', '16:01:52'],
             [{'rate': 20, 'start': '16:02:55', 'end': '16:06:58'}, {'rate': 12, 'start': '16:06:58', 'end': '16:10:10'}])
    sim_rows('模拟器 R125', 'r125sim-20261126T115404Z-node-ab.jsonl', 26, ['19:57:00', '20:01:30'],
             [{'rate': 20, 'start': '20:02:10', 'end': '20:05:20'}, {'rate': 12, 'start': '20:05:40', 'end': '20:09:10'}])
    sim_rows('模拟器 R127 一小时长测（冻结 R125 K5）', 'r127l1-20261127T062553Z-gateway.jsonl', 27, ['14:28:00', '14:54:55'],
             [{'rate': 20, 'start': '14:55:35', 'end': '15:19:30'}, {'rate': 12, 'start': '15:19:30', 'end': '15:28:00'}])
    human_rows('真人 R123', 'r123human-20261124T082448Z-node-ab.jsonl', 24, '16:29:07', '16:35:00', 300, 15.2, 45, '现场 5 次 30 s 抽样计数均值，R124 §4.3')
    human_rows('真人 R125', 'r125human-20261127T020900Z-node-ab.jsonl', 27, '10:27:40', '10:27:40', 180, 12, 90, '负责人裁定的实测值，R126 §3.3；窗口同验收')
    human_rows('真人 R125（同上，+45 s 起，只记录）', 'r125human-20261127T020900Z-node-ab.jsonl', 27, '10:27:40', '10:27:40', 180, 12, 45, '同上')
