"""只检查工具和配置；Pro 自检只 validate 内置规则，不读取项目源码。"""
import json
from pathlib import Path
import shutil
from common import HERE, dump, environment, execute, git, now, tool_root

def inspect(repo, output):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    probe = output / '.write-probe'
    probe.write_text('ok')
    probe.unlink()
    versions = {}
    commands = {'semgrep': ['semgrep', '--version'], 'trivy': ['trivy', '--version'],
                'gitleaks': ['gitleaks', 'version'], 'clang': ['clang', '--version'],
                'clang-tidy': ['clang-tidy', '--version'], 'gcc': ['gcc', '--version'],
                'node': ['node', '--version'], 'npm': ['npm', '--version'], 'bear': ['bear', '--version'],
                'docker': ['docker', 'version', '--format', '{{.Server.Version}}'],
                'pip-audit': [tool_root() / 'pip-audit-venv/bin/python', '-m', 'pip_audit', '--version']}
    for name, command in commands.items():
        result = execute(command, repo, output / 'raw', name, 35)
        lines = (output / 'raw' / (name + '.stdout')).read_text(errors='replace').strip().splitlines()
        versions[name] = {'status': result['status'], 'version': lines[0][:150] if lines and result['status'] == 'OK' else None}
    pro = execute(['semgrep', '--pro', '--validate', '--metrics=off', '--config', HERE / 'config/semgrep/quick.yml'],
                  repo, output / 'raw', 'semgrep-pro-validation', 120)
    versions['semgrep-pro'] = {'status': pro['status'], 'exit_code': pro['exit_code']}
    for sanitizer, library in [('asan', 'libasan.so'), ('ubsan', 'libubsan.so')]:
        row = execute(['gcc', '-print-file-name=' + library], repo, output / 'raw', sanitizer, 15)
        text = (output / 'raw' / (sanitizer + '.stdout')).read_text().strip()
        versions[sanitizer] = {'status': 'OK' if row['status'] == 'OK' and Path(text).is_file() else 'MISSING',
                               'version': 'GCC runtime library'}
    versions['arm'] = {'status': 'AVAILABLE' if shutil.which('arm-none-eabi-gcc') else 'PROJECT_CONFIGURATION_REQUIRED'}
    missing = [k for k, v in versions.items() if v['status'] != 'OK' and k not in ('docker', 'arm')]
    try:
        commit, dirty = git(repo, 'rev-parse', 'HEAD'), bool(git(repo, 'status', '--porcelain'))
    except ValueError:
        commit, dirty = None, None
    return {'status': 'ERROR' if missing else 'OK', 'checked_at': now(), 'versions': versions,
            'missing': missing, 'commit': commit, 'dirty': dirty, 'output_writable': True,
            'zap': 'DISABLED; requires authorized release target and pinned image digest', 'scan_performed': False}
