"""纯离线原码表征和冻结BIO_V2 C源回放；不打开探针，不冒称逐拍真值。"""
import argparse
import csv
import ctypes as C
import json
from pathlib import Path
import struct
import subprocess
import sys
import numpy as np
from readback_b import PRIVATE,require,sha,write_json

ROOT=Path(__file__).resolve().parents[2]
SOURCE=ROOT/'node-b/firmware/biov2/实验固件/HARDWARE/bio_v2.c'
SOURCE_SHA='3adca55cb1eb1fa3ed8e4148f837287d0454bcc2c08ae77a8f73deb1dac156a7'


def describe(values):
    x=np.asarray(values,dtype=float);y=x-np.mean(x);power=np.abs(np.fft.rfft(y*np.hanning(len(y))))**2
    hz=np.fft.rfftfreq(len(y),1/250);den=float(power.sum())
    return {'min_codes':int(x.min()),'max_codes':int(x.max()),'median_codes':float(np.median(x)),
            'peak_to_peak_codes':int(np.ptp(x)),'near_rail_fraction':float(np.mean(np.abs(x)>=8220835)),
            'rms_after_mean_removal_codes':float(np.sqrt(np.mean(y*y))),
            'power_fraction_24_26hz':float(power[(hz>=24)&(hz<=26)].sum()/den) if den else 0.,
            'power_fraction_49_51hz':float(power[(hz>=49)&(hz<=51)].sum()/den) if den else 0.}


def formal_evaluate(rows,live,replay,reference):
    """冻结工程判据：首个实板诊断时刻后30秒预热，再评价完整60秒，尾部2秒留裕量。"""
    require(reference in (60,90,120),'FORMAL_REFERENCE')
    anchor=live[0]['last_sample_ms']
    offset=lambda ms:(ms-anchor)&0xffffffff
    steady=[r for r in rows if 30000<=offset(r['device_ms'])<90000]
    diagnostics=[r for r in live if 30000<=offset(r['last_sample_ms'])<90000]
    derived=[r for r in replay if 30000<=offset(r['device_ms'])<90000]
    failures=[]
    if not steady or offset(steady[0]['device_ms'])>30004 or offset(steady[-1]['device_ms'])<89996:
        failures.append('LESS_THAN_COMPLETE_60S_RAW')
    if steady:
        if any(b['source_seq']!=a['source_seq']+1 for a,b in zip(steady,steady[1:])):failures.append('STEADY_SEQUENCE_GAP')
        if any(not 1<=(b['device_ms']-a['device_ms'])&0xffffffff<=8 for a,b in zip(steady,steady[1:])):failures.append('STEADY_TIME_GAP')
        if any(r['flags_raw'] for r in steady):failures.append('STEADY_SOURCE_FLAGS')
        if any(abs(r['ch2_raw'])>=8220835 for r in steady):failures.append('ECG_NEAR_RAIL')
    if len(diagnostics)<60 or (diagnostics and (offset(diagnostics[0]['last_sample_ms'])>31000 or offset(diagnostics[-1]['last_sample_ms'])<89000)):
        failures.append('INSUFFICIENT_LIVE_DIAG_COVERAGE')
    if any(not r['hr_valid'] or abs(r['hr']-reference)>2 for r in diagnostics):failures.append('LIVE_HR_NOT_WITHIN_2_BPM')
    if not derived or any(not r['hr_valid'] or abs(r['hr']-reference)>2 for r in derived):failures.append('REPLAY_HR_NOT_WITHIN_2_BPM')
    for key in ('init_errors','spi_errors','bad_status','queue_overflow'):
        if any(r['adc'][key] for r in live):failures.append('ADC_'+key.upper())
    host_span=(live[-1]['host_start_s']+live[-1]['host_end_s']-live[0]['host_start_s']-live[0]['host_end_s'])/2
    sps=(live[-1]['adc']['captured']-live[0]['adc']['captured'])/host_span
    if not 240<=sps<=260:failures.append('HOST_OBSERVED_SPS')
    return {'status':'ENGINEERING_RATE_WINDOW_PASS' if not failures else 'ENGINEERING_RATE_WINDOW_FAIL',
            'failures':failures,'nominal_reference_bpm':reference,'tolerance_bpm':2,
            'raw_steady_frames':len(steady),'live_steady_observations':len(diagnostics),
            'live_steady_hr_values':sorted({r['hr'] for r in diagnostics}),
            'replay_steady_hr_values':sorted({r['hr'] for r in derived}),
            'observed_host_sps':sps,'warmup_ms':30000,'analysis_interval_ms':[30000,90000],
            'anchor_device_ms':anchor,'scope':'Nominal simulator rate agreement; no clinical accuracy or per-beat sensitivity'}


def analyze(folder,source_record,out,formal=False):
    receipt=json.loads((folder/'receipt-private.json').read_text('utf-8'))
    require(receipt['status']=='CAPTURE_FILES_SAVED' and receipt['tail_halt_confirmed']
            and receipt['resume_confirmed'],'CAPTURE_NOT_CONFIRMED')
    require(sha(source_record)==receipt['source_record_sha256'],'SOURCE_RECORD_DRIFT')
    require(sha(SOURCE)==SOURCE_SHA,'BIO_SOURCE_DRIFT')
    with (folder/'stable-raw-private.csv').open(encoding='utf-8',newline='') as f:
        rows=[{k:int(r[k]) for k in ('source_seq','device_ms','irq_cycles','status_raw','flags_raw','ch1_raw','ch2_raw')} for r in csv.DictReader(f)]
    require(len(rows)>1,'INSUFFICIENT_FRAMES')
    out.mkdir(exist_ok=False)
    dll=out/'bio_v2_replay.dll'
    command=['C:/mingw64/bin/gcc.exe','-std=c99','-O2','-Wall','-Wextra','-Werror','-ffp-contract=off',
             '-shared',str(SOURCE),'-o',str(dll),'-lm']
    compiled=subprocess.run(command,capture_output=True,timeout=60)
    (out/'compile.stdout.log').write_bytes(compiled.stdout);(out/'compile.stderr.log').write_bytes(compiled.stderr)
    require(compiled.returncode==0,'REPLAY_COMPILE_FAILED')
    lib=C.CDLL(str(dll.resolve()))
    lib.BioV2_Init.argtypes=[C.c_uint32]
    lib.BioV2_Process.argtypes=[C.c_int32,C.c_int32,C.c_uint32,C.c_uint32,C.c_uint8]
    memory=(C.c_uint8*120).in_dll(lib,'g_bio_v2')
    fields=[x['name'] for x in json.loads((ROOT/'node-b/acquisition/field-biov2/profile.offline.json').read_text('utf-8'))['layout']['diag']['fields']]
    require(len(fields)==30,'REPLAY_ABI_FIELDS')
    lib.BioV2_Init(rows[0]['device_ms'])
    replay=[];events=[];previous_h=previous_r=0
    for raw in rows:
        lib.BioV2_Process(raw['ch2_raw'],raw['ch1_raw'],raw['device_ms'],raw['source_seq'],raw['flags_raw'])
        d=dict(zip(fields,struct.unpack('<8I4i14I4f',bytes(memory))))
        replay.append(dict(source_seq=raw['source_seq'],device_ms=raw['device_ms'],**d))
        if d['hr_candidates']!=previous_h or d['hr_accepted']!=previous_r:
            events.append({'origin':'EXACT_SOURCE_HOST_REPLAY','observed_at_sequence':raw['source_seq'],
                           'observed_at_device_ms':raw['device_ms'],'candidate_count':d['hr_candidates'],
                           'accepted_count':d['hr_accepted'],'last_accepted_cycle_ms':d['hr_last_cycle_ms']})
        previous_h,previous_r=d['hr_candidates'],d['hr_accepted']
    with (out/'replay-not-live-private.csv').open('x',encoding='utf-8',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(replay[0]));w.writeheader();w.writerows(replay)
    write_json(out/'peak-events-REPLAY-private.json',events)
    live=json.loads((folder/'diagnostics-private.json').read_text('utf-8'))
    source=json.loads(source_record.read_text('utf-8'))
    summary={'data_source':'ENGINEERING_NONHUMAN','source_mode':source['mode'],'nominal_reference_bpm':source.get('reference_bpm'),
             'stable_raw_sha256':sha(folder/'stable-raw-private.csv'),'source_record_sha256':sha(source_record),
             'bio_source_sha256':SOURCE_SHA,'host_dll_sha256':sha(dll),'samples':len(rows),
             'device_span_ms':(rows[-1]['device_ms']-rows[0]['device_ms'])&0xffffffff,
             'ecg_ch2':describe([r['ch2_raw'] for r in rows]),'resp_ch1':describe([r['ch1_raw'] for r in rows]),
             'live_hr_observations':[{'sequence':r['last_sequence'],'device_ms':r['last_sample_ms'],
                                      'hr':r['hr'],'valid':r['hr_valid'],'reason':r['hr_reason']} for r in live],
             'replay_final':replay[-1],'replay_valid_hr_frames':sum(bool(r['hr_valid']) for r in replay),
             'replay_peak_event_records':len(events),'accuracy':'NOT_ASSESSED_PILOT_NO_60S_STEADY_WINDOW',
             'limitations':['Replay starts with reset state at first retained frame; not the full live filter history',
                            'Exact frozen C source on Host; not a claim of bit-identical ARM execution',
                            'Peak events derived from Host replay; no synchronized external per-beat truth',
                            'Spectra use nominal 250SPS and mean removal; amplitudes remain uncalibrated ADC codes']}
    if formal:
        require(source['mode']=='ORDINARY_ECG','FORMAL_SOURCE_MODE')
        summary['formal']=formal_evaluate(rows,live,replay,source['reference_bpm'])
        summary['accuracy']='ENGINEERING_RATE_AGREEMENT_ONLY'
    write_json(out/'analysis-summary-private.json',summary)
    # 三种证据分行展示，避免把回放滤波和现场末帧诊断画成同一原子实板流。
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    t=np.array([((r['device_ms']-rows[0]['device_ms'])&0xffffffff)/1000 for r in rows])
    fig,axes=plt.subplots(3,1,figsize=(11,8),layout='constrained')
    axes[0].plot(t,[r['ch2_raw'] for r in rows],lw=.7);axes[0].set(title='CH2 raw ECG - engineering nonhuman',ylabel='ADC codes')
    axes[1].plot(t,[r['ecg_filtered'] for r in replay],lw=.7);axes[1].set(title='BIO_V2 filtered ECG - HOST REPLAY, reset initial state',ylabel='UI scale')
    axes[2].plot(t,[r['ch1_raw'] for r in rows],lw=.7);axes[2].set(title='CH1 raw - impedance reference NOT validated',ylabel='ADC codes',xlabel='Device time from first retained frame (s)')
    fig.savefig(out/'pilot-waveforms-private.png',dpi=150);plt.close(fig)
    return summary


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('capture','source-record','out'):p.add_argument('--'+n,required=True,type=Path)
    p.add_argument('--formal',action='store_true')
    args=p.parse_args();require(args.out.resolve().is_relative_to(PRIVATE.resolve()),'PRIVATE_OUTPUT_REQUIRED')
    result=analyze(args.capture,args.source_record,args.out,args.formal)
    print(json.dumps({'samples':result['samples'],'ecg_ch2':result['ecg_ch2'],
                      'live_last':result['live_hr_observations'][-1],'replay_final_hr':result['replay_final']['hr'],
                      'accuracy':result['accuracy'],'formal':result.get('formal')}))


if __name__=='__main__':main()
