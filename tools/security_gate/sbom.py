"""补齐自定义 Python runtime lock 的精确包清单，不猜测依赖关系或许可证。"""
import json
from pathlib import Path
import re
from common import dump, sha

def complete_runtime_locks(sbom_path, repo, requirements):
    data = json.loads(Path(sbom_path).read_text())
    if data.get('bomFormat') != 'CycloneDX':
        raise ValueError('invalid SBOM format')
    components = data.setdefault('components', [])
    known = {c.get('purl') for c in components}
    added = 0
    for name in requirements:
        lock = Path(repo) / name
        # 只接受精确版本；行内 marker/hash 不用于臆测平台兼容性或包关系。
        for line in lock.read_text(encoding='utf-8-sig').splitlines():
            line = line.strip()
            if not line or line.startswith(('#', '--hash=')):
                continue
            match = re.match(r'^([A-Za-z0-9_.-]+)==([A-Za-z0-9_.+!-]+)(?:\s|;|\\|$)', line)
            if not match:
                raise ValueError('SBOM requires explicit exact runtime lock')
            package, version = match.groups()
            normalized = re.sub(r'[-_.]+', '-', package).lower()
            purl = 'pkg:pypi/' + normalized + '@' + version
            if purl not in known:
                components.append({'type':'library', 'name':normalized, 'version':version,
                    'purl':purl, 'bom-ref':purl,
                    'properties':[{'name':'security-gate:source-lock', 'value':name},
                                  {'name':'security-gate:source-sha256', 'value':sha(lock)}]})
                known.add(purl)
                added += 1
    dump(sbom_path, data)
    return added
