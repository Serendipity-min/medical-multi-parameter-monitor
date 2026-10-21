"""本轮新增维护/发布工具的定向验证；不重复认领AC-1，不启动安全扫描。"""
from datetime import datetime,timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[3]


def main():
    stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    out=ROOT/'cloud/evidence/h3-ac-final'/('software-'+stamp);out.mkdir(parents=True)
    jobs=[('tool-regression',[sys.executable,'-m','pytest','cloud/backend/tests/test_final_delivery.py',
        'cloud/backend/tests/test_h3_formal_release.py','-q']),
        ('posix-recovery',['wsl','-d','HERA-C3','--cd','/mnt/e/medical-monitor-h3-ac-closeout',
            'python3','-m','cloud.deploy.h3.final_posix_check']),
        ('new-A-offline-plan',[sys.executable,'-m','gateway.physical_can.bench.final_a','plan',
            '--image','node-a/build/h3-ac-node-a.bin']),
        ('web-package-build',['npm.cmd','--prefix','cloud/web','run','build'])]
    commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    result=[]
    for name,command in jobs:
        start=datetime.now(timezone.utc).isoformat()
        run=subprocess.run(command,cwd=ROOT,capture_output=True,env={**os.environ,'PYTHONUTF8':'1'},timeout=180)
        raw=run.stdout+run.stderr
        (out/(name+'.log')).write_bytes(raw)
        receipt={'stage':'F1/F3_SOFTWARE','gate':'PASS' if run.returncode==0 else 'FAIL','source_commit':commit,
            'device_or_runtime_sha':None,'source_label':'SOFTWARE_SYNTHETIC_NO_ACQUISITION',
            'window_start_utc':start,'window_end_utc':datetime.now(timezone.utc).isoformat(),
            'command':command,'exit_code':run.returncode,'observed_vs_simulated':'LOCAL_SOFTWARE_ONLY',
            'raw_evidence_sha':hashlib.sha256(raw).hexdigest(),'security_scope':'NO_SCAN_NO_CLOUD_WRITE_NO_BOARD_ACCESS',
            'owner_auth_id':'MPM-H3-004_SIGNED_SOFTWARE','rollback_state':'SIMULATED_ONLY_SERVER_ROLLBACK_NOT_RUN',
            'unresolved':['PHYSICAL_AND_CLOUD_AUTH_GATES'],
            'null_reasons':{'device_or_runtime_sha':'NO_BOARD_ACCESS; OFFLINE_IMAGE_PLAN_SHA_IN_ADJACENT_LOG'}}
        (out/(name+'.json')).write_text(json.dumps(receipt,indent=2))
        result.append({'name':name,'exit_code':run.returncode,'receipt':(out/(name+'.json')).relative_to(ROOT).as_posix()})
    summary={'jobs':result,'exit_code':max(r['exit_code'] for r in result),'AC1':'INHERITED_NOT_RERUN',
        'new_code_tracked_but_not_committed':bool(subprocess.check_output(['git','status','--porcelain'],cwd=ROOT))}
    (out/'summary.json').write_text(json.dumps(summary,indent=2))
    print(json.dumps(summary,indent=2));return summary['exit_code']


if __name__=='__main__':raise SystemExit(main())
