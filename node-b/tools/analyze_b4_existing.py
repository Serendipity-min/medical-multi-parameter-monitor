"""既有 E3 的 CH2/HR 离线审查；只输出统计，不把菜单设定冒充校准真值。"""
from collections import Counter
import csv
import hashlib
import json
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
DATA = Path('E:/medical-monitor-node-b-field-private/field-r3/resp-003/e3-matrix-r1')
REASONS = {1: 'WARMUP', 2: 'NO_CYCLES', 4: 'UNSTABLE', 8: 'EXPIRED', 16: 'DISCONTINUITY',
           32: 'CLIPPED', 64: 'MAINS', 128: 'BROADBAND_NOISE'}


def digest(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def offset(ms, anchor):
    # 与历史采集工具相同的短窗口回绕算法，不将预热前置帧混进稳态统计。
    return ((int(ms) - anchor + 0x80000000) & 0xffffffff) - 0x80000000


def main():
    results = []
    for rate in (12, 18, 24):
        for run in (1, 2):
            capture = DATA / f'capture-{rate}-r{run}'
            analysis = DATA / f'analysis-{rate}-r{run}'
            live = [json.loads(s) for s in (capture / 'diagnostics-private.jsonl').read_text().splitlines()]
            receipt = json.loads((capture / 'receipt-private.json').read_text(encoding='utf-8'))
            assert digest(capture / 'stable-raw-private.csv') == receipt['stable_raw_sha256']
            assert digest(capture / 'diagnostics-private.jsonl') == receipt['diagnostics_sha256']
            anchor = live[0]['last_sample_ms']
            kept = [d for d in live if 45000 <= offset(d['last_sample_ms'], anchor) < 135000]
            with (capture / 'stable-raw-private.csv').open(newline='') as f:
                raw = [r for r in csv.DictReader(f) if 45000 <= offset(r['device_ms'], anchor) < 135000]
            with (analysis / 'replay-not-live-private.csv').open(newline='') as f:
                replay = [r for r in csv.DictReader(f) if 45000 <= offset(r['device_ms'], anchor) < 135000]
            x = np.array([int(r['ch2_raw']) for r in raw], dtype=float)
            y = x - np.mean(x)
            observed_sps = (len(raw) - 1) * 1000 / offset(raw[-1]['device_ms'], int(raw[0]['device_ms']))
            # 频带能量仅为离线描述性指标；矩形窗 PSD 不冒充固件的工频比例算法。
            spectrum = np.abs(np.fft.rfft(y)) ** 2
            hz = np.fft.rfftfreq(len(y), 1 / observed_sps)
            power = float(spectrum[1:].sum())
            fractions = {name: float(spectrum[(hz >= low) & (hz <= high)].sum() / power)
                         for name, low, high in [('49_51Hz', 49, 51), ('0_5_20Hz', .5, 20), ('20_100Hz', 20, 100)]}
            mask = Counter(str(d['hr_reason']) for d in kept)
            invalid = {name: sum(bool(d['hr_reason'] & bit) for d in kept) for bit, name in REASONS.items()}
            filtered = np.array([int(r['ecg_filtered']) for r in replay])
            results.append({'nominal_rr': rate, 'run': run, 'raw_frames': len(raw), 'live_observations': len(kept),
                            'live_hr_valid': sum(d['hr_valid'] != 0 for d in kept),
                            'live_valid_hr_values': dict(Counter(str(d['hr']) for d in kept if d['hr_valid'])),
                            'live_rr_valid': sum(d['rpm_valid'] != 0 for d in kept),
                            'live_reason_masks': dict(mask), 'live_reason_bit_counts': invalid,
                            'live_candidate_increment': kept[-1]['hr_candidates'] - kept[0]['hr_candidates'],
                            'live_accepted_increment': kept[-1]['hr_accepted'] - kept[0]['hr_accepted'],
                            'ch2_dc_codes': float(x.mean()), 'ch2_p2p_codes': float(np.ptp(x)),
                            'ch2_ac_rms_codes': float(np.sqrt(np.mean(y * y))),
                            'near_rail_frames': int(np.sum(np.abs(x) >= 8220835)), 'spectral_energy_fraction': fractions,
                            'sequence_gaps': sum(int(b['source_seq']) != int(a['source_seq']) + 1 for a, b in zip(raw, raw[1:])),
                            'observed_device_domain_sps_not_calibrated': observed_sps,
                            'sample_gap_not_4ms': sum(offset(b['device_ms'], int(a['device_ms'])) != 4 for a, b in zip(raw, raw[1:])),
                            'adc_error_max': {key: max(d['adc'][key] for d in live) for key in
                                ['init_errors', 'spi_errors', 'bad_status', 'queue_overflow', 'long_gap_count']},
                            'host_replay_filtered_p2p': int(np.ptp(filtered)),
                            'host_replay_hr_valid_frames': sum(int(r['hr_valid']) != 0 for r in replay),
                            'live_mains_fraction_range': [min(d['ecg_mains_fraction'] for d in kept), max(d['ecg_mains_fraction'] for d in kept)],
                            'invalid_observation_offsets_ms': [offset(d['last_sample_ms'], anchor) for d in kept if not d['hr_valid']],
                            'original_sha256': {p.name: digest(p) for p in [capture / 'stable-raw-private.csv',
                                capture / 'diagnostics-private.jsonl', analysis / 'replay-not-live-private.csv']}})
    out = {'scope': 'EXISTING_E3_OFFLINE_ONLY', 'hardware_access': False, 'windows': results,
           'simultaneous_gate': 'NOT_PASSED_EXISTING_RESP_WINDOWS_HAVE_INVALID_HR',
           'source_capability': 'UNPROVEN_NO_CALIBRATED_CH2_OUTPUT_EVIDENCE',
           'baseline_step': {'observation': 'Owner photo: RESP offset changes at JTAG unplug; periodicity/refresh continues',
                'continuous_raw_at_detach': False, 'cause': 'UNDETERMINED',
                'hypotheses_not_findings': ['ground_reference_or_coupling_change', 'connector_mechanical_transient'],
                'not_proven': ['MCU_reset', 'ROM_entry', 'absolute_impedance_change']},
           'limitations': ['HOST replay starts at first retained sample; not ARM bit-identical',
                'Saved live observations are non-atomic and not continuous per-frame validity',
                'Nominal source menu is not independently calibrated output truth; no accuracy calculated',
                'No threshold edits, no automatic retest, no absolute ohm inference']}
    (ROOT / 'node-b/evidence/B4-001/existing-ch2-analysis.json').write_text(json.dumps(out, indent=2) + '\n')
    for r in results:
        print(r['nominal_rr'], r['run'], 'HR', r['live_hr_valid'], '/', r['live_observations'],
              'reason', r['live_reason_masks'], '50Hz', round(r['spectral_energy_fraction']['49_51Hz'], 3))


if __name__ == '__main__':
    main()
