"""R123：主线 bio_v2.c 中 R1 的 C 实现与 resp_r1.py 逐窗对照（主机重放 MQTT RESP，不连接硬件）。
A 全片逐窗：C 按自身节拍（首点 +32 s 起、步长 2 s）出窗，Python 在同一窗末端调用 resp_r1.window，比较判因、单窗估计与持续输出。
B 判定复现：节拍段按各评估脚本的口径（首窗末端 = 段起 −4 s，只取窗起 ≥ 段起的窗）分别用 C 和 Python 计算 R1 判定。
用法：python3 -s -E r123_r1_equiv.py（需 numpy、gcc；在本目录运行）。"""
import ctypes as C, pathlib, subprocess, sys, numpy as np
from r109_eval import get, ms, K

import resp_r1
SRC = pathlib.Path('../../../../../firmware/biov2/实验固件/HARDWARE/bio_v2.c').resolve()
SO = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else '/tmp/r123_bio_v2_r1.so')
subprocess.run(['gcc', '-std=c99', '-O2', '-Wall', '-Wextra', '-Werror', '-ffp-contract=off', '-shared', '-fPIC',
                '-DBIO_V2_HOST_TEST', str(SRC), '-o', str(SO), '-lm'], check=True)
lib = C.CDLL(str(SO)); P = np.ctypeslib.ndpointer
lib.BioV2_R1Replay.argtypes = [P(np.uint32), P(np.float32), C.c_uint32, C.c_uint32, P(np.uint32), P(np.float32), P(np.uint8), P(np.float32), C.c_uint32]
lib.BioV2_R1Replay.restype = C.c_uint32
WHY = {'ok': 0, 'coverage': 1, 'gap': 2, 'transient': 3, 'amplitude': 4, 'edge': 5, 'quality': 6}
def series(f):
    w, _, _ = get(f); rt = np.array([x[0] for x in w['resp']]); rv = np.array([x[1] * K for x in w['resp']])
    return rt, rv
def c_run(rt, rv, base, first_end=0):
    cap = int((rt[-1] - rt[0]) / 2000) + 64; out = [np.zeros(cap, np.uint32), np.zeros(cap, np.float32), np.zeros(cap, np.uint8), np.zeros(cap, np.float32)]
    n = lib.BioV2_R1Replay(np.ascontiguousarray(rt - base, np.uint32), np.ascontiguousarray(rv, np.float32), len(rt), first_end, *out, cap)
    return [(int(e) + base, int(y), float(s), float(v) if v >= 0 else None) for e, s, y, v in zip(*[o[:n] for o in out])]
def py_run(rt, rv, ends):
    ts = rt / 1000; out, hist = [], []
    for e in ends:
        a = e / 1000 - resp_r1.W; i0, i1 = np.searchsorted(ts, [a - 1, a + resp_r1.W + 1])
        est, why = resp_r1.window(ts[i0:i1], rv[i0:i1], a); hist = (hist + [est])[-3:]
        val = float(np.median(hist)) if len(hist) == 3 and all(h is not None for h in hist) and max(hist) - min(hist) <= resp_r1.AGREE else None
        out.append((e, WHY[why], est, val))
    return out
def compare(cr, pr):
    why = sum(c[1] == p[1] for c, p in zip(cr, pr)); est = sum(c[1] == 0 and p[1] == 0 and abs(c[2] - p[2]) > 1e-3 for c, p in zip(cr, pr))
    outs = sum((c[3] is None) == (p[3] is None) and (c[3] is None or abs(c[3] - p[3]) < 1e-3) for c, p in zip(cr, pr))
    bad = [(c[0], c[1], p[1], round(c[2], 3), None if p[2] is None else round(p[2], 3)) for c, p in zip(cr, pr) if c[1] != p[1]][:5]
    return why, est, outs, bad
FILES = ['r83-20261118T065234Z-node-b.jsonl', 'r85-20261118T074904Z-node-ab.jsonl', 'r87-20261118T083445Z-node-ab.jsonl',
         'r89sim-20261118T093511Z-node-ab.jsonl', 'r89cal-20261118T100701Z-node-ab.jsonl', 'r89human-20261118T102758Z-node-ab.jsonl',
         'r91human-20261119T072140Z-node-ab.jsonl', 'r92sim-20261119T082651Z-node-ab.jsonl', 'r94human-20261119T090428Z-node-ab.jsonl',
         'r100rr-20261119T112442Z-node-ab.jsonl', 'r106sim-20261120T032641Z-node-ab.jsonl', 'r108human-20261120T061515Z-node-ab.jsonl',
         'r110human-20261120T073145Z-node-ab.jsonl', 'r112human-20261123T015825Z-node-ab.jsonl', 'r116human-20261123T085733Z-node-ab.jsonl',
         'r119human-20261123T112630Z-node-ab.jsonl']
PACED = [('R100 P10', 'r100rr-20261119T112442Z-node-ab.jsonl', ms(19,19,32,40), ms(19,19,34,0), 10),
         ('R100 P15', 'r100rr-20261119T112442Z-node-ab.jsonl', ms(19,19,35,10), ms(19,19,36,30), 15),
         ('R100 P20', 'r100rr-20261119T112442Z-node-ab.jsonl', ms(19,19,37,40), ms(19,19,39,0), 20),
         ('R113 节拍12', 'r112human-20261123T015825Z-node-ab.jsonl', ms(23,10,17,45), ms(23,10,19,45), 12),
         ('R113 节拍15', 'r112human-20261123T015825Z-node-ab.jsonl', ms(23,10,20,30), ms(23,10,22,30), 15),
         ('R113 节拍20', 'r112human-20261123T015825Z-node-ab.jsonl', ms(23,10,23,30), ms(23,10,25,30), 20),
         ('R117 节拍12', 'r116human-20261123T085733Z-node-ab.jsonl', ms(23,17,17,0), ms(23,17,19,0), 12),
         ('R117 节拍15', 'r116human-20261123T085733Z-node-ab.jsonl', ms(23,17,19,30), ms(23,17,21,30), 15),
         ('R117 节拍20', 'r116human-20261123T085733Z-node-ab.jsonl', ms(23,17,22,0), ms(23,17,24,0), 21)]
def verdict(o, truth):
    vals = [x[3] for x in o if x[3] is not None]; cov = len(vals) / max(len(o), 1); ok = sum(abs(v - truth) <= 2 for v in vals)
    return len(o), len(vals), ok, 'PASS' if cov >= .4 and ok / max(len(vals), 1) >= .9 else 'FAIL'
if __name__ == '__main__':
    print(f'源码 {SRC.name}，gcc -DBIO_V2_HOST_TEST')
    print('=== A 全片逐窗对照（判因一致 / 合格窗估计不一致 / 持续输出一致）')
    T_ = [0, 0, 0, 0]
    for f in FILES:
        rt, rv = series(f); base = int(rt[0]); cr = c_run(rt, rv, base); pr = py_run(rt, rv, [c[0] for c in cr])
        why, est, outs, bad = compare(cr, pr); n = len(cr); T_ = [T_[0] + n, T_[1] + why, T_[2] + est, T_[3] + outs]
        print(f'{f[:24]:24s} 窗 {n:5d} | 判因一致 {why:5d} | 估计不一致 {est} | 输出一致 {outs:5d} | C 输出 {sum(c[3] is not None for c in cr):4d} Py 输出 {sum(p[3] is not None for p in pr):4d}'
              + (f' | 判因不一致示例 {bad}' if bad else ''))
    print(f'合计 窗 {T_[0]}，判因一致 {T_[1]}（{100 * T_[1] / T_[0]:.3f}%），合格窗估计不一致 {T_[2]}，持续输出一致 {T_[3]}（{100 * T_[3] / T_[0]:.3f}%）')
    print('=== B 节拍段判定复现（覆盖 ≥40%，有输出窗 ≥90% 在真值 ±2 内）')
    for name, f, a, b, truth in PACED:
        rt, rv = series(f); m = (rt >= a - 40000) & (rt < b); rt, rv = rt[m], rv[m]; base = int(rt[0])
        ca = c_run(rt, rv, base, int(a - 4000 - base)); keep = [x[0] - 32000 >= a - 1 and x[0] <= b for x in ca]
        cr = [x for x, k in zip(ca, keep) if k]; pr = [x for x, k in zip(py_run(rt, rv, [x[0] for x in ca]), keep) if k]
        po = [(c, val, e, w) for c, val, e, w in resp_r1.run(rt / 1000, rv, (a - 36000) / 1000, b / 1000) if c * 1000 - resp_r1.W * 1000 >= a - 1]
        pv = [x[1] for x in po if x[1] is not None]
        print(f'{name}（真值 {truth}）C 窗 {verdict(cr, truth)} | Python 同窗 {verdict(pr, truth)} | 原评估 run() 窗 {len(po)} 有输出 {len(pv)}')
