"""E3单格离线评价与六格汇总；预热完整留证，工程名义匹配与阻抗精度分开。"""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import sys

import numpy as np
from analyze_resp_b import replay, require_capture_end, SOURCE_SHA
from readback_b import PRIVATE, require, sha, write_json
from resp_exploratory import decode, estimate_period, raw_integrity
from resp_matrix_b import validate_source, validate_profile, CRITERIA, CELLS, bindings


def ecg_period(rows):
    """仅描述CH2低位尖峰的实际间隔；不用ECG60作先验，不替代BIO或源校准。"""
    if len(rows) < 3:
        return {'status': 'INSUFFICIENT_DATA', 'median_bpm': None}
    y = np.array([r['ch2_raw'] for r in rows]); t = np.array([r['device_ms'] for r in rows], dtype=np.int64)
    threshold = (float(y.min())+float(np.percentile(y, 5)))/2; peaks = []
    for i in range(1, len(y)-1):
        if y[i] < threshold and y[i] <= y[i-1] and y[i] < y[i+1]:
            if peaks and t[i]-t[peaks[-1]] < 250:
                if y[i] < y[peaks[-1]]:
                    peaks[-1] = i
            else:
                peaks.append(i)
    intervals = np.diff(t[peaks])
    good = len(intervals) >= 3 and np.all(intervals > 0)
    return {'status': 'SHARP_EVENT_INTERVALS_ONLY' if good else 'PERIOD_UNRESOLVED',
            'peak_count': len(peaks), 'intervals_ms': intervals.tolist(),
            'median_bpm': 60000/float(np.median(intervals)) if good else None,
            'not_source_accuracy_or_BIO': True}


def offset_ms(ms, anchor):
    # 有符号差支持137秒内设备32位毫秒计数跨界；不能直接按无符号绝对值排序。
    return ((ms-anchor+0x80000000) & 0xffffffff)-0x80000000


def select_phases(rows, live):
    require(bool(live), 'E3_NO_LIVE_DIAGNOSTICS')
    anchor = live[0]['last_sample_ms']
    offset = lambda ms: offset_ms(ms, anchor)
    selected = [r for r in rows if 0 <= offset(r['device_ms']) < 137000]
    warmup = [d for d in live if 0 <= offset(d['last_sample_ms']) < 45000]
    steady = [r for r in rows if 45000 <= offset(r['device_ms']) < 135000]
    eligible = [d for d in live if 45000 <= offset(d['last_sample_ms']) < 135000]
    return anchor, selected, warmup, steady, eligible


def validity(estimate, live, failures, nominal, anchor):
    """采前冻结：全部稳态保存观察有效，边缘/间隔覆盖通过，原码与RR均匹配名义值。"""
    coherent = estimate['status'] == 'PERIOD_COHERENT_EXPLORATORY_ONLY'
    good = [d for d in live if d['rpm_valid'] == 1 and d['rpm_reason'] == 0]
    fraction = len(good)/len(live) if live else 0.0
    times = [offset_ms(d['last_sample_ms'], anchor) for d in live]
    coverage = bool(len(times) >= CRITERIA['min_live_observations']
        and 45000 <= times[0] <= 46500 and 133500 <= times[-1] < 135000
        and all(0 < b-a <= CRITERIA['max_live_gap_ms'] for a, b in zip(times, times[1:])))
    raw_rate = estimate.get('time_domain_rpm') if coherent else None
    nominal_match = bool(raw_rate is not None and abs(raw_rate-nominal) <= 1)
    agreement = bool(raw_rate is not None and good and all(abs(d['rpm']-raw_rate) <= 1 and abs(d['rpm']-nominal) <= 1 for d in good))
    passed = bool(coherent and nominal_match and agreement and coverage and fraction == 1 and not failures)
    return {'status': 'E3_INPUT_INTEGRITY_FAIL' if failures else ('E3_CELL_NOMINAL_RATE_MATCH' if passed else 'E3_CELL_NOT_PASS'),
        'analysis_exit_code': 2 if failures else (0 if passed else 3), 'CH1_period_coherent': coherent,
        'steady_live_observations': len(live), 'steady_live_valid_observations': len(good),
        'observed_rr_valid_fraction': fraction, 'saved_observation_coverage_pass': coverage,
        'max_saved_observation_gap_ms': max((b-a for a, b in zip(times, times[1:])), default=None),
        'BIO_RR_agrees_with_independent_raw_and_nominal_within_1rpm': agreement,
        'raw_nominal_rate_match': nominal_match, 'observed_live_rpm': sorted(set(d['rpm'] for d in good)),
        'no_calibrated_source_accuracy_claim': True}


def aggregate(results):
    """六格必须真实独立且全部通过；缺格、重复原件或两轮周期差异不能被平均掩盖。"""
    require(len(results) == 6 and {r.get('cell') for r in results} == set(CELLS), 'E3_SIX_DISTINCT_CELLS_REQUIRED')
    require(all(r.get('stage') == 'E3' and r.get('criteria') == CRITERIA and r.get('tools_sha256') == bindings()
                and r.get('bio_source_sha256') == SOURCE_SHA for r in results), 'E3_AGGREGATE_PROTOCOL_DRIFT')
    for key in ('capture_receipt_sha256', 'raw_csv_sha256', 'source_record_sha256', 'profile_sha256', 'card_sha256'):
        require(len({r.get(key) for r in results}) == 6 and all(r.get(key) for r in results), 'E3_REUSED_ORIGINAL_'+key)
    passed = all(r.get('analysis_exit_code') == 0 and r.get('status') == 'E3_CELL_NOMINAL_RATE_MATCH' for r in results)
    by_cell = {r['cell']: r for r in results}
    repeat_differences = {}
    for rate in (12, 18, 24):
        pair = [by_cell[f'{rate}-r{repeat}']['independent_raw_estimate'].get('time_domain_rpm') for repeat in (1, 2)]
        difference = abs(pair[0]-pair[1]) if all(v is not None for v in pair) else None
        repeat_differences[str(rate)] = difference
        passed = passed and difference is not None and difference <= 1
    code = 0 if passed else (2 if any(r.get('analysis_exit_code') == 2 for r in results) else 3)
    return {'status': 'E3_NOMINAL_RR_ENGINEERING_PASS' if passed else 'E3_MATRIX_NOT_PASS',
        'matrix_exit_code': code, 'repeat_raw_difference_rpm': repeat_differences,
        'cell_statuses': {r['cell']: {'status': r['status'], 'analysis_exit_code': r['analysis_exit_code']} for r in results},
        'reference_rpm': None, 'Z0_ohm': None, 'delta_Zpp_ohm': None,
        'scope': 'NOMINAL_RATE_MATCH_NOT_CALIBRATED_RESP_IMPEDANCE_OR_CLINICAL_ACCURACY'}


def analyze(folder, source_path, profile_path, out):
    profile = json.loads(profile_path.read_text('utf-8')); validate_profile(profile)
    source = json.loads(source_path.read_text('utf-8')); validate_source(source, profile['cell'], ready=True)
    receipt = json.loads((folder/'receipt-private.json').read_text('utf-8'))
    supervisor = json.loads((folder/'supervisor-receipt-private.json').read_text('utf-8'))
    require_capture_end(receipt, supervisor)
    require(receipt.get('cell') == profile['cell'] and receipt.get('criteria') == CRITERIA
            and receipt.get('tools_sha256') == bindings() and receipt.get('duration_s') == 137, 'E3_CAPTURE_PROTOCOL')
    for path, expected in ((source_path, receipt['source_record_sha256']), (profile_path, receipt['profile_sha256']),
            (folder/'final-paused-ram-private.bin', receipt['ram_sha256']),
            (folder/'stable-raw-private.csv', receipt['stable_raw_sha256']),
            (folder/'diagnostics-private.jsonl', receipt['diagnostics_sha256'])):
        require(sha(path) == expected, 'VALIDITY_ORIGINAL_SHA_MISMATCH')
    chunks = [json.loads(line) for line in (folder/'chunks-private.jsonl').read_text('utf-8').splitlines()]
    with (folder/'running-slots-private.bin').open('rb') as stream:
        for chunk in chunks:
            require(stream.tell() == chunk['offset'] and chunk['bytes'] == 3072, 'VALIDITY_CHUNK_LAYOUT')
            require(hashlib.sha256(stream.read(3072)).hexdigest() == chunk['sha256'], 'VALIDITY_CHUNK_SHA')
        require(not stream.read(1), 'VALIDITY_UNACCOUNTED_RAW_BYTES')
    live = [json.loads(line) for line in (folder/'diagnostics-private.jsonl').read_text('utf-8').splitlines()]
    originals = sorted(folder.glob('*-diag.bin'))
    require(live and len(originals) == len(live), 'VALIDITY_DIAGNOSTIC_COUNT')
    for f, diagnostic in zip(originals, live):
        stem = f.name.removesuffix('-diag.bin')
        actual = decode(f.read_bytes(), (folder/(stem+'-stats.bin')).read_bytes(), (folder/(stem+'-rreg-cache.bin')).read_bytes())
        require(all(actual[k] == diagnostic[k] for k in actual), 'VALIDITY_DIAGNOSTIC_ORIGINAL_MISMATCH')
    with (folder/'stable-raw-private.csv').open(encoding='utf-8', newline='') as stream:
        rows = [{k: int(row[k]) for k in ('source_seq', 'device_ms', 'irq_cycles', 'status_raw', 'flags_raw', 'ch1_raw', 'ch2_raw')}
                for row in csv.DictReader(stream)]
    require(len(rows) > 1, 'VALIDITY_NO_STABLE_FRAMES')
    # 45秒预热/90秒评价/2秒尾段互斥；全部原件和预热失效原因保留。
    anchor, selected, warmup, steady, eligible = select_phases(rows, live)
    offset = lambda ms: offset_ms(ms, anchor)
    failures = raw_integrity(selected, receipt['export'])
    if not steady or offset(steady[0]['device_ms']) > 45012 or offset(steady[-1]['device_ms']) < 134988:
        failures.append('STEADY_DEVICE_COVERAGE')
    if any(abs(r['ch2_raw']) >= 8220835 for r in selected):
        failures.append('CH2_NEAR_RAIL')
    errors = {k: max(d['adc'][k] for d in live) for k in ('init_errors', 'spi_errors', 'bad_status', 'queue_overflow')}
    if any(errors.values()):
        failures.append('ADC_ERRORS')
    span = (live[-1]['host_start_s']+live[-1]['host_end_s']-live[0]['host_start_s']-live[0]['host_end_s'])/2
    sps = (live[-1]['adc']['captured']-live[0]['adc']['captured'])/span if span > 0 else None
    if sps is None or not 240 <= sps <= 260:
        failures.append('HOST_OBSERVED_SPS')
    estimate = estimate_period(steady)
    result = validity(estimate, eligible, failures, source['nominal_rpm'], anchor)
    out.mkdir(exist_ok=False); derived, events, dll_sha = replay(rows, out)
    result.update(stage='E3', cell=profile['cell'], criteria=CRITERIA, tools_sha256=bindings(),
        card_sha256=receipt['card_sha256'], source_type='RESP_EXPLORATORY',
        menu=source['menu'], reference_rpm=None, nominal_rpm=source['nominal_rpm'], Z0_ohm=None, delta_Zpp_ohm=None,
        dynamic_pair='MANUFACTURER_MANUAL_RA_LL', impedance_calibration='NOT_CALIBRATED',
        independent_raw_estimate=estimate, ecg_period_observation=ecg_period(steady),
        source_record_sha256=sha(source_path), profile_sha256=sha(profile_path),
        capture_receipt_sha256=sha(folder/'receipt-private.json'), raw_csv_sha256=sha(folder/'stable-raw-private.csv'),
        bio_source_sha256=SOURCE_SHA, replay_dll_sha256=dll_sha, retained_frames=len(rows),
        selected_frames=len(selected), steady_frames=len(steady), pre_anchor_frames_preserved=sum(offset(r['device_ms']) < 0 for r in rows),
        evaluation_device_offsets_ms=[45000, 135000], warmup_live_diagnostics=warmup,
        warmup_observations=len(warmup), warmup_invalid_observations=sum(d['rpm_valid'] != 1 for d in warmup), failures=failures, adc_error_max=errors,
        observed_host_sps=sps, live_diagnostics=live, steady_live_diagnostics=eligible,
        replay_final=derived[-1], replay_resp_event_records=len(events),
        RR_validity_scope='SAVED_LIVE_OBSERVATIONS_NOT_CONTINUOUS_OR_CLINICAL_ACCEPTANCE',
        E3='ONE_CELL_ONLY_SIX_CELL_AGGREGATE_REQUIRED', CPU_ROM_Flash_issue='DEFERRED_NOT_INVESTIGATED')
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    t = [offset(r['device_ms'])/1000 for r in rows]
    fig, axes = plt.subplots(4, 1, figsize=(11, 10), layout='constrained')
    axes[0].plot(t, [r['ch1_raw'] for r in rows]); axes[0].set(title='CH1 raw: no impedance calibration', ylabel='ADC codes')
    axes[1].plot(t, [r['resp_filtered'] for r in derived]); axes[1].set(title='Frozen BIO RESP filtered: HOST REPLAY', ylabel='UI scale')
    axes[2].plot(t, [r['ch2_raw'] for r in rows]); axes[2].set(title='CH2 companion ECG; requested setting60 is not assumed measured', ylabel='ADC codes')
    axes[3].scatter([offset(d['last_sample_ms'])/1000 for d in live], [d['rpm'] for d in live], label='live RR')
    axes[3].scatter([offset(d['last_sample_ms'])/1000 for d in live], [d['rpm_reason'] for d in live], label='live reason bits')
    axes[3].legend(); axes[3].set(xlabel='Device seconds from first window diagnostic')
    for axis in axes:
        axis.axvspan(45, 135, alpha=.08, color='green')
    fig.savefig(out/'resp-validity-waveforms-private.png', dpi=150); plt.close(fig)
    # 图件也成功保存后才发布成功摘要，避免图件异常/退出1却留下可供下一格使用的通过文件。
    write_json(out/'analysis-summary-private.json', result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('capture', 'source-record', 'profile', 'out'):
        parser.add_argument('--'+name, type=Path)
    parser.add_argument('--summaries', nargs=6, type=Path)
    args = parser.parse_args()
    require(args.out is not None, 'E3_ANALYSIS_OUT_REQUIRED')
    require(args.out.resolve().is_relative_to(PRIVATE.resolve()) and not args.out.exists(), 'VALIDITY_PRIVATE_ANALYSIS_OUTPUT')
    try:
        if args.summaries:
            results = [json.loads(p.read_text('utf-8')) for p in args.summaries]
            result = aggregate(results)
            result['summary_sha256'] = {str(p): sha(p) for p in args.summaries}
            args.out.mkdir(exist_ok=False)
            write_json(args.out/'matrix-summary-private.json', result)
            print(json.dumps({'status': result['status'], 'matrix_exit_code': result['matrix_exit_code']}))
            return result['matrix_exit_code']
        require(all((args.capture, args.source_record, args.profile)), 'E3_ANALYSIS_ARGUMENTS')
        result = analyze(args.capture, args.source_record, args.profile, args.out)
        print(json.dumps({k: result[k] for k in ('status', 'analysis_exit_code', 'steady_frames', 'observed_rr_valid_fraction')}))
        return result['analysis_exit_code']
    except BaseException as error:
        args.out.mkdir(exist_ok=True)
        write_json(args.out/'analysis-failure-private.json', {'status': 'VALIDITY_ANALYSIS_FAILED', 'error': type(error).__name__+': '+str(error), 'analysis_exit_code': 1})
        return 1


if __name__ == '__main__':
    sys.exit(main())
