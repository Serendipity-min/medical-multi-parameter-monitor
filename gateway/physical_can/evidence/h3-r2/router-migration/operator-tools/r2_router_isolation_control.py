# 路由器窗口使用独立引用及证据目录，保留此前热点原始记录。
"""已批准C窗口的隔离服务/现场单地址防火墙；脚本经stdin运行，不写连接原文。"""
from pathlib import Path
import hashlib,inspect,json,subprocess,sys
ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT))


def remote(action,want,expected_credentials,tag):
    import hashlib,ipaddress,json,os,pwd,subprocess,time
    from pathlib import Path
    state=Path('/var/lib/medical-monitor-p6/h3-20261019')
    runtime=Path('/opt/medical-monitor-h3/releases/runtime-37808287a557')
    chain='MPH3R2C';nat_chain='MPH3R2N'
    broker_unit='medical-monitor-h3-r2c-broker-'+tag;backend_unit='medical-monitor-h3-r2c-backend-'+tag
    expiry_unit='medical-monitor-h3-r2c-expiry-'+tag
    owned=state/('r2c-'+tag);proof_path=owned/'proof.json'
    broker_conf=Path('/opt/medical-monitor-h3/broker')/('r2c-'+tag+'.conf')
    def run(cmd,check=True):
        r=subprocess.run(cmd,capture_output=True,text=True)
        if check and r.returncode:raise RuntimeError('COMMAND_FAILED_'+Path(cmd[0]).name)
        return r
    def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
    def formal():
        frozen=json.loads(Path('/opt/medical-monitor-h3/formal/20261020T034945Z/plan.json').read_text())
        units={u:{'pid':run(['systemctl','show',u,'-p','MainPID','--value']).stdout.strip(),
                  'state':run(['systemctl','show',u,'-p','ActiveState','--value']).stdout.strip()} for u in frozen['original_services']}
        return {'services':units,'services_match':units==frozen['original_services'],
                'files_match':all(sha(p)==h for p,h in frozen['original_hashes'].items()),
                'web_match':sha('/opt/medical-monitor/current/web/dist/index.html')==frozen['previous_web_index_sha256']}
    # 到期/正常清理使用同一固定范围函数；不含源地址，不触碰其他INPUT规则或生产单元。
    cleanup_code='''import hashlib,json,subprocess
from pathlib import Path
p=Path(PROOF_PATH)
d=json.loads(p.read_text())
def run(args):return subprocess.run(args,capture_output=True,text=True)
for unit in d['units']:run(['systemctl','stop',unit])
if 'nat_chain' in d:
 nc=d['nat_chain'];nr=run(['iptables','-t','nat','-S',nc])
 if nr.returncode==0:
  if hashlib.sha256(nr.stdout.encode()).hexdigest()!=d['nat_chain_sha256']:raise RuntimeError('OWNED_NAT_CHAIN_CHANGED_STOP')
  if run(['iptables','-t','nat','-D','OUTPUT','-p','tcp','--dport','8884','-j',nc]).returncode:raise RuntimeError('OWNED_NAT_JUMP_REMOVE_FAILED')
  if run(['iptables','-t','nat','-F',nc]).returncode or run(['iptables','-t','nat','-X',nc]).returncode:raise RuntimeError('OWNED_NAT_REMOVE_FAILED')
chain=d['chain']
r=run(['iptables','-S',chain])
if r.returncode==0:
 if hashlib.sha256(r.stdout.encode()).hexdigest()!=d['chain_sha256']:raise RuntimeError('OWNED_CHAIN_CHANGED_STOP')
 r=run(['iptables','-D','INPUT','-p','tcp','--dport','8884','-j',chain])
 if r.returncode:raise RuntimeError('OWNED_JUMP_REMOVE_FAILED')
 if run(['iptables','-F',chain]).returncode or run(['iptables','-X',chain]).returncode:raise RuntimeError('OWNED_CHAIN_REMOVE_FAILED')
for name,digest in d['owned_files'].items():
 f=Path(name)
 if f.exists():
  if hashlib.sha256(f.read_bytes()).hexdigest()!=digest:raise RuntimeError('OWNED_FILE_CHANGED_STOP')
  f.unlink()
'''.replace('PROOF_PATH',repr(str(proof_path)))
    if action=='stop':
        if not proof_path.is_file():raise RuntimeError('OWNED_PROOF_REQUIRED')
        run(['/usr/bin/python3','-c',cleanup_code])
        run(['systemctl','stop',expiry_unit+'.timer'],False)
        d=json.loads(proof_path.read_text())
        now=run(['iptables','-S']).stdout
        status=formal()
        return {'action':'stop','exit_code':0,'owned_services_stopped':all(run(['systemctl','show',u,'-p','ActiveState','--value']).stdout.strip()!='active' for u in d['units']),
                'owned_chain_absent':run(['iptables','-S',chain],False).returncode!=0,
                'input_rules_restored':hashlib.sha256(now.encode()).hexdigest()==d['iptables_before_sha256'],
                'nat_rules_restored':hashlib.sha256(run(['iptables','-t','nat','-S']).stdout.encode()).hexdigest()==d['nat_before_sha256'],
                'formal':status,'credentials_files_removed':True,'cloud_security_group_modified':False}
    if action!='start':raise RuntimeError('ACTION')
    f=formal()
    if not all(f[k] for k in ('services_match','files_match','web_match')):raise RuntimeError('FORMAL_IDENTITY_CHANGED')
    metadata=json.loads((runtime/'H3_RUNTIME_SOURCE.json').read_text())
    if not all(sha(runtime/p)==h for p,h in metadata['critical_source_sha256'].items()):raise RuntimeError('RUNTIME_MANIFEST_CHANGED')
    if not all((runtime/p).is_file() and sha(runtime/p)==h for p,h in want.items()):raise RuntimeError('BACKEND_SOURCE_MISMATCH')
    for port in (8884,18775):
        if run(['ss','-H','-ltn','sport','=',':'+str(port)]).stdout.strip():raise RuntimeError('ISOLATED_PORT_OCCUPIED')
    if run(['iptables','-S',chain],False).returncode==0:raise RuntimeError('OWNED_CHAIN_OCCUPIED')
    if run(['iptables','-t','nat','-S',nat_chain],False).returncode==0:raise RuntimeError('OWNED_NAT_CHAIN_OCCUPIED')
    for unit in (broker_unit,backend_unit,expiry_unit+'.timer'):
        if run(['systemctl','show',unit,'-p','ActiveState','--value']).stdout.strip()=='active':raise RuntimeError('OWNED_UNIT_OCCUPIED')
    peer=ipaddress.ip_address(os.environ['SSH_CONNECTION'].split()[0])
    if peer.version!=4:raise RuntimeError('IPV4_PEER_REQUIRED')
    gateway=json.loads((state/'gateway.json').read_text());backend=json.loads((state/'backend.json').read_text())
    actual=hashlib.sha256(json.dumps({k:gateway[k] for k in ('host','username','password','client_id')},sort_keys=True).encode()).hexdigest()
    if actual!=expected_credentials or gateway.get('port')!=8884 or backend.get('port')!=8884 or backend.get('username')!='h3-backend':raise RuntimeError('FROZEN_ISOLATED_CREDENTIALS_MISMATCH')
    original_conf=Path('/opt/medical-monitor-h3/broker/mosquitto.conf').read_text()
    if 'listener 8884\n' not in original_conf or 'log_dest none' not in original_conf or 'allow_anonymous false' not in original_conf:raise RuntimeError('ISOLATED_BROKER_POLICY')
    sys=__import__('sys');sys.path.insert(0,str(runtime))
    from cloud.deploy.h3.isolated_server import load_env,store_env
    env=load_env(state/'backend.env')
    if env.get('MONITOR_TESTING') not in (None,'0'):raise RuntimeError('REAL_BACKEND_REQUIRED')
    owned.mkdir(mode=0o700)
    user=pwd.getpwnam('medical-ai');os.chown(owned,user.pw_uid,user.pw_gid)
    backend['client_id']='h3-r2c-backend-'+tag
    config=owned/'backend.json'
    with config.open('x') as output:json.dump(backend,output)
    config.chmod(0o600);os.chown(config,user.pw_uid,user.pw_gid)
    env['MONITOR_MQTT_CONFIG']=str(config)
    environment=owned/'backend.env';store_env(environment,env);os.chown(environment,user.pw_uid,user.pw_gid)
    with broker_conf.open('x') as output:output.write(original_conf.replace('listener 8884\n','listener 8884 0.0.0.0\n'))
    broker_conf.chmod(0o640);os.chown(broker_conf,0,pwd.getpwnam('mosquitto').pw_gid)
    before=hashlib.sha256(run(['iptables','-S']).stdout.encode()).hexdigest()
    nat_before=hashlib.sha256(run(['iptables','-t','nat','-S']).stdout.encode()).hexdigest()
    # 临时链兜底DROP，不能把单个ACCEPT误当成仅允许/32；Broker只监听IPv4。
    run(['iptables','-N',chain]);run(['iptables','-A',chain,'-i','lo','-j','ACCEPT'])
    run(['iptables','-A',chain,'-s',str(peer)+'/32','-j','ACCEPT']);run(['iptables','-A',chain,'-j','DROP'])
    run(['iptables','-I','INPUT','1','-p','tcp','--dport','8884','-j',chain])
    # 只把本机隔离Backend用户到原Broker地址:8884的连接转回环；TLS仍用原host验证。
    # 不新增公网放行来源，不匹配8883，也不改Backend代码或DNS/证书校验。
    import socket
    targets=sorted(set(x[4][0] for x in socket.getaddrinfo(backend['host'],8884,socket.AF_INET,socket.SOCK_STREAM)))
    if len(targets)!=1:raise RuntimeError('SINGLE_ISOLATED_BROKER_TARGET_REQUIRED')
    run(['iptables','-t','nat','-N',nat_chain])
    run(['iptables','-t','nat','-A',nat_chain,'-d',targets[0]+'/32','-p','tcp','--dport','8884','-m','owner','--uid-owner',str(user.pw_uid),'-j','DNAT','--to-destination','127.0.0.1:8884'])
    run(['iptables','-t','nat','-I','OUTPUT','1','-p','tcp','--dport','8884','-j',nat_chain])
    proof={'units':[broker_unit,backend_unit],'chain':chain,
       'chain_sha256':hashlib.sha256(run(['iptables','-S',chain]).stdout.encode()).hexdigest(),
       'iptables_before_sha256':before,'nat_before_sha256':nat_before,'nat_chain':nat_chain,
       'nat_chain_sha256':hashlib.sha256(run(['iptables','-t','nat','-S',nat_chain]).stdout.encode()).hexdigest(),
       'owned_files':{str(p):sha(p) for p in (config,environment,broker_conf)}}
    with proof_path.open('x') as output:json.dump(proof,output)
    try:
        run(['systemd-run','--quiet','--unit='+expiry_unit,'--on-active=45m','/usr/bin/python3','-c',cleanup_code])
        run(['systemd-run','--quiet','--collect','--unit='+broker_unit,'--property=RuntimeMaxSec=2700',
             '/usr/sbin/mosquitto','-c',str(broker_conf)])
        run(['systemd-run','--quiet','--collect','--unit='+backend_unit,'--uid=medical-ai','--gid=medical-ai',
             '--property=WorkingDirectory='+str(runtime/'cloud/backend'),'--property=EnvironmentFile='+str(environment),
             '--property=UMask=0077','--property=NoNewPrivileges=true','--property=RuntimeMaxSec=2700',
             '/opt/medical-monitor-p6/.venv/bin/python','-m','uvicorn','app.main:app','--host','127.0.0.1','--port','18775','--no-access-log','--log-level','warning'])
        import urllib.request
        healthy=None
        for attempt in range(40):
            try:
                with urllib.request.urlopen('http://127.0.0.1:18775/health',timeout=1) as response:healthy=json.load(response)
                if healthy.get('status')=='ok' and healthy.get('mqtt_connected') is True:break
            except OSError:pass
            time.sleep(.25)
        if not healthy or healthy.get('mqtt_connected') is not True:raise RuntimeError('ISOLATED_BACKEND_NOT_READY')
        after=formal()
        if after!=f:raise RuntimeError('FORMAL_CHANGED_DURING_ISOLATION_START')
        return {'action':'start','exit_code':0,'broker_unit':broker_unit,'backend_unit':backend_unit,
            'backend_runtime':runtime.name,'backend_source_commit':metadata.get('source_commit'),
            'backend_current_source_match':True,'backend_health':healthy,'temporary_ipv4_port':8884,
            'source_scope':'LOOPBACK_AND_CURRENT_SSH_PEER_32_ONLY_WITH_DEFAULT_DROP','peer_digest':hashlib.sha256(str(peer).encode()).hexdigest(),
            'backend_local_loopback_dnat':'EXACT_BROKER_IP_PORT8884_AND_SERVICE_UID_ONLY','TLS_hostname_validation_unchanged':True,
            'auto_cleanup_after_seconds':2700,'formal_unchanged':True,'AI_started':False,'real_AI_calls':0,'cloud_security_group_modified':False}
    except BaseException:
        run(['/usr/bin/python3','-c',cleanup_code],False);run(['systemctl','stop',expiry_unit+'.timer'],False)
        raise


def main():
    action=sys.argv[1]
    private=Path('E:/medical-monitor-h3-private')
    ref=json.loads((private/'r2-router-active-window-reference.json').read_text())
    tag=ref.get('isolation_tag',Path(ref['private_dir']).name.removeprefix('r2-c-window-'))
    r=Path(ref['record']).read_bytes();offset=32;values=[]
    for size in (33,65,65,33,65,41):values.append(r[offset:offset+size].split(b'\0')[0].decode('utf-8'));offset+=size
    credentials=hashlib.sha256(json.dumps(dict(zip(('host','username','password','client_id'),values[2:])),sort_keys=True).encode()).hexdigest()
    want={p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in (ROOT/'cloud/backend/app').rglob('*.py')}
    want['cloud/deploy/h3/isolated_server.py']=hashlib.sha256((ROOT/'cloud/deploy/h3/isolated_server.py').read_bytes()).hexdigest()
    code=inspect.getsource(remote)+'\ntry:\n import json\n print(json.dumps(remote('+repr(action)+','+repr(want)+','+repr(credentials)+','+repr(tag)+')))\nexcept Exception as e:\n import json\n print(json.dumps({"exit_code":1,"failure_type":type(e).__name__,"failure_code":str(e) if type(e) is RuntimeError else "SUPPRESSED"}))\n raise SystemExit(1)\n'
    result=subprocess.run(['ssh','tencent-codex','sudo -n --preserve-env=SSH_CONNECTION python3 -'],input=code,text=True,capture_output=True,timeout=100)
    try:data=json.loads(result.stdout)
    except ValueError:data={'exit_code':result.returncode or 1,'failure_code':'SSH_OUTPUT_SUPPRESSED'}
    from datetime import datetime,timezone
    stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    with (ROOT/'gateway/physical_can/evidence/h3-r2/router-migration'/('isolation-'+action+'-'+stamp+'.json')).open('x') as f:json.dump(data,f,indent=2)
    print(json.dumps(data));return result.returncode or data.get('exit_code',0)


if __name__=='__main__':raise SystemExit(main())
