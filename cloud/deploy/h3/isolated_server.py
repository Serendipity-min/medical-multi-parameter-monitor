"""H3独立AI进程：凭据只在服务器加载，不修改正式unit/env/Nginx/Backend。"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import secrets
import shlex
import shutil
import subprocess
import time
import uuid

ROOT = Path(__file__).resolve().parents[3]
STATE = Path('/var/lib/medical-monitor-p6/h3-20261019')
PYTHON = '/opt/medical-monitor-p6/.venv/bin/python'
UNITS = ('medical-monitor-h3-fixture','medical-monitor-h3-ai-isolated')


def load_env(path):
    result = {}
    for line in Path(path).read_text().splitlines():
        if line.strip() and not line.lstrip().startswith('#'):
            key, value = line.split('=',1)
            parts=shlex.split(value); result[key]=parts[0] if parts else ''
    return result


def store_env(path, values):
    # systemd环境文件只写服务器受控目录；永不回传其正文。
    with path.open('x',encoding='utf-8') as f:
        f.write(''.join(k+'='+json.dumps(v)+'\n' for k,v in values.items()))
    path.chmod(0o600)


def prepare():
    # pwd仅用于Linux服务账户准备；纯状态/配置读取工具可在Windows导入。
    import pwd
    if STATE.exists():raise RuntimeError('H3_STATE_ALREADY_EXISTS')
    STATE.mkdir(mode=0o750)
    user=pwd.getpwnam('medical-ai');os.chown(STATE,user.pw_uid,user.pw_gid)
    env=load_env('/etc/medical-monitor/p6-ai.env')
    old=Path(env['P6_REAL_BUDGET_DIR'])
    hashes={}
    for p in old.glob('call-*.json'):
        target=STATE/p.name;shutil.copy2(p,target);target.chmod(0o600);os.chown(target,user.pw_uid,user.pw_gid)
        hashes[p.name]=hashlib.sha256(p.read_bytes()).hexdigest()
    fixture_token,ai_token=secrets.token_urlsafe(36),secrets.token_urlsafe(36)
    for key in ('P6_WEB_DIR','P6_MQTT_PORT','P6_MQTT_USERNAME','P6_MQTT_PASSWORD'):env.pop(key,None)
    env.update(P6_AI_TOKEN=ai_token,P6_REAL_BUDGET_DIR=str(STATE),P6_MQTT_MODE='DISABLED',
               P6_MODEL_MODE='DOUBAO',P6_SNAPSHOT_MODE='MONITOR',
               P6_MONITOR_WS_URL='ws://127.0.0.1:18775/ws/v1/monitor',
               P6_MONITOR_VIEW_TOKEN=fixture_token,P6_MONITOR_ORIGIN='http://127.0.0.1:18767',
               P6_ALLOWED_ORIGINS='http://127.0.0.1:18767')
    store_env(STATE/'ai.env',env);store_env(STATE/'fixture.env',{'H3_FIXTURE_TOKEN':fixture_token})
    return {'legacy_hashes':hashes,'legacy_files_unchanged':True,'model':env['ARK_MODEL_ID'],
            'real_snapshot_source':'NONPERSONAL_SOFTWARE_FIXTURE_NOT_HARDWARE','billing':'OPERATOR_REPORTED_FREE_OR_TRIAL_NOT_BILLING_VERIFIED'}


def start():
    for unit,envfile,module,port in [(UNITS[0],'fixture.env','cloud.ai.tests.h3_monitor_fixture:app',18775),
                                     (UNITS[1],'ai.env','cloud.ai.app:create_app',18776)]:
        cmd=['systemd-run','--quiet','--unit='+unit,'--uid=medical-ai','--gid=medical-ai',
             '--property=WorkingDirectory='+str(ROOT),'--property=EnvironmentFile='+str(STATE/envfile),
             '--property=NoNewPrivileges=true','--property=UMask=0077',
             PYTHON,'-m','uvicorn',module,'--host','127.0.0.1','--port',str(port),'--no-access-log']
        if port==18776:cmd.append('--factory')
        subprocess.run(cmd,check=True,capture_output=True)
    return {'units':list(UNITS),'ports':[18775,18776],'production_services_changed':False}


def test():
    import httpx
    env=load_env(STATE/'ai.env');token=env['P6_AI_TOKEN'];view=env['P6_MONITOR_VIEW_TOKEN']
    base='http://127.0.0.1:18776/medical-monitor/ai'
    headers={'Authorization':'Bearer '+token};control={'Authorization':'Bearer '+view}
    results=[]
    with httpx.Client(timeout=16,trust_env=False) as c:
        for label,method,path,h,expected in [('auth','POST','/api/v1/text',{},401),
                                            ('method','GET','/api/v1/text',{},405),
                                            ('unknown','POST','/api/v1/missing',headers,404)]:
            r=c.request(method,base+path,headers=h,json={});assert r.status_code==expected
            results.append({'case':label,'http':r.status_code})
        for label,validity,question,real in [
            ('current_readings','VALID','当前血氧多少',False),
            ('general_health','VALID','久坐办公有哪些一般健康提示',True),
            ('expired_readings','STALE','读数过期时应如何理解数据来源',True),
            ('node_b_absent','INVALID','Node-B没有连接时应如何理解界面',True),
            ('project','VALID','请说明这个工程监护样机的数据链路',True)]:
            c.post('http://127.0.0.1:18775/fixture/control',headers=control,json={'validity':validity,'delay':0}).raise_for_status()
            r=c.post(base+'/api/v1/text',headers=headers,json={'session_id':uuid.uuid4().hex,'gateway_id':'GW-C-001','question':question,'voice':False})
            row={'case':label,'http':r.status_code}
            if r.status_code==200:
                data=r.json();facts=data['facts']
                assert all(f['value'] is None for f in facts if f['node_id']=='NODE-B')
                assert all(f['source']=='MOCK' and f['synthetic'] for f in facts)
                if validity!='VALID':assert all(f['value'] is None for f in facts)
                assert (data['real_model']=='REAL_REQUEST_USED')==real
                row.update(real_model=data['real_model'],answer_kind=data['answer_kind'],
                           model_evidence=data['model_evidence'],fact_digest=data['fact_digest'],
                           node_b_offline=True,source='MOCK',synthetic=True,values_and_answers_saved=False)
            else:row['error']=r.json().get('detail')
            results.append(row)
            # 单次上游失败不自动重试；保留失败证据再定位。
            if r.status_code!=200:break
        c.post('http://127.0.0.1:18775/fixture/control',headers=control,json={'validity':'VALID','delay':4}).raise_for_status()
        r=c.post(base+'/api/v1/text',headers=headers,json={'session_id':uuid.uuid4().hex,'gateway_id':'GW-C-001','question':'当前血氧多少'})
        results.append({'case':'snapshot_timeout','http':r.status_code,'error':r.json().get('detail')});assert r.status_code==504
        c.post('http://127.0.0.1:18775/fixture/control',headers=control,json={'validity':'VALID','delay':0}).raise_for_status()
        health=c.get(base+'/health').json()
    return {'tested_at':datetime.now(timezone.utc).isoformat(),'cases':results,'health':health,
            'hardware_e2e':'NOT_TESTED','billing':'OPERATOR_REPORTED_FREE_OR_TRIAL_COST_NOT_INFERRED',
            'pass':all(r['http']==200 for r in results if 'answer_kind' in r) and sum(r.get('real_model')=='REAL_REQUEST_USED' for r in results)==4}


def main():
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['prepare','start','test','stop']);args=parser.parse_args()
    try:
        if args.action=='stop':
            for unit in UNITS:subprocess.run(['systemctl','stop',unit],capture_output=True)
            result={'stopped':list(UNITS)}
        else:result=globals()[args.action]()
        print(json.dumps(result,ensure_ascii=False,indent=2))
        return 1 if result.get('pass') is False else 0
    except Exception as exc:
        print(json.dumps({'action':args.action,'failure_type':type(exc).__name__,'details_suppressed':True}))
        return 1


if __name__=='__main__':raise SystemExit(main())
