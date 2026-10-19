"""只读观测既有UART状态，不操作串口、不复位开发板、不清累计计数。"""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import time


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--number', type=int, required=True, choices=(1, 2))
    parser.add_argument('--attempt', type=int, default=1)
    parser.add_argument('--seconds', type=int, default=312)
    args = parser.parse_args()
    if args.seconds < 310:
        parser.error('retain at least 300 seconds of complete interior reports')
    root = Path(__file__).resolve().parents[3]
    evidence = root / 'gateway/physical_can/evidence/h2r'
    status_path = root / 'gateway/physical_can/build/h2r/uart-status.json'
    suffix = '' if args.attempt == 1 else f'-attempt-{args.attempt}'
    destination = evidence / f'window-{args.number}{suffix}-observation.json'
    if destination.exists():
        raise RuntimeError('DO_NOT_OVERWRITE_PRIOR_WINDOW')
    result = {'mode': 'REAL_HARDWARE_READ_ONLY_STATUS_OBSERVATION',
              'number': args.number, 'attempt': args.attempt,
              'utc_start': datetime.now(timezone.utc).isoformat(),
              'target_seconds': args.seconds, 'samples': [], 'exit_code': None}
    started = time.monotonic()
    next_progress = 0
    expected_period = '1000' if args.number == 1 else '500'
    failure = None
    try:
        while True:
            # 共享文件以短生命周期读取，避免阻塞采集进程的原子状态发布。
            state = json.loads(status_path.read_text(encoding='utf-8-sig'))
            elapsed = time.monotonic() - started
            if result['samples'] and state['stamp'] != result['samples'][0]['state']['stamp']:
                raise RuntimeError('CAPTURE_CHANGED_WITHIN_WINDOW')
            bench = state['latest']
            if state['state'] != 'CAPTURING' or time.time()-status_path.stat().st_mtime > 4:
                raise RuntimeError('CAPTURE_NOT_FRESH')
            expected = {'fault': '0', 'BOFF': '0', 'TEC': '0', 'REC': '0', 'LEC': '0',
                        'A': '1', 'B': '0', 'paused': '0', 'diag_ms': expected_period}
            if any(bench.get(key) != value for key, value in expected.items()):
                raise RuntimeError('BENCH_STATE_OR_CAN_ERROR')
            for group, keys in (
                ('rx_queue', ('hw_fovr', 'sw_over', 'fault_discard', 'stale_discard', 'bus_drop')),
                ('model', ('over', 'bad', 'uart_drop', 'router_drop')),
                ('host_log', ('missing_reports', 'missing_lines', 'incomplete_reports',
                              'duplicate_lines', 'invalid_tags', 'device_boot_markers'))):
                if any(int(state[group][key]) for key in keys):
                    raise RuntimeError('LOSS_OR_RESET_OBSERVED_' + group)
            if int(bench['ms']) - int(state['rx']['701']['last']) > 1500:
                raise RuntimeError('HEARTBEAT_NOT_CURRENT')
            result['samples'].append({'elapsed_s': round(elapsed, 6), 'state': state})
            if elapsed >= next_progress:
                print(json.dumps({'window': args.number, 'elapsed_s': round(elapsed, 2),
                                  'device_ms': bench['ms'], 'errors': 0}), flush=True)
                next_progress += 30
            if elapsed >= args.seconds:
                break
            time.sleep(1)
    except Exception as exc:
        failure = str(exc)
    # 无论成功失败都保留完整脱敏快照，失败不能重跑覆盖成PASS。
    result.update(utc_end=datetime.now(timezone.utc).isoformat(),
                  elapsed_s=round(time.monotonic()-started, 6),
                  failure=failure, exit_code=1 if failure else 0)
    destination.write_text(json.dumps(result, indent=2)+'\n', encoding='utf-8')
    print(json.dumps({'path': str(destination), 'exit_code': result['exit_code'],
                      'elapsed_s': result['elapsed_s'], 'failure': failure}), flush=True)
    return result['exit_code']


if __name__ == '__main__':
    raise SystemExit(main())
