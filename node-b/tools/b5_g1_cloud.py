"""G1-A独立云事务：先只读冻结，审核后一次部署；秘密只在EFS与服务器受限目录。"""
import argparse
import base64
import hashlib
import inspect
import json
from pathlib import Path
import secrets
import subprocess
import sys
import time
import uuid

from b5_g0_readonly import ROOT, new_private, write_private

SCOPE = 'B5_G1A_ONE_CLOUD_NAMESPACE_AND_LOOPBACK_TLS_NO_FORMAL_RESTART'
DENY = 'mpm/v1/GW-B5-DENY-001/NODE-B/telemetry/hr'
WRAPPER_SHA = 'e9f215332b5d6822984f4bf7f19d3b97a242eb897e5c97fe7ba9ea48608b1340'


def sha(b): return hashlib.sha256(b).hexdigest()
def encode(x): return (json.dumps(x, indent=2, sort_keys=True)+'\n').encode()


def remote_prepare():
    import base64,hashlib,json,os,pwd,re,subprocess
    from pathlib import Path
    def command(a):
        r=subprocess.run(a,capture_output=True,text=True,timeout=10)
        if r.returncode: raise ValueError('READONLY_COMMAND_FAILED')
        return r.stdout
    files={}
    def capture(path):
        p=Path(path);b=p.read_bytes();s=p.stat()
        files[str(p)]={'base64':base64.b64encode(b).decode(),'sha256':hashlib.sha256(b).hexdigest(),
                       'mode':s.st_mode&0o777,'uid':s.st_uid,'gid':s.st_gid}
        return b
    units={}
    for name in ['medical-monitor-mqtt.service','medical-monitor.service','p6-ai.service','nginx.service']:
        text=command(['systemctl','show',name,'-p','MainPID','-p','ActiveState','-p','FragmentPath'])
        d=dict(line.split('=',1) for line in text.splitlines() if '=' in line)
        if d['ActiveState']!='active' or not int(d['MainPID']):raise ValueError('FORMAL_SERVICE_NOT_ACTIVE')
        units[name]={'pid':int(d['MainPID']),'active':d['ActiveState'],'fragment':d['FragmentPath']}
        capture(d['FragmentPath'])
    wrapper='/opt/medical-monitor/current/deploy/broker_logging.py';capture(wrapper)
    broker=[]
    for p in Path('/proc').iterdir():
        if not p.name.isdigit():continue
        try:
            if (p/'comm').read_text().strip()!='mosquitto':continue
            parent=int(re.search(r'^PPid:\s*(\d+)',(p/'status').read_text(),re.M)[1])
            if parent!=units['medical-monitor-mqtt.service']['pid']:continue
            args=(p/'cmdline').read_bytes().decode().split('\0')
            broker.append({'pid':int(p.name),'config':args[args.index('-c')+1]})
        except FileNotFoundError:continue
    if len(broker)!=1:raise ValueError('BROKER_PROCESS_AMBIGUOUS')
    config=capture(broker[0]['config']).decode();directives={}
    for line in config.splitlines():
        parts=line.strip().split(maxsplit=1)
        if len(parts)==2 and not parts[0].startswith('#'):directives.setdefault(parts[0],[]).append(parts[1])
    if any(k in directives for k in ['include_dir','plugin','auth_plugin']):raise ValueError('UNREVIEWED_AUTH_OR_INCLUDE')
    acl=directives['acl_file'][0];password=directives['password_file'][0]
    capture(acl);capture(password)
    for p in ['/opt/medical-monitor/config/backend.env','/opt/medical-monitor/mqtt-config/backend.json']:
        capture(p)
    backend=json.loads(Path('/opt/medical-monitor/mqtt-config/backend.json').read_text())
    key=directives['keyfile'][0];cert=directives['certfile'][0]
    # 不读取或复制TLS私钥，只绑定路径/权限，独立nginx主进程引用现有文件。
    if not Path(key).is_file() or not Path(cert).is_file():raise ValueError('TLS_REFERENCE_MISSING')
    capture(cert)
    listening=bool(command(['ss','-H','-ltn','sport','=',':18775']).strip())
    if listening:raise ValueError('LOOPBACK_PORT_OCCUPIED')
    try:pwd.getpwnam('b5-monitor');user_exists=True
    except KeyError:user_exists=False
    if user_exists:raise ValueError('TEST_OS_ROLE_ALREADY_EXISTS')
    versions=command(['/opt/medical-monitor/current/.venv/bin/python','-c',
        'import importlib.metadata,json;print(json.dumps({x:importlib.metadata.version(x) for x in ["fastapi","uvicorn","websockets","pydantic","paho-mqtt"]}))'])
    return {'files':files,'units':units,'broker':broker[0],'directives':directives,
            'acl_path':acl,'password_path':password,'backend':backend,'key_path':key,'cert_path':cert,
            'python':'/opt/medical-monitor/current/.venv/bin/python','versions':json.loads(versions),
            'loopback_port_free':True,'new_OS_role_absent':True}


def ssh(code, seconds, out, label):
    write_private(out/(label+'-executed-private.py'),code.encode())
    r=subprocess.run(['ssh','-o','BatchMode=yes','-o','StrictHostKeyChecking=yes','-o','ConnectTimeout=12',
                      'tencent-codex','sudo -n timeout '+str(seconds)+'s python3 -'],
                     input=code.encode(),capture_output=True,timeout=seconds+20)
    write_private(out/(label+'-stdout-private.json'),r.stdout)
    write_private(out/(label+'-stderr-private.bin'),r.stderr)
    if r.returncode:raise ValueError('REMOTE_'+label.upper()+'_FAILED')
    return json.loads(r.stdout)


def payload_files(snapshot, tx, publisher_password, observer_password, token):
    host=snapshot['backend']['host'];base='/opt/medical-monitor-b5/'+tx
    sock=base+'/run/backend.sock';origin='https://'+host+':18775'
    backend={'host':host,'port':8883,'username':'b5-observer','password':observer_password,'client_id':'b5-backend-isolated'}
    config={'backend.json':encode(backend),
       'backend.env':('\n'.join(['MONITOR_MQTT_CONFIG='+base+'/config/backend.json','MONITOR_VIEW_TOKEN='+token,
           'MONITOR_GATEWAY_IDS=GW-B5-001','MONITOR_ALLOWED_ORIGINS='+origin,'MONITOR_LOG_DIR='+base+'/logs/backend',
           'MONITOR_WEB_DIR='+base+'/web/dist','PYTHONDONTWRITEBYTECODE=1'])+'\n').encode()}
    nginx='''user b5-monitor;
worker_processes 1;
pid BASE/run/nginx.pid;
lock_file BASE/run/nginx.lock;
error_log BASE/logs/nginx-error.log warn;
events { worker_connections 128; }
http {
 include /etc/nginx/mime.types;
 access_log off;
 client_body_temp_path BASE/nginx/client_body_temp;
 proxy_temp_path BASE/nginx/proxy_temp;
 fastcgi_temp_path BASE/nginx/fastcgi_temp;
 uwsgi_temp_path BASE/nginx/uwsgi_temp;
 scgi_temp_path BASE/nginx/scgi_temp;
 server {
  listen 127.0.0.1:18775 ssl;
  server_name HOST;
  ssl_certificate CERT;
  ssl_certificate_key KEY;
  ssl_protocols TLSv1.2 TLSv1.3;
  location ^~ /medical-monitor/ai { return 404; }
  location ^~ /medical-monitor/ {
   proxy_pass http://unix:SOCKET:/;
   proxy_http_version 1.1;
   proxy_set_header Upgrade $http_upgrade;
   proxy_set_header Connection "upgrade";
   proxy_set_header Host $host;
   proxy_set_header X-Forwarded-Proto $scheme;
   proxy_buffering off;
   proxy_read_timeout 60s;
  }
 }
}
'''
    for a,b in [('BASE',base),('HOST',host),('CERT',snapshot['cert_path']),('KEY',snapshot['key_path']),('SOCKET',sock)]:nginx=nginx.replace(a,b)
    config['nginx.conf']=nginx.encode()
    backend_unit='''[Unit]
Description=Isolated nonhuman B5 Backend TX
After=network.target
[Service]
Type=simple
User=b5-monitor
Group=b5-monitor
WorkingDirectory=BASE/backend
EnvironmentFile=BASE/config/backend.env
ExecStart=PYTHON -m uvicorn app.main:app --uds SOCKET --workers 1 --ws-max-size 65536 --ws-max-queue 8 --no-access-log
Restart=no
RuntimeMaxSec=21600
UMask=0077
NoNewPrivileges=true
ProtectHome=true
ProtectSystem=strict
ReadWritePaths=BASE/run BASE/logs/backend
StandardOutput=append:BASE/logs/backend-service.log
StandardError=append:BASE/logs/backend-service.log
'''
    tls_unit='''[Unit]
Description=Isolated nonhuman B5 loopback TLS TX
[Service]
Type=simple
ExecStart=/usr/sbin/nginx -p BASE/nginx/ -c BASE/config/nginx.conf -g "daemon off;"
Restart=no
RuntimeMaxSec=21600
UMask=0077
NoNewPrivileges=true
ProtectHome=true
ProtectSystem=strict
ReadWritePaths=BASE/run BASE/logs BASE/nginx
StandardOutput=append:BASE/logs/tls-service.log
StandardError=append:BASE/logs/tls-service.log
'''
    for name,text in [('backend.service',backend_unit),('tls.service',tls_unit)]:
        for a,b in [('BASE',base),('TX',tx),('PYTHON',snapshot['python']),('SOCKET',sock)]:text=text.replace(a,b)
        config[name]=text.encode()
    return base,origin,config


def prepare():
    private=new_private();(ROOT/'node-b/build/b5-g1-private-pointer.json').write_bytes(encode({'base':str(private)}))
    snapshot=ssh(inspect.getsource(remote_prepare)+'\nimport json\nprint(json.dumps(remote_prepare()))\n',35,private,'prepare')
    g0=Path(json.loads((ROOT/'node-b/build/b5-g0-private-pointer.json').read_text())['base'])
    old=json.loads((g0/'ssh-stdout-private.json').read_bytes())
    assert all(snapshot['units'][k]['pid']==old['public']['units'][k]['pid'] for k in snapshot['units'])
    assert snapshot['files']['/opt/medical-monitor/current/deploy/broker_logging.py']['sha256']==WRAPPER_SHA
    assert all(snapshot['files'][k]['sha256']==old['files'][k]['sha256'] for k in snapshot['files'] if k in old['files'])
    expected={'fastapi':'0.135.1','uvicorn':'0.40.0','websockets':'16.0','pydantic':'2.12.5','paho-mqtt':'2.1.0'}
    assert snapshot['versions']==expected
    raw_acl=base64.b64decode(snapshot['files'][snapshot['acl_path']]['base64'])
    raw_pass=base64.b64decode(snapshot['files'][snapshot['password_path']]['base64'])
    assert b'user b5-' not in raw_acl and b'b5-gateway:' not in raw_pass and b'b5-observer:' not in raw_pass
    passwords={k:secrets.token_urlsafe(30) for k in ['b5-gateway','b5-observer']};token=secrets.token_urlsafe(36)
    write_private(private/'test-credentials-private.json',encode({'passwords':passwords,'view_token':token}))
    passwd=private/'new-users-passwd-private';write_private(passwd,('\n'.join(k+':'+v for k,v in passwords.items())+'\n').encode())
    runtime=ROOT/'node-b/build/b5-runtime/root'
    def linux(p):return '/mnt/'+p.drive[0].lower()+p.as_posix()[2:]
    r=subprocess.run(['wsl','-d','HERA-C3','--','env',
           'LD_LIBRARY_PATH='+linux(runtime/'usr/lib/x86_64-linux-gnu')+':'+linux(runtime/'lib/x86_64-linux-gnu'),
           linux(runtime/'usr/bin/mosquitto_passwd'),'-U',linux(passwd)],capture_output=True)
    write_private(private/'password-transform-stdout-private.bin',r.stdout);write_private(private/'password-transform-stderr-private.bin',r.stderr)
    if r.returncode:raise ValueError('PASSWORD_HASH_TRANSFORM_FAILED')
    new_hashes=passwd.read_bytes();assert b'$7$' in new_hashes and all(v.encode() not in new_hashes for v in passwords.values())
    acl_delta=b'\n# B5 isolated MOCK only\nuser b5-gateway\ntopic write mpm/v1/GW-B5-001/#\nuser b5-observer\ntopic read mpm/v1/GW-B5-001/#\n'
    tx='g1a-'+uuid.uuid4().hex[:10]
    base,origin,config=payload_files(snapshot,tx,passwords['b5-gateway'],passwords['b5-observer'],token)
    sources={}
    for folder in [ROOT/'cloud/backend/app',ROOT/'cloud/web/dist']:
        for q in folder.rglob('*'):
            if q.is_file() and '__pycache__' not in q.parts:
                rel=(Path('backend/app')/q.relative_to(folder)) if folder.name=='app' else (Path('web/dist')/q.relative_to(folder))
                sources[rel.as_posix()]=base64.b64encode(q.read_bytes()).decode()
    package={'scope':SCOPE,'tx':tx,'base':base,'origin':origin,'snapshot':snapshot,
             'config':{k:base64.b64encode(v).decode() for k,v in config.items()},'sources':sources,
             'new_acl_base64':base64.b64encode(raw_acl+acl_delta).decode(),
             'new_password_file_base64':base64.b64encode(raw_pass+(b'' if raw_pass.endswith(b'\n') else b'\n')+new_hashes).decode(),
             'test_namespace':'mpm/v1/GW-B5-001/#','negative_namespace':DENY,'HUP_limit':1,'setup_limit_s':180,'smoke_limit_s':120}
    blob=encode(package);write_private(private/'deployment-package-private.json',blob)
    result={'status':'PREPARED_NOT_EXECUTED','package_sha256':sha(blob),'tx':tx,'scope':SCOPE,
            'formal_services_match_G0':True,'formal_config_and_ACL_match_G0':True,'wrapper_sha256':WRAPPER_SHA,
            'loopback_port_free':True,'versions_match_frozen_B5':True,
            'minimal_patch':{'ACL_append_sha256':sha(acl_delta),'new_ACL_sha256':sha(raw_acl+acl_delta),
                            'new_password_file_sha256':sha(base64.b64decode(package['new_password_file_base64']))},
            'actual_paths_private_only':True,'config_sha256':{k:sha(v) for k,v in config.items()},
            'source_files_sha256':{k:sha(base64.b64decode(v)) for k,v in sources.items()},
            'new_OS_role':'b5-monitor_SYSTEM_LOCKED_NO_LOGIN','test_service_lifetime_seconds':21600,
            'cloud_write_operations':0,'board_operations':0,'HUP_sent':0,'exit_code':0}
    evidence=ROOT/'node-b/evidence/B5-G1';evidence.mkdir(exist_ok=True)
    (evidence/'prepare.json').write_bytes(encode(result));print(json.dumps(result));return 0


def authorize(a, package, raw_package):
    if not (a.get('enabled') is True and a.get('owner_approved') is True and a.get('scope')==SCOPE):
        raise ValueError('G1_OWNER_AUTH_REQUIRED')
    if a.get('package_sha256')!=sha(raw_package) or a.get('tx')!=package['tx']:
        raise ValueError('G1_PACKAGE_BINDING')
    if a.get('tool_sha256')!=sha(Path(__file__).read_bytes()):raise ValueError('G1_TOOL_BINDING')
    if not time.time()<a.get('expires_unix',0)<=time.time()+3600:raise ValueError('G1_AUTH_EXPIRED')
    if package.get('HUP_limit')!=1 or package.get('smoke_limit_s')!=120 or package.get('negative_namespace')!=DENY:
        raise ValueError('G1_SCOPE_LIMITS')
    if a.get('rollback_enabled') is not False:raise ValueError('G1_ROLLBACK_NOT_AUTHORIZED')
    return True


def remote_apply(P):
    import base64,hashlib,json,os,pwd,re,subprocess,time
    from pathlib import Path
    started=time.monotonic();events=[]
    def require(ok,why):
        if not ok:raise ValueError(why)
    def digest(b):return hashlib.sha256(b).hexdigest()
    def run(args,timeout=12):
        require(time.monotonic()-started<170,'SETUP_TIME_BUDGET')
        r=subprocess.run(args,capture_output=True,text=True,timeout=timeout)
        events.append({'operation':args[0:2],'exit_code':r.returncode})
        if (Path(P['base'])/'before-private').is_dir():
            folder=Path(P['base'])/'before-private'
            index=str(len(events))
            for suffix,data in [('stdout',r.stdout),('stderr',r.stderr)]:
                file=folder/('command-'+index+'-'+suffix+'-private.txt');file.write_text(data);file.chmod(0o600)
            with (folder/'command-receipts-private.jsonl').open('a') as f:f.write(json.dumps(events[-1])+'\n')
        if r.returncode:raise ValueError('SETUP_COMMAND_FAILED')
        return r.stdout
    def pid(name):return int(run(['systemctl','show',name,'-p','MainPID','--value']).strip())
    S=P['snapshot'];base=Path(P['base'])
    require(re.fullmatch(r'g1a-[0-9a-f]{10}',P['tx']) is not None,'TX_FORMAT')
    require(base==Path('/opt/medical-monitor-b5')/P['tx'],'BASE_SCOPE')
    require(not base.exists(),'TX_ALREADY_EXISTS')
    for name,meta in S['files'].items():
        path=Path(name);require(path.is_file() and digest(path.read_bytes())==meta['sha256'],'SOURCE_OR_BACKUP_DRIFT')
    for name,meta in S['units'].items():require(pid(name)==meta['pid'],'FORMAL_MAINPID_DRIFT')
    require(not run(['ss','-H','-ltn','sport','=',':18775']).strip(),'PORT_OCCUPIED')
    require(digest(Path('/opt/medical-monitor/current/deploy/broker_logging.py').read_bytes())==
            'e9f215332b5d6822984f4bf7f19d3b97a242eb897e5c97fe7ba9ea48608b1340','WRAPPER_DRIFT')
    try:pwd.getpwnam('b5-monitor')
    except KeyError:pass
    else:raise ValueError('OS_ROLE_ALREADY_EXISTS')
    for name in [S['acl_path'],S['password_path']]:require(not Path(name).is_symlink(),'AUTH_PATH_SYMLINK')
    # 先封存完整受影响原件；随后任何失败只保留，不自动恢复或继续第二次HUP。
    base.mkdir(parents=True,mode=0o750);backup=base/'before-private';backup.mkdir(mode=0o700)
    metadata={}
    for index,(name,meta) in enumerate(S['files'].items()):
        target=backup/(str(index)+'.bin');target.write_bytes(Path(name).read_bytes());target.chmod(0o600)
        metadata[str(index)]={'path':name,'sha256':meta['sha256'],'mode':meta['mode'],'uid':meta['uid'],'gid':meta['gid']}
    (backup/'metadata-private.json').write_text(json.dumps(metadata));(backup/'metadata-private.json').chmod(0o600)
    run(['useradd','--system','--user-group','--no-create-home','--shell','/usr/sbin/nologin','b5-monitor'])
    role=pwd.getpwnam('b5-monitor')
    os.chown(base,0,role.pw_gid)
    for rel in ['backend/app','web/dist/assets','config','run','logs/backend','nginx']:
        directory=base/rel;directory.mkdir(parents=True,exist_ok=True)
    for directory in [q for q in base.rglob('*') if q.is_dir() and backup not in q.parents and q!=backup]:
        directory.chmod(0o750);os.chown(directory,role.pw_uid,role.pw_gid)
    for rel,content in P['sources'].items():
        require(rel.startswith(('backend/app/','web/dist/')) and '..' not in Path(rel).parts,'SOURCE_SCOPE')
        target=base/rel;target.write_bytes(base64.b64decode(content));target.chmod(0o640);os.chown(target,role.pw_uid,role.pw_gid)
    config=P['config']
    for name in ['backend.json','backend.env','nginx.conf']:
        target=base/'config'/name;target.write_bytes(base64.b64decode(config[name]));target.chmod(0o600)
        if name=='backend.json':os.chown(target,role.pw_uid,role.pw_gid)
    for unit in ['backend','tls']:
        name='medical-monitor-b5-'+P['tx']+'-'+unit+'.service'
        target=Path('/etc/systemd/system')/name;require(not target.exists(),'UNIT_ALREADY_EXISTS')
        target.write_bytes(base64.b64decode(config[unit+'.service']));target.chmod(0o644)
    run(['/usr/sbin/nginx','-t','-p',str(base/'nginx')+'/', '-c',str(base/'config/nginx.conf')])
    # 最小补丁仅追加两条新角色；逐字节保留原正式账户/ACL前缀与权限。
    for key,field in [('acl_path','new_acl_base64'),('password_path','new_password_file_base64')]:
        path=Path(S[key]);old=path.read_bytes();new=base64.b64decode(P[field]);require(new.startswith(old),'FORMAL_AUTH_PREFIX_CHANGED')
        meta=S['files'][str(path)];require(digest(old)==meta['sha256'],'AUTH_DRIFT_BEFORE_COMMIT')
        temp=path.with_name(path.name+'.'+P['tx']);require(not temp.exists(),'AUTH_TEMP_EXISTS')
        temp.write_bytes(new);os.chown(temp,meta['uid'],meta['gid']);temp.chmod(meta['mode']);os.replace(temp,path)
    require(pid('medical-monitor-mqtt.service')==S['units']['medical-monitor-mqtt.service']['pid'],'HUP_PID_DRIFT')
    (base/'HUP-intent-private.json').write_text(json.dumps({'count':1,'pid':S['units']['medical-monitor-mqtt.service']['pid']}))
    run(['systemctl','kill','--kill-whom=main','--signal=HUP','medical-monitor-mqtt.service'])
    run(['systemctl','daemon-reload'])
    own={}
    for unit in ['backend','tls']:
        name='medical-monitor-b5-'+P['tx']+'-'+unit+'.service';run(['systemctl','start',name],timeout=20)
        own[unit]={'unit':name,'pid':pid(name),'start_exit_code':0}
    formal={name:pid(name) for name in S['units']}
    require(all(formal[name]==v['pid'] for name,v in S['units'].items()),'FORMAL_PROCESS_CHANGED')
    preserved={name:digest(Path(name).read_bytes())==meta['sha256'] for name,meta in S['files'].items()
               if name not in [S['acl_path'],S['password_path']]}
    require(all(preserved.values()),'FORMAL_CONFIG_CHANGED')
    result={'status':'DEPLOYED_ONCE_PENDING_SMOKE','HUP_count':1,'own_services':own,'formal_pids_unchanged':True,
            'formal_unaffected_config_hashes_unchanged':True,'new_OS_role':'b5-monitor','no_login_shell':True,
            'elapsed_s':time.monotonic()-started,'service_max_residency_s':21600,'events':events,
            'cloud_rollback_performed':False,'setup_exit_code':0,'created_utc_epoch':time.time()}
    (base/'deployment-receipt-private.json').write_text(json.dumps(result));(base/'deployment-receipt-private.json').chmod(0o600)
    return result


def apply(authorization):
    private=Path(json.loads((ROOT/'node-b/build/b5-g1-private-pointer.json').read_text())['base'])
    a=json.loads(authorization.read_bytes())
    name=a.get('package_filename','deployment-package-private.json')
    if Path(name).name!=name:raise ValueError('PACKAGE_FILENAME')
    raw=(private/name).read_bytes();package=json.loads(raw);authorize(a,package,raw)
    write_private(private/'G1-apply-started-private.json',encode({'tx':package['tx'],'authorization_sha256':sha(authorization.read_bytes())}))
    code=inspect.getsource(remote_apply)+'\nimport json\nprint(json.dumps(remote_apply(v["package"])))\n'
    write_private(private/'apply-executed-private.py',code.encode())
    message=encode({'script':code,'package':package})
    loader="import sys,json;v=json.load(sys.stdin);exec(v['script'])"
    try:
        r=subprocess.run(['ssh','-o','BatchMode=yes','-o','StrictHostKeyChecking=yes','-o','ConnectTimeout=12','tencent-codex',
                          'sudo -n timeout 180s python3 -c '+repr(loader)],input=message,capture_output=True,timeout=200)
    except subprocess.TimeoutExpired as e:
        write_private(private/'apply-timeout-stdout-private.bin',e.stdout or b'')
        write_private(private/'apply-timeout-stderr-private.bin',e.stderr or b'')
        result={'status':'STOP_APPLY_TIMEOUT_NO_RETRY','exit_code':124,'cloud_rollback_performed':False}
        (ROOT/'node-b/evidence/B5-G1/apply.json').write_bytes(encode(result));print(json.dumps(result));return 124
    write_private(private/'apply-stdout-private.json',r.stdout);write_private(private/'apply-stderr-private.bin',r.stderr)
    result=json.loads(r.stdout) if r.returncode==0 else {'status':'STOP_APPLY_FAILED_NO_RETRY','HUP_count':'SEE_PRIVATE_INTENT','cloud_rollback_performed':False}
    result.update(ssh_exit_code=r.returncode,scope=SCOPE,tx=package['tx'],package_sha256=sha(raw),
                  tool_sha256=sha(Path(__file__).read_bytes()),stdout_sha256=sha(r.stdout))
    (ROOT/'node-b/evidence/B5-G1/apply.json').write_bytes(encode(result));print(json.dumps(result));return r.returncode


def main():
    p=argparse.ArgumentParser();p.add_argument('--prepare',action='store_true');p.add_argument('--apply',action='store_true');p.add_argument('--authorization',type=Path);a=p.parse_args()
    try:
        if a.prepare:return prepare()
        if a.apply and a.authorization:return apply(a.authorization)
        raise ValueError('NO_AUTHORIZED_ACTION')
    except Exception as e:
        reason=str(e) if isinstance(e,(ValueError,AssertionError)) and str(e).replace('_','').isalnum() else type(e).__name__
        print(json.dumps({'status':'STOP','reason':reason,'exit_code':1}));return 1


if __name__=='__main__':raise SystemExit(main())
