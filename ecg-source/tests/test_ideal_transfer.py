"""DAC码→假定理想衰减/PGA码→冻结BIO_V2回放；绝不冒充真实模拟传递或端子校准。"""
from pathlib import Path
import collections,csv,ctypes as C,datetime,hashlib,json,subprocess
ROOT=Path(__file__).resolve().parent.parent
WT=ROOT.parent;BIO=WT/'review/biov2-current/HARDWARE/bio_v2.c'
stamp=datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
RUN=ROOT/'build'/('ideal-model-'+stamp);RUN.mkdir(parents=True)
result={'scope':'IDEAL_ASSUMED_TRANSFER_MODEL_ONLY','hardware_operations':[],
 'measured_VREF_or_attenuation':False,'resistor_values_approved_for_assembly':False,
 'assumptions':{'DAC_VREF_V':3.3,'DAC_divisor':4096,'attenuation':1/1001,'ADS_VREF_V':2.42,
                'ADS_gain':4,'ADC_sampling_sps':250,'no_ADS_digital_filter_or_loading_model':True},
 'checks':[]}
try:
    command=['C:/mingw64/bin/gcc.exe','-std=c99','-O2','-Wall','-Wextra','-Werror',
             '-ffp-contract=off','-shared',str(BIO),'-o',str(RUN/'bio.dll'),'-lm']
    p=subprocess.run(command,capture_output=True,timeout=60);result['compile_exit']=p.returncode
    (RUN/'compile.stdout.log').write_bytes(p.stdout);(RUN/'compile.stderr.log').write_bytes(p.stderr)
    if p.returncode:raise RuntimeError('理想传递模型Host编译失败')
    lib=C.CDLL(str(RUN/'bio.dll'));lib.BioV2_Init.argtypes=[C.c_uint32]
    lib.BioV2_Process.argtypes=[C.c_int32,C.c_int32,C.c_uint32,C.c_uint32,C.c_uint8]
    diag=(C.c_uint32*30).in_dll(lib,'g_bio_v2')
    codes=collections.defaultdict(list)
    with (WT/'artifacts/ecg-source/software-waveform.csv').open(encoding='utf-8') as f:
        for row in csv.DictReader(f):
            if row['mode']!='OFF':codes[row['mode']].append(int(row['DAC1_code']))
    for mode,target in [('BIAS',None),('sine',None),('ecg60',60),('ecg90',90)]:
        lib.BioV2_Init(1000);valid=[];rates=[];reasons=collections.Counter()
        for i in range(90*250):
            dac=codes[mode][(i*4)%len(codes[mode])]
            # 只是候选理想公式；RA/LA实物阻抗、共模/噪声/采样滤波必须另行测量。
            assumed_diff=(dac-2048)*3.3/4096/1001
            ecg=round(assumed_diff/(2.42/4)*(2**23))
            lib.BioV2_Process(ecg,8388607,1000+i*4,i+1,0)
            if i>=30*250:
                valid.append(bool(diag[14]))
                if diag[14]:rates.append(diag[12])
                reasons[str(diag[16])]+=1
        coverage=sum(valid)/len(valid)
        ok=(not any(valid)) if target is None else (coverage>=.8 and rates and all(abs(v-target)<=3 for v in rates))
        result['checks'].append({'mode':mode,'pass':bool(ok),'expected_HR':target,
           'steady_valid_fraction':coverage,'valid_HR_values':sorted(set(rates)),'reason_counts':dict(reasons),
           'resp_end_valid':diag[15],'resp_end_reason':diag[17]})
        if not ok:raise AssertionError(mode+'理想模型不符合预期，保留失败，不改算法阈值')
    result.update(status='PASS_IDEAL_MODEL',BIO_source_sha256=hashlib.sha256(BIO.read_bytes()).hexdigest())
except BaseException as error:
    result.update(status='FAIL_OR_INCOMPLETE',error=type(error).__name__+': '+str(error));raise
finally:
    (RUN/'receipt.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),'utf-8')
    (WT/'artifacts/ecg-source/ideal-transfer-summary.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),'utf-8')
print(json.dumps(result,ensure_ascii=True))
