"""受限EFS上的同算法峰证据分析；无设备/网络入口，不改被测C。"""
from collections import Counter
import ctypes as C
import json
from pathlib import Path
import shutil
import struct
import sys

import numpy as np
import b4_recovery as private
import b5_rr15_causal_replay as replay
import b5_g3_review as frozen

TRACE_C = '''#include "bio_v2.c"
void Causal_HeartState(uint32_t *u, float *f) {
 u[0]=heart.in_peak;u[1]=heart.above_ms;u[2]=heart.peak_ms;
 u[3]=heart.valid_start_ms;u[4]=heart.periods.anchored;
 u[5]=heart.periods.anchor;u[6]=heart.periods.last_good;
 u[7]=heart.periods.count;u[8]=heart.periods.index;
 u[9]=heart.periods.reason;u[10]=heart.periods.candidate_rate;
 for(uint32_t i=0;i<5;i++)u[11+i]=heart.periods.intervals[i];
 f[0]=heart.raw_power;f[1]=heart.line_power;f[2]=heart.clean_power;
 f[3]=heart.band_power;f[4]=heart.peak;f[5]=heart.gate;
}
'''


def host_lib(path):
    lib=C.CDLL(str(path));lib.BioV2_Init.argtypes=[C.c_uint32];lib.BioV2_Init.restype=None
    lib.BioV2_Process.argtypes=[C.c_int32,C.c_int32,C.c_uint32,C.c_uint32,C.c_uint8];lib.BioV2_Process.restype=None
    lib.BioV2_Tick.argtypes=[C.c_uint32];lib.BioV2_Tick.restype=None
    lib.BioV2_ReplayAbi.argtypes=[C.c_uint32];lib.BioV2_ReplayAbi.restype=C.c_uint32
    actual=[lib.BioV2_ReplayAbi(i) for i in range(len(replay.FIELDS)+1)]
    expected=[C.sizeof(replay.Diag)]+[getattr(replay.Diag,k).offset for k,_ in replay.FIELDS]
    if actual!=expected:raise ValueError('CAUSAL_C_ABI_MISMATCH')
    return lib,replay.Diag.in_dll(lib,'g_bio_v2')


def trace_window(rows, baseline_path, trace_path, diagnostics, t0, output):
    baseline,bd=host_lib(baseline_path);traced,d=host_lib(trace_path)
    traced.Causal_HeartState.argtypes=[C.POINTER(C.c_uint32),C.POINTER(C.c_float)]
    traced.Causal_HeartState.restype=None
    baseline.BioV2_Init(rows[0][1]);traced.BioV2_Init(rows[0][1])
    wanted={x['bio']['last_sequence']:x for x in diagnostics};candidates=[];matches=[]
    u=(C.c_uint32*16)();f=(C.c_float*6)();previous_candidates=0;previous_accepted=0
    saved=np.zeros((len(rows),9),dtype=np.float64)
    for i,row in enumerate(rows):
        seq,ms,ecg,resp,flags=row[:5]
        baseline.BioV2_Process(ecg,resp,ms,seq,flags);traced.BioV2_Process(ecg,resp,ms,seq,flags)
        if bytes(bd)!=bytes(d):raise ValueError('CAUSAL_OBSERVER_ALTERED_DIAGNOSTIC')
        traced.Causal_HeartState(u,f)
        saved[i]=[seq,ms,ecg,resp,d.ecg_filtered,d.hr,d.hr_valid,f[0],f[1]]
        if d.hr_candidates!=previous_candidates:
            candidates.append({'seq':seq,'end_ms':ms,'peak_ms':u[2],'above_ms':u[1],
                'width_ms':(ms-u[1])&0xffffffff,'peak_codes':f[4],'gate_codes':f[5],
                'accepted_counter_increment':int(d.hr_accepted)-previous_accepted,
                'anchor_ms':u[5],'last_good_ms':u[6],'intervals_ms':list(u[11:16]),
                'fresh_intervals':u[7],'reason':u[9],'rate':u[10],
                'raw_power':f[0],'line_power':f[1],'band_power':f[3]})
        previous_candidates=int(d.hr_candidates);previous_accepted=int(d.hr_accepted)
        if seq in wanted:
            target=wanted[seq];bio=target['bio'];fields=('hr','hr_valid','hr_reason','rpm','rpm_valid','hr_last_cycle_ms','hr_fresh_intervals')
            differences={k:{'host':getattr(d,k),'board':bio[k]} for k in fields if getattr(d,k)!=bio[k]}
            matches.append({'seq':seq,'evaluation':t0['monotonic']+45<=target['host_monotonic']<t0['monotonic']+345,
                'board_hr':bio['hr'],'board_hr_valid':bio['hr_valid'],'host_hr':d.hr,'host_hr_valid':d.hr_valid,
                'differences':differences,'IRQ_ms_matches':ms==bio['last_sample_ms'],
                'RMS_error_codes':float(d.ecg_rms_codes)-bio['ecg_rms_codes'],
                'mains_fraction_error':float(d.ecg_mains_fraction)-bio['ecg_mains_fraction']})
    np.savez_compressed(output/'trace-private.npz',values=saved,
        columns=np.array(['seq','irq_ms','ecg_raw','resp_raw','filtered_UI_quantized','hr','hr_valid','raw_power','line_power']))
    (output/'candidate-peaks-private.json').write_text(json.dumps(candidates,indent=2)+'\n')
    (output/'diagnostic-comparison-private.json').write_text(json.dumps(matches,indent=2)+'\n')
    selected=[x for x in matches if x['evaluation']]
    return saved,candidates,{'all_diagnostics_matched_by_seq':len(matches),'evaluation_diagnostics':len(selected),
        'evaluation_HR_pair_mismatches':sum((x['host_hr'],x['host_hr_valid'])!=(x['board_hr'],x['board_hr_valid']) for x in selected),
        'evaluation_all_primary_field_mismatches':sum(bool(x['differences']) for x in selected),
        'evaluation_IRQ_ms_mismatches':sum(not x['IRQ_ms_matches'] for x in selected),
        'evaluation_max_RMS_error_codes':max(abs(x['RMS_error_codes']) for x in selected),
        'evaluation_max_mains_fraction_error':max(abs(x['mains_fraction_error']) for x in selected),
        'observer_vs_original_all_120_bytes':'EXACT_EVERY_INPUT_FRAME','actual_getter_schedule':'NOT_CAPTURED_NOT_INVENTED',
        'candidate_peaks':len(candidates)}


def spectral_features(rows,center_ms,seconds=8):
    data=np.asarray([r[:4] for r in rows if center_ms-seconds*500<=r[1]<center_ms+seconds*500],dtype=float)
    t=(data[:,1]-data[0,1])/1000;x=data[:,2];r=data[:,3]
    x=x-x.mean();r=r-r.mean()
    design=np.column_stack([np.ones(len(t)),t-t.mean()]+[v for hz in (50,100) for v in (np.sin(2*np.pi*hz*t),np.cos(2*np.pi*hz*t))])
    fitted=design@np.linalg.lstsq(design,x,rcond=None)[0];residual=x-fitted
    raw_power=float(np.mean(x*x));residual_power=float(np.mean(residual*residual))
    frequencies=np.fft.rfftfreq(len(x),.004);spectrum=abs(np.fft.rfft(x))**2
    low=np.column_stack([np.ones(len(t))]+[v for hz in (.25,.5,.75,1) for v in (np.sin(2*np.pi*hz*t),np.cos(2*np.pi*hz*t))])
    resp_fit=low@np.linalg.lstsq(low,residual,rcond=None)[0]
    corr=float(np.corrcoef(residual,r)[0,1]) if r.std() else None
    return {'samples':len(x),'raw_rms_codes':raw_power**.5,'residual_50_100_rms_codes':residual_power**.5,
        'joint_50_100_LS_removed_fraction':1-residual_power/raw_power,
        'residual_RESP_linear_correlation':corr,'residual_RESP_harmonics_explained_fraction':float(np.mean(resp_fit**2))/residual_power,
        'raw_peak_abs_over_RMS':float(abs(x).max())/raw_power**.5,
        'peak_nominal_frequency_hz':float(frequencies[np.argmax(spectrum[1:])+1]),
        'limit':'LS uses actual IRQ ms; FFT nominal frequency is descriptive; correlation is not physical causation'},data,residual


def continuity(window,rows):
    raw,can,clocks,receipt=frozen.reconstruct(window)
    if set(raw)!={r[0] for r in rows}:raise ValueError('CAUSAL_RAW_RECONSTRUCTION_DISAGREEMENT')
    overlap=[(s,struct.unpack('<iiIIBB2x',b)) for s,b in sorted(can.items()) if s in raw]
    due=[s for s,b in overlap if b[4]]
    receipt.update(raw_seq_gaps=sum(b[0]!=a[0]+1 for a,b in zip(rows,rows[1:])),
        RESP_due_records=len(due),RESP_due_seq_gaps=sum(b!=a+5 for a,b in zip(due,due[1:])),
        CAN_flags_nonzero=sum(bool(b[5]) for s,b in overlap),
        IRQ_ms_mapping_mismatches=sum(struct.unpack_from('<I',raw[s],20)[0]!=b[2] for s,b in overlap),
        due_bit_or_modulo_mismatches=sum(b[4]!=int(s%5==0) for s,b in overlap))
    return receipt


def render_existing(inputs):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    work=Path(inputs['job'])/'causal-analysis';private.protected(work,False)
    result=json.loads(private.read(work/'causal-evidence-private.json',False));manifest=[]
    rendered=work/'waveforms-reviewed';rendered.mkdir(exist_ok=False);private.protected(rendered,False)
    for name,spec in inputs['windows'].items():
        destination=rendered/name;destination.mkdir();private.protected(destination,False)
        rows,_=replay.sealed_raw_frames(Path(spec['joint']),spec['blocks_sha256'],spec['index_sha256'])
        trace=np.load(work/name/'trace-private.npz')['values']
        if not np.array_equal(trace[:,:4],np.asarray([r[:4] for r in rows])):raise ValueError('PLOT_RAW_TRACE_DRIFT')
        peaks=json.loads(private.read(work/name/'candidate-peaks-private.json',False))
        centers=[e['first_last_good_timestamp_ms'] for e in result['windows'][name]['events']]
        if not centers:
            accepted=[c for c in peaks if c['accepted_counter_increment'] and c['end_ms']>rows[0][1]+60000]
            centers=[accepted[len(accepted)//2]['peak_ms']]
        for i,center in enumerate(centers,1):
            chosen=trace[(trace[:,1]>=center-8000)&(trace[:,1]<center+4000)];t=(chosen[:,1]-center)/1000
            fig,axes=plt.subplots(3,1,figsize=(10,7),sharex=True,layout='constrained')
            axes[0].plot(t,chosen[:,2]-np.median(chosen[:,2]),lw=.6,color='#214d7a')
            axes[0].set_ylabel('CH2 raw\nADC codes, centered')
            axes[1].plot(t,chosen[:,4],lw=.8,color='#214d7a');axes[1].set_ylabel('Original C ECG\nUI integer units')
            axes[2].plot(t,chosen[:,3]-np.median(chosen[:,3]),lw=.8,color='#35813e');axes[2].set_ylabel('CH1 RESP\nADC codes, centered')
            for c in peaks:
                offset=(c['peak_ms']-center)/1000
                if -8<=offset<4 and c['accepted_counter_increment']:
                    axes[1].axvline(offset,color='#a63232',lw=.7,alpha=.7)
            for ax in axes:ax.grid(alpha=.18);ax.axvline(0,color='black',lw=.6,ls='--')
            axes[2].set_xlabel('Original IRQ time relative to accepted peak (s)')
            fig.suptitle(f'{name} event {i}: raw source and unmodified C output\n'
                         'Red markers: accepted candidates; not independent QRS labels',fontsize=10)
            for extension in ('png','pdf'):
                target=destination/f'waveform-event-{i:02d}-private.{extension}'
                fig.savefig(target,dpi=160);manifest.append({'file':target.name,'dataset':name,'sha256':replay.digest(target.read_bytes()),'bytes':target.stat().st_size})
            plt.close(fig)
    (rendered/'waveform-artifacts-private.json').write_text(json.dumps({'artifacts':manifest,'raw_data_not_exported_to_Git':True,
        'rendering_source_sha256':replay.digest(Path(__file__).read_bytes()),
        'interpretation':'Engineering waveform evidence; candidate markers are not independent QRS labels'},indent=2)+'\n')
    print(json.dumps({'waveform_artifacts':len(manifest),'storage':'EFS_ONLY','raw_source_rechecked':True}))
    return 0


def main():
    import argparse
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--inputs-private',type=Path,required=True)
    p.add_argument('--render-existing',action='store_true');a=p.parse_args()
    inputs=json.loads(private.read(a.inputs_private,False));job=Path(inputs['job']);private.protected(job,False)
    if a.render_existing:return render_existing(inputs)
    work=job/'causal-analysis';work.mkdir(exist_ok=False);private.protected(work,False)
    stage=work/'host';stage.mkdir();private.protected(stage,False)
    source=Path(inputs['source']);header=source.with_suffix('.h')
    if replay.digest(source.read_bytes())!=inputs['source_sha256'] or replay.digest(header.read_bytes())!=inputs['header_sha256']:raise ValueError('CAUSAL_SOURCE_DRIFT')
    shutil.copyfile(source,stage/'bio_v2.c');shutil.copyfile(header,stage/'bio_v2.h')
    trace_source=stage/'trace_host.c';trace_source.write_text(TRACE_C,encoding='utf-8')
    provenance=replay.compile_host(trace_source,stage/'trace_host.dll','C:/mingw64/bin/gcc.exe')
    baseline=job/'initial-baseline-replay-private-host-build/baseline/bio_v2_host.dll'
    results={};all_data={};all_candidates={}
    for name,spec in inputs['windows'].items():
        window=Path(spec['joint']);private.protected(window,False)
        rows,seals=replay.sealed_raw_frames(window,spec['blocks_sha256'],spec['index_sha256'])
        diag_blob=private.read(window/'B/diagnostics-private.jsonl',False)
        if replay.digest(diag_blob)!=spec['diagnostics_sha256']:raise ValueError('CAUSAL_DIAGNOSTIC_DRIFT')
        diagnostics=[json.loads(x)['data'] for x in diag_blob.decode().splitlines()]
        t0=json.loads(private.read(window/'T0.json',False));out=work/name;out.mkdir();private.protected(out,False)
        trace,peaks,agreement=trace_window(rows,baseline,stage/'trace_host.dll',diagnostics,t0,out)
        chosen=[d for d in diagnostics if t0['monotonic']+45<=d['host_monotonic']<t0['monotonic']+345]
        groups=[]
        if name=='RR15':
            for d in chosen:
                if not d['bio']['hr_valid']:continue
                if not groups or d['host_monotonic']-groups[-1][-1]['host_monotonic']>1.1:groups.append([])
                groups[-1].append(d)
        events=[]
        for group in groups:
            peak=group[0]['bio']['hr_last_cycle_ms'];features,data,residual=spectral_features(rows,peak)
            candidates=[c for c in peaks if peak-10000<=c['end_ms']<=peak+5000]
            event={'board_diagnostics':len(group),'board_HR_values':sorted({d['bio']['hr'] for d in group}),
                'first_last_good_timestamp_ms':peak,'last_last_good_timestamp_ms':group[-1]['bio']['hr_last_cycle_ms'],
                'features':features,'candidate_evidence':candidates}
            events.append(event)
        results[name]={'seals':seals,'agreement':agreement,'continuity':continuity(window,rows),'events':events}
        all_data[name]=rows;all_candidates[name]=peaks
    result={'status':'CAUSAL_EVIDENCE_NOT_A_ROOT_CAUSE_VERDICT','source_sha256':inputs['source_sha256'],
        'header_sha256':inputs['header_sha256'],'trace_host_provenance':provenance,'windows':results}
    (work/'causal-evidence-private.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({name:{'agreement':v['agreement'],'continuity':v['continuity'],'events':len(v['events'])} for name,v in results.items()}))
    return 0


if __name__=='__main__':raise SystemExit(main())
