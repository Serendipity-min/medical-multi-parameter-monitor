"""只读补充核验：输出散列/枚举，不回传配置原文或连接地址。"""
from datetime import datetime, timezone
import inspect
import json
from pathlib import Path
import subprocess

from cloud.deploy.h3.formal_release import candidate_nginx
from cloud.deploy.h3.r2_audit import production_snapshot


def supplemental(candidate):
    import ast,hashlib,json,os,re,ssl,stat,subprocess
    from pathlib import Path
    root=Path('/opt/medical-monitor-p6/cloud/ai')
    cap=[]
    # 定位源码中确切的五槽循环；旧审计的窄正则未命中不能证明已取消上限。
    for path in root.glob('*.py'):
        tree=ast.parse(path.read_text())
        for node in ast.walk(tree):
            if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef)):
                loops=[n for n in ast.walk(node) if isinstance(n,ast.Call) and isinstance(n.func,ast.Name)
                       and n.func.id=='range' and all(isinstance(a,ast.Constant) for a in n.args)
                       and [a.value for a in n.args] in ([5],[1,6])]
                if loops:cap.append({'file':path.name,'function':node.name,'range_5_loops':len(loops)})
    syntax='error_log stderr; pid /tmp/h3-r2-unused-syntax.pid; events {} http { include /etc/nginx/mime.types; server { listen 127.0.0.1:18885; '+candidate+' } }'
    # Nginx解析器需要pread；pipe stdin不可seek，改为仅内存memfd，不落地正式配置。
    fd=os.memfd_create('h3-r2-nginx-syntax')
    try:
        os.write(fd,syntax.encode())
        checked=subprocess.run(['nginx','-t','-c','/proc/self/fd/'+str(fd)],pass_fds=(fd,),text=True,capture_output=True)
    finally:os.close(fd)
    current=subprocess.run(['nginx','-T'],text=True,capture_output=True)
    tls=[]
    if current.returncode==0:
        for value in sorted(set(re.findall(r'^\s*ssl_certificate\s+([^;]+);',current.stdout,re.M))):
            p=Path(value.strip())
            if p.is_file():
                d=ssl._ssl._test_decode_cert(str(p))
                tls.append({'certificate_sha256':hashlib.sha256(p.read_bytes()).hexdigest(),
                            'mode':oct(stat.S_IMODE(p.stat().st_mode)),
                            'not_before':d.get('notBefore'),'not_after':d.get('notAfter')})
    return {'legacy_five_slot_loops':cap,'legacy_five_slot_verified':bool(cap),
            'candidate_nginx_sha256':hashlib.sha256(candidate.encode()).hexdigest(),
            'candidate_nginx_syntax_exit_code':checked.returncode,'current_nginx_dump_exit_code':current.returncode,
            'tls_certificates':tls,'candidate_runtime_started':False,'formal_mutations':False}


def run():
    root=Path(__file__).resolve().parents[3]
    out=root/'gateway/physical_can/evidence/h3-r2'
    audit=json.loads((out/'H3-R2-0-AUDIT.json').read_text())
    candidate=candidate_nginx(Path('/opt/medical-monitor-h3/releases/runtime-R2-REPREPARE-REQUIRED'))
    code='import json\n'+inspect.getsource(production_snapshot)+'\n'+inspect.getsource(supplemental)+\
         '\nprint(json.dumps({"snapshot":production_snapshot(),"supplement":supplemental('+repr(candidate)+')}))\n'
    r=subprocess.run(['ssh','tencent-codex','sudo -n python3 -'],input=code,text=True,capture_output=True,timeout=50)
    if r.returncode:
        # 远端异常可能含连接信息，只保存退出码与异常类型，不输出原始stderr。
        import re
        kind=re.findall(r'^([A-Za-z_][A-Za-z_0-9]*(?:Error|Exception)):',r.stderr,re.M)
        with (out/('readonly-preflight-failure-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'.json')).open('x') as f:
            json.dump({'exit_code':r.returncode,'exception_type':kind[-1] if kind else 'UNCLASSIFIED','remote_stderr_suppressed':True},f)
        raise RuntimeError('READONLY_PREFLIGHT_FAILED_'+str(r.returncode))
    result=json.loads(r.stdout)
    before=audit['production_readonly'];after=result['snapshot']
    result.update(recorded_utc=datetime.now(timezone.utc).isoformat(),
                  identities_unchanged=all(after[k]==before[k] for k in ('services','files','web_index','production_ai_sources')),
                  real_ai_calls=0,hardware_accessed=False,formal_prepare='NOT_RUN_REPREPARE_REQUIRED')
    result['exit_code']=int(not result['identities_unchanged'] or result['supplement']['candidate_nginx_syntax_exit_code']!=0)
    target=out/('H3-R2-4-READONLY-PREFLIGHT-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'.json')
    with target.open('x',encoding='utf-8') as f:json.dump(result,f,indent=2)
    (out/'candidate.nginx.conf').write_text(candidate,encoding='utf-8')
    print(json.dumps({'exit_code':result['exit_code'],'identities_unchanged':result['identities_unchanged'],
                      'supplement':result['supplement']}))
    return result['exit_code']


if __name__=='__main__':raise SystemExit(run())
