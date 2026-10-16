"""核对本次公开资料清单的字节身份与路径边界，不执行安全扫描或硬件操作。"""
from pathlib import Path
import hashlib
import json


def main():
    root = Path(__file__).resolve().parents[2]
    data = json.loads((root / 'node-b/evidence/artifact-manifest.json').read_text('utf-8'))
    seen = set()
    failed = []
    for item in data['files']:
        rel = Path(item['path'])
        file = (root / rel).resolve()
        # 只允许清单中的项目文件；不跟随越界路径访问本机资料。
        if rel.is_absolute() or '..' in rel.parts or not file.is_relative_to(root) or item['path'] in seen:
            raise ValueError('资料清单路径越界或重复')
        seen.add(item['path'])
        if not file.is_file() or file.stat().st_size != item['bytes'] or \
                hashlib.sha256(file.read_bytes()).hexdigest() != item['sha256']:
            failed.append(item['path'])
    print(json.dumps({'scope': 'FILE_IDENTITY_ONLY', 'checked': len(seen), 'failed': failed}, ensure_ascii=False))
    return int(bool(failed))


if __name__ == '__main__':
    raise SystemExit(main())
