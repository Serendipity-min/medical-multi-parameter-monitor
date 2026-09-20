"""只输出结构化定位与规则标识，不公开源码片段、秘密值或漏洞描述中的地址。"""
import hashlib
import json
from pathlib import Path
import re
from common import relative, safe_id

def finding(tool, rule, path, repo, severity='MEDIUM', line=0, fix=None, kind='static'):
    item = {'tool': tool, 'rule': safe_id(rule), 'path': relative(path, repo),
            'severity': severity.upper(), 'line': int(line or 0), 'kind': kind, 'fix_available': fix}
    identity = '\0'.join(str(item[x]) for x in ('tool', 'rule', 'path', 'line'))
    item['id'] = hashlib.sha256(identity.encode()).hexdigest()[:24]
    return item

def parse(tool, path, repo):
    data = json.loads(Path(path).read_text(encoding='utf-8-sig'))
    results, gaps = [], []
    if tool == 'semgrep':
        if not isinstance(data, dict) or not isinstance(data.get('results'), list) or 'paths' not in data:
            raise ValueError('invalid Semgrep report')
        for row in data['results']:
            severity = {'ERROR': 'HIGH', 'WARNING': 'MEDIUM', 'INFO': 'LOW'}.get(row['extra']['severity'], 'MEDIUM')
            results.append(finding(tool, row['check_id'], row['path'], repo, severity, row.get('start', {}).get('line')))
        scanned = data['paths'].get('scanned', [])
        if not scanned:
            gaps.append({'id':'semgrep:zero-files-scanned', 'mandatory':True})
        gaps.extend('semgrep:' + safe_id(x.get('type', 'parse-error')) for x in data.get('errors', []))
        coverage = {'scanned': len(scanned), 'scanned_files': [relative(x, repo) for x in scanned],
                    'skipped': len(data['paths'].get('skipped', [])), 'errors': len(data.get('errors', []))}
    elif tool == 'gitleaks':
        if not isinstance(data, list):
            raise ValueError('invalid Gitleaks report')
        for row in data:
            results.append(finding(tool, row['RuleID'], row['File'], repo, 'CRITICAL', row.get('StartLine'), kind='secret'))
        coverage = {'findings': len(data)}
    elif tool == 'trivy':
        if not isinstance(data, dict) or 'SchemaVersion' not in data:
            raise ValueError('invalid Trivy report')
        for target in data.get('Results', []):
            for key, kind in [('Vulnerabilities', 'dependency'), ('Secrets', 'secret'), ('Misconfigurations', 'misconfig')]:
                for row in target.get(key, []) or []:
                    results.append(finding(tool, row.get('VulnerabilityID') or row.get('RuleID') or row.get('ID'),
                        target['Target'], repo, row.get('Severity', 'MEDIUM'),
                        row.get('StartLine', 0), bool(row.get('FixedVersion')) if kind == 'dependency' else None, kind))
        coverage = {'targets': len(data.get('Results', [])),
                    'licenses': sum(len(t.get('Licenses', []) or []) for t in data.get('Results', []))}
        if not coverage['targets']:
            gaps.append('trivy:no-recognized-targets')
        if not coverage['licenses']:
            gaps.append('trivy:license-inventory-incomplete')
    elif tool == 'pip-audit':
        if not isinstance(data, dict) or 'dependencies' not in data:
            raise ValueError('invalid pip-audit report')
        for dependency in data['dependencies']:
            if 'skip_reason' in dependency:
                gaps.append('pip-audit:dependency-skipped:' + safe_id(dependency['name']))
            for row in dependency.get('vulns', []):
                # PyPI 审计 API 不总是带 CVSS；未知严重度必须进入人工定性。
                results.append(finding(tool, row['id'], dependency['name'], repo, 'UNKNOWN',
                                       fix=bool(row.get('fix_versions')), kind='dependency'))
        coverage = {'dependencies': len(data['dependencies'])}
        if not coverage['dependencies']:
            gaps.append({'id':'pip-audit:empty-inventory', 'mandatory':True})
    elif tool == 'npm-audit':
        if not isinstance(data, dict) or 'vulnerabilities' not in data or 'error' in data:
            raise ValueError('invalid npm audit report')
        for name, row in data['vulnerabilities'].items():
            results.append(finding(tool, name, 'package-lock.json', repo, row['severity'],
                                   fix=bool(row.get('fixAvailable')), kind='dependency'))
        coverage = {'dependencies': data.get('metadata', {}).get('dependencies', {})}
    elif tool == 'clang-tidy':
        if not isinstance(data, dict) or 'files' not in data:
            raise ValueError('invalid clang report')
        for row in data['findings']:
            results.append(finding(tool, row['rule'], row['path'], repo, row['severity'], row['line']))
        gaps = data['gaps']
        coverage = {'files': len(data['files']), 'expected': data['expected']}
    elif tool == 'zap':
        if not isinstance(data, dict) or 'site' not in data:
            raise ValueError('invalid ZAP report')
        for site in data['site']:
            for row in site.get('alerts', []):
                results.append(finding(tool, row['pluginid'], '[authorized-staging]', repo,
                                       {'3': 'HIGH', '2': 'MEDIUM', '1': 'LOW', '0': 'INFO'}.get(str(row['riskcode']), 'MEDIUM')))
        coverage = {'sites': len(data['site'])}
    else:
        raise ValueError('unknown normalizer')
    return results, gaps, coverage
