"""项目适配：编译数据库捕获、固定命令与外部服务状态检查。"""
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import tarfile
from common import HERE, dump, environment, execute, relative, tool_root

def test_python(repo):
    identity = hashlib.sha256(str(Path(repo).resolve()).encode()).hexdigest()[:12]
    return tool_root() / 'test-envs' / identity / 'bin/python'

def project_command(argv, repo):
    return [str(test_python(repo)) if part == '{python}' else part for part in argv]

def copy_worktree(repo, destination, commit=None):
    """复制 Git 可见的当前文件作为构建快照；忽略安装缓存，拒绝链接逃逸。"""
    if commit:
        # 正式 release 必须取准确 Git 对象；避免并发编辑造成“扫描 A，发布 B”。
        archive_path = destination.parent / 'source.tar'
        with archive_path.open('wb') as output:
            subprocess.run(['git','-C',str(repo),'archive','--format=tar',commit],stdout=output,check=True)
        with tarfile.open(archive_path) as archive:
            for item in archive:
                target = destination / item.name
                if not target.resolve().is_relative_to(destination.resolve()) or item.issym() or item.islnk():
                    raise ValueError('release archive contains unsupported link or path')
                if item.isfile():
                    target.parent.mkdir(parents=True,exist_ok=True)
                    target.write_bytes(archive.extractfile(item).read())
        archive_path.unlink()
        names = sorted(p.relative_to(destination).as_posix() for p in destination.rglob('*') if p.is_file())
    else:
        result = subprocess.run(['git', '-C', str(repo), 'ls-files', '-z', '--cached', '--others', '--exclude-standard'],
                                capture_output=True, check=True)
        names = sorted(set(x.decode('utf-8') for x in result.stdout.split(b'\0') if x))
    manifest = hashlib.sha256()
    count = 0
    for name in names:
        source = (destination if commit else repo) / name
        if not source.exists() or not source.is_file():
            continue
        if not source.resolve().is_relative_to((destination if commit else repo).resolve()):
            raise ValueError('snapshot link escapes repository')
        target = destination / name
        target.parent.mkdir(parents=True, exist_ok=True)
        if not commit:
            shutil.copyfile(source, target)
        manifest.update(name.encode() + b'\0' + hashlib.sha256(target.read_bytes()).digest())
        count += 1
    return {'file_count': count, 'tree_sha256': manifest.hexdigest()}

def clang_analysis(repo, work, run, profile, mode, timeout):
    raw = run / 'raw'
    expected = sorted({p for part in profile.get('first_party_c', []) for p in (work / part).rglob('*.c')})
    dbpath = run / 'compile_commands.json'
    command = profile.get('compile_capture')
    if command:
        result = execute(['bear', '--output', dbpath, '--', *project_command(command, repo)],
                         work, raw, 'compile-database', timeout)
        if result['status'] != 'OK':
            return result, None
    elif profile.get('compile_database'):
        source = repo / profile['compile_database']
        if source.is_file():
            # 使用原编译参数，仅把工作区根路径映射到相同内容的构建快照。
            text = source.read_text().replace(str(repo), str(work))
            dbpath.write_text(text)
    if not dbpath.exists():
        return {'tool': 'clang-tidy', 'status': 'MISSING'}, None
    try:
        database = json.loads(dbpath.read_text())
    except (ValueError, OSError):
        return {'tool': 'clang-tidy', 'status': 'MALFORMED'}, None
    captured = {Path(row['directory'], row['file']).resolve() for row in database}
    selected = [p for p in expected if p.resolve() in captured]
    gaps = ['clang-tidy:no-compilation-command:' + relative(p, work) for p in expected if p.resolve() not in captured]
    findings, statuses = [], []
    for index, source in enumerate(selected):
        result = execute(['clang-tidy', str(source), '-p', str(run),
                          '--checks=-*,clang-analyzer-*,bugprone-*,cert-*,portability-*,performance-*',
                          '--quiet'], work, raw, f'clang-unit-{index}', timeout)
        statuses.append(result['status'])
        text = (raw / f'clang-unit-{index}.stdout').read_text(errors='replace')
        for match in re.finditer(r'^(.+?):(\d+):\d+: (warning|error): .*?\[([^\]]+)\]', text, re.M):
            location, line, level, rule = match.groups()
            if not Path(location).resolve().is_relative_to(work):
                continue
            # 只将 first-party 的诊断纳入门禁；第三方保留原始证据但不扩大范围。
            if not any(Path(location).resolve().is_relative_to((work / p).resolve()) for p in profile['first_party_c']):
                continue
            severity = 'LOW' if rule.startswith('performance-') else 'HIGH' if level == 'error' else 'MEDIUM'
            findings.append({'path': relative(location, work), 'line': int(line), 'rule': rule, 'severity': severity})
    if not selected:
        gaps.append('clang-tidy:no-first-party-units-analyzed')
    path = raw / 'clang-tidy.json'
    dump(path, {'files': [relative(p, work) for p in selected], 'expected': len(expected),
                'findings': findings, 'gaps': gaps})
    return {'tool': 'clang-tidy', 'status': 'ERROR' if any(x != 'OK' for x in statuses) else 'OK'}, path

def dependabot(repo, run, github_repository):
    if not github_repository or not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', github_repository):
        return {'tool': 'dependabot', 'status': 'MANUAL_CHECK_REQUIRED', 'mandatory': False}, []
    executable = shutil.which('gh', path=environment()['PATH']) or shutil.which('gh.exe', path=environment()['PATH'])
    if not executable:
        return {'tool': 'dependabot', 'status': 'MANUAL_CHECK_REQUIRED', 'mandatory': False}, []
    # 只查询 alert ID 与严重度，绝不导出账号认证信息或漏洞源码片段。
    result = execute([executable, 'api', '--paginate', '--slurp',
        f'repos/{github_repository}/dependabot/alerts?state=open&per_page=100',
        '--jq', '[.[][] | {number: .number, severity: .security_advisory.severity}]'],
        repo, run / 'raw', 'dependabot', 90)
    if result['status'] != 'OK':
        result.update(status='MANUAL_CHECK_REQUIRED', mandatory=False)
        return result, []
    from normalize import finding
    try:
        data = json.loads((run / 'raw/dependabot.stdout').read_text())
        findings = [finding('dependabot', 'alert-' + str(x['number']), '[github-advisory]', repo,
                            x['severity'], kind='dependency') for x in data]
    except (ValueError, KeyError):
        result.update(status='MALFORMED', mandatory=True)
        return result, []
    result['mandatory'] = True
    return result, findings
