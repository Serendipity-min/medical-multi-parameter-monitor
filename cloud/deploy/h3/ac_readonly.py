"""AC-0云端只读快照：不打开串口，不写服务器文件/规则，不返回配置或连接原文。"""
from datetime import datetime,timezone
import inspect,json,subprocess
from pathlib import Path
from .r2_audit import production_snapshot


def closeout_snapshot():
    import ast,hashlib,ipaddress,json,os,re,ssl,socket,stat,subprocess
    from collections import Counter
    from datetime import datetime,timezone
    from pathlib import Path
    def query(args):
        r=subprocess.run(args,capture_output=True,text=True)
        return r.returncode,r.stdout
    def sha(data):return hashlib.sha256(data).hexdigest()
    def address(value):
        try:
            net=ipaddress.ip_network(value,strict=False)
            scope='ANY' if not net.prefixlen else 'LOOPBACK' if net.is_loopback else 'HOST' if net.prefixlen==net.max_prefixlen else 'NETWORK'
        except ValueError:scope='NAMED_OR_OTHER'
        return {'scope':scope,'digest':sha(value.encode())}
    production=production_snapshot()
    # 逐条保留顺序及可对比散列；地址/注释等可能包含真实连接信息，正文不离开内存。
    tables={}
    for table in ('filter','nat'):
        status,text=query(['iptables','-t',table,'-S']);rows=[]
        for order,line in enumerate(text.splitlines()):
            tokens=line.split();entry={'order':order,'sha256':sha(line.encode()),'operation':tokens[0],
                'chain':tokens[1] if len(tokens)>1 else None}
            for flag,label in (('-s','source'),('-d','destination')):
                if flag in tokens:entry[label]=address(tokens[tokens.index(flag)+1])
            for flag,label in (('-j','target'),('-p','protocol'),('--dport','destination_port')):
                if flag in tokens:entry[label]=tokens[tokens.index(flag)+1]
            rows.append(entry)
        tables[table]={'query_exit_code':status,'sha256':sha(text.encode()),'lines':len(rows),'ordered_rules':rows,
          'owned_h3_references':sum('MPH3R2C' in l or 'MPH3R2N' in l for l in text.splitlines())}
    managers={}
    for unit in ('fail2ban.service','ufw.service','firewalld.service','nftables.service'):
        status,text=query(['systemctl','show',unit,'-p','ActiveState','--value'])
        managers[unit]={'exit_code':status,'state':text.strip()}
    # 动态管理器事件只计数，不把禁用地址/攻击来源或日志原文带回仓库。
    events=Counter();log=Path('/var/log/fail2ban.log');window=('2026-10-20 11:18','2026-10-20 11:27')
    if log.is_file():
        for line in log.read_text(errors='replace').splitlines():
            if window[0]<=line[:16]<=window[1]:
                match=re.search(r'\[([^\]]+)\]\s+(Ban|Unban)\s',line)
                if match:events[match[1]+':'+match[2]]+=1
    _,listening=query(['ss','-H','-ltn']);ports=Counter()
    for line in listening.splitlines():
        fields=line.split()
        if len(fields)>3:
            try:ports[str(int(fields[3].rsplit(':',1)[1]))]+=1
            except ValueError:pass
    ai=Path(production['services']['p6-ai.service']['cwd'])/'cloud/ai/providers.py'
    five=False
    if ai.is_file():
        for node in ast.walk(ast.parse(ai.read_text())):
            if isinstance(node,ast.Call) and isinstance(node.func,ast.Name) and node.func.id=='range':
                five|=len(node.args)==2 and all(isinstance(x,ast.Constant) for x in node.args) and [x.value for x in node.args]==[1,6]
    # 实际部署源码只返回摘要；不把.git缺失误称为特定Git版本。
    sources={}
    for role,base,names in (
      ('backend',Path(production['services']['medical-monitor.service']['cwd']),('app/hub.py','app/main.py','app/mqtt_adapter.py')),
      ('ai',ai.parent,('app.py','facts.py','providers.py','usage.py','snapshot.py'))):
        sources[role]={name:sha((base/name).read_bytes()) if (base/name).is_file() else None for name in names}
    # 只解析Nginx访问控制结构；私密URL和认证配置值一律不输出。
    frozen=json.loads(Path('/opt/medical-monitor-h3/formal/20261020T034945Z/plan.json').read_text())
    nginx=[]
    for name in frozen['original_hashes']:
        p=Path(name)
        if '/nginx/' not in name or not p.is_file():continue
        text=p.read_text();nginx.append({'file_sha256':sha(text.encode()),'ssl_listener':bool(re.search(r'listen\s+443',text)),
          'ai_prefix_present':'/medical-monitor/ai/' in text,'monitor_prefix_present':'/medical-monitor/' in text,
          'basic_auth_directive':bool(re.search(r'^\s*auth_basic\s+(?!off\b)',text,re.M)),
          'allow_directive_count':len(re.findall(r'^\s*allow\s+',text,re.M)),
          'complete_public_audience':'NOT_OBSERVED_DIRECTIVES_ARE_NOT_EFFECTIVE_ACCESS_PROOF'})
    return {'recorded_utc':datetime.now(timezone.utc).isoformat(),'production':production,
      'deployed_source_sha256':sources,'legacy_ai_actual_range_1_6':five,'nginx_structure':nginx,
      'firewall':tables,'firewall_managers':managers,'fail2ban_events_in_historical_utc_window':dict(events),
      'historical_rule_text_available':False,'historical_difference_attribution':'UNPROVEN',
      'listening_tcp_ports':dict(ports),'cloud_security_group':{'api_observed':False,'state':'NOT_OBSERVED',
        'previous_owner_report':'BROAD_TCP8884_RETAINED','production_gate':'BLOCKED_SECURITY_REVIEW'},
      'physical_flash_this_round':'NOT_OBSERVED_NO_SERIAL_OPEN','server_mutations':False,
      'real_AI_calls':0,'actual_public_HTTPS_audience':'NOT_OBSERVED','exit_code':0}


def main():
    root=Path(__file__).resolve().parents[3];out=root/'gateway/physical_can/evidence/h3-ac'
    code=inspect.getsource(production_snapshot)+'\n'+inspect.getsource(closeout_snapshot)+'\nimport json\nprint(json.dumps(closeout_snapshot()))\n'
    result=subprocess.run(['ssh','tencent-codex','sudo -n python3 -'],input=code,text=True,capture_output=True,timeout=60)
    try:data=json.loads(result.stdout)
    except ValueError:data={'exit_code':result.returncode or 1,'failure_code':'READONLY_SSH_OUTPUT_SUPPRESSED','server_mutations':False}
    data['ssh_exit_code']=result.returncode
    with (out/'AC0-cloud-readonly.json').open('x') as f:json.dump(data,f,indent=2)
    print(json.dumps({'exit_code':data['exit_code'],'ssh_exit_code':result.returncode,'server_mutations':False,
      'firewall_filter_lines':data.get('firewall',{}).get('filter',{}).get('lines'),'production_gate':'BLOCKED_SECURITY_REVIEW'}))
    return data['exit_code']


if __name__=='__main__':raise SystemExit(main())
