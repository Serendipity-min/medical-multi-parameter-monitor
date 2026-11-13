"""G1-RESUME专用：仅现有两个测试unit；默认计划，真实启动须独立授权。"""
import argparse
import base64
import hashlib
import inspect
import json
from pathlib import Path
import subprocess
import sys
import time

import b5_g1_lifecycle_readonly as lifecycle
from b5_g0_readonly import write_private
from b4_recovery import protected, require

ROOT = Path(__file__).resolve().parents[2]
SCOPE = 'B5_G1_RESUME_EXISTING_TEST_UNITS_ONLY'
CARD = ROOT/'node-b/docs/AUTH-B5-G1-RESUME-001-R2.md'
PACKAGE_SHA = 'dcee1658be5ce4db2531975069441444a0f50078828321a3e978a8352b520db0'
sha = lambda data: hashlib.sha256(data).hexdigest()
remote_lifecycle = lifecycle.remote_lifecycle


def bindings():
    return {n:sha((ROOT/'node-b/tools'/n).read_bytes()) for n in
            ('b5_g1_resume.py','b5_g1_lifecycle_readonly.py','b5_g0_readonly.py','b4_recovery.py')}


def build_inputs(P):
    S=P['snapshot']; base=P['base']
    I={'own_units':{n:'medical-monitor-b5-'+P['tx']+'-'+n+'.service' for n in ('backend','tls')},
       'formal_units':{n:m['pid'] for n,m in S['units'].items()}, 'config_references':{},
       'acl_path':S['acl_path'],'password_path':S['password_path'],
       'server_name':S['backend']['host'],'mode_references':[]}
    for index,(path,meta) in enumerate(S['files'].items()):
        if path in (S['acl_path'],S['password_path']):continue
        I['config_references']['FORMAL_'+str(index)]={'path':path,'sha256':meta['sha256']}
    for name,field,path in [('ACL','new_acl_base64',S['acl_path']),('PASSWORD','new_password_file_base64',S['password_path'])]:
        I['config_references'][name]={'path':path,'sha256':sha(base64.b64decode(P[field]))}
        meta=S['files'][path]
        I['mode_references'].append({'path':path,'mode':meta['mode'],'uid':meta['uid'],'gid':meta['gid']})
    for name,data in P['config'].items():
        path='/etc/systemd/system/'+I['own_units'][name.split('.')[0]] if name.endswith('.service') else base+'/config/'+name
        I['config_references']['B5_CONFIG_'+name]={'path':path,'sha256':sha(base64.b64decode(data))}
        I['mode_references'].append({'path':path,'mode':0o644 if name.endswith('.service') else 0o600,
                                    'owner':'b5-monitor' if name=='backend.json' else 'root'})
    for index,(relative,data) in enumerate(P['sources'].items()):
        require(relative.startswith(('backend/app/','web/dist/')) and '..' not in Path(relative).parts,'RESUME_SOURCE_PATH')
        path=base+'/'+relative
        I['config_references']['B5_SOURCE_'+str(index)]={'path':path,'sha256':sha(base64.b64decode(data))}
        I['mode_references'].append({'path':path,'mode':0o640,'owner':'b5-monitor'})
    return I


def authorize(a):
    require(a.get('enabled') is True and a.get('owner_approved') is True and a.get('scope') == SCOPE,
            'RESUME_OWNER_SCOPE_REQUIRED')
    require(a.get('tools_sha256') == bindings() and a.get('card_sha256') == sha(CARD.read_bytes()), 'RESUME_TOOL_CARD_DRIFT')
    require(a.get('expires_unix',0) > time.time() and a.get('timeout_s') == 300
            and a.get('SSH_sessions') == 1 and a.get('retries') == 0, 'RESUME_TIME_BOUND')
    require(a.get('Broker_HUP_ACL_config_writes') == 0 and a.get('B5START') == 0, 'RESUME_SCOPE_DENIED')
    raw=protected(Path(a['inputs']),False).read_bytes()
    require(sha(raw)==a.get('inputs_sha256'), 'RESUME_INPUT_DRIFT')
    inputs=json.loads(raw)
    package=protected(Path(a['package']),False).read_bytes()
    require(sha(package)==a.get('package_sha256')==PACKAGE_SHA,'RESUME_PACKAGE_DRIFT')
    P=json.loads(package); tx=P['tx']
    require(inputs==build_inputs(P),'RESUME_FULL_INPUT_BINDING')
    require(inputs['own_units']=={n:'medical-monitor-b5-'+tx+'-'+n+'.service' for n in ('backend','tls')},
            'RESUME_TEST_UNITS_ONLY')
    require(inputs.get('server_name')==P['snapshot']['backend']['host'], 'RESUME_TLS_IDENTITY')
    require(a.get('G2B_receipt_sha256')==sha((ROOT/'node-b/evidence/B5-G2B-SECTOR3-01/result.json').read_bytes()),
            'RESUME_G2B_RECEIPT_DRIFT')
    receipt=json.loads((ROOT/'node-b/evidence/B5-G2B-SECTOR3-01/result.json').read_bytes())
    require(receipt.get('status')=='SECTOR3_FULL_VERIFY_AND_DISARMED_BOOT_PASS' and receipt.get('exit_code')==0,
            'RESUME_G2B_NOT_PASS')
    protected(Path(a['output']).parent,False)
    return inputs


def remote_resume(I):
    import json,socket,ssl,subprocess,time,pwd,stat
    from pathlib import Path
    started=time.monotonic();actions=[]
    def require(ok,why):
        if not ok:raise ValueError(why)
    def common(s):
        require(s.get('formal_services_active') and s.get('formal_service_PIDs_match_last_G1'),'RESUME_FORMAL_CHANGED')
        require(all(x['matches_last_approved_G1'] for x in s['config_sha256'].values()),'RESUME_CONFIG_DRIFT')
        require(all(s['test_identity_ACL_residual'].values()) and not s['listeners']['8884'],'RESUME_ACL_OR_PORT')
    def tls_health():
        context=ssl.create_default_context()
        with socket.create_connection(('127.0.0.1',18775),timeout=5) as raw:
            with context.wrap_socket(raw,server_hostname=I['server_name']) as conn:
                conn.sendall(('GET /medical-monitor/api/health HTTP/1.0\r\nHost: '+I['server_name']+
                              ':18775\r\nConnection: close\r\n\r\n').encode())
                data=b''
                while True:
                    part=conn.recv(4096)
                    if not part:break
                    data+=part;require(len(data)<=65536,'RESUME_HEALTH_TOO_LARGE')
                head,body=data.split(b'\r\n\r\n',1)
                require(head.split(b'\r\n')[0].split()[1]==b'200','RESUME_HEALTH_HTTP')
                health=json.loads(body)
                return health.get('status')=='ok' and health.get('mqtt_connected') is True
    result={'status':'STOP','exit_code':1,'automatic_retry_or_rollback':False,'service_start_actions':actions,
            'Broker_HUP_ACL_config_writes':0,'B5START':0,'MQTT_test_publications':0,'WSS_sessions':0}
    try:
        require(set(I['own_units'])=={'backend','tls'},'RESUME_UNIT_COUNT')
        require(all(u.startswith('medical-monitor-b5-') and u.endswith('-'+n+'.service')
                    for n,u in I['own_units'].items()),'RESUME_UNIT_SCOPE')
        for ref in I['mode_references']:
            path=Path(ref['path']);meta=path.stat()
            require(not path.is_symlink() and stat.S_ISREG(meta.st_mode)
                    and stat.S_IMODE(meta.st_mode)==ref['mode'],'RESUME_FILE_PERMISSION')
            if 'owner' in ref: require(pwd.getpwuid(meta.st_uid).pw_name==ref['owner'],'RESUME_FILE_OWNER')
            else: require((meta.st_uid,meta.st_gid)==(ref['uid'],ref['gid']),'RESUME_FILE_OWNER')
        before=remote_lifecycle(I);common(before)
        require(before['both_test_units_stopped_with_RuntimeMax_timeout'] and not before['listeners']['18775'],
                'RESUME_NOT_STOPPED_OR_PORT_OCCUPIED')
        result['before']=before
        for n in ('backend','tls'):
            require(time.monotonic()-started<60,'RESUME_START_BUDGET')
            actions.append({'service':n,'attempt':1})
            r=subprocess.run(['systemctl','start',I['own_units'][n]],capture_output=True,timeout=20)
            actions[-1]['exit_code']=r.returncode
            require(r.returncode==0,'RESUME_START_FAILED')
        # 只读健康轮询，不重复start、不发测试流。
        healthy=False
        while time.monotonic()-started<90:
            try:
                healthy=tls_health()
            except (OSError,ValueError):
                healthy=False
            if healthy:break
            time.sleep(1)
        require(healthy,'RESUME_TLS_BACKEND_HEALTH_NOT_READY')
        after=remote_lifecycle(I);common(after);result['after']=after
        require(after['listeners']['18775'],'RESUME_LOOPBACK_NOT_LISTENING')
        require(all(x.get('ActiveState')=='active' and x.get('MainPID') not in ('0',None)
                and x.get('Restart')=='no' and x.get('RuntimeMaxUSec')=='6h' for x in after['own_units'].values()),
                'RESUME_UNIT_LIFETIME_OR_STATE')
        result.update(status='G1_EXISTING_TEST_BACKEND_TLS_RESUME_PASS',exit_code=0,
                      TLS_CA_SNI_checked=True,independent_Backend_health_and_MQTT_subscription_ready=True)
    except BaseException as e:
        reason=str(e)
        result.update(error_type=type(e).__name__,reason=reason if reason.startswith('RESUME_') and reason.replace('_','').isalnum() else 'PRIVATE_ERROR_SUPPRESSED')
    result['elapsed_s']=time.monotonic()-started
    return result


def execute(auth_path):
    started=time.monotonic()
    raw=protected(auth_path,False).read_bytes();a=json.loads(raw);inputs=authorize(a)
    out=Path(a['output']);require(not out.exists(),'RESUME_OUTPUT_EXISTS')
    write_private(auth_path.with_suffix('.used'),(json.dumps({'authorization_sha256':sha(raw),'started_unix':time.time()})+'\n').encode())
    out.mkdir(exist_ok=False);protected(out,False)
    source=inspect.getsource(remote_lifecycle)+'\n'+inspect.getsource(remote_resume)+'\nprint(json.dumps(remote_resume(v["inputs"])))\n'
    write_private(out/'executed-remote-private.py',source.encode())
    loader="import sys,json;v=json.load(sys.stdin);exec(v['script'])"
    command=['ssh','-o','BatchMode=yes','-o','StrictHostKeyChecking=yes','-o','ConnectTimeout=12',
             'tencent-codex','sudo -n timeout -s KILL 280s python3 -c '+repr(loader)]
    process=subprocess.Popen(command,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    try:
        stdout,stderr=process.communicate(json.dumps({'script':source,'inputs':inputs}).encode(),
                                         timeout=max(.1,300-(time.monotonic()-started)))
        write_private(out/'SSH-stdout-private.json',stdout);write_private(out/'SSH-stderr-private.bin',stderr)
        result=json.loads(stdout) if process.returncode==0 else {'status':'STOP_SSH','exit_code':1}
        result['SSH_exit_code']=process.returncode
    except subprocess.TimeoutExpired:
        process.kill();stdout,stderr=process.communicate(timeout=5)
        write_private(out/'SSH-timeout-stdout-private.bin',stdout);write_private(out/'SSH-timeout-stderr-private.bin',stderr)
        result={'status':'STOP_SUPERVISOR_TIMEOUT','exit_code':124,'remote_state':'UNKNOWN_NO_RETRY_OR_RECONNECT'}
    result.update(total_elapsed_s=time.monotonic()-started,authorization_sha256=sha(raw),automatic_retry_or_rollback=False)
    write_private(out/'receipt-private.json',(json.dumps(result,indent=2)+'\n').encode())
    print(json.dumps({'status':result['status'],'exit_code':result['exit_code']}))
    return result['exit_code']


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--execute',action='store_true')
    parser.add_argument('--authorization',type=Path);a=parser.parse_args()
    if not a.execute:
        print(json.dumps({'enabled':False,'owner_approved':False,'scope':SCOPE,'tools_sha256':bindings(),
                          'timeout_s':300,'SSH_sessions':1,'service_start_max_each':1,'retries':0,
                          'Broker_HUP_ACL_config_writes':0,'B5START':0}));return 0
    try:
        require(a.authorization is not None,'RESUME_AUTH_REQUIRED')
        return execute(a.authorization)
    except BaseException as e:
        print(json.dumps({'status':'STOP','exit_code':1,'error_type':type(e).__name__}));return 1

if __name__=='__main__':raise SystemExit(main())
