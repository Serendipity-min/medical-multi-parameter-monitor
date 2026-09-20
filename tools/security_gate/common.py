"""安全门的跨平台路径、子进程与证据基础；不读取认证文件。"""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import time
from datetime import datetime, timezone

HERE = Path(__file__).resolve().parent
VERSION = '1.0.0'

def now():
    return datetime.now(timezone.utc).isoformat()

def dump(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()

def linux_path(value):
    value = str(value)
    if re.match(r'^[A-Za-z]:[\\/]', value):
        return '/mnt/' + value[0].lower() + '/' + value[3:].replace('\\', '/')
    return value

def bridge():
    """Windows 仅转发到现有 WSL；不拼接 shell，不转发认证或代理环境。"""
    if os.name != 'nt':
        return
    wsl = Path(os.environ.get('SystemRoot', 'C:/Windows')) / 'System32/wsl.exe'
    env = []
    for key in ('SECURITY_GATE_TOOL_ROOT', 'SECURITY_GATE_OUTPUT_ROOT'):
        if os.environ.get(key):
            env.append(key + '=' + linux_path(os.environ[key]))
    args = [linux_path(a) for a in sys.argv[1:]]
    command = [str(wsl), '-d', os.environ.get('SECURITY_GATE_WSL_DISTRO', 'HERA-C3'),
               '--', 'env', *env, 'python3', linux_path(Path(sys.argv[0]).resolve()), *args]
    raise SystemExit(subprocess.call(command))

def settings():
    file = Path.home() / '.config/security-gate/settings.json'
    return json.loads(file.read_text()) if file.exists() else {}

def tool_root():
    return Path(os.environ.get('SECURITY_GATE_TOOL_ROOT') or settings().get('tool_root')
                or Path.home() / '.local/share/security-gate')

def output_root():
    return Path(os.environ.get('SECURITY_GATE_OUTPUT_ROOT') or settings().get('output_root')
                or Path.home() / '.local/state/security-gate')

def environment():
    env = os.environ.copy()
    env.update(SEMGREP_SEND_METRICS='off', SEMGREP_ENABLE_VERSION_CHECK='0',
               PYTHONDONTWRITEBYTECODE='1', PIP_DISABLE_PIP_VERSION_CHECK='1',
               NO_COLOR='1')
    env['PATH'] = str(tool_root() / 'bin') + os.pathsep + env.get('PATH', '')
    return env

def execute(command, cwd, raw, name, timeout=300, ok=(0,), stdin=None, env=None):
    """原始 stdout/stderr 只进仓库外文件；超时杀掉整个进程组防止遗留扫描。"""
    raw = Path(raw)
    raw.mkdir(parents=True, exist_ok=True)
    start = time.monotonic()
    result = {'tool': name, 'status': 'OK', 'exit_code': None, 'duration_seconds': 0}
    try:
        with (raw / (name + '.stdout')).open('wb') as out, (raw / (name + '.stderr')).open('wb') as err:
            proc = subprocess.Popen([str(c) for c in command], cwd=cwd, env=env or environment(),
                                    stdout=out, stderr=err, stdin=subprocess.PIPE if stdin else subprocess.DEVNULL,
                                    start_new_session=True)
            try:
                proc.communicate(stdin, timeout=timeout)
            except subprocess.TimeoutExpired:
                os.killpg(proc.pid, signal.SIGKILL)
                proc.wait()
                result['status'] = 'TIMEOUT'
            result['exit_code'] = proc.returncode
            if result['status'] == 'OK' and proc.returncode not in ok:
                result['status'] = 'ERROR'
    except OSError:
        result['status'] = 'MISSING'
    result['duration_seconds'] = round(time.monotonic() - start, 3)
    return result

def git(repo, *args):
    result = subprocess.run(['git', '-c', 'core.quotepath=false', '-C', str(repo), *args],
                            capture_output=True, text=True, encoding='utf-8', errors='replace')
    if result.returncode:
        raise ValueError('git operation failed: ' + args[0])
    return result.stdout.strip()

def relative(value, repo):
    """仅公开仓库相对位置；拒绝宿主绝对路径和外部 URL。"""
    value = str(value).replace('\\', '/')
    prefix = str(Path(repo).resolve()).replace('\\', '/') + '/'
    if value.startswith(prefix):
        value = value[len(prefix):]
    if value.startswith('/') or re.match(r'^[A-Za-z]:', value) or '://' in value or '..' in Path(value).parts:
        return '[external]'
    return value

def safe_id(value):
    return re.sub(r'[^a-zA-Z0-9_.:/@+\-]', '_', str(value))[:180]

def load_document(path):
    """JSON 是 YAML 子集；纯标准库可读取随包策略，用户 YAML 则用工具 venv。"""
    text = Path(path).read_text(encoding='utf-8-sig')
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        try:
            import yaml
        except ImportError:
            python = tool_root() / 'pip-audit-venv/bin/python'
            code = 'import sys,yaml,json; print(json.dumps(yaml.safe_load(sys.stdin.read())))'
            result = subprocess.run([str(python), '-c', code], input=text, text=True,
                                    capture_output=True, timeout=15)
            if result.returncode:
                raise ValueError('invalid YAML')
            return json.loads(result.stdout)
        return yaml.safe_load(text)
