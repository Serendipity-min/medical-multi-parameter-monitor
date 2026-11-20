"""R103：主线 C 版 ALC（drv_alc.c）与 R99 Python 原型 ecg_cands.alc 在同一批录制上逐点对照，并比较接 C2 后的逐样本 HR。
相位口径一致：两边都用 t mod 2^32 毫秒（板上 now 为 uint32）。"""
import contextlib, ctypes as C, io, subprocess, numpy as np
with contextlib.redirect_stdout(io.StringIO()):   # ecg_eval 导入时会重跑 R99 全表，这里只要数据段定义
    from ecg_eval import HUMAN, NEG, POS, data
from ecg_cands import alc, c2
SRC = '../../../../../firmware/biov2/实验固件/HARDWARE/bio_v2.c'
subprocess.run(['gcc', '-std=c99', '-O2', '-ffp-contract=off', '-shared', '-fPIC', f'-DBIO_SRC="{SRC}"', 'drv_alc.c', '-o', 'drv_alc.so', '-lm'], check=True)
L = C.CDLL('./drv_alc.so'); L.A_Init.argtypes = [C.c_uint32]
L.A_Line.argtypes = [C.c_float, C.c_uint32]; L.A_Line.restype = C.c_float
L.A_Feed.argtypes = [C.c_float, C.c_uint32]; L.A_Feed.restype = C.c_uint32
def c_run(y, feed):
    L.A_Init(int(y[0][0]) & 0xffffffff); out = []; prev = None
    for t, v in y:
        if prev is not None and t - prev > 20: L.A_Reset()
        prev = t; out.append(feed(v, int(t) & 0xffffffff))
    return out
print('数据段            样本   ALC 输出差 max/rms(相对 y 的 rms)   逐样本 HR 相同   逐样本有效%（含 20 s 引导段）Py / C')
for name, f, A, B in HUMAN + NEG + POS:
    y, _ = data(f, A, B)
    y = [(t % 2 ** 32, v) for t, v in y]
    py = np.array([e for _, e in alc(y)]); cc = np.array(c_run(y, L.A_Line))
    d = abs(py - cc); ref = np.std([v for _, v in y])
    hp = [r for _, r in c2(alc(y))]; hc = c_run(y, L.A_Feed)
    same = np.mean([a == b for a, b in zip(hp, hc)])
    print(f'{name:16s} {len(y):7d}   {d.max()/ref:.1e} / {np.sqrt((d**2).mean())/ref:.1e}            {100*same:6.2f}%      {100*np.mean([r>0 for r in hp]):5.1f} / {100*np.mean([r>0 for r in hc]):5.1f}')
