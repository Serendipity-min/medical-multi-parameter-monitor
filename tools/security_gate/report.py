"""统一报告从规范化结果生成，禁止将原始扫描内容拼进可提交摘要。"""
from common import HERE, dump, sha

SECTIONS = ['Commit / Branch', 'Tool Versions', 'Gate Mode', 'Coverage', 'Findings', 'Accepted Risk',
            'ASan/UBSan', 'SCA', 'Secrets', 'Static C', 'Build/Test', 'DAST', 'SBOM', 'GitHub Alerts',
            'Architecture Checklist', 'Residual Risk', 'Final Verdict']

def write(run, result, findings, steps, versions, manifest):
    # 配置失败也满足公共 schema；未知身份字段保持 null，禁止猜造提交。
    for key, default in {'commit': None, 'branch': None, 'dirty': None, 'mandatory_tools': {}, 'sbom_sha256': None}.items():
        result.setdefault(key, default)
    dump(run / 'gate-result.json', result)
    dump(run / 'normalized-findings.json', findings)
    dump(run / 'coverage.json', {'steps': steps, 'gaps': result['coverage_gaps']})
    dump(run / 'manifest.json', manifest)
    dump(run / 'tool-versions.json', versions)
    lines = ['# Security Gate Report', '', '> 结果仅适用于本次提交、规则集和实际覆盖范围。', '']
    for title in SECTIONS:
        lines.extend(['## ' + title, ''])
        if title == 'Commit / Branch':
            lines.append(f"Commit `{result.get('commit')}`; branch `{result.get('branch')}`; dirty `{result.get('dirty')}`")
        elif title == 'Tool Versions':
            lines.extend(f"- {name}: {row.get('version')} ({row.get('status', 'locked')})" for name, row in versions.items())
        elif title == 'Gate Mode':
            lines.append(result['mode'] + (' — dry-run; no security verdict' if result.get('dry_run') else ''))
        elif title == 'Coverage':
            lines += ['| Component | Status | Mandatory |', '| --- | --- | --- |']
            lines.extend(f"| {s['tool']} | {s['status']} | {s.get('mandatory', True)} |" for s in steps)
            lines.extend('- Gap: ' + (g['id'] if isinstance(g, dict) else g) for g in result['coverage_gaps'])
        elif title == 'Findings':
            lines += ['| ID | Tool / Rule | Relative path | Severity |', '| --- | --- | --- | --- |']
            lines.extend(f"| {f['id']} | {f['tool']} / {f['rule']} | {f['path'].replace('|', '_')}:{f['line']} | {f['severity']} |" for f in findings)
        elif title == 'Accepted Risk':
            lines.extend('- ' + x for x in result['accepted_risk'])
            if not result['accepted_risk']:
                lines.append('No recorded valid acceptance.')
        elif title == 'SBOM':
            lines.append('SHA-256: ' + str(result.get('sbom_sha256')))
        elif title == 'Final Verdict':
            lines.append(f"**{result['result']}**; exit `{result['exit_code']}`")
        elif title == 'Residual Risk':
            lines.extend('- ' + str(x) for x in result['warnings'] + result['blockers'] + result['tool_errors'])
        else:
            groups = {'ASan/UBSan': ('sanitizer',), 'SCA': ('trivy', 'pip-audit', 'npm-audit'),
                      'Secrets': ('gitleaks',), 'Static C': ('clang-tidy',), 'Build/Test': ('test', 'build', 'paho'),
                      'DAST': ('zap',), 'GitHub Alerts': ('dependabot',), 'Architecture Checklist': ('manual',)}
            matches = [s for s in steps if any(t in s['tool'] for t in groups.get(title, ()))]
            lines.extend(f"- {s['tool']}: {s['status']}" for s in matches)
            if not matches:
                lines.append('Not executed in this mode; see coverage and project checklist.')
        lines.append('')
    (run / 'gate-report.md').write_text('\n'.join(lines), encoding='utf-8')
    dump(run / 'report-integrity.json', {'report_sha256': sha(run / 'gate-report.md'),
                                       'result_sha256': sha(run / 'gate-result.json'),
                                       'commit': result.get('commit'), 'sbom_sha256': result.get('sbom_sha256')})
