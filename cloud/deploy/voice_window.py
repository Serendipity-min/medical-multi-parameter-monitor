"""VOICE-002有界正式试验/回退；仅修改卡内ACL/password/snippet，原H3进程保留。"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import shlex
import shutil
import ssl
import subprocess
import sys
import time

ACL=Path('/opt/medical-monitor/broker/acl')
PASSWORDS=Path('/opt/medical-monitor/broker/passwords')
SNIPPET=Path('/etc/nginx/snippets/medical-monitor.conf')
ENV=Path('/opt/medical-monitor-h3/formal/20261021T093335Z/ai.env')
BE_ENV=ENV.with_name('backend.env')
TOPIC='mpm/v1/GW-C-001/voice/reply'
UNIT='medical-monitor-voice002-trial'
PORT=18796
OLD_RELEASE=Path('/opt/medical-monitor-h3/releases/runtime-b8fbb14b5c35')
PYTHON='/opt/medical-monitor-h3/environments/runtime-b8fbb14b5c35/bin/python'


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def load_env(path):
    return {k:(shlex.split(v)[0] if shlex.split(v) else '') for k,v in
            (line.split('=',1) for line in Path(path).read_text().splitlines() if line.strip() and not line.lstrip().startswith('#'))}
def run(argv,**kwargs):
    p=subprocess.run(argv,capture_output=True,**kwargs)
    if p.returncode:raise ValueError('VOICE_COMMAND_FAILED_'+Path(argv[0]).name+'_'+str(p.returncode))
    return p.stdout
def write_new(path,data,mode=0o600):
    with Path(path).open('xb') as f:f.write(data)
    Path(path).chmod(mode)
def atomic_bytes(path,data):
    # 保留原owner/mode，在同目录原子替换；不把ACL密码原件输出到日志。
    stat=path.stat();tmp=path.with_name(path.name+'.voice002-tmp')
    write_new(tmp,data,stat.st_mode&0o777);os.chown(tmp,stat.st_uid,stat.st_gid);os.replace(tmp,path)
def emit(path,data):
    path.write_text(json.dumps(data,indent=2)+'\n');path.chmod(0o600)


def scoped_acl(text,cuser,publisher):
    # 旧宽C通配角色只对新voice主题增加deny，原遥测/Backend权限逐字保留。
    blocks=re.split(r'(?m)^(?=user\s)',text);found=0;result=[];legacy=0
    for block in blocks:
        first=block.splitlines()[0].split() if block.splitlines() else []
        if len(first)==2 and first[0]=='user':
            if first[1]==publisher:raise ValueError('VOICE_ROLE_ALREADY_EXISTS')
            if first[1]==cuser:
                if TOPIC in block:raise ValueError('VOICE_C_PERMISSION_ALREADY_PRESENT')
                block=block.rstrip()+'\ntopic read '+TOPIC+'\n\n';found+=1
            elif re.search(r'(?m)^topic\s+(?:read|write|readwrite)\s+mpm/v1/GW-C-001/#\s*$',block):
                block=block.rstrip()+'\ntopic deny '+TOPIC+'\n\n';legacy+=1
        result.append(block)
    if found!=1:raise ValueError('VOICE_CURRENT_C_ROLE_NOT_UNIQUE')
    return ''.join(result).rstrip()+'\n\nuser '+publisher+'\ntopic write '+TOPIC+'\n',legacy


def prepare(state,release,inputs):
    import pwd
    if state.exists() or not state.name.startswith('voice002-') or state.parent!=Path('/opt/medical-monitor-h3'):
        raise ValueError('VOICE_NEW_STATE_REQUIRED')
    if not release.name.startswith('voice-002-') or release.parent!=Path('/opt/medical-monitor-h3/releases'):
        raise ValueError('VOICE_NEW_RELEASE_REQUIRED')
    manifest=json.loads((release/'VOICE_RUNTIME_SOURCE.json').read_text())
    for name,digest in manifest['files'].items():
        if sha(release/name)!=digest:raise ValueError('VOICE_RELEASE_CHANGED')
    expected=inputs['expected_files']
    files=(ACL,PASSWORDS,SNIPPET,ENV,BE_ENV,Path('/etc/systemd/system/medical-monitor-h3-webai.service'))
    if any(sha(p)!=expected[str(p)] for p in files if str(p) in expected):raise ValueError('VOICE_FORMAL_BASE_CHANGED')
    state.mkdir(mode=0o700);a=state/'backup-a';b=state/'backup-b';a.mkdir();b.mkdir()
    receipt={}
    for index,p in enumerate(files):
        target=str(index);shutil.copy2(p,a/target);shutil.copy2(p,b/target)
        if sha(p)!=sha(a/target) or sha(p)!=sha(b/target):raise ValueError('VOICE_DOUBLE_BACKUP_FAILED')
        receipt[str(p)]={'copy':target,'sha256':sha(p)}
    cuser,cpass=inputs['c_username'],inputs['c_password']
    if hashlib.sha256(cuser.encode()).hexdigest()!=inputs['c_role_sha256']:raise ValueError('VOICE_C_IDENTITY_CHANGED')
    be=load_env(BE_ENV);mc=json.loads(Path(be['MONITOR_MQTT_CONFIG']).read_text())
    if mc['host']!=inputs['host']:raise ValueError('VOICE_DEVICE_SERVER_TARGET_MISMATCH')
    publisher='voice002-'+secrets.token_hex(8);password=secrets.token_urlsafe(36)
    acl,legacy=scoped_acl(ACL.read_text(),cuser,publisher)
    write_new(state/'candidate-acl',acl.encode())
    shutil.copy2(PASSWORDS,state/'candidate-passwords')
    # 不使用-b口令命令行；工具通过私有stdin接收两次口令，原始输出不落盘。
    run(['mosquitto_passwd',str(state/'candidate-passwords'),publisher],input=(password+'\n'+password+'\n').encode(),timeout=10)
    until=int(time.time()*1000)+7200000
    ai=load_env(ENV);ai.pop('P6_WEB_DIR',None)
    ai.update(P6_MQTT_MODE='FORMAL_VOICE_WINDOW',CVOICE_MQTT_HOST=mc['host'],
        CVOICE_CA_FILE=ssl.get_default_verify_paths().cafile,CVOICE_USERNAME=publisher,
        CVOICE_PASSWORD=password,CVOICE_UNTIL_MS=str(until),CVOICE_MODEL_BUDGET_FILE=str(state/'budget/voice.sqlite'))
    if ai.get('ARK_MODEL_ID')!='doubao-seed-2-0-mini-260428':raise ValueError('VOICE_MODEL_CHANGED')
    account=pwd.getpwnam('medical-ai');state.chmod(0o710);os.chown(state,0,account.pw_gid)
    budget=state/'budget';budget.mkdir(mode=0o700);os.chown(budget,account.pw_uid,account.pw_gid)
    write_new(state/'ai.env',''.join(k+'='+json.dumps(v)+'\n' for k,v in ai.items()).encode(),0o640);os.chown(state/'ai.env',0,account.pw_gid)
    old=SNIPPET.read_text()
    if old.count('127.0.0.1:18786')!=1 or str(OLD_RELEASE) not in old:raise ValueError('VOICE_OLD_ROUTE_NOT_EXACT')
    snippet=old.replace('127.0.0.1:18786','127.0.0.1:'+str(PORT)).replace(str(OLD_RELEASE),str(release))
    write_new(state/'candidate-snippet',snippet.encode())
    # 仅外部私有配置保存设备凭据，供权限负例；绝不进入release或输出回执。
    emit(state/'probe-auth.json',{'host':mc['host'],'c_username':cuser,'c_password':cpass,'publisher':publisher,'password':password,'ca':ai['CVOICE_CA_FILE']})
    plan={'state':str(state),'release':str(release),'release_manifest_sha256':sha(release/'VOICE_RUNTIME_SOURCE.json'),
        'before':receipt,'after':{str(ACL):sha(state/'candidate-acl'),str(PASSWORDS):sha(state/'candidate-passwords'),str(SNIPPET):sha(state/'candidate-snippet')},
        'until_ms':until,'legacy_exact_topic_denials':legacy,'pid_before':services(),'source_head':manifest['source_head']}
    emit(state/'plan.json',plan)
    return {'exit_code':0,'action':'PREPARED_NOT_ACTIVE','source_head':manifest['source_head'],'release_sha256':plan['release_manifest_sha256'],'backup_files':{k:v['sha256'] for k,v in receipt.items()},'legacy_exact_topic_denials':legacy,'until_ms':until}


def services():
    return {u:dict(l.split('=',1) for l in run(['systemctl','show',u,'-p','MainPID','-p','ActiveState']).decode().splitlines()) for u in
            ('medical-monitor-h3-webai.service','medical-monitor-h3-webbackend.service','medical-monitor-mqtt.service','nginx.service')}


def activate(state):
    plan=json.loads((state/'plan.json').read_text());release=Path(plan['release'])
    if time.time()*1000>=plan['until_ms']:raise ValueError('VOICE_WINDOW_EXPIRED')
    if any(sha(p)!=v['sha256'] for p,v in plan['before'].items()):raise ValueError('VOICE_PREACTIVATION_BASE_CHANGED')
    # 先安装自动回退定时器，再改正式文件；进程退出不能让试验权限无限续存。
    rollback=['systemd-run','--quiet','--unit=medical-monitor-voice002-rollback','--on-active=110min',
              '--property=WorkingDirectory='+str(release),PYTHON,'-m','cloud.deploy.voice_window','rollback','--state',str(state)]
    run(rollback,timeout=20)
    atomic_bytes(ACL,(state/'candidate-acl').read_bytes());atomic_bytes(PASSWORDS,(state/'candidate-passwords').read_bytes())
    emit(state/'activation-progress.json',{'acl_written':True,'nginx_written':False})
    run(['systemctl','kill','--kill-whom=main','--signal=HUP','medical-monitor-mqtt.service'],timeout=20)
    run(['systemd-run','--quiet','--unit='+UNIT,'--uid=medical-ai','--gid=medical-ai',
         '--property=WorkingDirectory='+str(release),'--property=EnvironmentFile='+str(state/'ai.env'),
         '--property=NoNewPrivileges=true','--property=UMask=0077','--property=RuntimeMaxSec=7200',
         PYTHON,'-m','uvicorn','cloud.ai.app:create_app','--factory','--host','127.0.0.1','--port',str(PORT),'--no-access-log'],timeout=20)
    import urllib.request
    for _ in range(30):
        try:
            d=json.load(urllib.request.urlopen('http://127.0.0.1:'+str(PORT)+'/health',timeout=1))
            if d.get('voice_mode')=='FORMAL_TLS_8883':break
        except Exception:time.sleep(.2)
    else:raise ValueError('VOICE_CANDIDATE_HEALTH_FAILED')
    atomic_bytes(SNIPPET,(state/'candidate-snippet').read_bytes())
    emit(state/'activation-progress.json',{'acl_written':True,'nginx_written':True})
    run(['nginx','-t'],timeout=10);run(['systemctl','reload','nginx'],timeout=20)
    after=services()
    if any(after[u]['MainPID']!=plan['pid_before'][u]['MainPID'] for u in after):raise ValueError('VOICE_ORIGINAL_SERVICE_RESTARTED')
    emit(state/'activated.json',{'utc':datetime.now(timezone.utc).isoformat(),'files':plan['after'],'services':after})
    return {'exit_code':0,'action':'ACTIVE_DEFAULT_VOICE_OFF','after_sha256':plan['after'],'services':after,'port':PORT}


def rollback(state):
    plan=json.loads((state/'plan.json').read_text());changed=[]
    # 只回退已知本次内容；陌生后续修改绝不能被自动覆盖。
    for path,after in plan['after'].items():
        p=Path(path);before=plan['before'][path]
        if sha(p)==before['sha256']:continue
        if sha(p)!=after:raise ValueError('VOICE_ROLLBACK_CURRENT_STATE_CHANGED')
        for name in ('backup-a','backup-b'):
            if sha(state/name/before['copy'])!=before['sha256']:raise ValueError('VOICE_ROLLBACK_ORIGINAL_CORRUPT')
        atomic_bytes(p,(state/'backup-a'/before['copy']).read_bytes());changed.append(path)
    run(['nginx','-t'],timeout=10)
    if str(SNIPPET) in changed:run(['systemctl','reload','nginx'],timeout=20)
    if any(str(p) in changed for p in (ACL,PASSWORDS)):run(['systemctl','kill','--kill-whom=main','--signal=HUP','medical-monitor-mqtt.service'],timeout=20)
    subprocess.run(['systemctl','stop',UNIT],capture_output=True,timeout=20)
    subprocess.run(['systemctl','stop','medical-monitor-voice002-rollback.timer'],capture_output=True,timeout=20)
    result={'exit_code':0,'action':'ACTUAL_CLOUD_ROLLBACK','restored_sha256':{p:sha(p) for p in plan['after']},'services':services()}
    if any(result['restored_sha256'][p]!=plan['before'][p]['sha256'] for p in plan['after']):raise ValueError('VOICE_ROLLBACK_HASH_FAILED')
    emit(state/'rollback-result.json',result);return result


def main():
    p=argparse.ArgumentParser();p.add_argument('action',choices=('prepare','activate','rollback'));p.add_argument('--state',type=Path,required=True);p.add_argument('--release',type=Path);a=p.parse_args()
    try:r=prepare(a.state,a.release,json.load(sys.stdin)) if a.action=='prepare' else activate(a.state) if a.action=='activate' else rollback(a.state)
    except Exception as e:
        # 密钥/目标/第三方错误内容不得流入stdout/journal。
        r={'exit_code':1,'error_type':type(e).__name__}
        if type(e) is ValueError:r['error_code']=str(e)
    print(json.dumps(r,indent=2));return r['exit_code']


if __name__=='__main__':raise SystemExit(main())
