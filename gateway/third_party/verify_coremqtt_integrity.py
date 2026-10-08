"""离线核验官方固定源码及 active 编译白名单，不运行编译或安全扫描。"""

import argparse
import ast
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
VENDOR = ROOT / 'coreMQTT'
COMMIT = '2beef04725328923e05e576b884212d53ec97af7'
MANIFEST_SHA256 = '6bd79091c82cfa9b53c75f9f9a04ba63f71cbe40a0850ad41c9a7bfd01b940d9'
FILES = (
    'LICENSE', 'source/core_mqtt.c', 'source/core_mqtt_serializer.c',
    'source/core_mqtt_state.c', 'source/include/core_mqtt.h',
    'source/include/core_mqtt_serializer.h', 'source/include/core_mqtt_state.h',
    'source/include/core_mqtt_config_defaults.h', 'source/interface/transport_interface.h',
)
SOURCES = FILES[1:4]


def verify_vendor(vendor: Path = VENDOR) -> int:
    """路径先限制到固定集合和 vendor 内部，再读取原字节核验两个独立摘要。"""
    root = vendor.resolve()
    raw = (root / 'upstream.json').read_bytes()
    if hashlib.sha256(raw).hexdigest() != MANIFEST_SHA256:
        raise ValueError('coreMQTT original manifest changed')
    manifest = json.loads(raw)
    if (manifest.get('commit') != COMMIT or manifest.get('tag') != 'v2.3.1'
            or manifest.get('license') != 'MIT'
            or set(manifest.get('sha256', {})) != set(FILES)):
        raise ValueError('coreMQTT pinned identity/file set mismatch')
    actual = {p.relative_to(root).as_posix() for p in (root / 'source').rglob('*') if p.is_file()}
    if actual != set(FILES[1:]):
        raise ValueError('coreMQTT source file allowlist mismatch')
    for name in FILES:
        path = (root / name).resolve()
        if not path.is_relative_to(root):
            raise ValueError('coreMQTT path escaped vendor')
        data = path.read_bytes()
        digest = hashlib.sha256(data).hexdigest()
        blob = hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest()
        if (digest != manifest['sha256'][name]
                or blob != manifest['git_blob_sha1'][name]):
            raise ValueError('coreMQTT file digest mismatch: ' + name)
    return len(FILES)


def check_build_sources(path: Path) -> None:
    """只解析 AST：MQTT 源必须显式固定，不能通过 glob 或列表追加扩大范围。"""
    tree = ast.parse(path.read_text(encoding='utf-8'))
    assigns = [n for n in ast.walk(tree) if isinstance(n, ast.Assign)
               and any(isinstance(t, ast.Name) and t.id == 'mqtt_sources' for t in n.targets)]
    if len(assigns) != 1 or not isinstance(assigns[0].value, ast.List):
        raise ValueError('one explicit mqtt_sources list required')
    names = []
    for entry in assigns[0].value.elts:
        if not (isinstance(entry, ast.BinOp) and isinstance(entry.op, ast.Div)
                and isinstance(entry.left, ast.Name) and entry.left.id == 'vendor'
                and isinstance(entry.right, ast.Constant) and isinstance(entry.right.value, str)):
            raise ValueError('MQTT source must be a vendor-relative literal')
        names.append(entry.right.value)
    if tuple(names) != SOURCES:
        raise ValueError('active coreMQTT sources changed')
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            if 'paho-embedded-c' in node.value or 'MQTTCLIENT_PLATFORM_HEADER' in node.value:
                raise ValueError('Paho must not remain in active build')
        if isinstance(node, ast.AugAssign) and isinstance(node.target, ast.Name):
            if node.target.id in ('mqtt_sources', 'sources'):
                raise ValueError('source list mutation is forbidden')
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            if isinstance(node.func.value, ast.Name) and node.func.value.id in ('mqtt_sources', 'sources'):
                raise ValueError('source list mutation is forbidden')
    # 编译总列表必须引用该白名单，防止只声明而未实际使用。
    uses = [n for n in ast.walk(tree) if isinstance(n, ast.Starred)
            and isinstance(n.value, ast.Name) and n.value.id == 'mqtt_sources']
    if len(uses) != 1:
        raise ValueError('active build must consume mqtt_sources exactly once')


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--vendor-only', action='store_true')
    args = parser.parse_args()
    count = verify_vendor()
    if not args.vendor_only:
        check_build_sources(ROOT.parent / 'mqtt/build.py')
    print(f'coreMQTT integrity PASS: {count} pinned files; tag v2.3.1; active=' + str(not args.vendor_only))


if __name__ == '__main__':
    main()
