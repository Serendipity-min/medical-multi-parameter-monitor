"""离线升级现有项目；校验、备份、切换和失败回滚，不操作其他站点。"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import time
import urllib.request
import zipfile

ROOT = Path('/opt/medical-monitor')

def run(*args):
    result = subprocess.run(args, capture_output=True, timeout=120)
    if result.returncode:
        # 子进程错误可能含外部配置值，不回显参数或原始输出。
        raise RuntimeError('Deployment command failed: '+Path(args[0]).name)
    return result.stdout

def private_json(path, data, owner='ubuntu'):
    path.write_text(json.dumps(data), encoding='utf-8')
    path.chmod(0o600)
    shutil.chown(path, user=owner, group=owner)

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--bundle',type=Path,required=True)
    parser.add_argument('--sha256',required=True)
    parser.add_argument('--config',type=Path,required=True)
    parser.add_argument('--release',required=True)
    args=parser.parse_args()
    assert os.geteuid()==0 and re.fullmatch(r'[a-zA-Z0-9-]+',args.release)
    assert hashlib.sha256(args.bundle.read_bytes()).hexdigest()==args.sha256
    config=json.loads(args.config.read_text())
    release=ROOT/'releases'/args.release
    backup=ROOT/'backups'/args.release
    broker=ROOT/'broker'
    assert not release.exists() and not backup.exists() and not broker.exists()
    # 独立 listener 必须空闲；已有 Mosquitto 配置和服务不作修改。
    import socket
    with socket.socket() as sock:
        sock.bind(('0.0.0.0',8883))
    old=(ROOT/'current').resolve()
    backup.mkdir(mode=0o700)
    (backup/'previous-current.txt').write_text(str(old))
    for source,name in [(ROOT/'config/backend.env','backend.env'),
                        (Path('/etc/systemd/system/medical-monitor.service'),'backend.service'),
                        (Path('/etc/nginx/snippets/medical-monitor.conf'),'nginx-snippet.conf')]:
        shutil.copy2(source,backup/name)
    # 完整 Nginx 配置只留服务器本机受限备份，绝不回显到运行日志。
    (backup/'nginx-config.txt').write_bytes(run('nginx','-T'))
    release.mkdir()
    with zipfile.ZipFile(args.bundle) as archive:
        for name in archive.namelist():
            assert (release/name).resolve().is_relative_to(release)
        archive.extractall(release)
    run('python3','-m','venv',str(release/'.venv'))
    run(str(release/'.venv/bin/python'),'-m','pip','install','--no-index','--find-links',str(release/'wheels'),'-r',str(release/'backend/requirements.lock'))
    broker.mkdir(mode=0o750)
    shutil.chown(broker,group='mosquitto')
    for folder in ['tls','data']:
        (broker/folder).mkdir(mode=0o750)
        shutil.chown(broker/folder,user='mosquitto',group='mosquitto')
    for source,target in [(config['certificate'],'server-chain.pem'),(config['private_key'],'server-key.pem')]:
        shutil.copyfile(source,broker/'tls'/target)
        (broker/'tls'/target).chmod(0o640)
        shutil.chown(broker/'tls'/target,group='mosquitto')
    for name in ['mosquitto.conf','acl']:
        shutil.copyfile(release/'broker'/name,broker/name)
        (broker/name).chmod(0o640)
        shutil.chown(broker/name,group='mosquitto')
    passwords=broker/'passwords'
    passwords.write_text(''.join(role['username']+':'+role['password']+'\n' for role in config['roles'].values()))
    passwords.chmod(0o600)
    run('mosquitto_passwd','-U',str(passwords))
    passwords.chmod(0o640)
    shutil.chown(passwords,group='mosquitto')
    # 原 EnvironmentFile 目录可能仅 root 可遍历；应用配置单独由服务账号持有。
    mqtt_config=ROOT/'mqtt-config'
    mqtt_config.mkdir(mode=0o700)
    shutil.chown(mqtt_config,user='ubuntu',group='ubuntu')
    for role in ['backend','mock']:
        private_json(mqtt_config/f'{role}.json',{'host':config['host'],'port':8883,**config['roles'][role]})
    private_json(mqtt_config/'mock-control.json',{})
    private_json(broker/'certificate-source.json',
                 {'certificate':config['certificate'],'private_key':config['private_key']},owner='root')
    # 合成源由服务器服务托管；证书定时器只复制现有续签文件，不联网下载。
    for name in ['medical-monitor-mqtt.service','medical-monitor-mock.service',
                 'medical-monitor-certificate.service','medical-monitor-certificate.timer']:
        shutil.copyfile(release/'deploy'/name,Path('/etc/systemd/system')/name)
    switched=False
    try:
        run('systemctl','daemon-reload')
        run('systemctl','enable','--now','medical-monitor-mqtt')
        env=ROOT/'config/backend.env'
        lines=[line for line in env.read_text().splitlines() if not line.startswith(('MONITOR_DEVICE_TOKEN=','MONITOR_GATEWAY_ID=','MONITOR_MQTT_CONFIG=','MONITOR_GATEWAY_IDS='))]
        lines += ['MONITOR_MQTT_CONFIG=/opt/medical-monitor/mqtt-config/backend.json','MONITOR_GATEWAY_IDS=GW-DEV-001,GW-C-001']
        env.write_text('\n'.join(lines)+'\n')
        link=ROOT/'current-mqtt-next'
        link.symlink_to(release)
        link.replace(ROOT/'current')
        switched=True
        run('systemctl','restart','medical-monitor')
        for _ in range(30):
            try:
                with urllib.request.urlopen('http://127.0.0.1:18765/health',timeout=2) as response:
                    health=json.load(response)
                if health.get('mqtt_connected'): break
            except (OSError,ValueError): pass
            time.sleep(1)
        else: raise RuntimeError('MQTT backend health timed out')
        run('nginx','-t')
        run('systemctl','reload','nginx')
        run('systemctl','enable','--now','medical-monitor-mock','medical-monitor-certificate.timer')
        print(json.dumps({'release':args.release,'mqtt_connected':True,'previous_release':old.name,'rollback_backup':backup.name}))
    except Exception:
        run('systemctl','disable','--now','medical-monitor-mock','medical-monitor-certificate.timer')
        if switched:
            link=ROOT/'current-mqtt-rollback'
            link.symlink_to(old)
            link.replace(ROOT/'current')
        shutil.copy2(backup/'backend.env',ROOT/'config/backend.env')
        run('systemctl','restart','medical-monitor')
        run('systemctl','disable','--now','medical-monitor-mqtt')
        raise RuntimeError('Upgrade failed; previous backend restored') from None

if __name__=='__main__':
    main()
