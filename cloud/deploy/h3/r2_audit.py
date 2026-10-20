"""H3-R2只读接管：不打开串口、不启动服务，连接原文仅在内存中使用。"""
from datetime import datetime, timezone
import hashlib
import inspect
import json
from pathlib import Path
import subprocess


def production_snapshot():
    """SSH内执行，只返回身份、散列、权限及枚举，不回传env/连接地址。"""
    import hashlib,json,os,re,stat,subprocess
    from pathlib import Path
    def digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
    def query(args):return subprocess.run(args,capture_output=True,text=True,check=True).stdout.strip()
    def info(path):
        p=Path(path)
        if not p.is_file():return {'exists':False}
        s=p.stat()
        return {'exists':True,'sha256':digest(p),'mode':oct(stat.S_IMODE(s.st_mode)),
                'owner_uid':s.st_uid,'group_gid':s.st_gid,'bytes':s.st_size}
    units=('medical-monitor.service','medical-monitor-mqtt.service','p6-ai.service','nginx.service')
    services={}
    for unit in units:
        pid=query(['systemctl','show',unit,'-p','MainPID','--value'])
        entry={'pid':pid,'state':query(['systemctl','show',unit,'-p','ActiveState','--value'])}
        if int(pid):
            entry.update(cwd=os.readlink('/proc/'+pid+'/cwd'),executable=os.readlink('/proc/'+pid+'/exe'))
            # 不读取进程cmdline/environ，避免令牌或真实连接参数混入日志。
            r=subprocess.run(['git','-C',entry['cwd'],'rev-parse','HEAD'],capture_output=True,text=True)
            sha=r.stdout.strip();entry['git_sha']=sha if re.fullmatch('[0-9a-f]{40}',sha) else 'NOT_A_GIT_WORKTREE'
        services[unit]=entry
    plan=Path('/opt/medical-monitor-h3/formal/20261020T034945Z/plan.json')
    frozen=json.loads(plan.read_text())
    files={path:info(path) for path in frozen['original_hashes']}
    web=info('/opt/medical-monitor/current/web/dist/index.html')
    # 只统计本轮拥有的隔离规则；主机规则不能证明云安全组已撤销。
    rules=query(['iptables','-S','INPUT'])
    ai_root=Path(services['p6-ai.service']['cwd'])
    ai_source={}
    five_hint=False
    for relative in ('cloud/ai/app.py','cloud/ai/providers.py','cloud/ai/usage.py'):
        path=ai_root/relative
        ai_source[relative]=info(path)
        if path.is_file():
            five_hint|=bool(re.search(r'(?:budget_used|len\([^\n]*\))\s*>=\s*5\b',path.read_text()))
    runtime=[]
    for p in sorted(Path('/opt/medical-monitor-h3/releases').glob('runtime-*/H3_RUNTIME_SOURCE.json')):
        d=json.loads(p.read_text())
        runtime.append({'directory':p.parent.name,'manifest_sha256':digest(p),
                        'source_commit':d.get('source_commit',d.get('commit','NOT_RECORDED'))})
    isolated={u:query(['systemctl','show',u,'-p','ActiveState','--value']) for u in
              ('medical-monitor-h3-broker-diagnostic.service','medical-monitor-h3-backend-nodebfix.service','medical-monitor-h3-ai-isolated.service')}
    return {'services':services,'files':files,'web_index':web,'production_ai_sources':ai_source,
        'legacy_ai_five_cap_source_hint':five_hint,'formal_plan_state':frozen['state'],
        'formal_plan_sha256':digest(plan),'prepared_runtimes':runtime,'isolated_services':isolated,
        'formal_hashes_match_previous_plan':all(files[p].get('sha256')==h for p,h in frozen['original_hashes'].items()),
        'web_matches_previous_plan':web['sha256']==frozen['previous_web_index_sha256'],
        'owned_host_8884_rules':rules.count('medical-monitor-h3-isolation'),
        'cloud_security_group_checked_by_api':False,'mutations':False}


def run():
    root=Path(__file__).resolve().parents[3]
    out=root/'gateway/physical_can/evidence/h3-r2';out.mkdir(exist_ok=True)
    expected={'refs/heads/A':'3fa14b00a0823d2855e9dd8bd1c6c8545abb8dc5',
        'refs/heads/P4':'67f5f57bd82c6e326e9e78ec9540481c80105e5f',
        'refs/heads/main':'50699048010c57ba10f8573461844c525b022a07',
        'refs/heads/dev/p6-cloud-ai-text-tts-v1':'77dd14d1ca761a488956f7a4ebf28cb3174835e4'}
    h3='refs/heads/dev/h3-nodea-cloud-ai-integration'
    remote=subprocess.run(['git','ls-remote','origin',*expected,h3],cwd=root,capture_output=True,text=True,check=True)
    heads={line.split()[1]:line.split()[0] for line in remote.stdout.splitlines()}
    initial=subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip()
    status=subprocess.check_output(['git','status','--short'],cwd=root,text=True)
    # 函数通过stdin在内存中运行，不在服务器落地脚本，不回显SSH错误原文。
    code=inspect.getsource(production_snapshot)+'\nimport json\nprint(json.dumps(production_snapshot()))\n'
    ssh=subprocess.run(['ssh','tencent-codex','sudo -n python3 -'],input=code,text=True,capture_output=True,timeout=40)
    if ssh.returncode:raise RuntimeError('READONLY_SERVER_QUERY_FAILED_'+str(ssh.returncode))
    production=json.loads(ssh.stdout)
    receipt=root/'gateway/physical_can/evidence/h3/c-download-20261020T074926Z.json'
    firmware=json.loads(receipt.read_text())
    inputs=json.loads((root/'gateway/physical_can/evidence/h3/isolated-arm-result.json').read_text())
    mismatch=[]
    for group in ('source_sha256','build_input_sha256'):
        for name,sha in inputs[group].items():
            if not name.startswith('external-sdk/') and hashlib.sha256((root/name).read_bytes()).hexdigest()!=sha:mismatch.append(name)
    result={'schema_version':1,'stage':'H3-R2-0','executor':'Codex','contract_executor_label':'DeepSeek (document label only)',
        'recorded_utc':datetime.now(timezone.utc).isoformat(),'initial_head':initial,'remote_heads':heads,
        'protected_refs_match':all(heads.get(k)==v for k,v in expected.items()),'h3_local_remote_match':heads.get(h3)==initial,
        'initial_worktree_status':status,'firmware_build_inputs_changed_since_hardware':mismatch,
        'historical_firmware':{'source_commit':firmware['source_commit'],'image':firmware['image'],
            'download_exit_code':firmware['exit_code'],'readback_verified':firmware['image_readback_match'],
            'this_round_hardware_readback':'NOT_RUN_NO_SERIAL_OPEN'},
        'physical_state':{'source':'OWNER_REPORTED_THIS_TURN','A':'OFF_JLINK_DISCONNECTED','C':'POWERED_USB_COM15',
            'BOOT':'UNCHANGED_DOWNLOAD_CONFIGURATION','RAM_CONFIG_RETENTION':'NOT_REOBSERVED',
            'serial_opened':False,'reset_or_power_action_performed':False},
        'cloud_8884':{'source':'OWNER_REPORTED_THIS_TURN','wide_ipv4_rule':'STILL_PRESENT','api_verified':False,
            'manual_removal_target':'existing inbound TCP8884/all IPv4 rule on instance referenced by local SSH alias; do not change other ports'},
        'section8':'EXCLUDED_USER_COMPLETED_SELECTION','production_readonly':production,
        'hardware_window':'NOT_AUTHORIZED_BY_CURRENT_MATRIX','formal_release':'FORMAL_RELEASE_NOT_AUTHORIZED'}
    result['exit_code']=int(not result['protected_refs_match'] or not result['h3_local_remote_match'] or bool(mismatch)
                            or not production['formal_hashes_match_previous_plan'] or not production['web_matches_previous_plan'])
    result['gate']='AUDIT_IDENTITIES_PASS_WITH_EXPLICIT_PHYSICAL_SG_GAPS' if not result['exit_code'] else 'STOP_AUDIT'
    target=out/'H3-R2-0-AUDIT.json'
    with target.open('x',encoding='utf-8') as f:json.dump(result,f,indent=2)
    print(json.dumps({'gate':result['gate'],'exit_code':result['exit_code'],'production_changed':False,
        'historical_firmware_sha256':firmware['image']['sha256'],'old_ai_five_cap_hint':production['legacy_ai_five_cap_source_hint']}))
    return result['exit_code']


if __name__=='__main__':raise SystemExit(run())
