"""sector3专用监督器；默认plan，真实入口仍需未来独立EFS授权，本轮禁止启用。"""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import time

import b5_sector3_write as writer


def watch(child, out, timeout_s=180, started_monotonic=None):
    started = time.monotonic() if started_monotonic is None else started_monotonic
    reason = None
    while child.poll() is None:
        if time.monotonic()-started >= timeout_s: reason = 'SESSION_TIMEOUT'
        if (out/'STOP').exists(): reason = 'OWNER_STOP'
        try:
            rows = (out/'heartbeat-events.jsonl').read_text('utf8').splitlines()
            last = json.loads(rows[-1]) if rows else {}
            if last.get('active') and time.monotonic() >= last['deadline_monotonic']: reason = 'NATIVE_CALL_TIMEOUT'
        except (OSError, ValueError): pass
        if reason: child.kill(); break
        time.sleep(.02)
    child.wait(timeout=5)
    return {'reason': reason, 'worker_exit_code': child.returncode,
            'supervisor_exit_code': 0 if reason is None and child.returncode == 0 else 1,
            'target_state': 'UNKNOWN_NO_RECONNECT_CLEANUP' if reason else 'SEE_WORKER_RECEIPT',
            'automatic_retry_or_recovery': False}


def describe_stop(result, receipt):
    reason = result.get('reason') or receipt.get('stop_reason') or 'WORKER_FAILED'
    message = {
        'SECTOR3_PREWRITE_BUDGET_INSUFFICIENT': '写前时间预算不足，尚未擦除或编程。',
        'SECTOR3_SESSION_TIMEOUT': '写入状态机达到会话时限，需核对写入阶段和回执。',
        'SESSION_TIMEOUT': '达到会话时限，需核对写入阶段和回执。',
        'NATIVE_CALL_TIMEOUT': 'J-Link 原生调用超时，需核对回执。',
        'OWNER_STOP': '收到现场停止指令，需核对回执。',
    }.get(reason, '写入已停止，需核对停止码和回执。')
    return {'stop_code': reason, 'operator_message': message}


def supervise(authorization, out, backend=writer, formal_cloud=False, commit_resume=False):
    writer = backend
    raw = writer.recovery.read(authorization, False); auth = json.loads(raw)
    writer.authorize(auth, out, formal_cloud, commit_resume)
    writer.require(not out.exists(), 'S3_OUTPUT_EXISTS')
    used = authorization.with_suffix('.used')
    started = time.monotonic()
    writer.ro.raw.write_json(used, {'scope': auth['scope'], 'authorization_sha256': writer.sha(raw),
                                  'started_unix': time.time(), 'started_monotonic': started})
    writer.recovery.protected(used, False)
    command = [sys.executable, '-X', 'utf8', str(Path(writer.__file__).resolve()), '--worker',
               '--authorization', str(authorization), '--out', str(out)]
    if formal_cloud: command.append('--formal-cloud')
    if commit_resume: command.append('--commit-resume')
    with out.with_name(out.name+'-worker-private.log').open('xb') as log:
        writer.recovery.protected(out.with_name(out.name+'-worker-private.log'), False)
        child = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT)
        try: result = watch(child, out, timeout_s=auth.get('session_timeout_s',180), started_monotonic=started)
        except BaseException as error:
            result = {'reason': 'SUPERVISOR_EXCEPTION', 'error_type': type(error).__name__, 'worker_exit_code': None,
                'supervisor_exit_code': 1, 'target_state': 'UNKNOWN_NO_RECONNECT_CLEANUP', 'automatic_retry_or_recovery': False}
        finally:
            if child.poll() is None: child.kill()
            child.wait(timeout=5)
        result['worker_exit_code'] = child.returncode
    out.mkdir(exist_ok=True)
    if result['supervisor_exit_code'] != 0:
        receipt = out/'receipt-private.json'
        details = json.loads(writer.recovery.read(receipt, False)) if result['reason'] is None and receipt.is_file() else {}
        result.update(describe_stop(result, details))
    writer.ro.raw.write_json(out/'supervisor-private.json', result)
    writer.recovery.protected(out/'supervisor-private.json', False)
    print(json.dumps(result)); return result['supervisor_exit_code']


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan', action='store_true'); parser.add_argument('--execute', action='store_true')
    parser.add_argument('--formal-cloud', action='store_true')
    parser.add_argument('--commit-resume', action='store_true')
    parser.add_argument('--authorization', type=Path); parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    if args.commit_resume and not args.formal_cloud:
        parser.error('--commit-resume requires --formal-cloud')
    if args.plan or not args.execute:
        print(json.dumps(writer.plan(args.formal_cloud, args.commit_resume), indent=2)); return 0
    try:
        writer.require(args.authorization is not None and args.out is not None, 'S3_AUTH_AND_OUTPUT_REQUIRED')
        return supervise(args.authorization, args.out, formal_cloud=args.formal_cloud, commit_resume=args.commit_resume)
    except BaseException as error:
        print(json.dumps({'status': 'STOP_BEFORE_NATIVE', 'error_type': type(error).__name__, 'exit_code': 1})); return 1


if __name__ == '__main__': raise SystemExit(main())
