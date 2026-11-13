"""RA–LL呼吸30的45秒独立离线分析：原件先核验，CH1周期、BIO RR、源名义设置分列。"""
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
from resp_rall30_b import validate_source, validate_profile


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


def validity(estimate, live, failures):
    """预冻结判据：原始周期相干、至少5次实板观察全有效、RR与原码估计相差≤1。"""
    coherent = estimate['status'] == 'PERIOD_COHERENT_EXPLORATORY_ONLY'
    good = [d for d in live if d['rpm_valid'] == 1]
    fraction = len(good)/len(live) if live else 0.0
    raw_rate = estimate.get('time_domain_rpm') if coherent else None
    agreement = bool(raw_rate is not None and good and all(abs(d['rpm']-raw_rate) <= 1 for d in good))
    rr_valid = len(live) >= 5 and fraction == 1 and agreement
    status = ('RESP_INPUT_INTEGRITY_FAIL' if failures else
              ('RESP_VALIDITY_OBSERVED_FOR_THIS_WINDOW' if coherent and rr_valid else
               ('RAW_PERIOD_OBSERVED_BIO_RR_NOT_VALID' if coherent else 'RESP_PATH_NOT_OBSERVED')))
    return {'status': status, 'analysis_exit_code': 2 if failures else (0 if coherent and rr_valid else 3),
            'CH1_period_coherent': coherent, 'steady_live_observations': len(live),
            'steady_live_valid_observations': len(good), 'observed_rr_valid_fraction': fraction,
            'BIO_RR_agrees_with_independent_raw_within_1rpm': agreement,
            'observed_live_rpm': sorted(set(d['rpm'] for d in good)),
            'nominal_30_match_descriptive_only': bool(coherent and abs(raw_rate-30) <= 1),
            'no_calibrated_source_accuracy_claim': True}


def analyze(folder, source_path, profile_path, out):
    source = json.loads(source_path.read_text('utf-8')); validate_source(source)
    profile = json.loads(profile_path.read_text('utf-8')); validate_profile(profile)
    receipt = json.loads((folder/'receipt-private.json').read_text('utf-8'))
    supervisor = json.loads((folder/'supervisor-receipt-private.json').read_text('utf-8'))
    require_capture_end(receipt, supervisor)
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
    # 用设备时钟锚定：首10秒预热，随后30秒评价，最后5秒留作覆盖裕量。
    anchor = live[0]['last_sample_ms']
    offset = lambda ms: ((ms-anchor+0x80000000) & 0xffffffff)-0x80000000
    selected = [r for r in rows if 0 <= offset(r['device_ms']) < 45000]
    steady = [r for r in rows if 10000 <= offset(r['device_ms']) < 40000]
    eligible = [d for d in live if 10000 <= offset(d['last_sample_ms']) < 40000]
    failures = raw_integrity(selected, receipt['export'])
    if not steady or offset(steady[0]['device_ms']) > 10008 or offset(steady[-1]['device_ms']) < 39988:
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
    result = validity(estimate, eligible, failures)
    out.mkdir(exist_ok=False); derived, events, dll_sha = replay(rows, out)
    result.update(stage='RESP_RA_LL30_SINGLE_WINDOW', source_type='RESP_EXPLORATORY',
        menu=source['menu'], reference_rpm=None, nominal_rpm=30, Z0_ohm=None, delta_Zpp_ohm=None,
        dynamic_pair='MANUFACTURER_MANUAL_RA_LL', impedance_calibration='NOT_CALIBRATED',
        independent_raw_estimate=estimate, ecg_period_observation=ecg_period(steady),
        source_record_sha256=sha(source_path), profile_sha256=sha(profile_path),
        capture_receipt_sha256=sha(folder/'receipt-private.json'), raw_csv_sha256=sha(folder/'stable-raw-private.csv'),
        bio_source_sha256=SOURCE_SHA, replay_dll_sha256=dll_sha, retained_frames=len(rows),
        selected_frames=len(selected), steady_frames=len(steady), pre_anchor_frames_preserved=sum(offset(r['device_ms']) < 0 for r in rows),
        evaluation_device_offsets_ms=[10000, 40000], failures=failures, adc_error_max=errors,
        observed_host_sps=sps, live_diagnostics=live, steady_live_diagnostics=eligible,
        replay_final=derived[-1], replay_resp_event_records=len(events),
        RR_validity_scope='SAVED_LIVE_OBSERVATIONS_NOT_CONTINUOUS_OR_CLINICAL_ACCEPTANCE',
        E2='WINDOW_ONLY_COMPARISON_SEPARATE', E3='NOT_RUN', CPU_ROM_Flash_issue='DEFERRED_NOT_INVESTIGATED')
    write_json(out/'analysis-summary-private.json', result)
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
        axis.axvspan(10, 40, alpha=.08, color='green')
    fig.savefig(out/'resp-validity-waveforms-private.png', dpi=150); plt.close(fig)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('capture', 'source-record', 'profile', 'out'):
        parser.add_argument('--'+name, required=True, type=Path)
    args = parser.parse_args()
    require(args.out.resolve().is_relative_to(PRIVATE.resolve()) and not args.out.exists(), 'VALIDITY_PRIVATE_ANALYSIS_OUTPUT')
    try:
        result = analyze(args.capture, args.source_record, args.profile, args.out)
        print(json.dumps({k: result[k] for k in ('status', 'analysis_exit_code', 'steady_frames', 'observed_rr_valid_fraction')}))
        return result['analysis_exit_code']
    except BaseException as error:
        args.out.mkdir(exist_ok=True)
        write_json(args.out/'analysis-failure-private.json', {'status': 'VALIDITY_ANALYSIS_FAILED', 'error': type(error).__name__+': '+str(error), 'analysis_exit_code': 1})
        return 1


if __name__ == '__main__':
    sys.exit(main())
