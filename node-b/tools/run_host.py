"""普通脱机回归汇总：所有输出写入唯一轮次，不接串口、J-Link或开发板。"""
from pathlib import Path
import datetime
import hashlib
import json
import os
import subprocess
import sys


def main():
    root = Path(__file__).resolve().parents[2]
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    out = root / 'node-b/build' / ('host-' + stamp)
    out.mkdir(parents=True, exist_ok=False)
    env = dict(os.environ, NODE_B_TEST_OUT=str(out), PYTHONIOENCODING='utf-8')
    cases = [
        ('queue', ['node-b/tests/run_queue.py']),
        ('algorithm', ['node-b/firmware/biov2/tests/run_host.py']),
        ('channel-isolation', ['node-b/firmware/biov2/tests/run_channel_isolation.py']),
        ('acquisition', ['node-b/acquisition/工具/tests/test_acq.py']),
        ('source-console', ['ecg-source/g2s-usb/test_console.py']),
        ('source-rom-model', ['ecg-source/g2s-usb/test_usb_rom.py']),
        ('bias-monitor', ['ecg-source/g2s-usb/test_observe_bias.py']),
    ]
    results = []
    for name, args in cases:
        # 捕获完整日志，包括失败；一次失败不抹掉其它独立普通测试结果。
        proc = subprocess.run([sys.executable, *args], cwd=root, env=env,
                              capture_output=True, timeout=180)
        log = out / (name + '.log')
        log.write_bytes(proc.stdout + proc.stderr)
        results.append({'name': name, 'exit_code': proc.returncode,
                        'input_sha256': hashlib.sha256((root / args[0]).read_bytes()).hexdigest(),
                        'log_sha256': hashlib.sha256(log.read_bytes()).hexdigest()})
        print(name + ': exit=' + str(proc.returncode), flush=True)
    report = {'scope': 'ORDINARY_HOST_ONLY', 'hardware_access': False,
              'results': results, 'history_replay': 'NOT_RUN_PRIVATE_RAW_NOT_INCLUDED'}
    for name, rel in [('algorithm', 'algorithm/host_receipt.json'),
                      ('channel-isolation', 'channel-isolation/receipt.json')]:
        file = out / rel
        if file.exists():
            data = json.loads(file.read_text('utf-8'))
            report[name] = {k: data[k] for k in ('pass', 'total')}
    (out / 'receipt.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print('receipt=' + str((out / 'receipt.json').relative_to(root)), flush=True)
    return int(any(item['exit_code'] for item in results))


if __name__ == '__main__':
    raise SystemExit(main())
