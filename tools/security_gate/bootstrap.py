"""安装专用工具与锁定来源；默认只显示计划，永不扫描项目。"""
from __future__ import annotations
import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import urllib.request
from common import HERE, bridge, dump, environment, now, sha, tool_root, output_root

def fetch(url):
    request = urllib.request.Request(url, headers={'User-Agent': 'security-gate-bootstrap/1.0'})
    with urllib.request.urlopen(request, timeout=120) as response:
        return response.read()

def resolve_zap():
    """只解析官方公开镜像 digest；匿名 registry token 仅留内存，不持久化或输出。"""
    auth = json.loads(fetch('https://ghcr.io/token?scope=repository:zaproxy/zaproxy:pull&service=ghcr.io'))
    request = urllib.request.Request('https://ghcr.io/v2/zaproxy/zaproxy/manifests/stable', headers={
        'Authorization': 'Bearer ' + auth['token'],
        'Accept': 'application/vnd.oci.image.index.v1+json, application/vnd.docker.distribution.manifest.list.v2+json'})
    with urllib.request.urlopen(request, timeout=90) as response:
        blob = response.read()
        digest = 'sha256:' + hashlib.sha256(blob).hexdigest()
        if response.headers.get('Docker-Content-Digest', digest) != digest:
            raise ValueError('ZAP manifest digest mismatch')
    return {'version': 'stable-resolved', 'digest': digest, 'sha256': digest.split(':')[1],
            'installation_source': 'ghcr.io/zaproxy/zaproxy:stable', 'installed_at': None,
            'resolved_at': now(), 'status': 'METADATA_PINNED; Docker daemon/image preparation required'}

def release_binary(owner, name, suffix, root, lock):
    previous = lock.get(name, {})
    if previous.get('archive_sha256'):
        version = previous['version']
    else:
        version = json.loads(fetch(f'https://api.github.com/repos/{owner}/{name}/releases/latest'))['tag_name'].lstrip('v')
    asset = f'{name}_{version}_{suffix}.tar.gz'
    base = f'https://github.com/{owner}/{name}/releases/download/v{version}/'
    checksums = fetch(base + f'{name}_{version}_checksums.txt').decode()
    expected = next(line.split()[0] for line in checksums.splitlines() if line.split()[-1].lstrip('*') == asset)
    if previous.get('archive_sha256') and expected != previous['archive_sha256']:
        raise ValueError(name + ': upstream checksum differs from lock')
    target = root / 'bin' / name
    if target.exists() and previous.get('sha256') == sha(target):
        return previous
    blob = fetch(base + asset)
    if hashlib.sha256(blob).hexdigest() != expected:
        raise ValueError(name + ': release checksum mismatch')
    # 只提取指定常规二进制，拒绝归档中的路径穿越与符号链接。
    with tarfile.open(fileobj=io.BytesIO(blob), mode='r:gz') as archive:
        member = next(m for m in archive if m.name == name and m.isfile())
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(archive.extractfile(member).read())
        target.chmod(0o755)
    return {'version': version, 'installation_source': base + asset, 'archive_sha256': expected,
            'sha256': sha(target), 'installed_at': now()}

def main():
    bridge()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--install', action='store_true')
    parser.add_argument('--authorized-machine', action='store_true')
    parser.add_argument('--system-deps', action='store_true', help='安装发行版 clang/clang-tidy/bear/node/npm')
    parser.add_argument('--tool-root', type=Path, default=tool_root())
    parser.add_argument('--output-root', type=Path, default=output_root())
    args = parser.parse_args()
    if not args.install:
        print('PLAN: official checksum-verified Trivy/Gitleaks; isolated pip-audit venv; detect existing Semgrep; no scan')
        return 0
    if not args.authorized_machine:
        parser.error('--install requires --authorized-machine')
    root = args.tool_root.resolve()
    root.mkdir(parents=True, exist_ok=True)
    args.output_root.mkdir(parents=True, exist_ok=True)
    dump(Path.home() / '.config/security-gate/settings.json',
         {'tool_root': str(root), 'output_root': str(args.output_root.resolve())})
    lockpath = HERE / 'toolchain.lock.json'
    lock = json.loads(lockpath.read_text()) if lockpath.exists() else {'schema_version': 1, 'tools': {}}
    if args.system_deps:
        # 系统组件仅在显式安装参数下补齐；不替换 Semgrep，不修改全局 Python。
        prefix = [] if os.geteuid() == 0 else ['sudo']
        subprocess.run([*prefix, 'apt-get', 'update', '-qq'], check=True)
        subprocess.run([*prefix, 'apt-get', 'install', '-y', '--no-install-recommends',
                        'clang', 'clang-tidy', 'bear', 'nodejs', 'npm', 'python3-venv', 'libasan8', 'libubsan1'], check=True)
    for owner, name, suffix in [('aquasecurity', 'trivy', 'Linux-64bit'), ('gitleaks', 'gitleaks', 'linux_x64')]:
        print('Installing/verifying ' + name, flush=True)
        lock['tools'][name] = release_binary(owner, name, suffix, root, lock['tools'])
        dump(lockpath, lock)
    venv = root / 'pip-audit-venv'
    if not (venv / 'bin/python').exists():
        subprocess.run([sys.executable, '-m', 'venv', str(venv)], check=True)
    version = lock['tools'].get('pip-audit', {}).get('version')
    if not version:
        version = json.loads(fetch('https://pypi.org/pypi/pip-audit/json'))['info']['version']
    install_report = root / 'pip-audit-install.json'
    requirements = lock['tools'].get('pip-audit', {}).get('dependency_versions') or [f'pip-audit=={version}', 'PyYAML', 'jsonschema']
    subprocess.run([str(venv / 'bin/python'), '-m', 'pip', 'install', '--index-url', 'https://pypi.org/simple',
                    '--report', str(install_report), *requirements], check=True)
    packages = subprocess.check_output([str(venv / 'bin/python'), '-m', 'pip', 'freeze'], text=True)
    prior_hashes = lock['tools'].get('pip-audit', {}).get('download_hashes', {})
    lock['tools']['pip-audit'] = {'version': version, 'installation_source': 'https://pypi.org/project/pip-audit/',
                                'sha256': sha(venv / 'bin/pip-audit'), 'installed_at': now(),
                                'dependency_versions': packages.splitlines(), 'download_hashes': prior_hashes}
    if install_report.exists():
        data = json.loads(install_report.read_text())
        lock['tools']['pip-audit']['download_hashes'].update({
            p['metadata']['name']: p['download_info']['archive_info'].get('hashes', {}).get('sha256')
            for p in data.get('install', [])})
    # 只记录可公开的版本与文件哈希，命令错误原文不进入锁文件。
    for name, command in [('semgrep', ['semgrep', '--version']), ('clang', ['clang', '--version']),
                          ('clang-tidy', ['clang-tidy', '--version']), ('gcc', ['gcc', '--version']),
                          ('node', ['node', '--version']), ('npm', ['npm', '--version']),
                          ('bear', ['bear', '--version']), ('docker', ['docker', '--version'])]:
        executable = shutil.which(command[0], path=environment()['PATH'])
        if not executable:
            lock['tools'][name] = {'version': None, 'installation_source': 'not installed',
                                   'sha256': None, 'installed_at': None, 'status': 'UNAVAILABLE'}
            continue
        result = subprocess.run(command, capture_output=True, text=True, env=environment(), timeout=30)
        lock['tools'][name] = {'version': result.stdout.strip().splitlines()[0] if result.returncode == 0 else None,
                               'installation_source': 'existing installation' if name == 'semgrep' else 'Debian signed package archive',
                               'sha256': sha(executable), 'installed_at': now()}
    if not lock['tools'].get('zap', {}).get('digest'):
        try:
            lock['tools']['zap'] = resolve_zap()
        except Exception:
            lock['tools']['zap'] = {'version': None, 'digest': None, 'sha256': None,
                'installation_source': 'ghcr.io/zaproxy/zaproxy', 'installed_at': None,
                'status': 'UNAVAILABLE: registry metadata unavailable; baseline disabled'}
    lock['updated_at'] = now()
    dump(lockpath, lock)
    from doctor import inspect
    evidence = inspect(HERE.parents[1], args.output_root / 'bootstrap-doctor')
    dump(args.output_root / 'bootstrap-doctor/doctor.json', evidence)
    print(json.dumps({'bootstrap': 'complete', 'doctor': evidence['status'], 'scanning': False}))
    return 0 if evidence['status'] != 'ERROR' else 3

if __name__ == '__main__':
    raise SystemExit(main())
