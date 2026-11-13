"""G2-RO独立监督器：单次消费授权，SDK/总时限失败只终止子进程，不重连。"""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import time

import b5_g2ro as read


def watch(child, out, timeout_s=180, poll_s=.05):
    start = time.monotonic(); reason = None
    while child.poll() is None:
        if time.monotonic()-start >= timeout_s: reason = 'SESSION_TIMEOUT'
        if (out/'STOP').exists(): reason = 'OWNER_STOP'
        try:
            lines = (out/'heartbeat-events.jsonl').read_text('utf8').splitlines()
            event = json.loads(lines[-1]) if lines else {}
            if event.get('active') and time.monotonic() > event['deadline_monotonic']: reason = 'SDK_TIMEOUT'
        except (OSError, ValueError): pass
        if reason: child.kill(); break
        time.sleep(poll_s)
    child.wait(timeout=5)
    return {'reason': reason, 'worker_exit_code': child.returncode,
            'supervisor_exit_code': 0 if reason is None and child.returncode == 0 else 1,
            'automatic_retry_or_hardware_recovery': False}


def supervise(authorization, out):
    blob = read.private_read(authorization); auth = json.loads(blob)
    read.validate_authorization(auth, out)
    read.require(not out.exists(), 'G2RO_OUTPUT_EXISTS')
    marker = Path(authorization).with_suffix('.used')
    read.raw.write_json(marker, {'scope': read.SCOPE, 'authorization_sha256': read.digest(blob), 'started_unix': time.time()})
    read.recovery.protected(marker, False)
    command = [sys.executable, '-X', 'utf8', str(Path(read.__file__).resolve()), '--worker',
               '--authorization', str(authorization), '--out', str(out)]
    logfile = out.with_name(out.name+'-worker-private.log')
    with logfile.open('xb') as log:
        read.recovery.protected(logfile, False)
        child = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT)
        try: result = watch(child, out)
        except BaseException as error:
            result = {'reason': 'SUPERVISOR_EXCEPTION', 'error_type': type(error).__name__,
                      'worker_exit_code': None, 'supervisor_exit_code': 1,
                      'automatic_retry_or_hardware_recovery': False}
        finally:
            if child.poll() is None: child.kill()
            child.wait(timeout=5)
        result['worker_exit_code'] = child.returncode
    out.mkdir(exist_ok=True)
    read.raw.write_json(out/'supervisor-private.json', result)
    for path in out.iterdir():
        if path.is_file(): read.recovery.protected(path, False)
    print(json.dumps(result)); return result['supervisor_exit_code']


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--authorization', required=True, type=Path); parser.add_argument('--out', required=True, type=Path)
    args = parser.parse_args()
    try: return supervise(args.authorization, args.out)
    except BaseException as error:
        print(json.dumps({'status': 'STOP_BEFORE_SDK', 'error_type': type(error).__name__, 'exit_code': 1})); return 1


if __name__ == '__main__': raise SystemExit(main())
