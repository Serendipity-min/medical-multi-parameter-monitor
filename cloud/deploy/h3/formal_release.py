"""H3正式发布准备/切换/回滚；prepare不变更正式路由，activate仅在现场发布窗口执行。"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import time
import urllib.request

from cloud.deploy.h3.isolated_server import STATE, load_env, store_env

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


def prepare(release):
    release = release.resolve()
    if release.parent != Path('/opt/medical-monitor-h3/releases') or not release.name.startswith('runtime-'):
        raise ValueError('VERSIONED_RELEASE_REQUIRED')
    metadata = json.loads((release / 'H3_RUNTIME_SOURCE.json').read_text())
    if not (release / 'cloud/web/dist/index.html').is_file():
        raise ValueError('WEB_RELEASE_MISSING')
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    stage = Path('/opt/medical-monitor-h3/formal') / stamp
    stage.mkdir(parents=True, mode=0o750)
    backup = stage / 'backup'; backup.mkdir(mode=0o700)
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
    ai = load_env(STATE / 'ai.env')
    ai.update(P6_AI_TOKEN=load_env(originals[2])['P6_AI_TOKEN'], P6_ALLOWED_ORIGINS=origins,
              P6_MONITOR_VIEW_TOKEN=env['MONITOR_VIEW_TOKEN'],
              P6_MONITOR_WS_URL='ws://127.0.0.1:18785/ws/v1/monitor',
              P6_MONITOR_ORIGIN=next(s for s in origins.split(',') if s.startswith('https://')))
    if min(len(backend['MONITOR_VIEW_TOKEN']), len(ai['P6_AI_TOKEN'])) < 32:
        raise ValueError('FORMAL_APPLICATION_TOKEN_INVALID')
    store_env(stage / 'backend.env', backend); store_env(stage / 'ai.env', ai)
    for unit, environment, working, command in [
        (UNITS[0], 'backend.env', release / 'cloud/backend',
         PYTHON + ' -m uvicorn app.main:app --host 127.0.0.1 --port 18785 --no-access-log'),
        (UNITS[1], 'ai.env', release,
         PYTHON + ' -m uvicorn cloud.ai.app:create_app --factory --host 127.0.0.1 --port 18786 --no-access-log')]:
        unit_path = Path('/etc/systemd/system') / unit
        if unit_path.exists():
            raise ValueError('NEW_UNIT_NAME_OCCUPIED')
        (stage / unit).write_text('[Unit]\nDescription=H3 validated monitor candidate\nAfter=network.target\n'
            '[Service]\nUser=medical-ai\nGroup=medical-ai\nWorkingDirectory=' + str(working) +
            '\nEnvironmentFile=' + str(stage / environment) + '\nExecStart=' + command +
            '\nRestart=on-failure\nRestartSec=3\nUMask=0077\n[Install]\nWantedBy=multi-user.target\n')
    # 哈希路由使用同一index；AI保留完整上游前缀，WS/API明确剥离项目前缀。
    candidate = '''location = /medical-monitor { return 301 /medical-monitor/; }
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
'''.replace('WEB_ROOT', str(release / 'cloud/web/dist'))
    (stage / 'candidate.nginx.conf').write_text(candidate)
    syntax = stage / 'syntax.nginx.conf'
    syntax.write_text('pid ' + str(stage / 'syntax.pid') + ';\nevents {}\nhttp { include /etc/nginx/mime.types; '
                     'server { listen 127.0.0.1:18885; include ' + str(stage / 'candidate.nginx.conf') + '; } }')
    run(['nginx', '-t', '-c', str(syntax)])
    assert service_identity() == before and all(digest(p) == sha for p, sha in hashes.items())
    plan = {'stage': str(stage), 'release': str(release), 'source': metadata,
            'original_hashes': hashes, 'original_services': before,
            'previous_web_release': str(Path('/opt/medical-monitor/current').resolve()),
            'previous_web_index_sha256': digest('/opt/medical-monitor/current/web/dist/index.html'),
            'candidate_web_index_sha256': digest(release / 'cloud/web/dist/index.html'),
            'candidate_nginx_sha256': digest(stage / 'candidate.nginx.conf'),
            'owned_unit_sha256': {unit: digest(stage / unit) for unit in UNITS},
            'state': 'PREPARED_ONLY_NOT_PUBLISHED', 'nginx_syntax_exit_code': 0,
            'original_services_unchanged': True, 'secrets_in_receipt': False}
    (stage / 'plan.json').write_text(json.dumps(plan, indent=2))
    return plan


def switch(plan_path, rollback=False):
    plan = json.loads(plan_path.read_text()); stage = Path(plan['stage'])
    if plan_path.resolve() != stage / 'plan.json' or stage.parent != Path('/opt/medical-monitor-h3/formal'):
        raise ValueError('PREPARED_PLAN_PATH_REQUIRED')
    if service_identity() != plan['original_services']:
        raise RuntimeError('FORMAL_SERVICE_IDENTITY_CHANGED')
    if digest(stage / 'candidate.nginx.conf') != plan['candidate_nginx_sha256']:
        raise RuntimeError('CANDIDATE_ROUTE_CHANGED')
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
        for unit, sha in plan['owned_unit_sha256'].items():
            source, destination = stage / unit, Path('/etc/systemd/system') / unit
            if digest(source) != sha or (destination.exists() and digest(destination) != sha):
                raise RuntimeError('OWNED_UNIT_MISMATCH')
            atomic_copy(source, destination)
        run(['systemctl', 'daemon-reload']); run(['systemctl', 'enable', '--now', *UNITS])
        for port in (18785, 18786):
            ready = False
            for attempt in range(30):
                try:
                    with urllib.request.urlopen('http://127.0.0.1:' + str(port) + '/health', timeout=1) as response:
                        ready = response.status == 200
                except OSError:
                    pass
                if ready: break
                time.sleep(.2)
            if not ready: raise RuntimeError('NEW_SERVICE_NOT_READY')
        atomic_copy(stage / 'candidate.nginx.conf', SNIPPET)
        try:
            run(['nginx', '-t']); run(['systemctl', 'reload', 'nginx'])
        except BaseException:
            # 语法/加载失败恢复原路由，不能让部分发布继续占用正式入口。
            atomic_copy(stage / 'backup/0', SNIPPET)
            run(['nginx', '-t']); run(['systemctl', 'reload', 'nginx'])
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
    args = parser.parse_args()
    try:
        result = prepare(args.release) if args.action == 'prepare' else switch(args.plan, args.action == 'rollback')
        print(json.dumps(result, indent=2))
    except Exception as exc:
        print(json.dumps({'exit_code': 1, 'failure_type': type(exc).__name__, 'details_suppressed': True}))
        raise SystemExit(1)
