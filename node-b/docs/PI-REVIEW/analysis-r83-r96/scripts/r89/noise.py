import sys, ctypes as C, math, random, subprocess, collections
src = sys.argv[1]; so = src.replace('.c', '.so')
subprocess.run(['gcc','-std=c99','-O2','-ffp-contract=off','-shared','-fPIC','-Isrc',src,'-o',so,'-lm'],check=True)
lib = C.CDLL('./' + so); lib.BioV2_Init.argtypes=[C.c_uint32]; lib.BioV2_Process.argtypes=[C.c_int32,C.c_int32,C.c_uint32,C.c_uint32,C.c_uint8]
exec(open('run_host.py').read().split("class Diag")[0].split("fields=")[1].join(["fields=",""]) if False else "")
fields=['tag','abi_version','samples','last_sequence','last_sample_ms','segment','discontinuities','clipped_samples']
raw=['ecg_raw','resp_raw','ecg_filtered','resp_filtered']
more=['hr','rpm','hr_valid','rpm_valid','hr_reason','rpm_reason','hr_candidates','hr_accepted','resp_candidates','resp_accepted','hr_last_cycle_ms','resp_last_cycle_ms','hr_fresh_intervals','resp_fresh_intervals']
flt=['ecg_rms_codes','resp_rms_codes','ecg_mains_fraction','resp_mains_fraction']
class Diag(C.Structure):
    _fields_=[(f,C.c_uint32) for f in fields]+[(f,C.c_int32) for f in raw]+[(f,C.c_uint32) for f in more]+[(f,C.c_float) for f in flt]
d=Diag.in_dll(lib,'g_bio_v2')
tot = []
for seed in range(1, 41):
    rng = random.Random(seed); lib.BioV2_Init(1000); v = 0; streak = longest = 0; vals = collections.Counter()
    for i in range(180*250):
        lib.BioV2_Process(int(round(200000+rng.gauss(0,2000))), int(round(640000+rng.gauss(0,2000))), 1000+i*4, i+1, 0)
        if d.hr_valid: v += 1; streak += 1; longest = max(longest, streak); vals[d.hr] += 1
        else: streak = 0
    tot.append((seed, 100*v/(180*250), longest*4, sorted(vals)[:6]))
bad = [x for x in tot if x[1] > 2]
print(src, 'mean %.2f%%' % (sum(x[1] for x in tot)/len(tot)), 'max %.2f%%' % max(x[1] for x in tot), 'seeds>2%:', len(bad), 'longest ms', max(x[2] for x in tot))
for x in bad[:5]: print('  ', x)
