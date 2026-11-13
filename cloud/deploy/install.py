"""首次离线部署：只改指定站点的一个 include，失败自动撤回本次配置。"""

import argparse
import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import time
import urllib.request
import zipfile

ROOT = Path('/opt/medical-monitor')
SERVICE = Path('/etc/systemd/system/medical-monitor.service')
SNIPPET = Path('/etc/nginx/snippets/medical-monitor.conf')
INCLUDE = '    include /etc/nginx/snippets/medical-monitor.conf;'


def command(*args):
    # 错误仅报告命令名与退出码，不把含站点信息的 stderr 写入执行日志。
    result = subprocess.run(args, capture_output=True, text=True)
    if result.returncode:
        raise RuntimeError(f'{args[0]} failed ({result.returncode})')


# 仅安装显式指定的本机已上传包；命令有副作用，不能作为普通导入或只读验证入口运行。
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--bundle', type=Path, required=True)
    parser.add_argument('--sha256', required=True)
    parser.add_argument('--environment', type=Path, required=True)
    parser.add_argument('--nginx-config', type=Path, required=True)
    parser.add_argument('--release', required=True)
    args = parser.parse_args()
    if os.geteuid() != 0:
        raise RuntimeError('Run via sudo')
    if not args.release.replace('-', '').isalnum():
        raise ValueError('Invalid release identifier')
    target = args.nginx_config.resolve()
    if not target.is_relative_to('/etc/nginx'):
        raise ValueError('Nginx target must remain within /etc/nginx')
    if hashlib.sha256(args.bundle.read_bytes()).hexdigest() != args.sha256:
        raise ValueError('Bundle checksum mismatch')
    if SERVICE.exists() or SNIPPET.exists() or (ROOT / 'current').exists():
        raise RuntimeError('Existing deployment: manual reviewed upgrade required')
    original = target.read_bytes()
    text = original.decode()
    # 只支持已经核查过的单 server 配置；存在歧义时停止，不猜测插入位置。
    if text.count('server {') != 1 or text.rstrip()[-1:] != '}' or '/medical-monitor' in text:
        raise RuntimeError('Unexpected Nginx structure')
    release = ROOT / 'releases' / args.release
    release.mkdir(parents=True, exist_ok=False)
    with zipfile.ZipFile(args.bundle) as archive:
        for name in archive.namelist():
            if not (release / name).resolve().is_relative_to(release):
                raise ValueError('Unsafe bundle member')
        archive.extractall(release)
    command('python3', '-m', 'venv', str(release / '.venv'))
    # 所有依赖来自本机上传的 wheel，不允许服务器访问 PyPI 或其他下载源。
    command(
        str(release / '.venv/bin/python'),
        '-m',
        'pip',
        'install',
        '--no-index',
        '--find-links',
        str(release / 'wheels'),
        '-r',
        str(release / 'backend/requirements.lock'),
    )
    backup = ROOT / 'backups' / args.release
    backup.mkdir(parents=True, mode=0o700)
    os.chmod(backup.parent, 0o700)
    shutil.copy2(target, backup / 'nginx-site.conf')
    (backup / 'nginx-target.txt').write_text(str(target))
    (ROOT / 'config').mkdir(mode=0o700, exist_ok=True)
    shutil.copyfile(args.environment, ROOT / 'config/backend.env')
    os.chmod(ROOT / 'config/backend.env', 0o600)
    try:
        (ROOT / 'current').symlink_to(release, target_is_directory=True)
        shutil.copyfile(release / 'deploy/medical-monitor.service', SERVICE)
        shutil.copyfile(release / 'deploy/nginx/medical-monitor.conf', SNIPPET)
        command('systemctl', 'daemon-reload')
        command('systemctl', 'start', 'medical-monitor')
        for attempt in range(20):
            try:
                with urllib.request.urlopen('http://127.0.0.1:18765/health', timeout=2) as response:
                    assert response.status == 200
                break
            except Exception:
                if attempt == 19:
                    raise RuntimeError('Backend readiness failed') from None
                time.sleep(0.5)
        # 配置落盘后先语法验证；只有验证通过才 reload 现有 Nginx。
        index = text.rfind('}')
        target.write_text(text[:index] + INCLUDE + '\n' + text[index:])
        command('nginx', '-t')
        command('systemctl', 'reload', 'nginx')
        command('systemctl', 'enable', 'medical-monitor')
    except Exception:
        target.write_bytes(original)
        command('nginx', '-t')
        command('systemctl', 'reload', 'nginx')
        command('systemctl', 'stop', 'medical-monitor')
        SERVICE.unlink(missing_ok=True)
        SNIPPET.unlink(missing_ok=True)
        (ROOT / 'current').unlink(missing_ok=True)
        command('systemctl', 'daemon-reload')
        raise
    print('DEPLOYED', args.release)
    print('BACKUP', backup)


if __name__ == '__main__':
    main()
