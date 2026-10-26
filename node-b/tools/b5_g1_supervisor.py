"""G1-A独立监督器：先验证授权/工具/包，唯一worker，超时不重试不回滚。"""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import time

import b5_g1_cloud as cloud
from b4_recovery import protected


def check(a, private, phase='apply'):
    if phase not in ('apply','smoke'):raise ValueError('G1_PHASE_DENIED')
    name=a.get('package_filename','deployment-package-private.json')
    if Path(name).name!=name:raise ValueError('PACKAGE_FILENAME')
    package_bytes=protected(private/name,False).read_bytes()
    package=json.loads(package_bytes)
    cloud.authorize(a,package,package_bytes)
    if a.get('supervisor_sha256')!=cloud.sha(Path(__file__).read_bytes()):raise ValueError('G1_SUPERVISOR_BINDING')
    if phase=='smoke':
        smoke=Path(__file__).with_name('b5_g1_smoke.py')
        if a.get('smoke_tool_sha256')!=cloud.sha(smoke.read_bytes()):raise ValueError('G1_SMOKE_TOOL_BINDING')
    if (private/('G1-'+phase+'-supervisor-started-private.json')).exists():raise ValueError('G1_ALREADY_ATTEMPTED')
    return package


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--authorization',required=True,type=Path);parser.add_argument('--phase',choices=['apply','smoke'],default='apply');args=parser.parse_args()
    private=Path(json.loads((cloud.ROOT/'node-b/build/b5-g1-private-pointer.json').read_bytes())['base'])
    result={'status':'STOP_BEFORE_WORKER','exit_code':1,'automatic_retries':0,'automatic_rollback':False}
    try:
        auth=protected(args.authorization,False).read_bytes();a=json.loads(auth);package=check(a,private,args.phase)
        cloud.write_private(private/('G1-'+args.phase+'-supervisor-started-private.json'),cloud.encode({'tx':package['tx'],'started':time.time(),'auth_sha256':cloud.sha(auth)}))
        command=[sys.executable,'-X','utf8',str(Path(cloud.__file__)),'--apply'] if args.phase=='apply' else [sys.executable,'-X','utf8',str(Path(__file__).with_name('b5_g1_smoke.py'))]
        command+=['--authorization',str(args.authorization)]
        child=subprocess.Popen(command,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        try:stdout,stderr=child.communicate(timeout=210 if args.phase=='apply' else 120)
        except subprocess.TimeoutExpired:
            # 仅结束本监督器刚创建的worker树，包括它独占的SSH转发，避免留下本地会话。
            subprocess.run(['taskkill','/PID',str(child.pid),'/T','/F'],capture_output=True,timeout=8)
            stdout,stderr=child.communicate(timeout=8)
            cloud.write_private(private/(args.phase+'-timeout-worker-stdout-private.bin'),stdout)
            cloud.write_private(private/(args.phase+'-timeout-worker-stderr-private.bin'),stderr)
            raise subprocess.TimeoutExpired(command,120 if args.phase=='smoke' else 210,output=stdout,stderr=stderr)
        cloud.write_private(private/(args.phase+'-supervisor-worker-stdout-private.bin'),stdout)
        cloud.write_private(private/(args.phase+'-supervisor-worker-stderr-private.bin'),stderr)
        result.update(status='WORKER_FINISHED' if child.returncode==0 else 'STOP_WORKER_FAILED',exit_code=child.returncode,
                      worker_exit_code=child.returncode,worker_stdout_sha256=cloud.sha(stdout),worker_stderr_sha256=cloud.sha(stderr))
    except subprocess.TimeoutExpired as e:
        cloud.write_private(private/(args.phase+'-supervisor-timeout-stdout-private.bin'),e.stdout or b'')
        cloud.write_private(private/(args.phase+'-supervisor-timeout-stderr-private.bin'),e.stderr or b'')
        result.update(status='STOP_SUPERVISOR_TIMEOUT',exit_code=124)
    except Exception as e:
        reason=str(e) if isinstance(e,ValueError) and str(e).replace('_','').isalnum() else type(e).__name__
        result.update(reason=reason)
    result['phase']=args.phase
    cloud.write_private(private/(args.phase+'-supervisor-result-private.json'),cloud.encode(result))
    (cloud.ROOT/('node-b/evidence/B5-G1/'+args.phase+'-supervisor.json')).write_bytes(cloud.encode(result))
    print(json.dumps(result));return result['exit_code']


if __name__=='__main__':raise SystemExit(main())
