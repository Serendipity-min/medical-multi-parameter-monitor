"""离线复盘：用合成的类人体 ECG/呼吸输入驱动当前 bio_v2.c，观察 HR/RR 有效占比与失效原因。
合成信号只用于检验判据对变异/噪声的敏感度，不代表任何真人测量值。"""
import ctypes as C, math, random, sys, collections

import os
lib = C.CDLL(os.environ.get('BIOLIB','./libbio.so'))
lib.BioV2_Init.argtypes = [C.c_uint32]
lib.BioV2_Process.argtypes = [C.c_int32, C.c_int32, C.c_uint32, C.c_uint32, C.c_uint8]
F = ['tag','abi_version','samples','last_sequence','last_sample_ms','segment','discontinuities','clipped_samples']
R = ['ecg_raw','resp_raw','ecg_filtered','resp_filtered']
M = ['hr','rpm','hr_valid','rpm_valid','hr_reason','rpm_reason','hr_candidates','hr_accepted','resp_candidates',
     'resp_accepted','hr_last_cycle_ms','resp_last_cycle_ms','hr_fresh_intervals','resp_fresh_intervals']
FL = ['ecg_rms_codes','resp_rms_codes','ecg_mains_fraction','resp_mains_fraction']
class Diag(C.Structure):
    _fields_ = [(f, C.c_uint32) for f in F] + [(f, C.c_int32) for f in R] + [(f, C.c_uint32) for f in M] + [(f, C.c_float) for f in FL]
d = Diag.in_dll(lib, 'g_bio_v2')
MV = 13870.0  # 增益4、Vref 2.42 V：1 mV ≈ 13870 码（ads1292.c 配置推算）
FS = 250

def beat_times(seconds, hr, rsa, rpm, jitter, rng, ectopic=0.0):
    """RR 间期：均值 60/hr，叠加呼吸性窦律变化 rsa（相对幅度）和随机抖动 jitter（相对标准差）。"""
    t, out = 0.5, []
    base = 60.0 / hr
    while t < seconds + 2:
        rr = base * (1 + rsa * math.sin(2 * math.pi * rpm / 60 * t) + rng.gauss(0, jitter))
        if ectopic and rng.random() < ectopic:
            rr *= 0.7  # 早搏：提前，随后代偿
            out.append(t); t += rr; out.append(t); t += base * 1.3; continue
        out.append(t); t += rr
    return out

def ecg_wave(t, beats, amp_r, lead_s, idx):
    """P-Q-R-S-T 高斯和（I 导联量级，单位 mV），idx 为最近心搏指针。"""
    v = 0.0
    for b in beats[max(0, idx - 1): idx + 2]:
        ph = t - b
        v += (0.08 if amp_r > 0 else 0.0) * math.exp(-.5 * ((ph + .16) / .025) ** 2)
        v -= 0.06 * amp_r * math.exp(-.5 * ((ph + .025) / .008) ** 2)
        v += amp_r * math.exp(-.5 * (ph / .010) ** 2)
        v -= lead_s * math.exp(-.5 * ((ph - .028) / .010) ** 2)
        v += 0.25 * amp_r * math.exp(-.5 * ((ph - .26) / .045) ** 2)
    return v

def run(name, seconds=120, hr=75, amp_r=0.6, lead_s=0.15, rsa=0.05, jitter=0.02, rpm=14, resp_cv=0.10,
        emg=0.0, mains=0.0, wander=0.0, resp_amp=1200.0, cardio_in_resp=0.0, ectopic=0.0, seed=1, mains_mod=0.0, resp_mains=0.0, cardio_sin=0.0, resp_noise=0.0, resp_drift=0.0):
    rng = random.Random(seed)
    beats = beat_times(seconds, hr, rsa, rpm, jitter, rng, ectopic)
    # 呼吸：逐周期随机周期长度（变异系数 resp_cv），相位连续
    br_phase, br_period, resp_vals = 0.0, 60.0 / rpm, []
    lib.BioV2_Init(1000)
    valid_h = valid_r = 0; reasons_h = collections.Counter(); reasons_r = collections.Counter()
    idx = 0; lp = 0.0; hrs = collections.Counter()
    for i in range(seconds * FS):
        t = i / FS
        while idx + 1 < len(beats) and beats[idx + 1] <= t: idx += 1
        e = ecg_wave(t, beats, amp_r, lead_s, idx)
        if emg:  # 肌电：简单一阶高通白噪声，RMS 约 emg mV
            n = rng.gauss(0, emg); e += n - lp * 0.5; lp = n
        if mains: e += mains * (1 + mains_mod * math.sin(2 * math.pi * 0.03 * t)) * math.sin(2 * math.pi * 50 * t)
        if wander: e += wander * math.sin(2 * math.pi * 0.25 * t) + 0.5 * wander * math.sin(2 * math.pi * 0.07 * t + 1)
        br_phase += 1.0 / FS / br_period
        if br_phase >= 1.0:
            br_phase -= 1.0
            br_period = max(1.6, (60.0 / rpm) * (1 + rng.gauss(0, resp_cv)))
        r = 640000 + resp_amp * math.sin(2 * math.pi * br_phase)
        if cardio_in_resp:
            r += cardio_in_resp * resp_amp * math.exp(-.5 * (((t - beats[idx]) - .3) / .08) ** 2)
        if resp_mains: r += resp_mains * MV * math.sin(2 * math.pi * 50 * t)
        if cardio_sin: r += cardio_sin * resp_amp * math.sin(2 * math.pi * hr / 60 * t)
        if resp_noise: r += rng.gauss(0, resp_noise * resp_amp)
        if resp_drift: r += resp_drift * resp_amp * (math.sin(2*math.pi*0.11*t) + 0.7*math.sin(2*math.pi*0.047*t+2))
        lib.BioV2_Process(int(200000 + e * MV), int(r), (1000 + i * 4) & 0xffffffff, i + 1, 0)
        if i >= 15 * FS:  # 前 15 s 预热不计
            valid_h += d.hr_valid; valid_r += d.rpm_valid
            reasons_h[d.hr_reason] += 1; reasons_r[d.rpm_reason] += 1
            if d.hr_valid: hrs[d.hr] += 1
    n = (seconds - 15) * FS
    top = lambda c: ' '.join(f'{k}:{100*v/n:.0f}%' for k, v in c.most_common(3))
    print(f'{name:<44} HRvalid {100*valid_h/n:5.1f}% (hr={d.hr:3d}, cand={d.hr_candidates}, acc={d.hr_accepted}) '
          f'RRvalid {100*valid_r/n:5.1f}% hrs={dict(hrs.most_common(4))} | HRreason {top(reasons_h)} | RRreason {top(reasons_r)}')

if __name__ == '__main__':
    exec(sys.stdin.read())
