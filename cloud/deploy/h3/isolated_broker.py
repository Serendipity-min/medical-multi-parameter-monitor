"""单独TLS监听与凭据，不重启/编辑生产Broker；连接目标仅从服务器外部配置取值。"""
import hashlib
import json
import os
from pathlib import Path
import pwd
import secrets
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT))
from cloud.deploy.h3.isolated_server import STATE,load_env,store_env


def main():
    out=Path('/opt/medical-monitor-h3/broker')
    if out.exists():raise RuntimeError('ISOLATED_BROKER_ALREADY_PREPARED')
    out.mkdir(mode=0o750)
    group=pwd.getpwnam('mosquitto');os.chown(out,0,group.pw_gid)
    # 只复用证书路径；不读取、导出或复制私钥材料，不更改正式证书。
    directives={}
    for line in Path('/opt/medical-monitor/broker/mosquitto.conf').read_text().splitlines():
        words=line.split()
        if words and words[0] in ('certfile','keyfile'):directives[words[0]]=words[1]
    assert set(directives)=={'certfile','keyfile'}
    external=json.loads(Path('/opt/medical-monitor/mqtt-config/backend.json').read_text())
    credentials={role:secrets.token_urlsafe(30) for role in ('h3-gateway','h3-backend')}
    # 直接生成Mosquitto PBKDF2密码文件，真实口令不进入进程参数或shell历史。
    import base64
    lines=[]
    for user,password in credentials.items():
        salt=secrets.token_bytes(12);count=101000
        key=hashlib.pbkdf2_hmac('sha512',password.encode(),salt,count)
        b64=lambda data:base64.b64encode(data).decode()
        lines.append(user+':$7$'+str(count)+'$'+b64(salt)+'$'+b64(key)+'\n')
    (out/'passwords').write_text(''.join(lines));(out/'passwords').chmod(0o640);os.chown(out/'passwords',0,group.pw_gid)
    (out/'acl').write_text('user h3-gateway\ntopic write mpm/v1/GW-C-001/#\nuser h3-backend\ntopic read mpm/v1/GW-C-001/#\n')
    config='listener 8884\nuser mosquitto\nallow_anonymous false\npersistence false\nconnection_messages false\nlog_dest none\n'
    config+=f'password_file {out}/passwords\nacl_file {out}/acl\n'
    config+=''.join(k+' '+v+'\n' for k,v in directives.items())
    config+='tls_version tlsv1.2\n'
    (out/'mosquitto.conf').write_text(config)
    for role in ('gateway','backend'):
        data={'host':external['host'],'port':8884,'username':'h3-'+role,
              'password':credentials['h3-'+role],'client_id':'h3-isolated-'+role,'gateway_id':'GW-C-001'}
        file=STATE/(role+'.json');file.write_text(json.dumps(data));file.chmod(0o600)
        if role=='backend':
            user=pwd.getpwnam('medical-ai');os.chown(file,user.pw_uid,user.pw_gid)
    env=load_env(STATE/'fixture.env')
    store_env(STATE/'backend.env',{'MONITOR_VIEW_TOKEN':env['H3_FIXTURE_TOKEN'],
              'MONITOR_ALLOWED_ORIGINS':'http://127.0.0.1:18767','MONITOR_GATEWAY_IDS':'GW-C-001',
              'MONITOR_MQTT_CONFIG':str(STATE/'backend.json')})
    # 只创建临时隔离服务；生产unit、监听和ACL保持原字节。
    subprocess.run(['systemd-run','--quiet','--unit=medical-monitor-h3-broker',
                    '/usr/sbin/mosquitto','-c',str(out/'mosquitto.conf')],check=True,capture_output=True)
    return {'unit':'medical-monitor-h3-broker','port':8884,'separate_credentials':True,
            'production_broker_modified':False,'config_sha256':hashlib.sha256(config.encode()).hexdigest()}


if __name__=='__main__':
    try:print(json.dumps(main(),indent=2))
    except Exception as exc:
        print(json.dumps({'failure_type':type(exc).__name__,'details_suppressed':True}));raise SystemExit(1)
