"""限定普通回归，逐条保留真实退出码；不调用硬件、生产服务或Security Gate。"""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT/'doc/VOICE/evidence'/datetime.now(timezone.utc).strftime('regression-%Y%m%dT%H%M%SZ')


def main():
    # 这里保留的是硬件实测时的H3整套回放入口；P6不引入该历史工程，不能虚报跳过为通过。
    if not (ROOT/'gateway/physical_can/build.py').exists():
        print('H3 regression sources not present on P6; use gateway/voice/build.py --host, '
              'gateway/voice/build.py and pytest gateway/voice/tests. Historical H3 results are retained in doc/VOICE/evidence/.')
        return 2
    OUT.mkdir(parents=True)
    suites = [
        ('paired-python', [sys.executable, '-m', 'pytest', 'cloud/backend/tests', 'cloud/ai/tests', 'gateway/physical_can/tests', '-q']),
        # Windows入口负责向WSL注入实际HEAD；不能在WSL里解析Windows worktree路径。
        ('p5-42-and-can', [sys.executable, 'gateway/mqtt/tests/run_p5_host_tests.py', '--with-can-capture']),
        ('p5-46', [sys.executable, 'gateway/mqtt/tests/run_p5_host_tests.py', '--network-irq', '--wifi-awake', '--fresh-sntp']),
        ('physical-irq-host', ['wsl', '-d', 'HERA-C3', '--cd', '/mnt/e/medical-monitor-c-voice', '--',
                               'python3', 'gateway/physical_can/build.py', '--host', '--irq', '--rx-order',
                               '--evidence-dir', 'doc/VOICE/evidence/physical-irq-host']),
        ('old-arm-formal', [sys.executable, 'gateway/physical_can/build.py', '--irq', '--synthetic-source',
                            '--fresh-sntp', '--persistent-config', '--macro-source-root', 'E:\\medical-monitor-h3',
                            '--evidence-dir', 'doc/VOICE/evidence/old-arm-formal']),
        ('old-arm-isolated', [sys.executable, 'gateway/physical_can/build.py', '--irq', '--isolated',
                              '--fresh-sntp', '--persistent-config', '--macro-source-root', 'E:\\medical-monitor-h3',
                              '--evidence-dir', 'doc/VOICE/evidence/old-arm-isolated']),
    ]
    failed = False
    for name, argv in suites:
        record = {'command': argv, 'cwd': str(ROOT), 'started_utc': datetime.now(timezone.utc).isoformat(),
                  'hardware': 'NOT_RUN', 'production': 'NOT_ACCESSED', 'security_gate': 'NOT_RUN'}
        result = subprocess.run(argv, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        (OUT/(name+'.log')).write_bytes(result.stdout)
        record.update(exit_code=result.returncode, ended_utc=datetime.now(timezone.utc).isoformat(),
                      log_sha256=hashlib.sha256(result.stdout).hexdigest())
        (OUT/(name+'.json')).write_text(json.dumps(record, indent=2)+'\n', encoding='utf-8')
        print(name, 'exit', result.returncode, result.stdout.decode(errors='replace')[-700:], flush=True)
        failed |= result.returncode != 0
    return int(failed)


if __name__ == '__main__':
    raise SystemExit(main())
