"""跨项目安全门。doctor/dry-run 不扫描；其他模式必须显式 --authorize。"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import sys
import tomllib
from urllib.parse import urlsplit
import uuid
from common import HERE, VERSION, bridge, dump, environment, execute, git, load_document, now, output_root, relative, sha, tool_root
from adapters import clang_analysis, copy_worktree, dependabot, project_command
from normalize import parse
from policy import evaluate
from report import write

def load_profile(value, repo):
    path = Path(value) if value else repo / '.security-gate.json'
    if not path.exists():
        path = HERE / 'profiles' / ((value or 'generic') + '.json')
    profile = json.loads(path.read_text(encoding='utf-8-sig'))
    if not profile.get('name') or not isinstance(profile.get('source_roots'), list):
        raise ValueError('invalid project profile')
    # 路径都受目标仓库约束；命令数组来自用户选择并授权执行的项目配置。
    for key in ('source_roots', 'requirements', 'npm_roots', 'first_party_c'):
        for value in profile.get(key, []):
            if not (repo / value).resolve().is_relative_to(repo):
                raise ValueError('profile path escapes repository')
    for command in profile.get('commands', []):
        if not (repo / command.get('cwd', '.')).resolve().is_relative_to(repo):
            raise ValueError('command working directory escapes repository')
    return profile, path

def check_manual(path, profile, commit):
    if not path:
        return {}
    data = load_document(path)
    # 勾选必须对应本次准确提交，并具备明确责任人与证据。
    valid = data.get('commit') == commit and bool(data.get('reviewer')) and bool(data.get('reviewed_at'))
    def complete(keys):
        return bool(keys) and valid and all(data.get('checks', {}).get(k, {}).get('status') == 'pass'
            and data.get('checks', {}).get(k, {}).get('evidence') for k in keys)
    return {'architecture_complete': complete(profile.get('manual_checklist', [])),
            'real_data_complete': complete(profile.get('real_data_checklist', []))}

def run_gate(args):
    repo = args.repo.resolve()
    if not repo.is_dir():
        raise ValueError('target repository missing')
    profile, profile_path = load_profile(args.profile, repo)
    config = tomllib.loads((HERE / 'config/security-gate.toml').read_text())
    if config['schema_version'] != 1 or config['zap_mode'] != 'baseline-only':
        raise ValueError('unsupported policy configuration')
    for key, value in {'scan_requires_explicit_authorization': True, 'release_requires_clean_tree': True,
                       'critical': 'fail', 'high': 'fail', 'moderate': 'review', 'unknown_severity': 'review'}.items():
        if config.get(key) != value:
            raise ValueError('unsupported policy override: ' + key)
    root = args.output_root.resolve()
    if root.is_relative_to(repo) or root.is_relative_to(HERE.parents[1]):
        raise ValueError('raw output must be outside target and tooling repositories')
    run = root / (args.mode + '-' + now().replace(':', '').replace('+', '_') + '-' + uuid.uuid4().hex[:6])
    run.mkdir(parents=True)
    raw = run / 'raw'
    raw.mkdir()
    commit, branch = git(repo, 'rev-parse', 'HEAD'), git(repo, 'branch', '--show-current')
    dirty = bool(git(repo, 'status', '--porcelain'))
    lock = json.loads((HERE / 'toolchain.lock.json').read_text())
    manifest = {'schema_version': 1, 'gate_version': VERSION, 'started_at': now(), 'commit': commit,
        'branch': branch, 'dirty': dirty, 'mode': args.mode, 'profile': profile['name'],
        'profile_sha256': sha(profile_path), 'policy_sha256': sha(HERE / 'config/security-gate.toml'),
        'toolchain_sha256': sha(HERE / 'toolchain.lock.json'), 'authorized': args.authorize,
        'target_authorized': args.authorize_target, 'target_url_sha256': hashlib.sha256(args.target.encode()).hexdigest() if args.target else None}
    findings, gaps, steps = [], [], []
    versions = lock['tools']
    if args.mode == 'doctor':
        from doctor import inspect
        doctor = inspect(repo, run)
        dump(run / 'doctor.json', doctor)
        result = evaluate('doctor', [{'tool': 'doctor', 'status': doctor['status']}], [], [])
        versions = doctor['versions']
        steps = [{'tool': k, 'status': v['status'], 'mandatory': k not in ('docker', 'arm')} for k, v in versions.items()]
    elif not args.authorize and not args.dry_run:
        steps = [{'tool': 'authorization', 'status': 'TOOL_ERROR', 'mandatory': True}]
        gaps.append({'id': 'not_run_by_explicit_user_policy_not_passed', 'mandatory': True})
        result = evaluate(args.mode, steps, [], gaps)
    elif args.target and (args.mode != 'release' or not args.authorize_target or not args.authorize):
        steps = [{'tool': 'zap-authorization', 'status': 'TOOL_ERROR', 'mandatory': True}]
        result = evaluate(args.mode, steps, [], [{'id': 'ZAP_TARGET_NOT_AUTHORIZED', 'mandatory': True}])
    elif args.dry_run:
        plan = ['semgrep-pro', 'gitleaks', 'project-tests', 'project-builds']
        if args.mode in ('pr', 'release'):
            plan += ['trivy', 'pip-audit', 'npm-audit', 'clang-tidy', 'sanitizer', 'paho-integrity']
        if args.mode == 'release':
            plan += ['sbom', 'dependabot', 'manual-checklist', 'zap']
        steps = [{'tool': x, 'status': 'PLANNED_NOT_RUN', 'mandatory': x != 'zap'} for x in plan]
        result = evaluate(args.mode, steps, [], [], dirty=dirty, dry_run=True, real_data=args.real_data)
    else:
        from doctor import inspect
        doctor = inspect(repo, run / 'environment')
        versions = doctor['versions']
        steps.append({'tool': 'doctor', 'status': doctor['status'], 'mandatory': True})
        # 二进制必须匹配已审核下载物；规则与锁的哈希写入本次 manifest。
        for name in ('trivy', 'gitleaks'):
            binary = shutil.which(name, path=environment()['PATH'])
            expected = lock['tools'].get(name, {}).get('sha256')
            if not binary or not expected or sha(binary) != expected:
                gaps.append({'id': name + ':toolchain-hash-mismatch', 'mandatory': True})
        # 固定快照保证构建和 npm ci 不修改目标工作树；Git 历史扫描仍读取授权仓库。
        work = run / 'work'
        work.mkdir()
        manifest['input_snapshot'] = copy_worktree(repo, work, commit if args.mode == 'release' else None)
        timeout = args.timeout or config['default_timeout']
        def step(name, command, cwd=work, ok=(0,), normalizer=None, report=None, mandatory=True):
            row = execute(command, cwd, raw, name, timeout, ok)
            row['mandatory'] = mandatory
            if row['status'] == 'OK' and normalizer:
                try:
                    got, missing, coverage = parse(normalizer, report, work)
                    findings.extend(got)
                    gaps.extend(missing)
                    row['coverage'] = coverage
                except (ValueError, KeyError, TypeError, OSError):
                    row['status'] = 'MALFORMED'
            steps.append(row)
            print(name + ': ' + row['status'], flush=True)
            return row
        rules = HERE / 'config/semgrep/quick.yml'
        if args.mode != 'quick' and (HERE / 'config/semgrep/security-audit.yml').exists():
            rules = HERE / 'config/semgrep/security-audit.yml'
        manifest['semgrep_rules_sha256'] = sha(rules)
        validation = step('semgrep-pro-validation', ['semgrep', '--pro', '--validate', '--metrics=off', '--config', rules])
        if validation['status'] == 'OK':
            targets = [str(work / x) for x in profile['source_roots'] if (work / x).exists()]
            if not targets:
                gaps.append({'id': 'semgrep:no-targets', 'mandatory': True})
            else:
                sem = raw / 'semgrep.json'
                # Pro inter-file 只接受单根目录；include 保持用户批准的源码范围。
                include = []
                for source in profile['source_roots']:
                    if source != '.':
                        include += ['--include', source.rstrip('/') + '/**']
                step('semgrep', ['semgrep', 'scan', '--pro', '--metrics=off', '--disable-version-check',
                     '--config', rules, '--json-output', sem, '--sarif-output', raw / 'semgrep.sarif',
                     '--no-git-ignore', '--exclude', 'node_modules', '--exclude', '.venv',
                     '--exclude', 'tools/security_gate/tests', *include, work], normalizer='semgrep', report=sem)
        # 固定配置使用默认规则、禁用源码内 ignore；allowlist 只在后续接受项中评审。
        leak = raw / 'gitleaks.json'
        base = ['gitleaks', '--no-banner', '--redact=100', '--ignore-gitleaks-allow', '--exit-code', '10',
                '--config', HERE / 'config/gitleaks.toml', '--report-format', 'json', '--report-path', leak]
        if args.mode == 'quick':
            step('gitleaks', [*base, 'dir', work], ok=(0, 10), normalizer='gitleaks', report=leak)
        elif args.mode == 'pr':
            if not args.base:
                steps.append({'tool': 'gitleaks', 'status': 'TOOL_ERROR', 'mandatory': True})
                gaps.append({'id': 'pr:explicit-base-ref-required', 'mandatory': True})
            elif not args.base.startswith('-'):
                base_sha = git(repo, 'rev-parse', '--verify', args.base + '^{commit}')
                manifest['base_commit'] = base_sha
                step('gitleaks', [*base, 'git', '--log-opts=' + base_sha + '..' + commit, repo],
                     ok=(0, 10), normalizer='gitleaks', report=leak)
            else:
                gaps.append({'id': 'pr:invalid-base-ref', 'mandatory': True})
        else:
            shallow = git(repo, 'rev-parse', '--is-shallow-repository') == 'true'
            if shallow:
                gaps.append({'id': 'gitleaks:shallow-history', 'mandatory': True})
            step('gitleaks', [*base, 'git', '--log-opts=--all', repo], ok=(0, 10), normalizer='gitleaks', report=leak)
        if args.mode != 'quick':
            trivy = raw / 'trivy.json'
            step('trivy', ['trivy', 'fs', '--scanners', 'vuln,secret,misconfig,license', '--format', 'json',
                 '--output', trivy, '--cache-dir', tool_root() / 'trivy-cache', '--timeout', str(timeout) + 's',
                 '--include-dev-deps', '--skip-dirs', '.git', '--skip-dirs', 'node_modules', work], normalizer='trivy', report=trivy)
            for index, rel in enumerate(profile.get('requirements', [])):
                path = work / rel
                if not path.exists():
                    steps.append({'tool': f'pip-audit-{index}', 'status': 'MISSING', 'mandatory': True})
                    continue
                audit = raw / f'pip-audit-{index}.json'
                option = '--require-hashes' if '--hash=' in path.read_text() else '--no-deps'
                step(f'pip-audit-{index}', [tool_root() / 'pip-audit-venv/bin/python', '-m', 'pip_audit', option,
                     '--disable-pip', '-r', path, '-f', 'json', '-o', audit], ok=(0, 1), normalizer='pip-audit', report=audit)
            for index, rel in enumerate(profile.get('npm_roots', [])):
                row = step(f'npm-audit-{index}', ['npm', 'audit', '--json'], cwd=work / rel, ok=(0, 1),
                           normalizer='npm-audit', report=raw / f'npm-audit-{index}.stdout')
            if profile.get('first_party_c'):
                row, path = clang_analysis(repo, work, run, profile, args.mode, timeout)
                row['tool'] = 'clang-tidy'
                row['mandatory'] = True
                if path:
                    got, missing, coverage = parse('clang-tidy', path, work)
                    findings.extend(got)
                    gaps.extend(missing)
                    row['coverage'] = coverage
                steps.append(row)
        # 只在构建快照中安装锁定的前端依赖；不执行安装脚本或自动依赖升级。
        for index, rel in enumerate(profile.get('npm_roots', [])):
            step(f'npm-ci-{index}', ['npm', 'ci', '--ignore-scripts', '--no-audit', '--no-fund'], cwd=work / rel)
        for command in profile.get('commands', []):
            if args.mode not in command['modes']:
                continue
            if command.get('required_file') and not (work / command['required_file']).exists():
                steps.append({'tool': command['name'], 'status': 'MISSING', 'mandatory': command.get('mandatory', True)})
                continue
            row = step(command['name'], project_command(command['argv'], repo), cwd=work / command.get('cwd', '.'),
                       mandatory=command.get('mandatory', True))
            if row['status'] == 'ERROR' and row['exit_code'] is not None:
                row['status'] = 'FAIL' if command.get('mandatory', True) else 'COVERAGE_GAP'
        gaps.extend(profile.get('coverage_notes', []))
        if args.mode == 'release':
            sbom = run / 'sbom.cyclonedx.json'
            row = step('sbom', ['trivy', 'fs', '--format', 'cyclonedx', '--output', sbom,
                               '--scanners', 'license', '--skip-dirs', 'node_modules', work])
            if row['status'] == 'OK':
                try:
                    from sbom import complete_runtime_locks
                    complete_runtime_locks(sbom, work, profile.get('requirements', []))
                    data = json.loads(sbom.read_text())
                    if data.get('bomFormat') != 'CycloneDX' or not data.get('components'):
                        raise ValueError('empty SBOM')
                    types = {c.get('purl', '').split(':')[1].split('/')[0] for c in data['components'] if c.get('purl')}
                    if profile.get('requirements') and 'pypi' not in types:
                        gaps.append({'id': 'sbom:python-missing', 'mandatory': True})
                    if profile.get('npm_roots') and 'npm' not in types:
                        gaps.append({'id': 'sbom:npm-missing', 'mandatory': True})
                except (ValueError, KeyError, IndexError, OSError):
                    row['status'] = 'MALFORMED'
            row, got = dependabot(repo, run, profile.get('github_repository'))
            steps.append(row)
            findings.extend(got)
            if args.target:
                parsed = urlsplit(args.target)
                if parsed.scheme not in ('https', 'http') or not parsed.hostname or parsed.username or parsed.password:
                    steps.append({'tool': 'zap', 'status': 'TOOL_ERROR', 'mandatory': True})
                else:
                    digest = lock['tools'].get('zap', {}).get('digest')
                    if not digest or not re.fullmatch(r'sha256:[a-f0-9]{64}', digest):
                        steps.append({'tool': 'zap', 'status': 'MISSING', 'mandatory': True})
                    else:
                        shutil.copyfile(HERE / 'config/zap-baseline.conf', raw / 'zap-baseline.conf')
                        row = step('zap', ['docker', 'run', '--rm', '-v', str(raw) + ':/zap/wrk:rw',
                            'ghcr.io/zaproxy/zaproxy@' + digest, 'zap-baseline.py', '-t', args.target,
                            '-m', '1', '-T', '5', '-c', 'zap-baseline.conf', '-J', 'zap.json', '-r', 'zap.html'],
                            ok=(0, 1, 2), normalizer='zap', report=raw / 'zap.json')
                        if row['exit_code'] == 1:
                            row['status'] = 'FAIL'
            else:
                steps.append({'tool': 'zap', 'status': 'MANUAL_NOT_RUN', 'mandatory': False})
            steps.append({'tool': 'codeql', 'status': 'OPTIONAL_UNAVAILABLE', 'mandatory': False})
        acceptance = args.accepted or (repo / '.security-gate/accepted-findings.yml')
        if not acceptance.exists():
            acceptance = HERE / 'config/accepted-findings.yml'
        accepted = load_document(acceptance).get('accepted_findings', [])
        baseline = repo / '.security-gate/clang-tidy-baseline.json'
        if baseline.exists():
            accepted += load_document(baseline).get('accepted_findings', [])
        if not isinstance(accepted, list) or not all(isinstance(row, dict) for row in accepted):
            raise ValueError('invalid accepted-findings schema')
        checklist = check_manual(args.checklist, profile, commit)
        if git(repo, 'rev-parse', 'HEAD') != commit:
            gaps.append({'id': 'target-commit-changed-during-run', 'mandatory': True})
        result = evaluate(args.mode, steps, findings, gaps, accepted, dirty=dirty,
                          real_data=args.real_data, checklist=checklist)
    result.update(commit=commit, branch=branch, dirty=dirty,
                  mandatory_tools={s['tool']: s['status'] for s in steps if s.get('mandatory', True)},
                  sbom_sha256=sha(run / 'sbom.cyclonedx.json') if (run / 'sbom.cyclonedx.json').exists() else None)
    manifest['finished_at'] = now()
    write(run, result, findings, steps, versions, manifest)
    # 快照只是隔离构建输入，不是备份；保留固定回归结果后清除它，原始扫描证据仍留在 raw。
    work = run / 'work'
    if work.exists() and work.resolve().parent == run.resolve() and not work.is_symlink():
        regression = work / 'gateway/canopen/build/security-regression'
        if regression.is_dir():
            for item in regression.iterdir():
                if item.suffix in ('.json', '.log'):
                    shutil.copyfile(item, raw / ('regression-' + item.name))
        shutil.rmtree(work)
    print(json.dumps({'result': result['result'], 'exit_code': result['exit_code'], 'output': str(run)}, ensure_ascii=False))
    return result['exit_code']

def main():
    bridge()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=['doctor', 'quick', 'pr', 'release'])
    parser.add_argument('--repo', type=Path, default=Path.cwd())
    parser.add_argument('--profile')
    parser.add_argument('--output-root', type=Path, default=output_root())
    parser.add_argument('--authorize', action='store_true', help='只代表已获得本次目标与模式的明确用户授权')
    parser.add_argument('--base', help='PR 模式的明确基线 commit/ref')
    parser.add_argument('--target')
    parser.add_argument('--authorize-target', action='store_true')
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--real-data', action='store_true')
    parser.add_argument('--checklist', type=Path)
    parser.add_argument('--accepted', type=Path)
    parser.add_argument('--timeout', type=int)
    args = parser.parse_args()
    try:
        return run_gate(args)
    except (ValueError, OSError, KeyError, TypeError) as error:
        # 不回显异常正文，避免第三方工具把凭据、URL 或环境信息带到聊天。
        # 提前配置失败同样交付一致的结果与报告，不能只抛栈让调用方误判。
        root = args.output_root.resolve()
        if not root.is_relative_to(args.repo.resolve()) and not root.is_relative_to(HERE.parents[1]):
            failure = root / ('configuration-error-' + uuid.uuid4().hex[:10])
            failure.mkdir(parents=True)
            result = evaluate(args.mode, [{'tool': 'configuration', 'status': 'TOOL_ERROR'}], [],
                              [{'id': type(error).__name__, 'mandatory': True}])
            write(failure, result, [], [], {}, {'error_type': type(error).__name__})
        print(json.dumps({'result': 'TOOL / COVERAGE ERROR', 'exit_code': 3, 'error_type': type(error).__name__}))
        return 3

if __name__ == '__main__':
    raise SystemExit(main())
