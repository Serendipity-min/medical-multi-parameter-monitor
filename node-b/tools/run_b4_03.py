"""B4-0.3只读工具与补证判据的离线验证；计划模式不得构造任何SDK连接。"""
import datetime
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]


def main():
    out = ROOT / 'node-b/build' / ('b4-03-offline-' + datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ'))
    out.mkdir(); cases = []
    for name, args, expected in (
        ('c-readonly-fakes', ['node-b/tests/test_c_b4_readonly.py'], 0),
        ('sync-criteria-fakes', ['node-b/tests/test_b4_sync.py'], 0),
        ('c-disabled-plan', ['node-b/tools/c_b4_readonly.py', '--plan'], 0),
        ('c-no-authorization-negative', ['node-b/tools/c_b4_readonly.py'], 1),
        ('sync-disabled-plan', ['node-b/tools/b4_sync.py', '--plan'], 0),
        ('sync-no-authorization-negative', ['node-b/tools/b4_sync.py'], 1)):
        # 只运行合成替身和--plan/缺授权拒绝；没有启用的授权文件，更不调用原生SDK。
        p = subprocess.run([sys.executable, '-X', 'utf8', *args], cwd=ROOT, capture_output=True, timeout=60)
        log = p.stdout + p.stderr; (out / (name + '.log')).write_bytes(log)
        cases.append({'name': name, 'exit_code': p.returncode, 'expected_exit': expected,
                      'passed': p.returncode == expected, 'log_sha256': hashlib.sha256(log).hexdigest()})
        print(name, p.returncode, flush=True)
        if p.returncode != expected: print(log.decode(errors='replace')[-3000:])
    files = ['node-b/tools/c_b4_readonly.py', 'node-b/tools/b4_sync.py', 'node-b/tests/test_c_b4_readonly.py',
             'node-b/tests/test_b4_sync.py', 'node-b/tools/run_b4_03.py']
    report = {'status': 'PASS' if all(c['passed'] for c in cases) else 'FAIL', 'cases': cases,
              'scope': 'B4_03_SOFTWARE_ONLY_NO_HARDWARE', 'hardware_operations': 0,
              'source_sha256': {n: hashlib.sha256((ROOT / n).read_bytes()).hexdigest() for n in files}}
    (out / 'receipt.json').write_bytes((json.dumps(report, indent=2) + '\n').encode('utf-8'))
    print(str(out.relative_to(ROOT)), report['status']); return int(report['status'] != 'PASS')


if __name__ == '__main__': sys.exit(main())
