"""固定退出码策略：执行器负责事实，本模块只作可测试的确定性裁决。"""
from datetime import date

REQUIRED_ACCEPTANCE = ('id', 'tool', 'path', 'reason', 'owner', 'accepted_at', 'expires_at', 'review_issue')

def valid_acceptance(row, today=None):
    today = today or date.today()
    if not all(row.get(key) for key in REQUIRED_ACCEPTANCE):
        return False
    if len(row['reason'].strip()) < 15 or row['reason'].strip().lower() == 'false-positive':
        return False
    try:
        return date.fromisoformat(str(row['accepted_at'])) <= today < date.fromisoformat(str(row['expires_at']))
    except ValueError:
        return False

def evaluate(mode, steps, findings, gaps, accepted=(), dirty=False, dry_run=False,
             real_data=False, checklist=None, optional_codeql=False):
    blockers, warnings, errors, risks = [], [], [], []
    for row in steps:
        status = row['status']
        if status in ('ERROR', 'MISSING', 'TIMEOUT', 'MALFORMED', 'TOOL_ERROR'):
            (errors if row.get('mandatory', True) else warnings).append(row['tool'] + ':' + status)
        elif status == 'FAIL':
            blockers.append(row['tool'] + ':failed')
        elif status not in ('OK', 'NOT_APPLICABLE'):
            warnings.append(row['tool'] + ':' + status)
    for f in findings:
        match = next((a for a in accepted if a.get('id') == f['id'] and a.get('tool') == f['tool']
                      and a.get('path') == f['path'] and valid_acceptance(a)), None)
        if match and (f['kind'] != 'secret' or (match.get('disposition') == 'false_positive' and match.get('evidence'))):
            risks.append(f['id'])
            warnings.append('accepted:' + f['id'])
        elif f['kind'] == 'secret' or f['severity'] == 'CRITICAL':
            blockers.append(f['id'])
        elif f['severity'] == 'HIGH':
            if f['kind'] == 'dependency' and not f['fix_available'] and mode != 'release':
                warnings.append('no-fix:' + f['id'])
            else:
                blockers.append(f['id'])
        elif f['severity'] in ('MEDIUM', 'MODERATE', 'UNKNOWN'):
            warnings.append('review:' + f['id'])
    for gap in gaps:
        if isinstance(gap, dict) and gap.get('mandatory'):
            errors.append(gap['id'])
        else:
            warnings.append(gap['id'] if isinstance(gap, dict) else str(gap))
    if dirty:
        (blockers if mode == 'release' and not dry_run else warnings).append('dirty-worktree')
    if dry_run:
        warnings.append('DRY_RUN_NOT_A_SECURITY_PASS')
    fail_real = False
    if mode == 'release':
        checklist = checklist or {}
        if not checklist.get('architecture_complete'):
            warnings.append('MANUAL_ARCHITECTURE_REVIEW_REQUIRED')
        if real_data and not checklist.get('real_data_complete'):
            blockers.append('FAIL_FOR_REAL_DATA')
            fail_real = True
    # 工具缺口优先为 3；仍保留同时发现的漏洞 blocker，避免错误被“零发现”掩盖。
    code = 3 if errors else 1 if blockers else 2 if warnings else 0
    return {'result': {0: 'PASS', 1: 'FAIL', 2: 'CONDITIONAL PASS', 3: 'TOOL / COVERAGE ERROR'}[code],
            'exit_code': code, 'mode': mode, 'blockers': blockers, 'warnings': warnings,
            'coverage_gaps': gaps, 'tool_errors': errors, 'accepted_risk': risks,
            'real_data_result': 'FAIL_FOR_REAL_DATA' if fail_real else 'NOT_ASSESSED' if not real_data else 'REVIEWED',
            'dry_run': dry_run}
