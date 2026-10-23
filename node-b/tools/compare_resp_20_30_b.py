"""脱机比较20→30的原码周期跟踪；不连接硬件，不将菜单值用作独立标定真值。"""
import argparse
import json
from pathlib import Path
import statistics
import sys

from readback_b import PRIVATE, require, sha, write_json

BASELINE_SHA = '954a06da964f538e99f851ceff878974955882783f6ba84ea97537e6e4171406'
BASELINE_SOURCE_SHA = '4c01a79ace48ce1aa5e90932238994f2f268ff184a5bfe0402122b9036704f8f'


def compare(baseline, current, source20, source30):
    # 只允许呼吸率改变；同单位的波形周期必须独立固定，避免两个参数同时变化。
    for key in ('leads', 'mode', 'manual_sha256', 'dynamic_pair', 'impedance_calibration'):
        require(source20[key] == source30[key], 'TRACKING_CHANGED_CONTROL_'+key)
    for key in ('mode_literal', 'amplitude_literal', 'waveform_period_literal', 'apnea_literal', 'ecg_rate_literal'):
        require(source20['menu'][key] == source30['menu'][key], 'TRACKING_CHANGED_MENU_'+key)
    require(source20['menu']['waveform_period_literal'] == '20bpm', 'TRACKING_WAVEFORM_PERIOD_NOT20')
    require(source20['nominal_rpm'] == 20 and source30['nominal_rpm'] == 30
            and source20['menu']['respiration_rate_literal'] == '20bpm'
            and source30['menu']['respiration_rate_literal'] == '30bpm', 'TRACKING_MENU_RATES')
    for source in (source20, source30):
        require(all(source.get(k) is None and k in source for k in ('reference_rpm', 'Z0_ohm', 'delta_Zpp_ohm')),
                'TRACKING_NO_CALIBRATED_TRUTH')
    require(baseline['bio_source_sha256'] == current['bio_source_sha256'], 'TRACKING_ALGORITHM_CHANGED')
    require(baseline['evaluation_device_offsets_ms'] == current['evaluation_device_offsets_ms'] == [10000, 40000],
            'TRACKING_EVALUATION_CHANGED')
    require(baseline['source_record_sha256'] == BASELINE_SOURCE_SHA, 'TRACKING_BASELINE_SOURCE_BINDING')
    estimates = [baseline['independent_raw_estimate'], current['independent_raw_estimate']]
    integrity = not baseline['failures'] and not current['failures']
    coherent = all(e['status'] == 'PERIOD_COHERENT_EXPLORATORY_ONLY' for e in estimates)
    periods = [None, None]; ratio = None; nominal_match = False; follows = False
    if coherent and integrity:
        periods = [float(statistics.median(e['periods_ms'])) for e in estimates]
        require(all(t > 0 for t in periods), 'TRACKING_NONPOSITIVE_PERIOD')
        ratio = periods[1]/periods[0]
        # 工程预期为2/3，允许相对10%偏差；这是跟踪判据，不是Ω或医学准确度阈值。
        nominal_match = all(abs(e['time_domain_rpm']-rate) <= 1 for e, rate in zip(estimates, (20, 30)))
        follows = abs(ratio/(2/3)-1) <= .10 and nominal_match
    seen = bool(integrity and coherent and follows)
    return {'status': 'E2_RATE_TRACKING_SEEN' if seen else
                ('TRACKING_INPUT_INTEGRITY_FAIL' if not integrity else 'RATE_TRACKING_NOT_ESTABLISHED'),
            'comparison_exit_code': 0 if seen else (2 if not integrity else 3),
            'CH1_median_period_ms_20_then30': periods, 'period_ratio_30_over20': ratio,
            'expected_period_ratio': 2/3, 'relative_ratio_tolerance': .10,
            'raw_nominal_match_within_1rpm': nominal_match,
            'fixed_waveform_period_literal': '20bpm', 'only_respiration_rate_menu_changed': True,
            'baseline_window_validity_analysis_exit': baseline['analysis_exit_code'],
            'current_window_validity_analysis_exit': current['analysis_exit_code'],
            'both_windows_full_RR_validity_pass': baseline['analysis_exit_code'] == current['analysis_exit_code'] == 0,
            'RR_startup_invalid_observations_retained': True,
            'scope': 'TWO_NOMINAL_SETTINGS_NONHUMAN_ENGINEERING_PERIOD_TRACKING_ONLY',
            'reference_rpm': None, 'Z0_ohm': None, 'delta_Zpp_ohm': None,
            'source_accuracy': 'NOT_CALIBRATED', 'E3': 'NOT_RUN', 'CPU_issue': 'DEFERRED_BY_OWNER'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('baseline-summary', 'current-summary', 'baseline-source', 'current-source', 'out'):
        parser.add_argument('--'+name, required=True, type=Path)
    args = parser.parse_args()
    require(args.out.resolve().is_relative_to(PRIVATE.resolve()) and not args.out.exists(), 'TRACKING_PRIVATE_EXCLUSIVE_OUTPUT')
    require(sha(args.baseline_summary) == BASELINE_SHA
            and sha(args.baseline_source) == BASELINE_SOURCE_SHA, 'TRACKING_BASELINE_SHA')
    load = lambda p: json.loads(p.read_text('utf-8'))
    baseline = load(args.baseline_summary); current = load(args.current_summary)
    require(current['source_record_sha256'] == sha(args.current_source), 'TRACKING_CURRENT_SOURCE_SHA')
    result = compare(baseline, current, load(args.baseline_source), load(args.current_source))
    result.update(baseline_summary_sha256=sha(args.baseline_summary), current_summary_sha256=sha(args.current_summary),
                  baseline_source_sha256=sha(args.baseline_source), current_source_sha256=sha(args.current_source))
    write_json(args.out, result)
    print(json.dumps(result)); return result['comparison_exit_code']


if __name__ == '__main__':
    sys.exit(main())
