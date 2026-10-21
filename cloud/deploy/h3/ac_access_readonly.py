"""补充现有正式HTTPS/TLS/HTTP健康只读证据，不建立MQTT业务会话或调用模型。"""
from datetime import datetime,timezone
import inspect,json,subprocess
from pathlib import Path


def snapshot():
    import hashlib,http.client,json,shlex,socket,ssl,subprocess,urllib.parse,urllib.request
    from datetime import datetime,timezone
    from pathlib import Path
    def env(path):
        result={}
        for line in Path(path).read_text().splitlines():
            if line.strip() and not line.lstrip().startswith('#'):
                key,value=line.split('=',1);words=shlex.split(value);result[key]=words[0] if words else ''
        return result
    def tls(host,port,connect_host,ca=None):
        try:
            context=ssl.create_default_context(cafile=ca or None)
            with socket.create_connection((connect_host,port),timeout=4) as raw:
                with context.wrap_socket(raw,server_hostname=host) as connection:
                    return {'verified':True,'TLS':connection.version(),'certificate_sha256':hashlib.sha256(connection.getpeercert(binary_form=True)).hexdigest()}
        except Exception as error:return {'verified':False,'failure_type':type(error).__name__}
    backend=env('/opt/medical-monitor/config/backend.env');ai=env('/etc/medical-monitor/p6-ai.env')
    origins=[x for x in backend.get('MONITOR_ALLOWED_ORIGINS','').split(',') if x.startswith('https://')]
    https={'state':'NOT_OBSERVED'}
    if origins:
        origin=urllib.parse.urlsplit(origins[0]);https=tls(origin.hostname,origin.port or 443,'127.0.0.1')
        https['origin_reference']='EXISTING_PRIVATE_BACKEND_ALLOWED_ORIGINS'
        # HEAD只查看静态入口状态，不传令牌或读取测量内容；不把匿名入口200等同于数据公开。
        try:
            connection=http.client.HTTPSConnection(origin.hostname,origin.port or 443,timeout=4)
            connection.request('HEAD','/medical-monitor/');response=connection.getresponse()
            https['anonymous_static_HEAD_status']=response.status;connection.close()
        except Exception as error:https['public_HEAD_failure_type']=type(error).__name__
    mqtt={'state':'NOT_OBSERVED','business_session_started':False}
    config_path=backend.get('MONITOR_MQTT_CONFIG')
    if config_path and Path(config_path).is_file():
        config=json.loads(Path(config_path).read_text());port=config.get('port',8883)
        mqtt.update(state='TLS_ONLY_OBSERVED_NO_MQTT_SESSION',port=port,config_sha256=hashlib.sha256(Path(config_path).read_bytes()).hexdigest(),
          config_mode=oct(Path(config_path).stat().st_mode&0o777),TLS=tls(config['host'],port,'127.0.0.1',config.get('ca_file')),
          role='DEPLOYED_BACKEND_CONFIG_ACL_NOT_INDEPENDENTLY_PROVEN')
    health={}
    for label,port in (('backend',18765),('ai',18766)):
        try:
            with urllib.request.urlopen('http://127.0.0.1:'+str(port)+'/health',timeout=3) as response:data=json.load(response)
            health[label]={k:data[k] for k in ('status','mqtt_connected','model_mode','snapshot_mode','mode','transport') if k in data}
        except Exception as error:health[label]={'failure_type':type(error).__name__}
    rule_policies=[]
    r=subprocess.run(['iptables','-S'],capture_output=True,text=True)
    for line in r.stdout.splitlines():
        words=line.split()
        if len(words)==3 and words[0]=='-P':rule_policies.append({'chain':words[1],'policy':words[2]})
    return {'recorded_utc':datetime.now(timezone.utc).isoformat(),'HTTPS':https,'broker_TLS':mqtt,
      'deployed_health':health,'filter_policies':rule_policies,
      'backend_view_token_configured':len(backend.get('MONITOR_VIEW_TOKEN',''))>=32,
      'AI_browser_token_configured':len(ai.get('P6_AI_TOKEN',''))>=32,
      'public_API_audience':'NOT_OBSERVED_NO_TOKEN_REQUEST_SENT','publisher_subscriber_ACL':'NOT_INDEPENDENTLY_PROVEN',
      'server_mutations':False,'real_AI_calls':0,'exit_code':0}


def main():
    root=Path(__file__).resolve().parents[3]
    code=inspect.getsource(snapshot)+'\nimport json\nprint(json.dumps(snapshot()))\n'
    r=subprocess.run(['ssh','tencent-codex','sudo -n python3 -'],input=code,text=True,capture_output=True,timeout=40)
    try:data=json.loads(r.stdout)
    except ValueError:data={'exit_code':r.returncode or 1,'failure_code':'OUTPUT_SUPPRESSED'}
    data['ssh_exit_code']=r.returncode
    # 每次复核独占新文件，保留首轮占位state未更新的原始回执，不能覆盖旧证据。
    stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    with (root/'gateway/physical_can/evidence/h3-ac'/('AC0-access-readonly-'+stamp+'.json')).open('x') as f:json.dump(data,f,indent=2)
    print(json.dumps(data));return data['exit_code']


if __name__=='__main__':raise SystemExit(main())
