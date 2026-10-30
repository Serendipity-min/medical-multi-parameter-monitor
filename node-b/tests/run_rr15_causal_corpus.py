"""受限EFS真实语料、固定合成正反例与独立留出；纯host C，不连接目标。"""
import argparse
from collections import Counter
import csv
import json
from pathlib import Path
import sys

import numpy as np

ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'node-b/tools'))
import b4_recovery as private
import b5_rr15_causal_replay as replay
from b5_rr15_causal_analysis import host_lib


def run_rows(path,rows,nominal=None,tick_offset=None):
    lib,d=host_lib(path);lib.BioV2_Init(int(rows[0][1]));rates=Counter();eligible=valid=rr=0
    for row in rows:
        seq,ms,h,r,flags=map(int,row[:5]);lib.BioV2_Process(h,r,ms,seq,flags)
        if tick_offset is not None:lib.BioV2_Tick((ms+tick_offset)&0xffffffff)
        if ((ms-int(rows[0][1]))&0xffffffff)<45000:continue
        eligible+=1;rr+=bool(d.rpm_valid)
        if d.hr_valid:valid+=1;rates[int(d.hr)]+=1
    correct=sum(n for rate,n in rates.items() if nominal is not None and abs(rate-nominal)<=2)
    return {'input_samples':len(rows),'eligible_after_45s':eligible,'hr_valid_samples':valid,
        'hr_valid_fraction':valid/eligible if eligible else None,'correct_rate_fraction':correct/eligible if nominal is not None and eligible else None,
        'hr_rates':dict(sorted(rates.items())),'RR_valid_samples':rr,'final_hr':int(d.hr),'final_hr_valid':int(d.hr_valid),
        'final_discontinuities':int(d.discontinuities),'final_sequence':int(d.last_sequence),'final_irq_ms':int(d.last_sample_ms),
        'final_raw_matches_input':(int(d.ecg_raw),int(d.resp_raw))==(int(rows[-1][2]),int(rows[-1][3])),
        'tick_sensitivity_offset_ms':tick_offset,'true_getter_schedule':'NOT_CAPTURED'}


def read_csv(entry):
    blob=private.read(entry['path'],False)
    if replay.digest(blob)!=entry['sha256']:raise ValueError('CORPUS_CSV_DRIFT')
    rows=[]
    for x in csv.DictReader(blob.decode().splitlines()):
        rows.append((int(x['source_seq']),int(x['device_ms']),int(x['ch2_raw']),int(x['ch1_raw']),
                     int(x['flags_raw']),int(x['irq_cycles']),int(x['status_raw'],0)))
    return rows,{'sha256':entry['sha256'],'frames':len(rows),'flags_nonzero':sum(bool(x[4]) for x in rows),
        'seq_gaps':sum(b[0]!=a[0]+1 for a,b in zip(rows,rows[1:])),
        'IRQ_ms_steps':dict(Counter((b[1]-a[1])&0xffffffff for a,b in zip(rows,rows[1:]))),
        'status_values':sorted({x[6] for x in rows})}


def synthetic(seconds,hr=None,amplitude=10000,mains=0,noise=0,seed=47,phase=.3,kind=None):
    n=seconds*250;t=np.arange(n)/250;rng=np.random.default_rng(seed)
    h=np.full(n,200000.,dtype=float)
    if hr is not None:
        period=60/hr;p=(t-phase+period/2)%period-period/2
        h+=amplitude*(np.exp(-.5*(p/.012)**2)+.18*np.exp(-.5*((p-.23)/.055)**2)+.07*np.exp(-.5*((p+.16)/.035)**2))
    h+=mains*np.sin(2*np.pi*50*t)+noise*rng.normal(size=n)
    if kind=='AM_50':h+=500*(1+.5*np.sin(2*np.pi*.25*t))*np.sin(2*np.pi*50*t)
    elif kind=='AM_50_colored_RESP':
        colored=np.convolve(rng.normal(size=n+2),np.ones(3)/3,mode='valid')
        h+=500*(1+.5*np.sin(2*np.pi*.25*t))*np.sin(2*np.pi*50*t)+100*colored+250*np.sin(2*np.pi*.25*t)
    elif kind and kind.startswith('sine_'):h+=500*np.sin(2*np.pi*float(kind[5:])*t)
    rows=np.zeros((n,7),dtype=np.int64);rows[:,0]=np.arange(1,n+1);rows[:,1]=1000+np.arange(n)*4
    rows[:,2]=np.rint(h).astype(np.int64);rows[:,3]=np.rint(640000+1200*np.sin(2*np.pi*.25*t)).astype(np.int64)
    rows[:,5]=(np.arange(n,dtype=np.int64)*672000)&0xffffffff;rows[:,6]=0xc00000
    return rows


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--inputs-private',type=Path,required=True)
    p.add_argument('--corpus-sha256',required=True);a=p.parse_args();inputs=json.loads(private.read(a.inputs_private,False))
    job=Path(inputs['job']);private.protected(job,False)
    decision=job/'development-decision-before-holdout.md'
    if not decision.is_file() or 'ALGORITHM_PATCH = NOT_IMPLEMENTED' not in decision.read_text():raise ValueError('HOLDOUT_DEVELOPMENT_DECISION_REQUIRED')
    corpus_blob=private.read(job/'corpus-index-private.json',False)
    if replay.digest(corpus_blob)!=a.corpus_sha256:raise ValueError('CORPUS_INDEX_DRIFT')
    corpus=json.loads(corpus_blob);out=job/'corpus-evaluation';out.mkdir(exist_ok=False);private.protected(out,False)
    libpath=job/'initial-baseline-replay-private-host-build/baseline/bio_v2_host.dll';results=[]
    for entry in corpus['datasets']:
        rows,seals=read_csv(entry);r=run_rows(libpath,rows,entry['nominal_bpm_from_dataset'])
        results.append({'id':entry['id'],'kind':'REAL_ECG','split':'HOLDOUT' if entry['id'].endswith('-02') else 'DEVELOPMENT',
            'input_split_label_before_evaluation':entry['split'],'evaluation_completed':True,
            'nominal_bpm':entry['nominal_bpm_from_dataset'],'seals':seals,'result':r})
    holdout=private.PRIVATE/'time-init-field-6cd64b90/owner-observed-RR15-R5-5bb61eef/joint';private.protected(holdout,False)
    rows,seals=replay.sealed_raw_frames(holdout,'0351f74c6c71feaab98374fdb340c7d3c3cbde4acacc63abdbdcd629984a5b97',
        '28dc9d6bdb007487f42f466998300bb0b5a2e5913b83984f353f70140e19c02e')
    results.append({'id':'R5_RR15_INDEPENDENT_HOLDOUT','kind':'REAL_RESP_CONFIG_NOT_PROVEN_QRS_ABSENT','split':'HOLDOUT',
        'seals':seals,'result':run_rows(libpath,rows)})
    synthetic_manifest=[]
    for split,seed,phase in [('DEVELOPMENT',47,.3),('HOLDOUT',9047,.47)]:
        for hr in (60,90,120):
            for amp,mains,noise in ((10000,0,0),(1000,300,20),(300,0,0),(300,300,50)):
                ident=f'{split}_QRS{hr}_amp{amp}_mains{mains}_noise{noise}'
                rows=synthetic(90,hr,amp,mains,noise,seed,phase);r=run_rows(libpath,rows,hr)
                results.append({'id':ident,'kind':'SYNTHETIC_KNOWN_QRS','split':split,'nominal_bpm':hr,'result':r})
                synthetic_manifest.append({'id':ident,'seed':seed,'phase_s':phase,'input_SHA256':replay.digest(rows.tobytes())})
        for kind in ('sine_1','sine_8','sine_25','sine_50','sine_100','AM_50','AM_50_colored_RESP','white_noise'):
            rows=synthetic(120,noise=100 if kind=='white_noise' else 0,seed=seed,kind=kind)
            ident=f'{split}_NON_QRS_{kind}';r=run_rows(libpath,rows)
            results.append({'id':ident,'kind':'SYNTHETIC_PROVEN_NON_QRS','split':split,'result':r})
            synthetic_manifest.append({'id':ident,'seed':seed,'input_SHA256':replay.digest(rows.tobytes())})
    spec=inputs['windows']['RR15'];rows,seals=replay.sealed_raw_frames(Path(spec['joint']),spec['blocks_sha256'],spec['index_sha256'])
    sensitivity={str(offset):run_rows(libpath,rows,tick_offset=offset) for offset in (0,1,4)}
    result={'status':'UNCHANGED_C_OFFLINE_CHARACTERIZATION_NOT_FIRMWARE_ACCEPTANCE','algorithm_sha256':inputs['source_sha256'],
        'library_sha256':replay.digest(libpath.read_bytes()),'pre_holdout_decision_sha256':replay.digest(decision.read_bytes()),
        'corpus_index_sha256':a.corpus_sha256,'results':results,'synthetic_inputs':synthetic_manifest,'tick_sensitivity':sensitivity,
        'algorithm_patch':'NOT_IMPLEMENTED','root_cause':'ROOT_CAUSE_UNRESOLVED','historical_formal_results':'UNCHANGED'}
    (out/'corpus-results-private.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({'operation':'UNCHANGED_C_CORPUS_COMPLETE','real_ECG_cases':sum(r['kind']=='REAL_ECG' for r in results),
        'real_ECG_results':[{k:r[k] for k in ('id','result')} for r in results if r['kind']=='REAL_ECG'],
        'nonQRS_false_positive_cases':[{k:r[k] for k in ('id','result')} for r in results if r['kind']=='SYNTHETIC_PROVEN_NON_QRS' and r['result']['hr_valid_samples']],
        'real_R5_holdout_result':next(r['result'] for r in results if r['id']=='R5_RR15_INDEPENDENT_HOLDOUT'),
        'synthetic_cases':len(synthetic_manifest)}))
    return 0


if __name__=='__main__':raise SystemExit(main())
