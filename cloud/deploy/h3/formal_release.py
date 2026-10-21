"""H3正式发布准备/切换/回滚；prepare不变更正式路由，activate仅在现场发布窗口执行。"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import time
import urllib.request

from cloud.deploy.h3.isolated_server import STATE, load_env, store_env
from cloud.deploy.h3 import recovery_bundle, runtime_package

SNIPPET = Path('/etc/nginx/snippets/medical-monitor.conf')
FORMAL = ('medical-monitor.service', 'medical-monitor-mqtt.service', 'p6-ai.service')
UNITS = ('medical-monitor-h3-webbackend.service', 'medical-monitor-h3-webai.service')
PYTHON = '/opt/medical-monitor-p6/.venv/bin/python'


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def run(args):
    result = subprocess.run(args, capture_output=True)
    if result.returncode:
        # systemd/nginx错误可能含连接地址或环境值，只返回失败命令类型及退出码。
        raise RuntimeError('COMMAND_FAILED_' + Path(args[0]).name + '_' + str(result.returncode))
    return result.stdout.decode()


def service_identity():
    return {unit: {'pid': run(['systemctl', 'show', unit, '-p', 'MainPID', '--value']).strip(),
                   'state': run(['systemctl', 'show', unit, '-p', 'ActiveState', '--value']).strip()}
            for unit in FORMAL}


def atomic_copy(source, destination):
    # 同一目录内原子替换；不移动原发布链接，不触及主站其他location。
    temporary = destination.with_name(destination.name + '.h3-tmp')
    if temporary.exists():
        raise RuntimeError('TEMPORARY_PATH_OCCUPIED')
    shutil.copy2(source, temporary)
    os.replace(temporary, destination)


def formal_mqtt_config(path,release):
    """显式正式只读角色配置；不把隔离8884/测试角色复制到正式服务。"""
    if path is None:raise ValueError('FORMAL_MQTT_CONFIG_REQUIRED')
    path=path.resolve()
    if path.is_relative_to(release) or stat.S_IMODE(path.stat().st_mode)&0o077:
        raise ValueError('PRIVATE_EXTERNAL_FORMAL_MQTT_CONFIG_REQUIRED')
    config=json.loads(path.read_text())
    if config.get('port')!=8883 or config.get('purpose')!='FORMAL_BACKEND_READONLY' or \
       any(not isinstance(config.get(k),str) or not config[k] for k in ('host','username','password')) or \
       config['username'].startswith('h3-'):
        raise ValueError('FORMAL_MQTT_POLICY_REQUIRED')
    return config


def candidate_nginx(release):
    """保持AI完整前缀、剥离监护API/WS前缀，供prepare与只读语法预检共用。"""
    return '''location = /medical-monitor { return 301 /medical-monitor/; }
location ^~ /medical-monitor/ai/ {
 client_max_body_size 4k;
 proxy_pass http://127.0.0.1:18786;
 proxy_set_header Host $host;
 proxy_set_header X-Forwarded-Proto $scheme;
 proxy_connect_timeout 2s;
 proxy_read_timeout 15s;
 access_log off;
}
location ^~ /medical-monitor/ws/ {
 proxy_pass http://127.0.0.1:18785/ws/;
 proxy_http_version 1.1;
 proxy_set_header Upgrade $http_upgrade;
 proxy_set_header Connection "upgrade";
 proxy_set_header Host $host;
 proxy_buffering off;
 proxy_read_timeout 60s;
 access_log off;
}
location ^~ /medical-monitor/api/ {
 proxy_pass http://127.0.0.1:18785/api/;
 access_log off;
}
location ^~ /medical-monitor/ {
 alias WEB_ROOT/;
 index index.html;
 access_log off;
}
'''.replace('WEB_ROOT',str(release / 'cloud/web/dist'))


def require_recovery_coverage(specs):
    """角色标签不足以证明完整性；将清单与当前进程、环境和实际Nginx引用逐项绑定。"""
    def covered(role,path):
        path=Path(path).absolute()
        return any(s['role']==role and (path==Path(s['path']).absolute() or
            Path(s['path']).absolute() in path.parents) for s in specs)
    def need(role,path):
        if not covered(role,path):raise ValueError('RECOVERY_COVERAGE_MISSING_'+role)
    for unit in (*FORMAL,'nginx.service'):
        fragment=run(['systemctl','show',unit,'-p','FragmentPath','--value']).strip()
        need('UNIT',fragment)
        for dropin in run(['systemctl','show',unit,'-p','DropInPaths','--value']).split():
            need('UNIT',dropin)
        pid=run(['systemctl','show',unit,'-p','MainPID','--value']).strip()
        need('EXECUTABLE',os.readlink('/proc/'+pid+'/exe'))
        if unit=='medical-monitor.service':need('BACKEND_TREE',Path(os.readlink('/proc/'+pid+'/cwd'))/'app')
        if unit=='p6-ai.service':need('AI_TREE',Path(os.readlink('/proc/'+pid+'/cwd'))/'cloud/ai')
    need('WEB_TREE',Path('/opt/medical-monitor/current').resolve()/'web/dist')
    need('RELEASE_LINK','/opt/medical-monitor/current')
    for name in ('/etc/medical-monitor/p6-ai.env','/opt/medical-monitor/config/backend.env'):
        need('ENV',name)
    old_ai=load_env('/etc/medical-monitor/p6-ai.env')
    need('STATE',old_ai['P6_REAL_BUDGET_DIR']);need('STATE',STATE)
    backend=load_env('/opt/medical-monitor/config/backend.env')
    need('BROKER',backend['MONITOR_MQTT_CONFIG'])
    # 实际Broker ACL/config路径仍须由F3只读审查另行冻结，不能仅凭订阅端凭据判定ACL。
    import re
    text=run(['nginx','-T'])
    for name in re.findall(r'^# configuration file (.+):$',text,re.M):need('NGINX',name)
    need('NGINX',SNIPPET)


def prepare(release,formal_mqtt_path=None,recovery_spec=None,python_path=None):
    release = release.resolve()
    if release.parent != Path('/opt/medical-monitor-h3/releases') or not release.name.startswith('runtime-'):
        raise ValueError('VERSIONED_RELEASE_REQUIRED')
    mqtt_config=formal_mqtt_config(formal_mqtt_path,release)
    metadata = runtime_package.verify(release)
    if recovery_spec is None or python_path is None:
        raise ValueError('COMPLETE_BACKUP_SPEC_AND_VERSIONED_PYTHON_REQUIRED')
    specs=json.loads(recovery_spec.read_text())
    require_recovery_coverage(specs)
    python_path=python_path.absolute()
    expected_python=Path('/opt/medical-monitor-h3/environments')/release.name/'bin/python'
    # 独立环境通过wheel锁安装；不可继续借用旧P6共享venv，避免候选依赖随旧服务变化。
    if python_path!=expected_python or not python_path.is_file():
        raise ValueError('VERSIONED_PYTHON_REQUIRED')
    installed=json.loads(run([str(python_path),'-c',
        'import importlib.metadata as m,json; print(json.dumps({d.metadata["Name"].lower().replace("_","-"):d.version for d in m.distributions()}))']))
    for line in (release/'cloud/deploy/h3/runtime-requirements.lock').read_text().splitlines():
        if not line.strip() or line.startswith('#'):continue
        name,version=line.strip().split('==')
        if installed.get(name.lower().replace('_','-'))!=version:
            raise ValueError('VERSIONED_DEPENDENCIES_MISMATCH')
    # 发布身份必须由当前文件逐项证明，不能仅相信旁边的来源标签。
    for name, expected in metadata['critical_source_sha256'].items():
        file=release/name
        if not file.resolve().is_relative_to(release) or digest(file)!=expected:
            raise ValueError('RELEASE_SOURCE_CHANGED')
    if not (release / 'cloud/web/dist/index.html').is_file():
        raise ValueError('WEB_RELEASE_MISSING')
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    stage = Path('/opt/medical-monitor-h3/formal') / stamp
    stage.mkdir(parents=True, mode=0o750)
    import pwd
    service_user=pwd.getpwnam('medical-ai')
    os.chown(stage,0,service_user.pw_gid)
    backup = stage / 'backup'; backup.mkdir(mode=0o700)
    # 完整对象清单由只读审计后冻结，创建备份本身仍属于AUTH-AC-CLOUD-STAGE。
    full_backup=recovery_bundle.create(specs,stage/'complete-backup')
    # 旧AI unit/env及访问控制原件只备份到服务器，秘密不进入返回JSON或Git。
    originals = [SNIPPET, Path('/etc/systemd/system/p6-ai.service'),
                 Path('/etc/medical-monitor/p6-ai.env'),
                 Path('/opt/medical-monitor/config/backend.env')]
    hashes = {}
    for index, source in enumerate(originals):
        target = backup / str(index)
        shutil.copy2(source, target); target.chmod(0o600)
        hashes[str(source)] = digest(source)
    before = service_identity()
    if any(v['state'] != 'active' or v['pid'] == '0' for v in before.values()):
        raise RuntimeError('FORMAL_SERVICE_NOT_ACTIVE')
    env = load_env(originals[3])
    origins = env['MONITOR_ALLOWED_ORIGINS']
    if not any(s.startswith('https://') for s in origins.split(',')):
        raise ValueError('FORMAL_HTTPS_ORIGIN_MISSING')
    backend = load_env(STATE / 'backend.env')
    backend.update(MONITOR_VIEW_TOKEN=env['MONITOR_VIEW_TOKEN'], MONITOR_ALLOWED_ORIGINS=origins)
    backend.pop('MONITOR_WEB_DIR', None)
    # 正式候选和隔离Backend并存时不能复用MQTT client_id，否则Broker会相互踢线。
    # 外部配置只在服务器内复制，口令不进入plan；服务账户沿用STATE的访问边界。
    # 输入已经过正式端口/角色/权限门禁，不再继承STATE隔离Backend的8884配置。
    mqtt_config['client_id']='h3-formal-backend-'+stamp
    mqtt_path=STATE/('formal-backend-'+stamp+'.json')
    with mqtt_path.open('x') as output:json.dump(mqtt_config,output)
    mqtt_path.chmod(0o600)
    os.chown(mqtt_path,service_user.pw_uid,service_user.pw_gid)
    backend['MONITOR_MQTT_CONFIG']=str(mqtt_path)
    ai = load_env(STATE / 'ai.env')
    ai.update(P6_AI_TOKEN=load_env(originals[2])['P6_AI_TOKEN'], P6_ALLOWED_ORIGINS=origins,
              P6_MONITOR_VIEW_TOKEN=env['MONITOR_VIEW_TOKEN'],
              P6_MONITOR_WS_URL='ws://127.0.0.1:18785/ws/v1/monitor',
              P6_MONITOR_ORIGIN=next(s for s in origins.split(',') if s.startswith('https://')))
    if min(len(backend['MONITOR_VIEW_TOKEN']), len(ai['P6_AI_TOKEN'])) < 32:
        raise ValueError('FORMAL_APPLICATION_TOKEN_INVALID')
    store_env(stage / 'backend.env', backend); store_env(stage / 'ai.env', ai)
    for name in ('backend.env','ai.env'):
        os.chown(stage/name,service_user.pw_uid,service_user.pw_gid)
    for unit, environment, working, command in [
        (UNITS[0], 'backend.env', release / 'cloud/backend',
         str(python_path) + ' -m uvicorn app.main:app --host 127.0.0.1 --port 18785 --no-access-log'),
        (UNITS[1], 'ai.env', release,
         str(python_path) + ' -m uvicorn cloud.ai.app:create_app --factory --host 127.0.0.1 --port 18786 --no-access-log')]:
        unit_path = Path('/etc/systemd/system') / unit
        if unit_path.exists():
            raise ValueError('NEW_UNIT_NAME_OCCUPIED')
        (stage / unit).write_text('[Unit]\nDescription=H3 validated monitor candidate\nAfter=network.target\n'
            '[Service]\nUser=medical-ai\nGroup=medical-ai\nWorkingDirectory=' + str(working) +
            '\nEnvironmentFile=' + str(stage / environment) + '\nExecStart=' + command +
            '\nRestart=on-failure\nRestartSec=3\nUMask=0077\n[Install]\nWantedBy=multi-user.target\n')
    # 哈希路由使用同一index；AI保留完整上游前缀，WS/API明确剥离项目前缀。
    candidate = candidate_nginx(release)
    (stage / 'candidate.nginx.conf').write_text(candidate)
    syntax = stage / 'syntax.nginx.conf'
    syntax.write_text('pid ' + str(stage / 'syntax.pid') + ';\nevents {}\nhttp { include /etc/nginx/mime.types; '
                     'server { listen 127.0.0.1:18885; include ' + str(stage / 'candidate.nginx.conf') + '; } }')
    run(['nginx', '-t', '-c', str(syntax)])
    assert service_identity() == before and all(digest(p) == sha for p, sha in hashes.items())
    plan = {'plan_schema_version':2,'stage': str(stage), 'release': str(release), 'source': metadata,
            'formal_mqtt_policy':{'port':8883,'purpose':'FORMAL_BACKEND_READONLY'},
            'complete_backup':full_backup,'versioned_python':str(python_path),
            'original_hashes': hashes, 'original_services': before,
            'previous_web_release': str(Path('/opt/medical-monitor/current').resolve()),
            'previous_web_index_sha256': digest('/opt/medical-monitor/current/web/dist/index.html'),
            'candidate_web_index_sha256': digest(release / 'cloud/web/dist/index.html'),
            'candidate_nginx_sha256': digest(stage / 'candidate.nginx.conf'),
            'owned_unit_sha256': {unit: digest(stage / unit) for unit in UNITS},
            'owned_env_sha256': {name:digest(stage/name) for name in ('backend.env','ai.env')},
            'owned_mqtt_config':{'path':str(mqtt_path),'sha256':digest(mqtt_path)},
            'state': 'PREPARED_ONLY_NOT_PUBLISHED', 'nginx_syntax_exit_code': 0,
            'original_services_unchanged': True, 'secrets_in_receipt': False}
    (stage / 'plan.json').write_text(json.dumps(plan, indent=2))
    return plan


def switch(plan_path, rollback=False):
    plan = json.loads(plan_path.read_text()); stage = Path(plan['stage'])
    if plan_path.resolve() != stage / 'plan.json' or stage.parent != Path('/opt/medical-monitor-h3/formal'):
        raise ValueError('PREPARED_PLAN_PATH_REQUIRED')
    if not rollback and (plan.get('plan_schema_version')!=2 or plan.get('formal_mqtt_policy')!={'port':8883,'purpose':'FORMAL_BACKEND_READONLY'}):
        raise RuntimeError('R2_REPREPARE_WITH_FORMAL_MQTT_REQUIRED')
    full=plan.get('complete_backup')
    if not full or full.get('state')!='VERIFIED_COMPLETE':
        raise RuntimeError('COMPLETE_RECOVERY_PACKAGE_REQUIRED')
    recovery_bundle.verify(full['path'],full['manifest_sha256'])
    # 候选损坏不应封锁回退；回退只依赖可信原件和当前已批准路由的身份。
    if not rollback:runtime_package.verify(plan['release'])
    if service_identity() != plan['original_services']:
        raise RuntimeError('FORMAL_SERVICE_IDENTITY_CHANGED')
    if not rollback and digest(stage / 'candidate.nginx.conf') != plan['candidate_nginx_sha256']:
        raise RuntimeError('CANDIDATE_ROUTE_CHANGED')
    # 回滚原件与候选环境均须在变更前核对，不能把损坏备份切到正式入口。
    if digest(stage/'backup/0')!=plan['original_hashes'][str(SNIPPET)]:
        raise RuntimeError('ROLLBACK_BACKUP_CHANGED')
    if rollback:
        if digest(SNIPPET) != plan['candidate_nginx_sha256']:
            raise RuntimeError('ROLLBACK_CURRENT_ROUTE_MISMATCH')
        atomic_copy(stage / 'backup/0', SNIPPET)
        run(['nginx', '-t']); run(['systemctl', 'reload', 'nginx'])
        run(['systemctl', 'disable', '--now', *UNITS])
        state = 'ROLLED_BACK_ORIGINAL_ROUTE'
    else:
        if any(digest(p) != sha for p, sha in plan['original_hashes'].items()):
            raise RuntimeError('ORIGINAL_CONFIGURATION_CHANGED')
        for name, expected in plan['owned_env_sha256'].items():
            if digest(stage/name)!=expected:raise RuntimeError('CANDIDATE_ENVIRONMENT_CHANGED')
        mqtt=plan['owned_mqtt_config']
        if digest(mqtt['path'])!=mqtt['sha256']:raise RuntimeError('CANDIDATE_MQTT_CONFIG_CHANGED')
        config=json.loads(Path(mqtt['path']).read_text())
        if config.get('port')!=8883 or config.get('purpose')!='FORMAL_BACKEND_READONLY':
            raise RuntimeError('CANDIDATE_MQTT_POLICY_CHANGED')
        for name, expected in plan['source']['critical_source_sha256'].items():
            if digest(Path(plan['release'])/name)!=expected:raise RuntimeError('RELEASE_SOURCE_CHANGED')
        for unit, sha in plan['owned_unit_sha256'].items():
            source, destination = stage / unit, Path('/etc/systemd/system') / unit
            if digest(source) != sha or (destination.exists() and digest(destination) != sha):
                raise RuntimeError('OWNED_UNIT_MISMATCH')
        try:
            # 先验证所有unit再复制；第二份复制失败也进入同一清理边界，避免部分安装漏处理。
            for unit in plan['owned_unit_sha256']:
                atomic_copy(stage / unit, Path('/etc/systemd/system') / unit)
            run(['systemctl', 'daemon-reload']); run(['systemctl', 'enable', '--now', *UNITS])
            for port in (18785, 18786):
                ready = False
                for attempt in range(30):
                    try:
                        with urllib.request.urlopen('http://127.0.0.1:' + str(port) + '/health', timeout=1) as response:
                            # Backend的HTTP 200/degraded不能被当成MQTT订阅就绪。
                            data=json.load(response)
                            ready=response.status==200 and data.get('status')=='ok'
                            if port==18785:ready=ready and data.get('mqtt_connected') is True
                            else:ready=ready and data.get('model_mode')=='DOUBAO' and data.get('snapshot_mode')=='MONITOR'
                    except OSError:
                        pass
                    if ready: break
                    time.sleep(.2)
                if not ready: raise RuntimeError('NEW_SERVICE_NOT_READY')
            atomic_copy(stage / 'candidate.nginx.conf', SNIPPET)
            run(['nginx', '-t']); run(['systemctl', 'reload', 'nginx'])
        except BaseException:
            # 启动/健康检查也属于同一失败边界；只清理本次新服务，保留原始异常。
            try:
                if digest(SNIPPET)!=plan['original_hashes'][str(SNIPPET)]:
                    atomic_copy(stage / 'backup/0', SNIPPET)
                    run(['nginx', '-t']); run(['systemctl', 'reload', 'nginx'])
            finally:
                run(['systemctl', 'disable', '--now', *UNITS])
            raise
        state = 'ACTIVATED_PENDING_HTTPS_ACCEPTANCE'
    assert service_identity() == plan['original_services']
    return {'state': state, 'stage': str(stage), 'nginx_sha256': digest(SNIPPET),
            'original_services_unchanged': True, 'exit_code': 0}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=('prepare', 'activate', 'rollback'))
    parser.add_argument('--release', type=Path); parser.add_argument('--plan', type=Path)
    parser.add_argument('--formal-mqtt-config',type=Path)
    parser.add_argument('--recovery-spec',type=Path)
    parser.add_argument('--python',type=Path)
    args = parser.parse_args()
    try:
        result = prepare(args.release,args.formal_mqtt_config,args.recovery_spec,args.python) if args.action == 'prepare' else switch(args.plan, args.action == 'rollback')
        print(json.dumps(result, indent=2))
    except Exception as exc:
        print(json.dumps({'exit_code': 1, 'failure_type': type(exc).__name__, 'details_suppressed': True}))
        raise SystemExit(1)
