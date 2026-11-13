"""M0复用既有隔离Broker/语音及Backend；配置只从受限档案读取。"""
import argparse
import base64
import hashlib
import inspect
import json
from pathlib import Path
import secrets
import shlex
import subprocess
import sys

import b5_g1_cloud as old

ROOT=Path(__file__).resolve().parents[2]


def remote_start(p):
    import base64,json,os,pwd,subprocess,time
    from pathlib import Path
    base=Path(p['base']);voice=Path(p['voice']['server_base'])
    assert base==Path('/opt/medical-monitor-b5/m0-abc-20261103')
    assert json.loads((voice/'voice-runtime-credentials-private.json').read_text())==p['voice']
    role=pwd.getpwnam('b5-monitor');native=[]
    def run(args):
        r=subprocess.run(args,capture_output=True,timeout=15)
        native.append({'operation':args[0],'exit_code':r.returncode})
        if r.returncode:
            (base/'failure-private.log').write_bytes(r.stdout+r.stderr)
            raise RuntimeError('M0_OWN_SERVICE_COMMAND_FAILED')
    base.mkdir(mode=0o750,exist_ok=True);os.chown(base,role.pw_uid,role.pw_gid)
    for rel in ('backend/app','web/dist','config','run','logs/backend','nginx'):
        q=base/rel;q.mkdir(parents=True,exist_ok=True)
    for rel,data in p['files'].items():
        assert rel.startswith(('backend/app/','web/dist/','config/')) and '..' not in Path(rel).parts
        f=base/rel;f.parent.mkdir(parents=True,exist_ok=True);f.write_bytes(base64.b64decode(data));f.chmod(0o640)
    for f in base.rglob('*'):
        os.chown(f,role.pw_uid,role.pw_gid)
        if f.is_dir():f.chmod(0o750)
    def start(name,cmd,props=()):
        state=subprocess.run(['systemctl','is-active',name],capture_output=True,text=True,timeout=3).stdout.strip()
        assert state!='active','M0_UNIT_ALREADY_ACTIVE'
        load=subprocess.run(['systemctl','show',name,'-p','LoadState','--value'],capture_output=True,text=True,timeout=3).stdout.strip()
        if load=='loaded':run(['systemctl','start',name])
        else:run(['systemd-run','--quiet','--unit='+name,'--property=RuntimeMaxSec=21600','--property=NoNewPrivileges=true',*props,*cmd])
    start('mpm-unified-c-mqtt-20261103',['mosquitto','-c',str(voice/'mqtt.conf')],['--property=MemoryMax=64M','--property=CPUQuota=25%'])
    time.sleep(1)
    ready=voice/'worker-ready.json'
    if ready.exists():ready.unlink()
    python='/opt/medical-monitor-h3/environments/runtime-b8fbb14b5c35/bin/python'
    start('mpm-unified-c-worker-m0-240-20261103',[python,str(voice/'worker-app/worker.py'),'--base',str(voice),'--assembly-timeout-seconds','240'],
          ['--property=MemoryMax=768M','--property=CPUQuota=75%','--property=Nice=10','--property=EnvironmentFile=/opt/medical-monitor-h3/formal/20261021T093335Z/ai.env'])
    start('mpm-unified-c-ingress-20261103',['/usr/bin/python3',str(voice/'ingress.py')],['--property=MemoryMax=32M','--property=CPUQuota=10%'])
    assert not subprocess.run(['ss','-H','-ltn','sport','=',':18775'],capture_output=True,text=True).stdout.strip(),'M0_LOOPBACK_PORT_IN_USE'
    start('mpm-m0-baseline-backend',[python,'-m','uvicorn','app.main:app','--uds',str(base/'run/backend.sock'),'--workers','1','--no-access-log'],
          ['--uid=b5-monitor','--working-directory='+str(base/'backend'),'--property=EnvironmentFile='+str(base/'config/backend.env'),
           '--property=MemoryMax=256M','--property=CPUQuota=50%'])
    start('mpm-m0-baseline-tls',['/usr/sbin/nginx','-p',str(base/'nginx')+'/','-c',str(base/'config/nginx.conf'),'-g','daemon off;'],['--property=MemoryMax=64M'])
    for _ in range(20):
        if ready.exists() and (base/'run/backend.sock').exists():break
        time.sleep(.5)
    assert ready.exists() and (base/'run/backend.sock').exists(),'M0_SERVICES_NOT_READY'
    print(json.dumps({'native':native,'worker_ready':True,'backend_socket':True,'formal_service_changes':0,'formal_ACL_changes':0}))


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--start',action='store_true');a=p.parse_args()
    pointer=json.loads((ROOT/'node-b/build/m0-current-pointer.json').read_text());job=Path(pointer['job'])
    if not a.start:print(json.dumps({'execute':False,'scope':'M0_TASK_ISOLATION_ONLY'}));return 0
    voice=json.loads((Path(pointer['previous_job'])/'voice-runtime-credentials-private.json').read_text())
    prior=Path(json.loads((ROOT/'node-b/build/abc-two-group-pointer.json').read_text())['job'])
    group=Path(json.loads((ROOT/'node-b/build/abc-two-group-resume-state.json').read_text())['ECG60_pass_window'])
    bundle=json.loads((group/'bundle-private.json').read_text());package=json.loads(Path(bundle['cloud_package']['path']).read_text())
    snapshot=package['snapshot'];token=secrets.token_urlsafe(36)
    base,origin,config=old.payload_files(snapshot,'m0-abc-20261103','unused',voice['roles']['mic-observer'],token)
    backend={'host':'127.0.0.1','port':18885,'tls':False,'username':'mic-observer','password':voice['roles']['mic-observer'],'client_id':'m0-backend-isolated'}
    config['backend.json']=json.dumps(backend).encode()
    config['backend.env']+=b'MONITOR_WAVE_BATCH_DELIVERY=1\n'
    files={'config/'+n:base64.b64encode(config[n]).decode() for n in ('backend.json','backend.env','nginx.conf')}
    for path in sorted((ROOT/'cloud/backend/app').glob('*.py')):files['backend/app/'+path.name]=base64.b64encode(path.read_bytes()).decode()
    dist=ROOT/'cloud/web/dist'
    for path in sorted(dist.rglob('*')):
        if path.is_file():files['web/dist/'+path.relative_to(dist).as_posix()]=base64.b64encode(path.read_bytes()).decode()
    assert len(files)>10,'M0_BACKEND_WEB_BUILD_REQUIRED'
    settings={'voice':voice,'base':base,'files':files}
    (job/'cloud-package-private.json').write_text(json.dumps({'snapshot':snapshot,'origin':origin,'base':base},indent=2))
    (job/'cloud-credentials-private.json').write_text(json.dumps({'view_token':token,'passwords':{'b5-observer':voice['roles']['mic-observer']}}))
    (job/'cloud-start-settings-private.json').write_text(json.dumps(settings))
    code=inspect.getsource(remote_start)+'\nimport json,sys\nremote_start(json.load(sys.stdin))\n'
    (job/'cloud-start-executed.py').write_text(code)
    r=subprocess.run(['ssh','-o','BatchMode=yes','-o','StrictHostKeyChecking=yes','tencent-codex','sudo -n python3 -c '+shlex.quote(code)],input=json.dumps(settings).encode(),capture_output=True,timeout=100)
    (job/'cloud-start-stdout-private.json').write_bytes(r.stdout);(job/'cloud-start-stderr-private.log').write_bytes(r.stderr)
    print(json.dumps({'native_exit':r.returncode,'report':'cloud-start-stdout-private.json','uploaded_sources_sha256':{n:hashlib.sha256(base64.b64decode(b)).hexdigest() for n,b in files.items() if n.startswith('backend/')}}))
    return r.returncode


if __name__=='__main__':raise SystemExit(main())
