"""只读核验测试用 Paho 固定源码，并确认 Gateway 仍编译 coreMQTT。"""

import hashlib
import json
from pathlib import Path
import sys

from verify_coremqtt_integrity import check_build_sources


ROOT = Path(__file__).resolve().parent
VENDOR = ROOT / 'paho-embedded-c'
GATEWAY_BUILD = ROOT.parent / 'mqtt/build.py'
UPSTREAM_COMMIT = '6035ea2d4922bb7558b444fb2a051743f3f1974b'
# 仅规范化 Git 的 CRLF/LF 差异；原始上游元数据和每个原始 SHA 均不能随补丁重写。
UPSTREAM_MANIFEST_SHA256 = 'd3964efd7c864d93c34ac026a6e4c8228902cb7715ffe36b7a23d76a2aaa2569'
PATCHED_FILES = frozenset(
    (
        'MQTTClient-C/src/MQTTClient.c',
        'MQTTClient-C/src/MQTTClient.h',
        'MQTTPacket/src/MQTTConnectClient.c',
        'MQTTPacket/src/MQTTDeserializePublish.c',
        'MQTTPacket/src/MQTTFormat.c',
        'MQTTPacket/src/MQTTPacket.c',
        'MQTTPacket/src/MQTTPacket.h',
        'MQTTPacket/src/MQTTSubscribeClient.c',
        'MQTTPacket/src/MQTTUnsubscribeClient.c',
    )
)
class IntegrityError(ValueError):
    """固定元数据、补丁内容或构建范围与已评审基线不一致。"""


def verify_vendor(vendor: Path = VENDOR, build_path: Path = GATEWAY_BUILD) -> tuple[int, int]:
    """pristine 按原上游 SHA 校验；评审过的补丁仅按独立 patched 清单校验。"""
    upstream_bytes = (vendor / 'upstream.json').read_bytes()
    normalized = upstream_bytes.replace(b'\r\n', b'\n')
    if hashlib.sha256(normalized).hexdigest() != UPSTREAM_MANIFEST_SHA256:
        raise IntegrityError('upstream.json no longer matches the pinned original manifest')
    upstream = json.loads(upstream_bytes)
    patched = json.loads((vendor / 'patched.json').read_text(encoding='utf-8'))
    if upstream['commit'] != UPSTREAM_COMMIT or patched.get('upstream_commit') != UPSTREAM_COMMIT:
        raise IntegrityError('Paho upstream commit mismatch')
    hashes = patched.get('sha256', {})
    if patched.get('schema_version') != 1 or set(hashes) != PATCHED_FILES:
        raise IntegrityError('patched.json must list exactly the reviewed patched files')
    if not PATCHED_FILES.issubset(upstream['sha256']):
        raise IntegrityError('Patched files must retain an original upstream SHA')

    for name in ('edl-v10', 'epl-v20', 'PATCHES.md'):
        if not (vendor / name).is_file() or not (vendor / name).stat().st_size:
            raise IntegrityError('Missing or empty required vendor document: ' + name)

    for name, original_sha in upstream['sha256'].items():
        expected = hashes.get(name, original_sha)
        if not isinstance(expected, str) or len(expected) != 64:
            raise IntegrityError('Invalid SHA-256 entry: ' + name)
        actual = hashlib.sha256((vendor / name).read_bytes()).hexdigest()
        if actual != expected:
            group = 'patched' if name in hashes else 'pristine'
            raise IntegrityError(f'Paho {group} file mismatch: {name}')

    check_build_sources(build_path)
    return len(upstream['sha256']) - len(hashes), len(hashes)


def main() -> int:
    try:
        pristine, patched = verify_vendor()
    except (OSError, ValueError, KeyError, TypeError, SyntaxError) as error:
        print(f'Paho integrity FAILED: {error}', file=sys.stderr)
        return 1
    print(
        f'Paho integrity PASS: {pristine} pristine, {patched} patched; '
        'Paho excluded from Gateway build'
    )
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
