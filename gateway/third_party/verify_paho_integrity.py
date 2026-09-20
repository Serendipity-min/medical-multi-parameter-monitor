"""只读核验固定 Paho 上游、项目补丁和 Gateway 编译白名单，不导入构建脚本。"""

import ast
import hashlib
import json
from pathlib import Path
import sys


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
PAHO_SOURCES = (
    'MQTTClient-C/src/MQTTClient.c',
    'MQTTPacket/src/MQTTConnectClient.c',
    'MQTTPacket/src/MQTTDeserializePublish.c',
    'MQTTPacket/src/MQTTPacket.c',
    'MQTTPacket/src/MQTTSerializePublish.c',
    'MQTTPacket/src/MQTTSubscribeClient.c',
    'MQTTPacket/src/MQTTUnsubscribeClient.c',
)


class IntegrityError(ValueError):
    """固定元数据、补丁内容或构建范围与已评审基线不一致。"""


def check_build_sources(build_path: Path = GATEWAY_BUILD) -> tuple[str, ...]:
    """只解析 AST，避免 import build.py 触发编译或创建构建目录。"""
    tree = ast.parse(build_path.read_text(encoding='utf-8'), filename='gateway/mqtt/build.py')
    assignments = [
        node
        for node in tree.body
        if isinstance(node, ast.Assign)
        and any(isinstance(target, ast.Name) and target.id == 'sources' for target in node.targets)
    ]
    if len(assignments) != 1 or not isinstance(assignments[0].value, ast.List):
        raise IntegrityError('Gateway sources must be one explicit list')
    for node in ast.walk(tree):
        # 白名单之后追加 sources 会绕过上面的字面量核对，因此也拒绝这种构建写法。
        if (
            isinstance(node, ast.AugAssign)
            and isinstance(node.target, ast.Name)
            and node.target.id == 'sources'
        ):
            raise IntegrityError('Gateway sources must not be extended after declaration')
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == 'sources'
        ):
            raise IntegrityError('Gateway sources must not use mutation methods')
    if any(
        isinstance(node, ast.Constant)
        and isinstance(node.value, str)
        and 'MQTTFormat.c' in node.value
        for node in ast.walk(assignments[0].value)
    ):
        raise IntegrityError('MQTTFormat.c must not enter the Gateway source list')

    paho_sources = []
    for entry in assignments[0].value.elts:
        if not any(isinstance(node, ast.Name) and node.id == 'vendor' for node in ast.walk(entry)):
            continue
        # 只接受 vendor / "固定相对路径"；不执行表达式，也不允许 Paho glob 扩大编译范围。
        if not (
            isinstance(entry, ast.BinOp)
            and isinstance(entry.op, ast.Div)
            and isinstance(entry.left, ast.Name)
            and entry.left.id == 'vendor'
            and isinstance(entry.right, ast.Constant)
            and isinstance(entry.right.value, str)
        ):
            raise IntegrityError('Paho sources must use explicit vendor-relative literals')
        paho_sources.append(entry.right.value)

    if tuple(paho_sources) != PAHO_SOURCES:
        raise IntegrityError('Gateway Paho source allowlist changed; MQTTFormat.c is not permitted')
    return tuple(paho_sources)


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
        '7 allowed sources; MQTTFormat excluded'
    )
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
