"""普通Host：先复现旧共同失效，再验证单路保护、恢复和共同链路失效；不连接硬件。"""
from pathlib import Path
import ctypes as C,csv,hashlib,json,math,struct,subprocess,os
ROOT=Path(__file__).resolve().parent.parent
# 以随包冻结的旧C源复现共同失效，不引用现场绝对路径。
OLD=ROOT.parents[1]/'reference/biov2-before-isolation/HARDWARE/bio_v2.c'
OUT=Path(os.environ['NODE_B_TEST_OUT'])/'channel-isolation';OUT.mkdir(parents=True,exist_ok=False)
U=['tag','abi_version','samples','last_sequence','last_sample_ms','segment','discontinuities','clipped_samples']
I=['ecg_raw','resp_raw','ecg_filtered','resp_filtered']
MORE=['hr','rpm','hr_valid','rpm_valid','hr_reason','rpm_reason','hr_candidates','hr_accepted','resp_candidates','resp_accepted','hr_last_cycle_ms','resp_last_cycle_ms','hr_fresh_intervals','resp_fresh_intervals']
F=['ecg_rms_codes','resp_rms_codes','ecg_mains_fraction','resp_mains_fraction']
class Diag(C.Structure):_fields_=[(x,C.c_uint32) for x in U]+[(x,C.c_int32) for x in I]+[(x,C.c_uint32) for x in MORE]+[(x,C.c_float) for x in F]
def compile_lib(source,name):
    dll=OUT/(name+'.dll');cmd=['C:/mingw64/bin/gcc.exe','-std=c99','-O2','-Wall','-Wextra','-Werror','-ffp-contract=off','-shared',str(source),'-o',str(dll),'-lm']
    p=subprocess.run(cmd,capture_output=True);(OUT/(name+'.compile.log')).write_bytes(p.stdout+p.stderr)
    assert p.returncode==0,p.stderr
    lib=C.CDLL(str(dll));lib.BioV2_Init.argtypes=[C.c_uint32];lib.BioV2_Process.argtypes=[C.c_int32,C.c_int32,C.c_uint32,C.c_uint32,C.c_uint8];lib.BioV2_Tick.argtypes=[C.c_uint32]
    for f in ['BioV2_GetHeart','BioV2_GetResp']:getattr(lib,f).argtypes=[C.POINTER(C.c_uint16),C.c_uint32]
    return lib,Diag.in_dll(lib,'g_bio_v2')
oldsrc=OLD;newsrc=ROOT/'实验固件/HARDWARE/bio_v2.c'
old,od=compile_lib(oldsrc,'before');new,nd=compile_lib(newsrc,'after')
def value(t):
    # 已知工程夹具：60bpm QRS/P/T与15次/分正弦呼吸，仅供算法普通测试。
    phase=((t-.3+.5)%1)-.5
    h=200000+10000*math.exp(-.5*(phase/.012)**2)+1800*math.exp(-.5*((phase-.23)/.055)**2)+700*math.exp(-.5*((phase+.16)/.035)**2)
    return int(round(h)),int(round(640000+1200*math.sin(2*math.pi*.25*t)))
def snap(d):return {k:getattr(d,k) for k in U+I+MORE+F}
def feed(lib,d,rows,start=1000):
    lib.BioV2_Init(start);states=[]
    for i,(h,r) in enumerate(rows):
        now=(start+i*4)&0xFFFFFFFF;lib.BioV2_Process(h,r,now,i+1,0)
        # 覆盖UI/CAN常用getter路径，另一通道的发布不能覆盖当前通道削顶状态。
        if i%50==0:
            a=C.c_uint16();b=C.c_uint16();lib.BioV2_GetHeart(C.byref(a),now);lib.BioV2_GetResp(C.byref(b),now)
        states.append(snap(d))
    return states
heart_fields=['ecg_raw','ecg_filtered','ecg_rms_codes','ecg_mains_fraction','hr','hr_valid','hr_reason','hr_candidates','hr_accepted','hr_last_cycle_ms','hr_fresh_intervals']
resp_fields=['resp_raw','resp_filtered','resp_rms_codes','resp_mains_fraction','rpm','rpm_valid','rpm_reason','resp_candidates','resp_accepted','resp_last_cycle_ms','resp_fresh_intervals']
def same(a,b,fields):return all(all(x[k]==y[k] for k in fields) for x,y in zip(a,b))
tests=[]
def check(name,ok,details=None):
    tests.append({'case':name,'pass':bool(ok),'details':details})
    if not ok:raise AssertionError(name)
rows=[value(i/250) for i in range(17500)]
reference=feed(new,nd,rows)
check('no_clip_both_channels_identical_to_old',same(feed(old,od,rows),reference,heart_fields+resp_fields))
old_clipped=feed(old,od,[(h,8388607) for h,r in rows])
check('old_failure_reproduced',not any(s['hr_valid'] for s in old_clipped) and reference[-1]['hr_valid'],
      {'old_valid_hr_samples':sum(s['hr_valid'] for s in old_clipped),'reference_final_hr':reference[-1]['hr'],'old_clipped_frames':old_clipped[-1]['clipped_samples']})
for rail in [8388607,-8388608]:
    a=feed(new,nd,[(h,rail) for h,r in rows])
    check('resp_clip_ECG_identical_'+str(rail),same(reference,a,heart_fields) and all(not s['rpm_valid'] and s['rpm_reason']&32 for s in a),
          {'final_hr':a[-1]['hr'],'accepted_frames':a[-1]['samples'],'clipped_frames':a[-1]['clipped_samples']})
    b=feed(new,nd,[(rail,r) for h,r in rows])
    check('ECG_clip_resp_identical_'+str(rail),same(reference,b,resp_fields) and all(not s['hr_valid'] and s['hr_reason']&32 for s in b),{'final_rpm':b[-1]['rpm']})
both=feed(new,nd,[(8388607,-8388608)]*1000)
check('both_clip_protection_and_frame_evidence',all(not s['hr_valid'] and not s['rpm_valid'] and s['hr_reason']&32 and s['rpm_reason']&32 for s in both)
      and both[-1]['samples']==both[-1]['clipped_samples']==both[-1]['last_sequence']==1000 and both[-1]['ecg_raw']==8388607 and both[-1]['resp_raw']==-8388608)
for fault,fields in [('resp',heart_fields),('ecg',resp_fields)]:
    trajectory=[value(i/250) for i in range(40000)]
    normal=feed(new,nd,trajectory)
    # 只在指定时间段注入单路故障；其它时段保持相同输入，才能严格比较健康通道。
    damaged=[((h,8388607) if fault=='resp' else (-8388608,r)) if 17500<=i<23750 else (h,r) for i,(h,r) in enumerate(trajectory)]
    recovered=feed(new,nd,damaged)
    check(fault+'_transition_healthy_channel_unchanged',same(normal,recovered,fields))
    valid='rpm_valid' if fault=='resp' else 'hr_valid';reason='rpm_reason' if fault=='resp' else 'hr_reason';fresh='resp_fresh_intervals' if fault=='resp' else 'hr_fresh_intervals'
    check(fault+'_fault_clears_only_own_history',not recovered[17500][valid] and recovered[17500][reason]&32 and recovered[17500][fresh]==0)
    warmup=2500 if fault=='resp' else 1250
    check(fault+'_recovery_requires_new_warmup',all(not s[valid] for s in recovered[23750:23750+warmup]))
    check(fault+'_fresh_cycles_restore',recovered[-1][valid] and abs(recovered[-1]['rpm' if fault=='resp' else 'hr']-(15 if fault=='resp' else 60))<=1)
for a in [8304721,-8304721]:
    s=feed(new,nd,[(a,640000)])[-1];check('ECG_threshold_inclusive_'+str(a),not s['hr_valid'] and s['hr_reason']&32)
    s=feed(new,nd,[(200000,a)])[-1];check('resp_threshold_inclusive_'+str(a),not s['rpm_valid'] and s['rpm_reason']&32)
for a in [8304720,-8304720]:
    s=feed(new,nd,[(a,a)])[-1];check('just_below_threshold_not_clipped_'+str(a),s['clipped_samples']==0 and not s['hr_reason']&32 and not s['rpm_reason']&32)
for kind in ['sequence','flags','time']:
    feed(new,nd,[(h,8388607) for h,r in rows]);seq=17501+(7 if kind=='sequence' else 0);now=1000+17500*4+(200 if kind=='time' else 0)
    h,r=value(70);new.BioV2_Process(h,8388607,now,seq,1 if kind=='flags' else 0)
    check('shared_'+kind+'_still_invalidates',not nd.hr_valid and not nd.rpm_valid and nd.discontinuities==1 and nd.hr_fresh_intervals==0 and nd.resp_fresh_intervals==0)
feed(new,nd,[(h,8388607) for h,r in rows]);new.BioV2_Tick(1000+17499*4+200)
check('input_timeout_still_invalidates_both',not nd.hr_valid and not nd.rpm_valid and nd.rpm_reason&32 and nd.hr_reason&16)
wrapped=feed(new,nd,[(h,8388607) for h,r in rows],0xFFFFFF00)
check('independent_warmup_u32_wrap',wrapped[-1]['hr_valid'] and wrapped[-1]['hr']==60 and not wrapped[-1]['rpm_valid'])
flat=feed(new,nd,[(200000,8388607)]*10000)
check('healthy_DC_not_falsely_valid_with_other_clip',not any(s['hr_valid'] for s in flat))
check('ABI_size_preserved',C.sizeof(Diag)==120)

# 公开回归不含历史开放输入原码：该项NOT_RUN，不以合成数据冒充真实回放。
receipt={'hardware_access':False,'scope':'ORDINARY_HOST_SYNTHETIC_ONLY',
         'pass':sum(t['pass'] for t in tests),'total':len(tests),'cases':tests,
         'before_source_sha256':hashlib.sha256(oldsrc.read_bytes()).hexdigest(),
         'after_source_sha256':hashlib.sha256(newsrc.read_bytes()).hexdigest(),
         'historical_real_input_replay':'NOT_RUN_PRIVATE_RAW_NOT_INCLUDED'}
(OUT/'receipt.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'pass':receipt['pass'],'total':receipt['total'],'historic':'NOT_RUN'},ensure_ascii=True))
raise SystemExit(0 if receipt['pass']==receipt['total'] else 1)
