"""对保存的脱敏快照及完整报告交叉验收，不补造逐帧到达时间。"""
import argparse
import importlib.util
import json
from pathlib import Path
import re


def fields(line):
    return dict(re.findall(r'(\w+)=([^ ]+)', line))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--number', type=int, required=True, choices=(1, 2))
    parser.add_argument('--attempt', type=int, default=1)
    args = parser.parse_args()
    directory = Path(__file__).resolve().parents[1] / 'evidence/h2r'
    suffix = '' if args.attempt == 1 else f'-attempt-{args.attempt}'
    observation = json.loads((directory / f'window-{args.number}{suffix}-observation.json').read_text())
    samples = observation['samples']
    first, last = samples[0]['state'], samples[-1]['state']
    low, high = int(first['latest']['rs'])+1, int(last['latest']['rs'])-1
    reports, current = [], None
    spec = importlib.util.spec_from_file_location('capture', Path(__file__).with_name('capture_uart.py'))
    capture = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(capture)
    tracker = capture.ReportTracker()
    # 只纳入观测起止之间的完整报告，避免USB缓冲及边界半份报告放大时长。
    for line in (directory / first['log']).read_text(encoding='utf-8').splitlines():
        data = fields(line)
        if line.startswith('DIAG_BEGIN '):
            seq = int(data['seq'])
            current = {'seq': seq, 'rx': {}} if low <= seq <= high else None
        if current is None:
            continue
        tracker.feed(line)
        for prefix, key in (('BENCH ', 'latest'), ('MIRROR ', 'mirror'), ('MODEL ', 'model'),
                            ('RXQ ', 'rx_queue'), ('TIMING ', 'timing')):
            if line.startswith(prefix):
                current[key] = data
        if line.startswith('RX id='):
            current['rx'][data['id']] = data
        if line.startswith('DIAG_END '):
            reports.append(current)
            current = None
    checks = {}
    checks['observer_exit_zero'] = observation['exit_code'] == 0
    checks['interior_device_duration_at_least_300s'] = len(reports) > 1 and (
        int(reports[-1]['latest']['ms'])-int(reports[0]['latest']['ms']) >= 300000)
    checks['complete_contiguous_reports'] = len(reports) == high-low+1 and all(
        not tracker.stats[k] for k in ('missing_reports', 'missing_lines', 'incomplete_reports',
                                       'duplicate_lines', 'invalid_tags', 'device_boot_markers'))
    checks['all_reports_online_without_can_error'] = all(
        all(r['latest'].get(k) == v for k, v in
            {'fault': '0', 'BOFF': '0', 'TEC': '0', 'REC': '0', 'LEC': '0',
             'A': '1', 'B': '0', 'paused': '0', 'diag_ms': '1000' if args.number == 1 else '500'}.items())
        and int(r['latest']['ms'])-int(r['rx']['701']['last']) <= 1500 for r in reports)
    checks['all_loss_counters_zero'] = all(
        all(int(r[group][key]) == 0 for group, keys in (
            ('rx_queue', ('hw_fovr', 'sw_over', 'fault_discard', 'stale_discard', 'bus_drop')),
            ('model', ('over', 'bad', 'uart_drop', 'router_drop'))) for key in keys)
        for r in reports)
    # 本轮验收窗口已冻结为无人/无合格夹具状态，新增波形或质量变化不得悄悄当成同一负载。
    checks['disconnected_source_state_retained'] = (
        all(r['mirror']['Q'] == '00000000' for r in reports)
        and first['rx'].get('181', {}).get('n', '0') == last['rx'].get('181', {}).get('n', '0'))
    rhythm = {}
    for ident in ('701', '181', '381', '481', '681'):
        if ident not in last['rx']:
            rhythm[ident] = {'status': 'NOT_OBSERVED_IN_WINDOW'}
            continue
        # 观测中途新增的流仍须记录，不能因为起点没有该ID就误报未接收到。
        a, b = first['rx'].get(ident), last['rx'][ident]
        advances = []
        previous = None
        for report in reports:
            if ident not in report['rx']:
                continue
            stamp = int(report['rx'][ident]['last'])
            if previous is not None and stamp != previous:
                advances.append(stamp-previous)
            previous = stamp
        rhythm[ident] = {'count_delta': int(b['n'])-(int(a['n']) if a else 0),
                         'appeared_after_start': a is None,
                         'first_snapshot_last_ms': int(a['last']) if a else None,
                         'end_snapshot_last_ms': int(b['last']),
                         'lifetime_dt_min_ms': int(b['dt_min']),
                         'lifetime_dt_max_ms_includes_cold_power_off': int(b['dt_max']),
                         'report_last_timestamp_advance_min_ms': min(advances) if advances else None,
                         'report_last_timestamp_advance_max_ms': max(advances) if advances else None}
    # 报告中只保存每类帧的最近时间，不能据此声称每一帧逐样本完全一致。
    result = {'number': args.number, 'attempt': args.attempt,
              'checks': checks, 'exit_code': 0 if all(checks.values()) else 1,
              'capture_stamp': first['stamp'], 'log': first['log'],
              'host_observation_seconds': observation['elapsed_s'],
              'first_report': low, 'last_report': high, 'complete_reports': len(reports),
              'interior_device_duration_seconds': (
                  int(reports[-1]['latest']['ms'])-int(reports[0]['latest']['ms']))/1000 if reports else 0,
              'host_report_integrity': tracker.snapshot(), 'rhythm': rhythm,
              'loss_counters_start': {g: first[g] for g in ('rx_queue', 'model', 'host_log')},
              'loss_counters_end': {g: last[g] for g in ('rx_queue', 'model', 'host_log')},
              'timing_lifetime_maxima': last['timing'],
              'limits': 'No per-frame sample-perfect comparison; lifetime rhythm includes cold boots; acquisition source requires separate operator evidence.'}
    (directory / f'window-{args.number}{suffix}-result.json').write_text(json.dumps(result, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(result))
    return result['exit_code']


if __name__ == '__main__':
    raise SystemExit(main())
