"""本次39948B同步窗口离线分析：槽一致性、原码周期、实板诊断及发送资格分开。"""
from collections import Counter
import csv
import hashlib
import json
from pathlib import Path
import sys

import numpy as np
from scipy.signal import find_peaks, welch

import b4_recovery as pkg
import b4_sync_current as capture
from analyze_resp_b import replay, SOURCE_SHA
from readback_b import require, sha, write_json
from resp_exploratory import decode, estimate_period

sys.path.insert(0, str(capture.ROOT / 'node-b/acquisition/工具'))
from stable_slot_export import StableSlots, unpack_slot_fields


def offset(ms, anchor):
    return ((int(ms) - anchor + 0x80000000) & 0xffffffff) - 0x80000000


def raw_channel(rows, key):
    """谱与尖峰只作描述，既不以60/15/20为搜索先验，也不换算未经标定的欧姆。"""
    x = np.array([r[key] for r in rows], dtype=float)
    t = np.array([r['device_ms'] for r in rows], dtype=np.int64)
    sps = (len(x) - 1) * 1000 / (t[-1] - t[0])
    frequencies, power = welch(x, fs=sps, nperseg=min(len(x), 4096))
    den = power.sum()
    fraction = lambda lo, hi: float(power[(frequencies >= lo) & (frequencies <= hi)].sum() / den) if den else 0.0
    # 正负两极事件均保留；突出尖峰的重复不等于满足BIO的QRS峰宽/间隔资格。
    events = {}
    for polarity in (-1, 1):
        peaks, properties = find_peaks(polarity * x, prominence=max(1, 4 * np.std(x)),
                                       distance=max(1, int(.25 * sps)), width=0)
        intervals = np.diff(t[peaks])
        events[str(polarity)] = {'count': len(peaks),
            'median_interval_ms': float(np.median(intervals)) if len(intervals) else None,
            'median_width_ms': float(np.median(properties['widths']) * 1000 / sps) if len(peaks) else None}
    return {'min_codes': int(x.min()), 'max_codes': int(x.max()), 'p2p_codes': int(np.ptp(x)),
            'p01_p99_codes': np.percentile(x, [1, 99]).tolist(), 'mean_codes': float(x.mean()),
            'ac_rms_codes': float(np.std(x)), 'near_rail_frames': int(np.sum(np.abs(x) >= 8220835)),
            'spectral_fraction': {'49_51Hz': fraction(49, 51), '0_1_1Hz': fraction(.1, 1),
                                  '0_5_20Hz': fraction(.5, 20), '20_100Hz': fraction(20, 100)},
            'prominent_event_descriptions_not_BIO': events}


def evaluate(rows, diagnostics, anchor):
    selected = [r for r in rows if 45000 <= offset(r['device_ms'], anchor) < 135000]
    saved = [d for d in diagnostics if 45000 <= offset(d['bio']['last_sample_ms'], anchor) < 135000]
    failures = []
    if len(selected) < 22000:
        failures.append('INSUFFICIENT_RAW_FRAMES')
    if not rows or offset(rows[-1]['device_ms'], anchor) < 135000:
        failures.append('EVALUATION_NOT_COVERED')
    gaps = sum(b['source_seq'] != a['source_seq'] + 1 for a, b in zip(selected, selected[1:]))
    if gaps:
        failures.append('RAW_SEQUENCE_GAP')
    if any(r['flags_raw'] for r in selected):
        failures.append('RAW_FLAGS')
    times = [offset(d['bio']['last_sample_ms'], anchor) for d in saved]
    if len(saved) < 90 or not times or times[0] > 46500 or times[-1] < 133500:
        failures.append('DIAGNOSTIC_COVERAGE')
    if any(not 0 < b - a <= 1500 for a, b in zip(times, times[1:])):
        failures.append('DIAGNOSTIC_GAP')
    sps = ((len(selected) - 1) * 1000 / (selected[-1]['device_ms'] - selected[0]['device_ms'])
           if len(selected) > 1 else None)
    if sps is None or not 247.5 <= sps <= 252.5:
        failures.append('NOT_250SPS')
    first, last = diagnostics[0], diagnostics[-1]
    adc_delta = {k: last['bio']['adc'][k] - first['bio']['adc'][k] for k in
                 ('captured', 'delivered', 'bad_status', 'spi_errors', 'queue_overflow', 'init_errors', 'long_gap_count')}
    if any(adc_delta[k] for k in ('bad_status', 'spi_errors', 'queue_overflow', 'init_errors', 'long_gap_count')):
        failures.append('NEW_ADC_ERRORS')
    bios = [d['bio'] for d in saved]
    valid_hr = [d for d in bios if d['hr_valid'] and d['hr_reason'] == 0]
    valid_rr = [d for d in bios if d['rpm_valid'] and d['rpm_reason'] == 0]
    joint = [d for d in bios if d['hr_valid'] and not d['hr_reason'] and 58 <= d['hr'] <= 62
             and d['rpm_valid'] and not d['rpm_reason'] and 19 <= d['rpm'] <= 21]
    can_delta = {k: last['CAN'][k] - first['CAN'][k] for k in first['CAN'] if k != 'high_water'}
    summary = {'scope': capture.SCOPE, 'source_menu': capture.MENU, 'criteria': capture.CRITERIA,
        'capture_integrity': 'PASS' if not failures else 'FAIL', 'integrity_failures': failures,
        'evaluation_raw_frames': len(selected), 'saved_observations': len(saved), 'sequence_gaps': gaps,
        'device_domain_SPS_not_calibrated': sps, 'maximum_diagnostic_gap_ms': max(np.diff(times), default=0).item() if len(times)>1 else None,
        'HR_valid_observations': len(valid_hr), 'RR_valid_observations': len(valid_rr),
        'joint_nominal_pass_observations': len(joint),
        'HR_values': dict(Counter(str(d['hr']) for d in valid_hr)),
        'RR_values': dict(Counter(str(d['rpm']) for d in valid_rr)),
        'HR_reason_masks': dict(Counter(str(d['hr_reason']) for d in bios)),
        'RR_reason_masks': dict(Counter(str(d['rpm_reason']) for d in bios)),
        'ADC_counter_increments_whole_capture': adc_delta,
        'CAN_counter_increments_whole_capture': can_delta,
        'CAN1_ESR_nonzero_observations': sum(d['CAN1_ESR'] != 0 for d in diagnostics),
        'CAN1_ESR_values': sorted(set(d['CAN1_ESR'] for d in diagnostics)),
        'new_C_receive_evidence': False, 'new_end_to_end_transport_pass': False,
        'simultaneous_engineering_pass': bool(not failures and bios and len(joint) == len(bios)),
        'absolute_accuracy': 'NOT_CLAIMED_NO_INDEPENDENT_SOURCE_TRUTH',
        'impedance_calibration': 'NOT_CALIBRATED', 'Z0_ohm': None, 'delta_Zpp_ohm': None}
    # 保存观察的连续同状态区间只以首末采样时间界定，不填补快照之间的真实状态。
    for label, value_key, valid_key, reason_key in [('HR', 'hr', 'hr_valid', 'hr_reason'),
                                                   ('RR', 'rpm', 'rpm_valid', 'rpm_reason')]:
        runs = []
        for d in bios:
            state = [d[value_key], d[valid_key], d[reason_key]]
            at = offset(d['last_sample_ms'], anchor)
            if runs and runs[-1]['value_valid_reason'] == state:
                runs[-1]['last_observed_offset_ms'] = at
                runs[-1]['observations'] += 1
            else:
                runs.append({'value_valid_reason': state, 'first_observed_offset_ms': at,
                             'last_observed_offset_ms': at, 'observations': 1})
        summary[label + '_saved_state_runs'] = runs
    for label, fields in [('HR', ('hr_candidates', 'hr_accepted')),
                          ('RR', ('resp_candidates', 'resp_accepted'))]:
        summary[label + '_increments_evaluation'] = {k: bios[-1][k] - bios[0][k] for k in fields} if bios else {}
    # last_cycle是可清零的资格时间戳，不是累计计数；失效归零不能报告成负数“周期增量”。
    summary['last_cycle_timestamps_evaluation_edges'] = {
        k: [bios[0][k], bios[-1][k]] for k in ('hr_last_cycle_ms', 'resp_last_cycle_ms')} if bios else {}
    return summary, selected, saved


def analyze(folder, out):
    pkg.protected(folder, False); pkg.protected(out.parent, False)
    require(not out.exists(), 'ANALYSIS_OUTPUT_EXISTS')
    receipt = json.loads((folder / 'receipt-private.json').read_text())
    supervisor = json.loads((folder / 'supervisor-private.json').read_text())
    require(receipt['exit_code'] == supervisor['worker_exit_code'] == 0 and supervisor['reason'] is None,
            'CAPTURE_FAILED_NO_FULL_WINDOW_CLAIM')
    stable = StableSlots()
    chunks = [json.loads(x) for x in (folder / 'chunks-private.jsonl').read_text().splitlines()]
    with (folder / 'slots-private.bin').open('rb') as stream:
        for chunk in chunks:
            require(stream.tell() == chunk['offset'], 'RAW_LAYOUT')
            block = stream.read(3072)
            require(hashlib.sha256(block).hexdigest() == chunk['sha256'], 'RAW_CHUNK_SHA')
            stable.add_running_chunk(block, source_path=f"slots-private.bin@{chunk['offset']}")
        require(not stream.read(1), 'RAW_EXTRA_BYTES')
    selection = stable.select()
    # 单次撕裂版本也显式保留冲突，两个重复版本/跨启动不得继续宣告完整原码。
    require(len(selection.boots) == 1 and not selection.multi_repeat_conflicts
            and not selection.ambiguous_reset_chunks, 'RAW_CONFLICT_OR_RESET')
    rows = []
    for _, data in sorted(selection.frames.items()):
        r = unpack_slot_fields(data)
        r['padding_hex'] = r.pop('padding').hex()  # 原始填充字节保留成hex，避免bytes破坏JSON落盘。
        r['device_ms'] = r['device_tick_raw']; rows.append(r)
    diagnostics = [json.loads(x) for x in (folder / 'diagnostics-private.jsonl').read_text().splitlines()]
    names = ['entry'] + [f"diag-{c['index']:04d}" for c in chunks if c['index'] % 10 == 0] + ['final']
    require(len(names) == len(diagnostics), 'DIAGNOSTIC_COUNT')
    for name, d in zip(names, diagnostics):
        actual = decode(*[(folder / f'{name}-{kind}-private.bin').read_bytes() for kind in ('bio', 'adc', 'registers')])
        require(actual == d['bio'], 'DIAGNOSTIC_BYTE_MISMATCH')
    window = json.loads((folder / 'window-private.json').read_text())
    anchor = window['anchor_device_ms']
    report, selected, saved = evaluate(rows, diagnostics, anchor)
    out.mkdir()
    write_json(out / 'stable-raw-private.json', rows)
    report.update(total_stable_frames=len(rows), raw_blocks=len(chunks), pending_slots=len(selection.pending),
                  single_version_conflict_sequences=len(selection.conflicts), multiple_repeat_conflicts=len(selection.multi_repeat_conflicts),
                  bio_source_sha256=SOURCE_SHA, image_sha256=capture.live.IMAGE_SHA,
                  reconstruction='REPEATED_IDENTICAL_24B_SLOTS_NO_HALT_TAIL')
    report['CH1_raw'] = raw_channel(selected, 'ch1_raw')
    report['CH2_raw'] = raw_channel(selected, 'ch2_raw')
    report['CH1_independent_period'] = estimate_period(selected)
    # 完整性是传输/重建判断，削顶属于实测输入质量；两者分别报告，绝不靠删段修正90秒结论。
    clipped = [r for r in selected if abs(r['ch1_raw']) >= 8304721 or abs(r['ch2_raw']) >= 8304721]
    report['input_quality'] = {'status': 'FAIL_CLIPPED' if clipped else 'NO_RAW_CLIPPING_OBSERVED',
        'clipped_frames': len(clipped), 'diagnostic_clipped_increment_whole_capture':
        diagnostics[-1]['bio']['clipped_samples'] - diagnostics[0]['bio']['clipped_samples'],
        'clipped_first_last_offsets_ms': [offset(clipped[0]['device_ms'], anchor),
                                         offset(clipped[-1]['device_ms'], anchor)] if clipped else None}
    # 事后45–95秒分段只解释屏上15的来历，不替换已冻结的45–135秒评价窗。
    descriptive = [r for r in selected if offset(r['device_ms'], anchor) < 95000]
    report['descriptive_45_95s_not_acceptance'] = {
        'selection': 'POST_HOC_FOR_FAILURE_EXPLANATION_DOES_NOT_REPLACE_FROZEN_EVALUATION',
        'CH1_period': estimate_period(descriptive), 'CH1': raw_channel(descriptive, 'ch1_raw'),
        'CH2': raw_channel(descriptive, 'ch2_raw')}
    report['CPU_saved_states'] = {k: sorted(set(d['state'][k] for d in diagnostics))
                                  for k in ('RCC_CSR', 'VTOR', 'DHCSR', 'CFSR', 'HFSR')}
    replay_out = out / 'host-replay'; replay_out.mkdir()
    derived, events, dll_sha = replay(rows, replay_out)
    steady_replay = [d for d in derived if 45000 <= offset(d['device_ms'], anchor) < 135000]
    report['HOST_replay_not_live'] = {'DLL_sha256': dll_sha, 'HR_valid_samples': sum(d['hr_valid'] for d in steady_replay),
        'RR_valid_samples': sum(d['rpm_valid'] for d in steady_replay),
        'ecg_filtered_UI_minmax': [min(d['ecg_filtered'] for d in steady_replay), max(d['ecg_filtered'] for d in steady_replay)],
        'resp_filtered_UI_minmax': [min(d['resp_filtered'] for d in steady_replay), max(d['resp_filtered'] for d in steady_replay)],
        'initial_state': 'RESET_HOST_STATE_AT_FIRST_RETAINED_FRAME_NOT_ARM_BIT_IDENTICAL'}
    report['originals_sha256'] = {p.name: sha(p) for p in folder.iterdir() if p.is_file()}
    write_json(out / 'analysis-private.json', report)
    plot(selected, steady_replay, anchor, out / 'waveform-review.png')
    for p in out.rglob('*'):
        if p.is_file(): pkg.protected(p, False)
    return report


def plot(rows, replay_rows, anchor, target):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    t = np.array([offset(r['device_ms'], anchor) / 1000 for r in rows])
    fig, axes = plt.subplots(4, 1, figsize=(13, 10), constrained_layout=True)
    axes[0].plot(t, [r['ch1_raw'] for r in rows], lw=.5)
    axes[0].set(title='CH1 raw - common evaluation 45 to 135 s', ylabel='ADC codes')
    axes[1].plot(t, [r['resp_filtered'] for r in replay_rows], lw=.7)
    axes[1].set(title='RESP filtered - frozen C HOST replay, relative UI scale', ylabel='UI units')
    mask = (t >= 75) & (t < 80)
    axes[2].plot(t[mask], np.array([r['ch2_raw'] for r in rows])[mask], lw=.7)
    axes[2].set(title='CH2 raw - 5 s detail, no source reference calibration', ylabel='ADC codes')
    axes[3].plot(t[mask], np.array([r['ecg_filtered'] for r in replay_rows])[mask], lw=.7)
    axes[3].set(title='ECG filtered - frozen C HOST replay', ylabel='UI units', xlabel='Seconds since capture anchor')
    fig.savefig(target, dpi=160); plt.close(fig)


if __name__ == '__main__':
    pointer = json.loads((capture.ROOT / 'node-b/build/c-com15-can2-review/current-sync-pointer.json').read_text())
    result = analyze(Path(pointer['capture']), Path(pointer['base']) / 'analysis')
    print(json.dumps({k: result[k] for k in ('capture_integrity', 'evaluation_raw_frames', 'saved_observations',
                      'HR_valid_observations', 'RR_valid_observations', 'RR_values', 'simultaneous_engineering_pass')}))
    sys.exit(0 if result['simultaneous_engineering_pass'] else 3)
