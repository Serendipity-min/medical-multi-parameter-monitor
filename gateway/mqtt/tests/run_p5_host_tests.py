"""用既有 GCC 编译真实 P5 源码的普通功能用例；不启用 sanitizer 或扫描器。"""
import json
import os
from pathlib import Path
import subprocess
import sys
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[3]
MQTT = ROOT / 'gateway/mqtt'
VENDOR = ROOT / 'gateway/third_party/coreMQTT'


def main() -> int:
    if sys.platform == 'win32':
        # 只复用已安装 HERA-C3 的 GCC，不安装工具；argv 直接传递，避免 shell 拼接路径。
        linux_root = '/mnt/' + ROOT.drive[0].lower() + ROOT.as_posix()[2:]
        commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip()
        # Windows worktree 的 .git 绝对路径无法由 Linux Git 解析，仅传公开提交标识。
        return subprocess.call(['wsl', '-d', 'HERA-C3', '--cd', linux_root, '--',
                                'env', 'P5_COMMIT=' + commit,
                                'python3', 'gateway/mqtt/tests/run_p5_host_tests.py'])
    out = MQTT / 'build/p5-tests'
    out.mkdir(parents=True, exist_ok=True)
    report = {'started_at': datetime.now(timezone.utc).isoformat(), 'synthetic': True,
              'security_gate': 'NOT_AUTHORIZED/NOT_RUN', 'tests': []}
    report['commit'] = os.environ.get('P5_COMMIT') or subprocess.check_output(
        ['git', 'rev-parse', 'HEAD'], text=True).strip()
    report['compiler'] = subprocess.check_output(['gcc', '--version'], text=True).splitlines()[0]
    suites = {'transport': ['mqtt_transport_adapter.c']}
    for name, project_sources in suites.items():
        command = ['gcc', '-std=c11', '-O1', '-Wall', '-Wextra', '-Werror',
                   '-I' + str(MQTT / 'src'), '-I' + str(VENDOR / 'source/include'),
                   '-I' + str(VENDOR / 'source/interface'),
                   *[str(MQTT / 'src' / source) for source in project_sources],
                   str(MQTT / f'tests/test_p5_{name}.c'), '-o', str(out / name)]
        subprocess.run(command, check=True)
        result = subprocess.run([str(out / name)], text=True, capture_output=True)
        (out / f'{name}.log').write_text(result.stdout + result.stderr, encoding='utf-8')
        report['tests'].append({'suite': name, 'exit_code': result.returncode,
                                'cases': result.stdout.splitlines(), 'command': command})
        print(result.stdout, end='')
        if result.returncode:
            print(result.stderr)
            report['result'] = 'FAIL'
            (out / 'result.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
            return 1
    report['result'] = 'PASS'
    report['passed'] = sum(len(t['cases']) for t in report['tests'])
    (out / 'result.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print('P5 ordinary host checks PASS:', report['passed'])
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
