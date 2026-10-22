"""监督受限B备份子进程；SDK超时或STOP只终止，不追加目标恢复命令。"""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import time
from readback_b import PRIVATE, require, sha, write_json


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dll', required=True, type=Path)
    parser.add_argument('--card', required=True, type=Path)
    parser.add_argument('--card-sha256', required=True)
    parser.add_argument('--out', required=True, type=Path)
    parser.add_argument('--operation',choices=['readback','install','precheck','fault','boot','path','pulse','capture'],default='readback')
    parser.add_argument('--plan',type=Path)
    parser.add_argument('--reference',type=Path)
    parser.add_argument('--profile',type=Path)
    parser.add_argument('--source-record',type=Path)
    parser.add_argument('--seconds',type=int,choices=(10,90),default=10)
    args = parser.parse_args()
    require(args.out.resolve().is_relative_to(PRIVATE.resolve()), 'OUTPUT_NOT_RESTRICTED')
    require(not args.out.exists(), 'OUTPUT_ALREADY_EXISTS')
    require(sha(args.card) == args.card_sha256, 'CARD_SHA_MISMATCH')
    log = args.out.parent/(args.out.name+'-worker-output.log')
    started = time.monotonic()
    worker={'readback':'readback_b.py','install':'install_b.py','precheck':'precheck_b.py','fault':'fault_snapshot_b.py','boot':'boot_check_b.py','path':'adc_path_b.py','pulse':'start_pulse_b.py','capture':'capture_b.py'}[args.operation]
    command = [sys.executable, str(Path(__file__).with_name(worker)),
               '--dll', str(args.dll), '--card', str(args.card),
               '--card-sha256', args.card_sha256, '--out', str(args.out)]
    if args.operation=='install':
        require(args.plan is not None,'INSTALL_PLAN_REQUIRED')
        command += ['--plan',str(args.plan)]
    if args.operation in ('precheck','fault','boot','path','pulse'):
        require(args.reference is not None,'PRECHECK_REFERENCE_REQUIRED')
        command += ['--reference',str(args.reference)]
    if args.operation=='capture':
        require(args.profile is not None and args.source_record is not None,'CAPTURE_BINDING_REQUIRED')
        command += ['--profile',str(args.profile),'--source-record',str(args.source_record),'--seconds',str(args.seconds)]
    reason = None
    with log.open('xb') as stream:
        process = subprocess.Popen(command, stdout=stream, stderr=subprocess.STDOUT)
        try:
            while process.poll() is None:
                if (args.out/'STOP').exists():
                    reason = 'OWNER_STOP'
                if time.monotonic()-started > (240 if args.operation=='capture' else 180):
                    reason = 'SESSION_HARD_TIMEOUT'
                heartbeat = args.out/'heartbeat-events.jsonl'
                if heartbeat.exists():
                    try:
                        # Windows读句柄会阻止rename/unlink；改用只追加事件流，保留原始时序。
                        data = heartbeat.read_text('utf-8')
                        complete = data.rsplit('\n',1)[0].splitlines()
                        event = json.loads(complete[-1]) if complete else {}
                        if event.get('active') and time.monotonic() > event['deadline_monotonic']:
                            reason = 'SDK_CALL_HARD_TIMEOUT'
                    except (FileNotFoundError, PermissionError, json.JSONDecodeError):
                        pass  # 正在追加的尾行或短暂共享冲突，下轮重读；全会话硬上限仍有效。
                if reason:
                    process.kill()
                    process.wait(timeout=5)
                    break
                time.sleep(.02)
        finally:
            if process.poll() is None:
                process.kill()
                process.wait(timeout=5)
    if reason:
        args.out.mkdir(exist_ok=True)
        write_json(args.out/'supervisor-stop.json', {'status': reason,
                   'target_end_state': 'UNKNOWN_NO_AUTOMATIC_RECOVERY', 'worker_exit': process.returncode})
    receipt = args.out/'receipt-private.json'
    result = json.loads(receipt.read_text('utf-8')) if receipt.exists() else {}
    # 只输出固定状态；UID/探针序号、原件路径和DLL原始文本留受限日志。
    print(json.dumps({'status': reason or result.get('status', 'WORKER_FAILED'),
                      'error': result.get('error'), 'worker_exit': process.returncode,
                      'target_end_state': result.get('target_end_state', 'UNKNOWN')}))
    return 0 if not reason and process.returncode == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
