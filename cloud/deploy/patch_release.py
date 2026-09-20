"""给现有项目 release 应用小型源码补丁；不下载依赖，失败自动切回旧链接。"""

import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import time
import urllib.request
import zipfile


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--bundle', type=Path, required=True)
    parser.add_argument('--sha256', required=True)
    parser.add_argument('--release', required=True)
    args = parser.parse_args()
    root = Path('/opt/medical-monitor')
    if not re.fullmatch(r'[a-z0-9-]{1,80}', args.release):
        raise RuntimeError('Invalid release name')
    old = (root / 'current').resolve()
    release = root / 'releases' / args.release
    if not old.is_relative_to(root / 'releases') or release.exists():
        raise RuntimeError('Release boundary failed')
    if hashlib.sha256(args.bundle.read_bytes()).hexdigest() != args.sha256:
        raise RuntimeError('Bundle verification failed')
    allowed = {'backend/app/adapters.py', 'backend/app/mqtt_adapter.py'}
    # 只允许本次审核过的应用模块，补丁不能改凭据、Broker、站点或服务权限。
    with zipfile.ZipFile(args.bundle) as archive:
        if set(archive.namelist()) != allowed:
            raise RuntimeError('Unexpected patch members')
        shutil.copytree(old, release, symlinks=True)
        for name in archive.namelist():
            target = release / name
            if not target.resolve().is_relative_to(release):
                raise RuntimeError('Unsafe patch target')
            target.write_bytes(archive.read(name))
    backup = root / 'backups' / args.release
    backup.mkdir(mode=0o700)
    (backup / 'previous-current.txt').write_text(str(old))

    # 临时链接原子替换 current 后重启 Backend；外层健康检查失败时用同一路径切回旧版。
    def switch(target):
        link = root / (args.release + '-next')
        link.symlink_to(target)
        link.replace(root / 'current')
        result = subprocess.run(
            ['systemctl', 'restart', 'medical-monitor'], capture_output=True, timeout=30
        )
        if result.returncode:
            raise RuntimeError('Backend restart failed')

    try:
        switch(release)
        for _ in range(30):
            try:
                with urllib.request.urlopen(
                    'http://127.0.0.1:18765/api/health', timeout=2
                ) as response:
                    health = json.load(response)
                if health.get('mqtt_connected'):
                    break
            except (OSError, ValueError):
                pass
            time.sleep(1)
        else:
            raise RuntimeError('Backend health check failed')
        hashes = {
            name: hashlib.sha256((release / name).read_bytes()).hexdigest()
            for name in sorted(allowed)
        }
        print(
            json.dumps(
                {
                    'release': args.release,
                    'mqtt_connected': True,
                    'source_sha256': hashes,
                    'previous_release': old.name,
                }
            )
        )
    except Exception:
        switch(old)
        raise RuntimeError('Patch failed; previous Backend release restored') from None


if __name__ == '__main__':
    main()
