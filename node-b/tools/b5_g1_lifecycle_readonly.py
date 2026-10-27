"""G1次日一次只读到期检查：不启停服务、不发MQTT、不访问实板。"""
import hashlib
import inspect
import json
from pathlib import Path
import subprocess
from datetime import datetime, timezone

from b5_g0_readonly import ROOT, new_private, write_private


def remote_lifecycle(I):
    import datetime,hashlib,json,os,subprocess
    from pathlib import Path
    from zoneinfo import ZoneInfo
    def query(args):
        r=subprocess.run(args,capture_output=True,text=True,timeout=8)
        if r.returncode:raise ValueError('READONLY_QUERY_FAILED')
        return r.stdout.strip()
    link=Path('/etc/localtime').resolve().as_posix()
    zone=link.split('/zoneinfo/',1)[1] if '/zoneinfo/' in link else None
    def utc(value):
        if not value or not zone:return None
        try:
            fields=value.split();d=datetime.datetime.fromisoformat(fields[1]+'T'+fields[2])
            return d.replace(tzinfo=ZoneInfo(zone)).astimezone(datetime.timezone.utc).isoformat()
        except (ValueError,IndexError):return None
    def status(name):
        props=['ActiveState','SubState','Result','MainPID','Restart','RuntimeMaxUSec',
               'ActiveEnterTimestamp','ActiveEnterTimestampMonotonic',
               'InactiveEnterTimestamp','InactiveEnterTimestampMonotonic',
               'ExecMainExitTimestamp','ExecMainStatus','ExecMainCode']
        args=['systemctl','show',name]
        for prop in props:args+=['-p',prop]
        text=query(args);s=dict(x.split('=',1) for x in text.splitlines() if '=' in x)
        s['InactiveEnterUTC']=utc(s.get('InactiveEnterTimestamp',''))
        s['ExecMainExitUTC']=utc(s.get('ExecMainExitTimestamp',''))
        s['ActiveEnterUTC']=utc(s.get('ActiveEnterTimestamp',''))
        start=int(s.get('ActiveEnterTimestampMonotonic','0'));stop=int(s.get('InactiveEnterTimestampMonotonic','0'))
        s['elapsed_active_to_inactive_seconds']=(stop-start)/1e6 if start and stop>=start else None
        return s
    own={name:status(unit) for name,unit in I['own_units'].items()}
    formal={name:status(name) for name in I['formal_units']}
    hashes={}
    for label,entry in I['config_references'].items():
        p=Path(entry['path']);value=hashlib.sha256(p.read_bytes()).hexdigest() if p.is_file() else None
        hashes[label]={'sha256':value,'matches_last_approved_G1':value==entry['sha256'],'exists':p.is_file()}
    acl=Path(I['acl_path']).read_text();password=Path(I['password_path']).read_bytes()
    users={row.split(':',1)[0] for row in password.decode().splitlines() if ':' in row}
    roles={};current=None
    for row in acl.splitlines():
        parts=row.strip().split()
        if not parts or parts[0].startswith('#'):continue
        if parts[0]=='user' and len(parts)==2:current=parts[1]
        elif parts[0] in ('topic','pattern') and current in ('b5-gateway','b5-observer'):
            roles.setdefault(current,[]).append(parts)
    still={'publisher_account_exists':'b5-gateway' in users,'observer_account_exists':'b5-observer' in users,
           'publisher_exact_write_only_rule':roles.get('b5-gateway')==[['topic','write','mpm/v1/GW-B5-001/#']],
           'observer_exact_read_only_rule':roles.get('b5-observer')==[['topic','read','mpm/v1/GW-B5-001/#']]}
    listeners={}
    for port in (18775,8884):
        listeners[str(port)]=bool(query(['ss','-H','-ltn','sport','=',':'+str(port)]))
    timeout_stop=all(s.get('Result')=='timeout' and s.get('MainPID')=='0' and s.get('Restart')=='no'
                     and s.get('RuntimeMaxUSec')=='6h' and s.get('ActiveState') in ('inactive','failed') for s in own.values())
    return {'snapshot_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'server_timezone':zone,
            'own_units':own,'formal_units':formal,'config_sha256':hashes,'test_identity_ACL_residual':still,
            'listeners':listeners,'both_test_units_stopped_with_RuntimeMax_timeout':timeout_stop,
            'formal_services_active':all(s.get('ActiveState')=='active' and s.get('MainPID') not in ('0',None) for s in formal.values()),
            'formal_service_PIDs_match_last_G1':all(formal[n].get('MainPID')==str(pid) for n,pid in I['formal_units'].items()),
            'test_account_cleanup_complete':False,'cloud_mutations':0,'MQTT_connects_or_publishes':0,
            'WSS_sessions':0,'physical_board_access':False,'TLS_private_key_read':False}


def main():
    g1_link=json.loads((ROOT/'node-b/build/b5-g1-private-pointer.json').read_bytes())
    previous=Path(g1_link['base']);P=json.loads((previous/g1_link['package']).read_bytes())
    snapshot=P['snapshot'];inputs={'own_units':{},'formal_units':{},'config_references':{},
                                 'acl_path':snapshot['acl_path'],'password_path':snapshot['password_path']}
    for name in ('backend','tls'):inputs['own_units'][name]='medical-monitor-b5-'+P['tx']+'-'+name+'.service'
    for name,meta in snapshot['units'].items():inputs['formal_units'][name]=meta['pid']
    for number,(path,meta) in enumerate(snapshot['files'].items()):
        if path in (snapshot['acl_path'],snapshot['password_path']):continue
        inputs['config_references']['FORMAL_CONFIG_'+str(number)]={'path':path,'sha256':meta['sha256']}
    for label,key in [('B5_ACL','new_acl_base64'),('B5_PASSWORD_FILE','new_password_file_base64')]:
        import base64
        path=snapshot['acl_path'] if label=='B5_ACL' else snapshot['password_path']
        inputs['config_references'][label]={'path':path,'sha256':hashlib.sha256(base64.b64decode(P[key])).hexdigest()}
    for name in ('backend','tls'):
        inputs['config_references']['B5_'+name+'_UNIT']={
            'path':'/etc/systemd/system/'+inputs['own_units'][name],
            'sha256':hashlib.sha256(base64.b64decode(P['config'][name+'.service'])).hexdigest()}
    private=new_private();stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    pointer=ROOT/'node-b/build'/('b5-g1-lifecycle-'+stamp+'-private-pointer.json')
    with pointer.open('xb') as f:f.write(json.dumps({'base':str(private)}).encode())
    code=inspect.getsource(remote_lifecycle)+'\nprint(json.dumps(remote_lifecycle(v["inputs"])))\n'
    write_private(private/'lifecycle-executed-private.py',code.encode())
    write_private(private/'lifecycle-inputs-private.json',json.dumps(inputs,indent=2).encode())
    loader="import sys,json;v=json.load(sys.stdin);exec(v['script'])"
    try:
        r=subprocess.run(['ssh','-o','BatchMode=yes','-o','StrictHostKeyChecking=yes','-o','ConnectTimeout=12','tencent-codex',
                          'sudo -n timeout 45s python3 -c '+repr(loader)],
                         input=json.dumps({'script':code,'inputs':inputs}).encode(),capture_output=True,timeout=55)
        write_private(private/'lifecycle-stdout-private.json',r.stdout)
        write_private(private/'lifecycle-stderr-private.bin',r.stderr)
        result=json.loads(r.stdout) if r.returncode==0 else {'status':'STOP_READONLY_QUERY_FAILED'}
        code_value=r.returncode
    except subprocess.TimeoutExpired as e:
        write_private(private/'lifecycle-timeout-stdout-private.bin',e.stdout or b'')
        write_private(private/'lifecycle-timeout-stderr-private.bin',e.stderr or b'')
        result={'status':'STOP_READONLY_TIMEOUT'};code_value=124
    result.update(ssh_exit_code=code_value,actual_SSH_queries=1,retries=0,
                  source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
    if (private/'lifecycle-stdout-private.json').exists():
        result['raw_stdout_sha256']=hashlib.sha256((private/'lifecycle-stdout-private.json').read_bytes()).hexdigest()
    write_private(private/'lifecycle-summary-private.json',json.dumps(result,indent=2).encode())
    evidence=ROOT/'node-b/evidence/B5-G2B-PREP';evidence.mkdir(exist_ok=True)
    target=evidence/('cloud-lifecycle-'+stamp+'.json')
    with target.open('xb') as f:f.write((json.dumps(result,indent=2)+'\n').encode())
    print(json.dumps({'receipt':target.relative_to(ROOT).as_posix(),'private_pointer':pointer.relative_to(ROOT).as_posix(),**result}))
    return code_value


if __name__=='__main__':raise SystemExit(main())
