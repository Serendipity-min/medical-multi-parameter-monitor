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


def supervise(authorization, out, backend=writer, formal_cloud=False):
    writer=backend
    raw = writer.recovery.read(authorization, False); auth = json.loads(raw)
    if formal_cloud: writer.authorize(auth, out, True)
    else: writer.authorize(auth, out)
    writer.require(not out.exists(), 'S3_OUTPUT_EXISTS')
    used = authorization.with_suffix('.used')
    started = time.monotonic()
    writer.ro.raw.write_json(used, {'scope': auth['scope'], 'authorization_sha256': writer.sha(raw),
                                  'started_unix': time.time(), 'started_monotonic': started})
    writer.recovery.protected(used, False)
    command = [sys.executable, '-X', 'utf8', str(Path(writer.__file__).resolve()), '--worker',
               '--authorization', str(authorization), '--out', str(out)]
    if formal_cloud: command.append('--formal-cloud')
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
    out.mkdir(exist_ok=True); writer.ro.raw.write_json(out/'supervisor-private.json', result)
    writer.recovery.protected(out/'supervisor-private.json', False)
    print(json.dumps(result)); return result['supervisor_exit_code']


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan', action='store_true'); parser.add_argument('--execute', action='store_true')
    parser.add_argument('--formal-cloud', action='store_true')
    parser.add_argument('--authorization', type=Path); parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    if args.plan or not args.execute: print(json.dumps(writer.plan(args.formal_cloud), indent=2)); return 0
    try:
        writer.require(args.authorization is not None and args.out is not None, 'S3_AUTH_AND_OUTPUT_REQUIRED')
        return supervise(args.authorization, args.out, formal_cloud=args.formal_cloud)
    except BaseException as error:
        print(json.dumps({'status': 'STOP_BEFORE_NATIVE', 'error_type': type(error).__name__, 'exit_code': 1})); return 1


if __name__ == '__main__': raise SystemExit(main())
