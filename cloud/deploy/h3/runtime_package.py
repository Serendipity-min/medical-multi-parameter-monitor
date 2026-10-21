"""只在本机制作完整候选包；无SSH/SCP、无服务启动，也不读取任何凭据。"""
import argparse
import gzip
import hashlib
import io
import json
from pathlib import Path
import subprocess
import tarfile

ROOT = Path(__file__).resolve().parents[3]
REQUIRED = ('cloud/backend/app/hub.py', 'cloud/ai/usage.py', 'cloud/web/dist/index.html',
            'cloud/backend/requirements.lock', 'cloud/deploy/h3/runtime-requirements.lock')


def digest(data):
    return hashlib.sha256(data).hexdigest()


def verify(release):
    release = Path(release)
    data = json.loads((release / 'H3_RUNTIME_SOURCE.json').read_text())
    if data.get('schema') != 2 or not set(REQUIRED).issubset(data['critical_source_sha256']):
        raise ValueError('COMPLETE_NEW_RUNTIME_REQUIRED')
    paths = data['critical_source_sha256']
    actual = {p.relative_to(release).as_posix() for p in release.rglob('*') if p.is_file()}
    if actual != set(paths) | {'H3_RUNTIME_SOURCE.json'}:
        raise ValueError('RUNTIME_UNMANIFESTED_OR_MISSING_FILE')
    for name, expected in paths.items():
        target = release / name
        if target.is_symlink() or not target.resolve().is_relative_to(release.resolve()) or digest(target.read_bytes()) != expected:
            raise ValueError('RUNTIME_FILE_CHANGED')
    frozen = digest(json.dumps(paths, sort_keys=True).encode())
    if frozen != data['payload_sha256']:
        raise ValueError('RUNTIME_IDENTITY_MISMATCH')
    if not data.get('backend_session_fix_present') or not data.get('persistent_usage_ledger'):
        raise ValueError('RUNTIME_REQUIRED_FIX_MISSING')
    return data


def package(destination, wheelhouse, source=ROOT):
    source, destination, wheelhouse = Path(source).resolve(), Path(destination).resolve(), Path(wheelhouse).resolve()
    if destination.is_relative_to(source) or wheelhouse.is_relative_to(source):
        raise ValueError('EXTERNAL_PACKAGE_AND_WHEELHOUSE_REQUIRED')
    commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=source, text=True).strip()
    if subprocess.run(['git', 'diff', '--quiet', 'HEAD', '--', 'cloud'], cwd=source).returncode:
        raise ValueError('COMMIT_RUNTIME_INPUTS_FIRST')
    tracked = subprocess.check_output(['git', 'ls-files', '-z', 'cloud'], cwd=source).decode().split('\0')
    files = {}
    for name in tracked:
        path = Path(name)
        include = (name.startswith('cloud/backend/app/') or name.startswith('cloud/ai/')) and path.suffix == '.py' and 'tests' not in path.parts
        include |= name.startswith('cloud/deploy/h3/') and path.suffix in ('.py', '.lock')
        include |= name in ('cloud/backend/requirements.txt', 'cloud/backend/requirements.lock',
                            'cloud/ai/requirements.txt', 'cloud/web/package.json', 'cloud/web/package-lock.json')
        if name and include:
            files[name] = (source / name).read_bytes()
    for p in sorted((source / 'cloud/web/dist').rglob('*')):
        if p.is_file():
            if p.is_symlink():
                raise ValueError('WEB_SYMLINK_NOT_ALLOWED')
            files[p.relative_to(source).as_posix()] = p.read_bytes()
    wheels = list(wheelhouse.glob('*.whl'))
    if not wheels:
        raise ValueError('OFFLINE_LINUX_WHEELS_REQUIRED')
    for p in wheels:
        files['wheels/' + p.name] = p.read_bytes()
    # 来源必须包含已接受的Backend修复，不能给旧树贴上新标签。
    subprocess.run(['git', 'merge-base', '--is-ancestor', '8afb1e2903f18c3a562769b9e9352db7e1db438a', commit], cwd=source, check=True)
    hub = files['cloud/backend/app/hub.py'].decode()
    usage = files['cloud/ai/usage.py'].decode()
    if 'current_generation' not in hub or 'gateway_generation' not in hub or 'sqlite3' not in usage:
        raise ValueError('REQUIRED_RUNTIME_FIX_NOT_PRESENT')
    hashes = {n: digest(b) for n, b in sorted(files.items())}
    payload = digest(json.dumps(hashes, sort_keys=True).encode())
    metadata = {'schema': 2, 'source_commit': commit, 'payload_sha256': payload,
        'backend_session_fix_commit': '8afb1e2903f18c3a562769b9e9352db7e1db438a',
        'backend_session_fix_present': True, 'persistent_usage_ledger': True,
        'critical_source_sha256': hashes, 'python_target': 'CPython3.12_Linux_x86_64',
        'runtime_install': 'create sibling environments/runtime-ID with python3.12; install --no-index --find-links RELEASE/wheels -r RELEASE/cloud/deploy/h3/runtime-requirements.lock',
        'server_dependency_install': 'NOT_EXECUTED_AUTH_CLOUD_STAGE_REQUIRED',
        'web_dist_sha256': digest(json.dumps({n: v for n, v in hashes.items() if n.startswith('cloud/web/dist/')}, sort_keys=True).encode())}
    files['H3_RUNTIME_SOURCE.json'] = json.dumps(metadata, sort_keys=True, indent=2).encode()
    destination.mkdir(parents=True, exist_ok=False)
    archive_path = destination / ('runtime-' + payload[:12] + '.tar.gz')
    # 固定tar/gzip元数据；相同提交、dist和wheel集合可精确复现包字节。
    with archive_path.open('xb') as raw, gzip.GzipFile(fileobj=raw, mode='wb', filename='', mtime=0) as compressed:
        with tarfile.open(fileobj=compressed, mode='w') as archive:
            for name, data in sorted(files.items()):
                info = tarfile.TarInfo(name); info.size = len(data); info.mode = 0o644
                archive.addfile(info, io.BytesIO(data))
    unpacked = destination / 'unpacked'; unpacked.mkdir()
    with tarfile.open(archive_path) as archive:
        archive.extractall(unpacked, filter='data')
    verify(unpacked)
    result = {'schema': 2, 'source_commit': commit, 'runtime_payload_sha256': payload,
        'archive_sha256': digest(archive_path.read_bytes()), 'archive_bytes': archive_path.stat().st_size,
        'web_dist_sha256': metadata['web_dist_sha256'], 'wheel_count': len(wheels),
        'files': len(files), 'state': 'LOCAL_IMMUTABLE_PACKAGE_VERIFIED_NOT_UPLOADED', 'exit_code': 0}
    (destination / 'receipt.json').write_text(json.dumps(result, indent=2))
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--destination', type=Path, required=True)
    parser.add_argument('--wheelhouse', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(package(args.destination, args.wheelhouse), indent=2))
