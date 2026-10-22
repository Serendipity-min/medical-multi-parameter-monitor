"""RESP-003 E1独立监督入口；保存子进程真实退出码，超时不补发硬件恢复。"""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import time

from readback_b import PRIVATE, require, sha, write_json


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('dll', 'card', 'profile', 'source-record', 'out'):
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--card-sha256', required=True)
    parser.add_argument('--seconds', type=int, choices=(10,), required=True)
    args = parser.parse_args()
    require(args.out.resolve().is_relative_to(PRIVATE.resolve()), 'RESP_PRIVATE_OUTPUT_REQUIRED')
    require(not args.out.exists(), 'RESP_OUTPUT_ALREADY_EXISTS')
    require(sha(args.card) == args.card_sha256, 'RESP_CARD_SHA')
    command = [sys.executable, str(Path(__file__).with_name('capture_resp_b.py'))]
    for name in ('dll', 'card', 'profile', 'source_record', 'out', 'card_sha256', 'seconds'):
        command += ['--' + name.replace('_', '-'), str(getattr(args, name))]
    started = time.monotonic();reason = None
    # worker原始stdout/stderr和返回码均留私有目录；输出目录独占，禁止覆盖失败后重跑。
    with (args.out.parent / (args.out.name + '-worker-output.log')).open('xb') as stream:
        process = subprocess.Popen(command, stdout=stream, stderr=subprocess.STDOUT)
        try:
            while process.poll() is None:
                if (args.out / 'STOP').exists():
                    reason = 'OWNER_STOP'
                if time.monotonic() - started > 240:
                    reason = 'SESSION_HARD_TIMEOUT'
                heartbeat = args.out / 'heartbeat-events.jsonl'
                if heartbeat.exists():
                    try:
                        complete = heartbeat.read_text('utf-8').rsplit('\n', 1)[0].splitlines()
                        event = json.loads(complete[-1]) if complete else {}
                        if event.get('active') and time.monotonic() > event['deadline_monotonic']:
                            reason = 'SDK_CALL_HARD_TIMEOUT'
                    except (FileNotFoundError, PermissionError, json.JSONDecodeError):
                        pass  # 追加尾行暂不可读不作成功；240秒硬上限持续有效。
                if reason:
                    process.kill();process.wait(timeout=5);break
                time.sleep(.02)
        finally:
            if process.poll() is None:
                process.kill();process.wait(timeout=5)
    args.out.mkdir(exist_ok=True)
    result = {'status': reason or ('WORKER_EXIT_ZERO' if process.returncode == 0 else 'WORKER_FAILED'),
              'worker_exit_code': process.returncode, 'supervisor_exit_code': 0 if not reason and process.returncode == 0 else 1,
              'elapsed_s': time.monotonic() - started,
              'target_state_on_failure': 'UNKNOWN_NO_AUTOMATIC_RECOVERY' if reason or process.returncode else None}
    write_json(args.out / 'supervisor-receipt-private.json', result)
    print(json.dumps(result))
    return result['supervisor_exit_code']


if __name__ == '__main__':
    sys.exit(main())
