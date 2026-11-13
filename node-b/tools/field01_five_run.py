"""五板40–41Ω诊断编排；上电/接线由负责人完成，不刷写、不启泵、不录音。"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time

from b4_recovery import protected

ROOT = Path(__file__).resolve().parents[2]


def run(job, installed_b, profile):
    protected(job, False)
    if (job / 'RUN_STARTED.json').exists():
        raise ValueError('NEW_FIELD_TRANSACTION_REQUIRED')
    bindings = json.loads((job / 'tool-source-sha256.json').read_text())
    if any(hashlib.sha256((ROOT / name).read_bytes()).hexdigest() != digest for name, digest in bindings.items()):
        raise ValueError('FIVE_FIELD_TOOL_DRIFT')
    (job / 'RUN_STARTED.json').write_text(json.dumps(dict(monotonic=time.monotonic(), profile=profile)) + '\n')
    logs = []
    children = {}
    result = dict(exit_code=1, profile=profile, formal_acceptance=False, electrical='40_41_OHM_DIAGNOSTIC')

    def child(name, command):
        log = (job / (name + '-native-private.log')).open('xb')
        logs.append(log)
        process = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT,
                                   creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        children[name] = process
        return process

    def wait_ready(path, seconds):
        until = time.monotonic() + seconds
        while not path.exists():
            if any(p.poll() is not None for p in children.values()):
                raise RuntimeError('FIVE_PREARM_PROCESS_EXIT')
            if time.monotonic() >= until:
                raise TimeoutError('FIVE_PREARM_READY_BOUND')
            time.sleep(.1)

    try:
        receiver = child('receiver', [sys.executable, '-X', 'utf8', str(ROOT / 'node-b/tools/field01_receiver.py'),
            '--output', str(job / 'receiver'), '--credentials', str(job / 'voice-runtime-credentials-private.json')])
        wait_ready(job / 'receiver/READY.json', 25)
        source = child('B-source', [sys.executable, '-X', 'utf8', str(ROOT / 'node-b/tools/field01_b_source.py'),
                                  '--job', str(job), '--installed', str(installed_b)])
        wait_ready(job / 'B_READY.json', 90)
        controller = child('C-controller', [sys.executable, '-X', 'utf8', str(ROOT / 'node-b/tools/field01_ad_window.py'),
            '--job', str(job), '--mode', 'FIVE_DIAG', '--channel-profile', profile])
        notices = set()
        until = time.monotonic() + 415
        while controller.poll() is None:
            for name, event in [('COMMON_T0.json', 'FIVE_COMMON_WARMUP_45S'), ('T0.json', 'FIVE_EVALUATION_300S')]:
                if (job / name).exists() and name not in notices:
                    print(json.dumps(dict(event=event, profile=profile)), flush=True)
                    notices.add(name)
            if time.monotonic() > until:
                raise TimeoutError('FIVE_CONTROLLER_PROCESS_BOUND')
            time.sleep(.1)
        result['controller_native_exit'] = controller.returncode
        (job / 'END_B').touch()
        source.wait(timeout=15)
        receiver.wait(timeout=20)
        result.update(exit_code=0 if all(p.returncode == 0 for p in children.values()) else 1,
                      status='FIVE_DIAGNOSTIC_CAPTURED_LAYERED_REVIEW_REQUIRED')
    except (Exception, KeyboardInterrupt) as error:
        (job / 'supervisor-failure-private.json').write_text(json.dumps(dict(type=type(error).__name__, detail=str(error))) + '\n')
        result['error_type'] = type(error).__name__
    finally:
        (job / 'END_B').touch()
        if (job / 'receiver').exists():
            (job / 'receiver/STOP_RECEIVER').touch()
        for name, process in children.items():
            if process.poll() is None:
                try:
                    process.wait(timeout=15)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=3)
                    result.setdefault('forced_host_process_exits', []).append(name)
        result['native_process_exit_codes'] = {name: p.returncode for name, p in children.items()}
        result['all_own_processes_exited'] = all(p.poll() is not None for p in children.values())
        (job / 'native-process-exits.json').write_text(json.dumps(result, indent=2) + '\n')
        for log in logs:
            log.close()
    print(json.dumps(result), flush=True)
    return result['exit_code']


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--job', type=Path, required=True)
    parser.add_argument('--installed-B', type=Path, required=True)
    parser.add_argument('--channel-profile', choices=('ECG60', 'RR'), required=True)
    parser.add_argument('--execute', action='store_true')
    args = parser.parse_args()
    if args.execute:
        raise SystemExit(run(args.job, args.installed_B, args.channel_profile))
    print(json.dumps(dict(execute=False, warmup_s=45, evaluation_s=300, electrical='40_41_OHM_DIAGNOSTIC', recording=False)))
