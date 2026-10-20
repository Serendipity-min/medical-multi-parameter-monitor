"""清理后的规则差异只读归因；仅输出链名/目标/摘要，绝不恢复整张规则表。"""
from pathlib import Path
from datetime import datetime,timezone
import inspect,json,subprocess


def remote(tag):
    import hashlib,json,subprocess
    from pathlib import Path
    def run(args):return subprocess.run(args,capture_output=True,text=True)
    owned=Path('/var/lib/medical-monitor-p6/h3-20261019')/('r2c-'+tag)
    proof=json.loads((owned/'proof.json').read_text())
    rules=run(['iptables','-S']).stdout;lines=rules.splitlines(keepends=True)
    matches=[];pair_matches=[]
    def describe(line):
        tokens=line.split()
        return {'operation':tokens[0],'chain':tokens[1],
          'target':tokens[tokens.index('-j')+1] if '-j' in tokens else None,'source_present':'-s' in tokens}
    # 在内存逐条排除比对基线；仅定位新规则，不打印源地址或发出任何修改指令。
    for i,line in enumerate(lines):
        if hashlib.sha256(''.join(lines[:i]+lines[i+1:]).encode()).hexdigest()==proof['iptables_before_sha256']:
            matches.append({'removed_line_to_match':i,**describe(line)})
    # 最多比较两条新增规则并限制表大小；只验证是否能精确还原已知摘要，不猜测/删除未知规则。
    if not matches and len(lines)<=256:
        for i in range(len(lines)):
            for j in range(i+1,len(lines)):
                candidate=''.join(lines[:i]+lines[i+1:j]+lines[j+1:])
                if hashlib.sha256(candidate.encode()).hexdigest()==proof['iptables_before_sha256']:
                    pair_matches.append([describe(lines[i]),describe(lines[j])])
    listeners={str(p):bool(run(['ss','-H','-ltn','sport','=',':'+str(p)]).stdout.strip()) for p in (8883,8884,18775)}
    return {'exit_code':0,'before_sha256':proof['iptables_before_sha256'],
      'current_sha256':hashlib.sha256(rules.encode()).hexdigest(),'matching_single_added_rules':matches,
      'matching_pair_added_rules':pair_matches,'current_rule_lines':len(lines),
      'owned_chain_references_remaining':sum('MPH3R2C' in x for x in lines),
      'listeners':listeners,'table_modified_by_this_check':False}


root=Path(__file__).resolve().parents[3]
ref=json.loads(Path('E:/medical-monitor-h3-private/r2-router-active-window-reference.json').read_text())
code='import json\n'+inspect.getsource(remote)+'\nprint(json.dumps(remote('+repr(ref['isolation_tag'])+')))\n'
r=subprocess.run(['ssh','tencent-codex','sudo -n python3 -'],input=code,text=True,capture_output=True,timeout=30)
try:value=json.loads(r.stdout)
except ValueError:value={'exit_code':r.returncode or 1,'failure_code':'CLEANUP_AUDIT_SUPPRESSED'}
stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
with (root/'gateway/physical_can/evidence/h3-r2/router-migration'/('cleanup-audit-'+stamp+'.json')).open('x') as f:json.dump(value,f,indent=2)
print(json.dumps(value))
