"""45秒RESP有效性独立硬时限监督；失败不重试或自动恢复。"""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import time

from readback_b import PRIVATE, require, write_json


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('dll', 'card', 'manifest', 'out'):
        parser.add_argument('--'+name, required=True, type=Path)
    parser.add_argument('--card-sha256', required=True)
    args = parser.parse_args()
    require(args.out.resolve().is_relative_to(PRIVATE.resolve()), 'RUNTIME_PRIVATE_OUTPUT')
    require(not args.out.exists(), 'RUNTIME_OUTPUT_EXISTS')
    argv = [sys.executable, '-X', 'utf8', str(Path(__file__).with_name('resp_validity_b.py'))]
    for name in ('dll', 'card', 'manifest', 'out', 'card_sha256'):
        argv += ['--'+name.replace('_', '-'), str(getattr(args, name))]
    started = time.monotonic(); reason = None
    # 输出文件独占；轮询只读取磁盘心跳，禁止监督进程另开调试连接。
    with (args.out.parent/(args.out.name+'-worker-output.log')).open('xb') as stream:
        process = subprocess.Popen(argv, stdout=stream, stderr=subprocess.STDOUT)
        try:
            while process.poll() is None:
                if (args.out/'STOP').exists():
                    reason = 'OWNER_STOP'
                if time.monotonic()-started > 240:
                    reason = 'RUNTIME_SESSION_TIMEOUT'
                for heartbeat in args.out.glob('heartbeat-events.jsonl'):
                    try:
                        lines = heartbeat.read_text('utf-8').rsplit('\n', 1)[0].splitlines()
                        event = json.loads(lines[-1]) if lines else {}
                        if event.get('active') and time.monotonic() > event['deadline_monotonic']:
                            reason = 'RUNTIME_SDK_CALL_TIMEOUT'
                    except (FileNotFoundError, PermissionError, json.JSONDecodeError):
                        pass  # 暂时追加中的行不能作成功依据；全会话硬时限始终生效。
                if reason:
                    process.kill(); process.wait(timeout=5); break
                time.sleep(.02)
        finally:
            if process.poll() is None:
                process.kill(); process.wait(timeout=5)
    args.out.mkdir(exist_ok=True)
    result = {'status': reason or 'WORKER_RETURNED', 'worker_exit_code': process.returncode,
              'supervisor_exit_code': 0 if not reason and process.returncode == 0 else 1,
              'elapsed_s': time.monotonic()-started, 'automatic_hardware_recovery': False}
    write_json(args.out/'supervisor-receipt-private.json', result)
    print(json.dumps(result)); return result['supervisor_exit_code']


if __name__ == '__main__':
    sys.exit(main())
