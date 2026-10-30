"""复用冻结联评器和调度模型的P1-A只读复算；输出到新的审计目录。"""
import argparse
import ctypes
import hashlib
import json
from pathlib import Path
import platform
import subprocess
import sys
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[2]
BASE='01864fb4c1ea35c9da38aa98b1e85790d2ed5415'
SHA=lambda raw:hashlib.sha256(raw).hexdigest()


def save(path,data):
    with path.open('x',encoding='utf-8',newline='\n') as stream:
        json.dump(data,stream,ensure_ascii=False,indent=2)
        stream.write('\n')


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--private-root',type=Path)
    parser.add_argument('--build-root',type=Path)
    parser.add_argument('--out',type=Path,required=True)
    parser.add_argument('--mode',choices=('integrity','replay','model'),required=True)
    args=parser.parse_args()
    if args.build_root:args.build_root=args.build_root.resolve()
    if args.private_root:
        args.private_root=args.private_root.resolve()
        if args.out.resolve().is_relative_to(args.private_root):
            parser.error('P1A_PRIVATE_OUTPUT_FORBIDDEN')
    if args.mode=='integrity':
        old=json.loads((ROOT/'node-b/docs/B5-R6-PATCH01/R6-EVIDENCE-HASHES.json').read_text())
        rows=[]
        for name,expected in old['files'].items():
            raw=subprocess.check_output(['git','show',BASE+':'+name],cwd=ROOT)
            working=(ROOT/name).read_bytes()
            rows.append({'path':name,'base_blob_match':len(raw)==expected['bytes'] and SHA(raw)==expected['sha256'],
                         'working_match':working==raw})
        frozen=['node-b/tools/b5_channel_review.py']+[f'node-b/evidence/B5-GEMINI-R5/{p}-WINDOW-01/criteria.json' for p in ('ECG60','TEMP_OBJECT','RR15')]
        invariants=[]
        for name in frozen:
            raw=subprocess.check_output(['git','show',BASE+':'+name],cwd=ROOT)
            invariants.append({'path':name,'sha256':SHA(raw),'unchanged':raw==(ROOT/name).read_bytes()})
        result={'base':BASE,'historical_manifest':rows,'frozen_evaluator_and_criteria':invariants}
        if args.build_root:
            receipt=json.loads((args.build_root/'receipt.json').read_text())
            paths={'BIN':args.build_root/'B5_TEMP_NODE_B.bin','AXF':args.build_root/'firmware/OBJ/BIO_V2.axf',
                   'symbols':args.build_root/'symbols.txt','MAP':args.build_root/'firmware/USER/Listings/BIO_V2.map',
                   'log':args.build_root/'firmware/build.log','candidate_source':args.build_root/'hr_page.candidate.c',
                   'compiled_source':args.build_root/'firmware/HARDWARE/hr_page.c','builder':args.build_root/'executed-builder.py'}
            chain={name:{'bytes':p.stat().st_size,'sha256':SHA(p.read_bytes())} if p.is_file() else {'status':'UNKNOWN_MISSING'} for name,p in paths.items()}
            result['new_build']={'directory':args.build_root.relative_to(ROOT).as_posix(),'receipt':receipt,
                'chain':chain,'bin_matches_archived':paths['BIN'].read_bytes()==(ROOT/'node-b/evidence/B5-R6-PATCH01/B5_TEMP_NODE_B.candidate.bin').read_bytes(),
                'candidate_source_matches_compiled':paths['candidate_source'].read_bytes()==paths['compiled_source'].read_bytes(),
                'candidate_source_matches_archived':paths['candidate_source'].read_bytes()==(ROOT/'node-b/evidence/B5-R6-PATCH01/hr_page.candidate.c').read_bytes(),
                'WCET':'MODEL_ONLY_NOT_MEASURED','hardware_eligible':False}
        ok=all(r['base_blob_match'] for r in rows) and all(r['unchanged'] for r in invariants)
        result.update(status='PASS_OFFLINE_INTEGRITY' if ok else 'FAIL',exit_code=0 if ok else 1)
        save(args.out,result);print(json.dumps({'status':result['status'],'exit_code':result['exit_code']}));return result['exit_code']

    def guard(event,values):
        if event in ('ctypes.dlopen','subprocess.Popen','socket.connect','socket.bind','socket.sendto','socket.getaddrinfo'):
            raise RuntimeError('P1A_OFFLINE_FORBIDDEN_'+event)
        if event=='open' and isinstance(values[0],str):
            mode,flags=values[1:3]
            if (mode and any(c in mode for c in 'wax+') or flags&3) and args.private_root and args.private_root.as_posix().lower() in values[0].replace('\\','/').lower():
                raise RuntimeError('P1A_PRIVATE_WRITE_FORBIDDEN')
    sys.addaudithook(guard)
    sys.path[:0]=[str(ROOT/'node-b/tools'),str(ROOT/'node-b/temperature'),str(ROOT)]
    with patch.object(platform,'system',return_value='Windows' if sys.platform=='win32' else sys.platform):
        if args.mode=='model':
            import test_timing_simulation as timing
            result={'status':'PASS_SYNTHETIC','WCET':'WCET_MODEL_ONLY','real_cpu_WCET':'NOT_MEASURED',
                    'phase_sweep':timing.run_phase_sweep_regression(),
                    'scheduling':timing.simulate_scheduling(candidate_patch=True,duration_s=600),
                    'coincident':timing.run_coincident_multitask_stress_test(),
                    'source_sha256':SHA(Path(timing.__file__).read_bytes())}
            ok=result['phase_sweep']['cand_fails']==0 and result['scheduling']['fails_count']==0 and result['coincident']['cand']['fails']==0
            result.update(exit_code=0 if ok else 1)
        else:
            if args.private_root is None:parser.error('--private-root is required for replay')
            import b5_channel_review as review
            rows=[]
            runs=(('ECG60','owner-observed-ECG60-R5-55d99a50'),('TEMP_OBJECT','owner-observed-TEMP_OBJECT-R5-6104c2e6'),('RR15','owner-observed-RR15-R5-5bb61eef'))
            for profile,alias in runs:
                folder=args.private_root/alias
                original=folder/('formal-'+profile+'-review-private.json')
                formal=json.loads(original.read_bytes())
                actual=review.review(folder/'joint',profile)
                rows.append({'profile':profile,'original_sha256':SHA(original.read_bytes()),
                    'status':actual['status'],'exit_code':actual['exit_code'],'failures':actual['failures'],
                    'original_failure_set_match':set(actual['failures'])==set(formal['failures']),
                    'original_status_match':actual['status']==formal['status'],
                    'criteria_sha256':SHA(json.dumps(actual['criteria'],sort_keys=True).encode()),
                    'wave_batches_observed_in_WSS':actual['wave_batches_observed_in_WSS']})
            preserved=all(r['exit_code']==3 and r['original_failure_set_match'] and r['original_status_match'] for r in rows)
            result={'status':'HISTORICAL_NOT_PASS_REPRODUCED' if preserved else 'REPLAY_MISMATCH',
                    'exit_code':3 if preserved else 1,'runs':rows,'reviewer_sha256':SHA(Path(review.__file__).read_bytes())}
    save(args.out,result)
    print(json.dumps(result,ensure_ascii=False))
    return result['exit_code']


if __name__=='__main__':
    raise SystemExit(main())
