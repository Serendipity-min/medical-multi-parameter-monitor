"""只读离线核对C共同90秒内实收的B源tick、HR有效位/数值与网关模型。"""
from collections import Counter
import json
from pathlib import Path
import struct
import sys

import b4_capture_decode as codec
import b4_recovery as pkg
from readback_b import require, write_json, sha
from analyze_b4_ecg_rala_can_current import offset


def review(rows, b_raw, diagnostics, transport):
    start = next(r for r in rows if r['kind'] == 9)
    selected = [r for r in rows if 45000 <= codec.signed_delta(r['tick'], start['tick']) < 135000]
    waves = [r for r in selected if r['kind'] == 1 and r['bus'] == 1 and r['id'] == 0x182]
    ticks = [struct.unpack('<iI', bytes.fromhex(r['data']))[1] for r in waves]
    raw_by_tick = {r['device_ms']: r for r in b_raw}
    matches = [raw_by_tick[t] for t in ticks if t in raw_by_tick]
    failures = list(transport['failures'])
    if len(ticks) < 22000 or len(matches) != len(ticks): failures.append('C_WAVE_B_RAW_TICK_MISSING')
    if any(b['source_seq'] != a['source_seq'] + 1 for a, b in zip(matches, matches[1:])):
        failures.append('C_WAVE_B_RAW_SEQUENCE_GAP')
    if any(r['flags_raw'] or abs(r['ch2_raw']) >= 8220835 for r in matches):
        failures.append('B_RAW_FLAGS_OR_CH2_NEAR_RAIL')
    saved = [d['bio'] for d in diagnostics if ticks and
             0 <= codec.signed_delta(d['bio']['last_sample_ms'], ticks[0]) <= codec.signed_delta(ticks[-1], ticks[0])]
    if len(saved) < 90 or any(not d['hr_valid'] or d['hr_reason'] or not 58 <= d['hr'] <= 62 for d in saved):
        failures.append('B_COMMON_HR_NOT_ALL_VALID60')
    if not saved or codec.signed_delta(saved[0]['last_sample_ms'], ticks[0]) > 1500 or codec.signed_delta(ticks[-1], saved[-1]['last_sample_ms']) > 1500:
        failures.append('B_COMMON_DIAGNOSTIC_COVERAGE')
    if any(not 0 < codec.signed_delta(b['last_sample_ms'], a['last_sample_ms']) <= 1500 for a, b in zip(saved, saved[1:])):
        failures.append('B_COMMON_DIAGNOSTIC_GAP')
    vitals = [struct.unpack('<4H', bytes.fromhex(r['data'])) for r in selected
              if r['kind'] == 1 and r['bus'] == 1 and r['id'] == 0x382]
    if len(vitals) < 85 or any(not 5800 <= v[0] <= 6200 for v in vitals):
        failures.append('C_VITALS_HR_NOT_VALID60')
    quality = [struct.unpack('<II', bytes.fromhex(r['data']))[0] for r in selected
               if r['kind'] == 1 and r['bus'] == 1 and r['id'] == 0x682]
    if len(quality) < 85 or any(q & 5 != 5 for q in quality): failures.append('C_ECG_HR_VALID_BITS')
    model_counts = {}
    for stream, minimum in ((4, 200), (5, 85)):
        models = [r for r in selected if r['kind'] == 8 and r['id'] == stream]
        model_counts[str(stream)] = {'rows': len(models), 'valid': sum(bool(r['flags'] & 256) for r in models)}
        if len(models) < minimum or any(not r['flags'] & 256 or r['flags'] & 0x600 for r in models):
            failures.append('C_MODEL_VALIDITY_' + str(stream))
        if stream == 5 and any(not 5800 <= struct.unpack('<iI', bytes.fromhex(r['data']))[0] <= 6200 for r in models):
            failures.append('C_MODEL_HR_NOT_60')
    # 共同窗由C的实际START及实收B源tick界定；不将两个设备的开机时钟强行相减。
    return {'status': 'ECG60_B_TO_C_VALID_TRANSPORT_ENGINEERING_PASS' if not failures else 'ECG60_B_TO_C_NOT_PASS',
            'failures': sorted(set(failures)), 'analysis_exit_code': 0 if not failures else 3,
            'C_evaluation_relative_ms': [45000, 135000], 'C_START_tick': start['tick'],
            'C_received_ECG_wave_points': len(ticks), 'matched_B_raw_points': len(matches),
            'B_sample_tick_first_last': [ticks[0], ticks[-1]] if ticks else None,
            'B_saved_common_observations': len(saved), 'B_HR_values': dict(Counter(str(d['hr']) for d in saved)),
            'B_HR_valid_observations': sum(bool(d['hr_valid']) and not d['hr_reason'] for d in saved),
            'C_vitals_rows': len(vitals), 'C_HR_centi_bpm_values': dict(Counter(str(v[0]) for v in vitals)),
            'C_RR_centi_rpm_values_characterization_only': dict(Counter(str(v[1]) for v in vitals)),
            'C_quality_flags': dict(Counter(str(q) for q in quality)), 'C_model_validity': model_counts,
            'HR_RR_simultaneous_engineering_pass': False, 'RR_valid_transport_pass': False,
            'absolute_accuracy': 'NOT_CALIBRATED_NOMINAL60_REFERENCE_ONLY',
            'mapping': 'C_START_WINDOW_WITH_ACTUALLY_RECEIVED_B_SAMPLE_TICKS_NO_C_B_UPTIME_EQUALITY_ASSUMPTION'}


def main():
    root = Path(__file__).resolve().parents[2]
    pointer = json.loads((root / 'node-b/build/c-com15-can2-review/current-ecg-can-pointer.json').read_text())
    base = pkg.protected(Path(pointer['base']), False); c = Path(pointer['C']); b = Path(pointer['B'])
    # 完整结束但判据不通过的负例也必须分析，沿用全部原始failures，不能改写成PASS。
    receipt = json.loads((c/'receipt-private.json').read_text())
    require(receipt['exit_code'] in (0, 3), 'C_WINDOW_INCOMPLETE')
    require(json.loads((b/'receipt-private.json').read_text())['exit_code'] == 0, 'B_CAPTURE_INCOMPLETE')
    rows = [json.loads(s) for s in (c/'packets-private.jsonl').read_text().splitlines()]
    require(sum(r['kind'] == 9 for r in rows) == 1 and sum(r['kind'] == 6 for r in rows) == 1,
            'C_START_STOP_EVIDENCE_INCOMPLETE')
    b_raw = json.loads((base/'analysis/stable-raw-private.json').read_text())
    diagnostics = [json.loads(s) for s in (b/'diagnostics-private.jsonl').read_text().splitlines()]
    transport = json.loads((c/'receipt-private.json').read_text())
    result = review(rows, b_raw, diagnostics, transport)
    result['originals_sha256'] = {name: sha(path) for name, path in (
        ('C-serial', c/'serial-raw-private.bin'), ('C-packets', c/'packets-private.jsonl'),
        ('C-receipt', c/'receipt-private.json'), ('B-slots', b/'slots-private.bin'),
        ('B-diagnostics', b/'diagnostics-private.jsonl'), ('B-analysis', base/'analysis/analysis-private.json'))}
    write_json(base/'common-review-private.json', result); pkg.protected(base/'common-review-private.json', False)
    print(json.dumps({k: result[k] for k in ('status', 'failures', 'C_received_ECG_wave_points', 'matched_B_raw_points')}))
    return result['analysis_exit_code']


if __name__ == '__main__':
    sys.exit(main())
