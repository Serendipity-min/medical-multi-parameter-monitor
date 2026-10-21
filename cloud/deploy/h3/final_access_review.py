"""F3定向配置只读审查，不扫描端口、不连接MQTT业务、不输出凭据/真实地址。"""
import hashlib
import inspect
import json
from pathlib import Path
import subprocess
from datetime import datetime, timezone


def remote_review():
    import hashlib,json,re,subprocess
    from pathlib import Path
    def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
    def query(args):
        r=subprocess.run(args,capture_output=True,text=True)
        return r.returncode,r.stdout
    units={}
    for name in ('medical-monitor.service','medical-monitor-mqtt.service','p6-ai.service','nginx.service'):
        entry={}
        for prop in ('User','Group','ActiveState','NoNewPrivileges','ProtectSystem'):
            code,value=query(['systemctl','show',name,'-p',prop,'--value'])
            entry[prop]={'exit_code':code,'value':value.strip()}
        units[name]=entry
    code,text=query(['nginx','-T'])
    referenced=[]
    for index,name in enumerate(re.findall(r'^# configuration file (.+):$',text,re.M)):
        p=Path(name)
        # 其他虚拟站点文件名也可能含真实主机名，公开证据只给引用别名与摘要。
        if p.is_file():referenced.append({'reference_alias':'NGINX_REF_'+str(index),
            'monitor_snippet':str(p)=='/etc/nginx/snippets/medical-monitor.conf',
            'sha256':sha(p),'mode':oct(p.stat().st_mode&0o777)})
    configs=[]
    # 精确限定业务配置目录，不遍历服务器家目录、密码文件或其他项目。
    candidates=set(Path('/opt/medical-monitor/config').glob('*.conf'))
    # 从已运行包装器的unit定位配置，不读取/proc/cmdline或环境原文。
    _,unit=query(['systemctl','cat','medical-monitor-mqtt.service'])
    wrappers=[]
    for name in re.findall(r'/opt/[^\s;"\']+\.py',unit):
        p=Path(name)
        if p.is_file():wrappers.append(p)
    for wrapper in wrappers:
        # 包装器通常将Broker配置目录写为Path常量，只取绝对.conf引用，绝不输出源码。
        content=wrapper.read_text()
        for name in re.findall(r'["\'](/[^"\'\n]+\.conf)["\']',content):
            if Path(name).is_file():candidates.add(Path(name))
    for p in sorted(candidates):
        content=p.read_text();acl=re.search(r'^\s*acl_file\s+(.+)$',content,re.M)
        roles=[]
        if acl:
            aclpath=Path(acl[1].strip())
            if aclpath.is_file():
                role=None
                for line in aclpath.read_text().splitlines():
                    fields=line.strip().split()
                    if not fields or fields[0].startswith('#'):continue
                    if fields[0]=='user' and len(fields)==2:
                        # 账号/Topic仅给散列，实际角色批准需引用服务器受限原件。
                        role={'identity_sha256':hashlib.sha256(fields[1].encode()).hexdigest(),'topics':[]}
                        roles.append(role)
                    elif fields[0] in ('topic','pattern') and role is not None:
                        direction=fields[1] if len(fields)>2 else 'readwrite'
                        topic=fields[-1]
                        role['topics'].append({'permission':direction,'topic_sha256':hashlib.sha256(topic.encode()).hexdigest(),
                            'has_hash_wildcard':'#' in topic,'has_plus_wildcard':'+' in topic})
        configs.append({'config_reference_alias':'BROKER_CONFIG_'+str(len(configs)),
                        'sha256':sha(p),'acl_reference_found':bool(acl),'roles':roles,
                        'acl_role_semantics':'NOT_OWNER_APPROVED_FORMAL_NEW_ROLES'})
    return {'service_users':units,'nginx_syntax_and_dump_exit_code':code,'nginx_references':referenced,
        'business_broker_configs':configs,'acl_coverage':'PARTIAL_CONFIG_SEARCH_NOT_EFFECTIVE_ACL_PROOF',
        'audience':'NOT_OWNER_APPROVED','SG_control_plane':'NOT_OBSERVED_NO_CONFIGURED_API_SESSION',
        'cloud_write':False,'MQTT_business_connection':False,'real_AI_calls':0,'exit_code':0}


def main():
    root=Path(__file__).resolve().parents[3]
    started=datetime.now(timezone.utc).isoformat()
    code=inspect.getsource(remote_review)+'\nimport json\nprint(json.dumps(remote_review()))\n'
    r=subprocess.run(['ssh','tencent-codex','sudo -n python3 -'],input=code,text=True,capture_output=True,timeout=45)
    try:data=json.loads(r.stdout)
    except ValueError:data={'exit_code':r.returncode or 1,'error':'REMOTE_OUTPUT_SUPPRESSED'}
    raw=json.dumps(data,indent=2).encode()
    out=root/'cloud/evidence/h3-ac-final';out.mkdir(parents=True,exist_ok=True)
    stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    with (out/('F3-access-readonly-'+stamp+'.json')).open('xb') as f:f.write(raw)
    result={'stage':'F3','gate':'BLOCKED_SECURITY_REVIEW','source_commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip(),
        'device_or_runtime_sha':None,'source_label':'NO_ACQUISITION','window_start_utc':started,
        'window_end_utc':datetime.now(timezone.utc).isoformat(),'command':'python -m cloud.deploy.h3.final_access_review',
        'exit_code':r.returncode or data['exit_code'],'observed_vs_simulated':'ACTUAL_READONLY_CONFIGURATION',
        'raw_evidence_sha':hashlib.sha256(raw).hexdigest(),'security_scope':'READONLY_NOT_SECURITY_GATE',
        'owner_auth_id':'MPM-H3-004_SIGNED_READONLY','rollback_state':'NO_MUTATION',
        'unresolved':['SG_CONTROL_PLANE','FORMAL_PUBLISHER_SUBSCRIBER_ACL','PUBLIC_AUDIENCE','HISTORICAL_FILTER_ATTRIBUTION'],
        'null_reasons':{'device_or_runtime_sha':'DEPLOYMENT_NOT_PERFORMED'}}
    with (out/('F3-access-receipt-'+stamp+'.json')).open('x') as f:json.dump(result,f,indent=2)
    print(json.dumps({'exit_code':result['exit_code'],'gate':result['gate'],'cloud_write':False}))
    return result['exit_code']


if __name__=='__main__':raise SystemExit(main())
