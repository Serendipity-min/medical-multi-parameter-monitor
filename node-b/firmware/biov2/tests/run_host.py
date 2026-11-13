"""独立算法普通Host验证：已知合成输入、失效恢复及原始历史回放，不连接硬件。"""
from pathlib import Path
import ctypes as C
import hashlib
import json
import math
import random
import os
import struct
import subprocess

root=Path(__file__).resolve().parent.parent
# 每次普通回归使用独立目录，不覆盖历史验收。
evidence=Path(os.environ['NODE_B_TEST_OUT'])/'algorithm'
evidence.mkdir(parents=True,exist_ok=False)
source=root/'实验固件/HARDWARE/bio_v2.c'
dll=evidence/'bio_v2_host.dll'
cmd=['C:/mingw64/bin/gcc.exe','-std=c99','-O2','-Wall','-Wextra','-Werror',
     '-ffp-contract=off','-shared',str(source),'-o',str(dll),'-lm']
compiled=subprocess.run(cmd,capture_output=True)
(evidence/'host_compile.stdout.log').write_bytes(compiled.stdout)
(evidence/'host_compile.stderr.log').write_bytes(compiled.stderr)
if compiled.returncode:
    raise SystemExit(compiled.returncode)
lib=C.CDLL(str(dll.resolve()))
lib.BioV2_Init.argtypes=[C.c_uint32]
lib.BioV2_Process.argtypes=[C.c_int32,C.c_int32,C.c_uint32,C.c_uint32,C.c_uint8]
lib.BioV2_Tick.argtypes=[C.c_uint32]
fields=['tag','abi_version','samples','last_sequence','last_sample_ms','segment','discontinuities','clipped_samples']
raw=['ecg_raw','resp_raw','ecg_filtered','resp_filtered']
more=['hr','rpm','hr_valid','rpm_valid','hr_reason','rpm_reason','hr_candidates','hr_accepted','resp_candidates',
      'resp_accepted','hr_last_cycle_ms','resp_last_cycle_ms','hr_fresh_intervals','resp_fresh_intervals']
flt=['ecg_rms_codes','resp_rms_codes','ecg_mains_fraction','resp_mains_fraction']
class Diag(C.Structure):
    _fields_=[(f,C.c_uint32) for f in fields]+[(f,C.c_int32) for f in raw]+[(f,C.c_uint32) for f in more]+[(f,C.c_float) for f in flt]
d=Diag.in_dll(lib,'g_bio_v2')
results=[]
def sample(t,hr=60,rpm=15,noise=0,mains=0):
    # 明确的工程合成夹具，Gaussian QRS/P/T仅作算法测试，不冒充人体真值。
    period=60/hr;phase=((t-.3+period/2)%period)-period/2
    ecg=200000+10000*math.exp(-.5*(phase/.012)**2)
    ecg+=1800*math.exp(-.5*((phase-.23)/.055)**2)+700*math.exp(-.5*((phase+.16)/.035)**2)
    resp=640000+1200*math.sin(2*math.pi*rpm/60*t)
    ecg+=mains*math.sin(2*math.pi*50*t)+noise*math.sin(2*math.pi*17.3*t)
    return int(round(ecg)),int(round(resp))
def run(name,seconds,feed,check,start=1000):
    lib.BioV2_Init(start);valid_h=valid_r=0
    for i in range(int(seconds*250)):
        t=i/250;h,r=feed(t)
        lib.BioV2_Process(h,r,(start+i*4)&0xffffffff,i+1,0)
        valid_h+=int(bool(d.hr_valid));valid_r+=int(bool(d.rpm_valid))
        if not all(math.isfinite(getattr(d,k)) for k in flt):
            raise AssertionError('非有限状态 '+name)
        if d.hr_valid and not 30<=d.hr<=220:raise AssertionError('心率越界')
        if d.rpm_valid and not 6<=d.rpm<=40:raise AssertionError('呼吸越界')
    passed=bool(check(d,valid_h,valid_r))
    result={'case':name,'pass':passed,'final_hr':d.hr,'final_hr_valid':d.hr_valid,'final_resp':d.rpm,
            'final_resp_valid':d.rpm_valid,'hr_valid_samples':valid_h,'resp_valid_samples':valid_r,
            'hr_reason':d.hr_reason,'resp_reason':d.rpm_reason,'diag':{k:getattr(d,k) for k in more+flt}}
    results.append(result);return result
for hr in [40,60,90,120,180]:
    run(f'qrs_{hr}',65,lambda t,hr=hr:sample(t,hr),lambda d,h,r,hr=hr:d.hr_valid and abs(d.hr-hr)<=2)
for rpm in [6,12,15,24,30,40]:
    run(f'breath_{rpm}',90,lambda t,rpm=rpm:sample(t,60,rpm),lambda d,h,r,rpm=rpm:d.rpm_valid and abs(d.rpm-rpm)<=1)
run('zero',40,lambda t:(0,0),lambda d,h,r:not h and not r)
run('constant_large_dc',40,lambda t:(200000,640000),lambda d,h,r:not h and not r)
for hz in [1,8,25,50,100]:
    run(f'non_qrs_sine_{hz}',45,lambda t,hz=hz:(int(200000+10000*math.sin(2*math.pi*hz*t)),640000),
        lambda d,h,r:not h and not r)
run('qrs_with_moderate_mains',65,lambda t:sample(t,60,15,mains=3000),lambda d,h,r:d.hr_valid and abs(d.hr-60)<=2)
rng=random.Random(20261013)
run('white_noise',90,lambda t:(int(200000+rng.gauss(0,2000)),int(640000+rng.gauss(0,2000))),
    lambda d,h,r:not h and not r)
run('u32_timestamp_wrap',65,lambda t:sample(t),lambda d,h,r:d.hr_valid and d.rpm_valid,start=0xfffff000)

# 已有效→连续直流保持无周期→过期→孤立起伏不恢复旧值→正常新周期恢复。
run('freshness_initial',70,lambda t:sample(t),lambda d,h,r:d.hr_valid and d.rpm_valid)
for i in range(17500,21500):lib.BioV2_Process(200000,640000,1000+i*4,i+1,0)
stale_invalid=(d.hr_valid==0 and d.rpm_valid==0 and d.hr_fresh_intervals==0 and d.resp_fresh_intervals==0)
for i in range(21500,23000):
    t=(i-21500)/250
    r=int(640000+1200*math.exp(-.5*((t-2)/.6)**2))
    lib.BioV2_Process(200000,r,1000+i*4,i+1,0)
no_revival=(d.hr_valid==0 and d.rpm_valid==0)
results.append({'case':'expire_then_isolated_peak_no_old_rate','pass':stale_invalid and no_revival})
for i in range(23000,40500):
    h,r=sample((i-23000)/250);lib.BioV2_Process(h,r,1000+i*4,i+1,0)
results.append({'case':'fresh_cycles_restore','pass':bool(d.hr_valid and d.rpm_valid)})
lib.BioV2_Process(200000,640000,1000+40500*4,40510,1)
results.append({'case':'sequence_gap_and_flags_clear_qualification','pass':not d.hr_valid and not d.rpm_valid and d.discontinuities==1})
lib.BioV2_Process(8388607,640000,1000+40501*4,40511,0)
results.append({'case':'clip_invalidates','pass':not d.hr_valid and not d.rpm_valid and d.clipped_samples==1})
lib.BioV2_Tick(1000+40501*4+200)
results.append({'case':'getter_without_new_input_invalid','pass':not d.hr_valid and not d.rpm_valid})

# 冻结原始历史样本回放只作表征：没有真值，不以输出数值正常作为PASS门槛。
base=root.parent
# 历史原始样本不公开；本入口固定只执行合成夹具，不误用本机原件。
historic=evidence/'NOT_INCLUDED_historic_frames.bin'
if historic.exists():
    blob=historic.read_bytes();lib.BioV2_Init(1351);h_count=r_count=0
    lines=['seq,ms,hr,hr_valid,rpm,rpm_valid,hr_reason,rpm_reason,ecg_wave,resp_wave,ecg_mains,resp_mains']
    for pos in range(0,len(blob),24):
        f=blob[pos:pos+24];seq,cyc,ms=struct.unpack_from('<III',f,12)
        h=int.from_bytes(f[6:9],'big',signed=True);r=int.from_bytes(f[3:6],'big',signed=True)
        lib.BioV2_Process(h,r,ms,seq,f[9]);h_count+=d.hr_valid;r_count+=d.rpm_valid
        lines.append(f'{seq},{ms},{d.hr},{d.hr_valid},{d.rpm},{d.rpm_valid},{d.hr_reason},{d.rpm_reason},{d.ecg_filtered},{d.resp_filtered},{d.ecg_mains_fraction:.9g},{d.resp_mains_fraction:.9g}')
    (evidence/'historic_v2_replay.csv').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    history={'raw_sha256':hashlib.sha256(blob).hexdigest(),'samples':len(blob)//24,
             'hr_valid_samples':h_count,'resp_valid_samples':r_count,'last_hr':d.hr,'last_rpm':d.rpm,
             'reason_hr':d.hr_reason,'reason_rpm':d.rpm_reason,'accuracy':'NOT_EVALUATED'}
else:history=None
receipt={'compile_exit':compiled.returncode,'cases':results,'pass':sum(r['pass'] for r in results),
         'total':len(results),'historic':history,'diag_size':C.sizeof(Diag),
         'algorithm_sha256':hashlib.sha256(source.read_bytes()).hexdigest()}
(evidence/'host_receipt.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'pass':receipt['pass'],'total':receipt['total'],
                  'failed':[r for r in results if not r['pass']],'historic':history},ensure_ascii=True,indent=2))
raise SystemExit(0 if receipt['pass']==receipt['total'] else 1)
