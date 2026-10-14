"""本机中转上传后的脱机安装：只新增 P6 目录/服务，不改生产监护与 Broker。"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import pwd
import subprocess
import tarfile


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--bundle', type=Path, required=True)
    parser.add_argument('--sha256', required=True)
    args = parser.parse_args()
    if os.geteuid() != 0:
        raise SystemExit('ROOT_INSTALL_REQUIRED')
    if hashlib.sha256(args.bundle.read_bytes()).hexdigest() != args.sha256:
        raise SystemExit('BUNDLE_HASH_MISMATCH')
    root = Path('/opt/medical-monitor-p6')
    if root.exists():
        raise SystemExit('P6_ISOLATED_DIRECTORY_EXISTS')
    root.mkdir(mode=0o755)
    # 只解压本轮本机生成的相对路径；拒绝符号链接与目录逃逸，不覆盖既有服务。
    with tarfile.open(args.bundle) as archive:
        for item in archive.getmembers():
            destination = (root / item.name).resolve()
            if not destination.is_relative_to(root) or item.issym() or item.islnk():
                raise SystemExit('BUNDLE_PATH_INVALID')
        archive.extractall(root, filter='data')
    subprocess.run(['python3', '-m', 'venv', str(root / '.venv')], check=True, capture_output=True)
    # 严禁服务器直接下载；所有依赖只从本机上传的 wheel 文件安装。
    subprocess.run([str(root / '.venv/bin/python'), '-m', 'pip', 'install', '--no-index', '--find-links', str(root / 'wheels'),
                    '-r', str(root / 'cloud/ai/requirements.txt')], check=True, capture_output=True)
    try:
        account = pwd.getpwnam('medical-ai')
    except KeyError:
        subprocess.run(['useradd', '--system', '--home', '/nonexistent', '--shell', '/usr/sbin/nologin', 'medical-ai'], check=True, capture_output=True)
        account = pwd.getpwnam('medical-ai')
    state = Path('/var/lib/medical-monitor-p6/20261014-budget')
    state.mkdir(parents=True, mode=0o700)
    os.chown(state, account.pw_uid, account.pw_gid)
    unit = root / 'cloud/deploy/p6-ai/p6-ai.service.example'
    target = Path('/etc/systemd/system/p6-ai.service')
    if target.exists():
        raise SystemExit('P6_SERVICE_ALREADY_EXISTS')
    target.write_bytes(unit.read_bytes())
    subprocess.run(['systemctl', 'daemon-reload'], check=True, capture_output=True)
    print(json.dumps({'installed': True, 'bundle_sha256': args.sha256, 'production_services_changed': False,
                      'state_directory': str(state), 'service_started': False}))


if __name__ == '__main__': main()
