"""RESP-003脱机源门禁、完整120B诊断和独立周期估计；不包含硬件入口。"""
import json
import math
from pathlib import Path
import re
import struct

import numpy as np

from readback_b import require, sha

ROOT = Path(__file__).resolve().parents[2]
SCHEMA = 'BIO_V2_RESP_EXPLORATORY_CAPTURE_1'
SOURCE_SCHEMA = 'RESP_EXPLORATORY_SOURCE_1'
STAGES = {'E1': (10,), 'E2': (45, 60), 'E3': (137,)}
LEADS = {'R_red': 'RA', 'L_yellow': 'LA', 'F_green': 'RL'}
REASONS = {1: 'WARMUP', 2: 'NO_CYCLES', 4: 'UNSTABLE', 8: 'EXPIRED',
           16: 'DISCONTINUITY', 32: 'CLIPPED', 64: 'MAINS', 128: 'BROADBAND_NOISE'}
FIELDS = ('tag abi_version samples last_sequence last_sample_ms segment discontinuities clipped_samples '
          'ecg_raw resp_raw ecg_filtered resp_filtered hr rpm hr_valid rpm_valid hr_reason rpm_reason '
          'hr_candidates hr_accepted resp_candidates resp_accepted hr_last_cycle_ms resp_last_cycle_ms '
          'hr_fresh_intervals resp_fresh_intervals ecg_rms_codes resp_rms_codes '
          'ecg_mains_fraction resp_mains_fraction').split()
STATS = ('irq_count captured delivered bad_status spi_errors queue_overflow queue_peak '
         'init_errors long_gap_count min_irq_gap_cycles max_irq_gap_cycles max_read_cycles').split()


def reason_names(value):
    """保留未知位，不能把未来原因码静默解码为有效。"""
    result = [name for bit, name in REASONS.items() if value & bit]
    if value & ~255:
        result.append('UNKNOWN_BITS')
    return result or ['VALID']


def decode(diag, stats, registers):
    require((len(diag), len(stats), len(registers)) == (120, 48, 12), 'RESP_DIAG_LENGTH')
    # 前8个无符号、4个有符号原码/滤后值，后14个无符号和4个float，严格匹配C布局。
    result = dict(zip(FIELDS, struct.unpack('<8I4i14I4f', diag)))
    require((result['tag'], result['abi_version']) == (0x324f4942, 2), 'RESP_DIAG_ABI')
    require(all(math.isfinite(result[k]) for k in FIELDS[-4:]), 'RESP_DIAG_NONFINITE')
    result.update(adc=dict(zip(STATS, struct.unpack('<12I', stats))),
                  registers_hex=registers.hex(), hr_reason_names=reason_names(result['hr_reason']),
                  rpm_reason_names=reason_names(result['rpm_reason']))
    return result


def validate_source(source, stage, ready=False):
    require(source.get('schema') == SOURCE_SCHEMA and source.get('source_type') == 'RESP_EXPLORATORY', 'RESP_SOURCE_TYPE')
    require(source.get('data_source') == 'ENGINEERING_NONHUMAN', 'RESP_SOURCE_CLASS')
    require(stage in STAGES and source.get('stage') == stage, 'RESP_SOURCE_STAGE')
    require(source.get('acceptance_class') == 'EXPLORATORY_NOMINAL_RATE_ONLY', 'RESP_NOT_ABSOLUTE_CALIBRATION')
    require(source.get('mode') == 'INDEPENDENT_RESPIRATION', 'RESP_SOURCE_MODE')
    require(source.get('Z0_ohm') is None and source.get('delta_Zpp_ohm') is None
            and 'Z0_ohm' in source and 'delta_Zpp_ohm' in source, 'RESP_UNKNOWN_Z_MUST_BE_NULL')
    require(source.get('dynamic_pair') == 'UNVERIFIED', 'RESP_PAIR_NOT_VERIFIED')
    require(source.get('impedance_calibration') == 'NOT_CALIBRATED', 'RESP_NOT_ABSOLUTE_CALIBRATION')
    require(source.get('leads') == LEADS, 'RESP_LEADS')
    require(source.get('battery_only') is True and source.get('usb_disconnected') is True, 'RESP_SOURCE_POWER')
    require(source.get('CAN_A_C_human_disconnected') is True, 'RESP_SCOPE_CONNECTIONS')
    rate = source.get('nominal_rpm')
    require(type(rate) in (int, float) and math.isfinite(rate) and 6 <= rate <= 40, 'RESP_RATE_RANGE')
    menu = source.get('menu', {})
    require(all(isinstance(menu.get(k), str) and menu[k].strip()
                for k in ('mode_literal', 'rate_literal', 'amplitude_literal', 'apnea_literal')), 'RESP_EMPTY_MENU')
    require(source.get('menu_rate_rpm') == rate, 'RESP_MENU_RATE_MISMATCH')
    require(source.get('amplitude_literal') == menu['amplitude_literal'], 'RESP_AMPLITUDE_LITERAL_MISMATCH')
    if stage == 'E1':
        require(rate == 15 and source['amplitude_literal'] == '1.5R', 'RESP_E1_FROZEN_SETTING')
    # 模板可保留未就绪；真正进入硬件前必须有独立安全记录和本次菜单确认。
    if ready:
        require(source.get('operator_ready') is True and source.get('menu_confirmed') is True, 'RESP_SOURCE_NOT_READY')
        require(isinstance(source.get('owner_confirmation'), str) and source['owner_confirmation'].strip(), 'RESP_OWNER_CONFIRMATION')
        require(source.get('safety_confirmed') is True, 'RESP_SAFETY_NOT_CONFIRMED')
        # 本机呼吸页面实际沿用bpm字样；只在已确认的独立呼吸模式解释为呼吸次数/分。
        # 保留原菜单文字，不能为迎合旧解析器将15bpm伪写成15rbpm或改成ECG来源。
        require(menu['mode_literal'].strip() == '呼吸波形'
                and re.fullmatch(r'\s*15\s*(rbpm|rpm|bpm|次/分)\s*', menu['rate_literal'], re.I), 'RESP_ACTUAL_MENU_NOT_CONFIRMED')
        record = Path(source.get('safety_record', ''))
        require(record.is_file() and sha(record) == source.get('safety_record_sha256'), 'RESP_SAFETY_RECORD_BINDING')
        evidence = json.loads(record.read_text('utf-8'))
        require(evidence.get('status') == 'CONFIRMED_FOR_BOUNDED_' + stage and evidence.get('stage') == stage, 'RESP_SAFETY_RECORD_STATUS')
        require(all(evidence.get(k) is True for k in ('same_ECG_setup', 'battery_no_USB', 'no_grounded_instrument',
                    'no_shorts_or_abnormalities', 'CAN_A_C_human_disconnected')), 'RESP_SAFETY_FACTS')
        require(bool(evidence.get('voltage_current_safety_basis')) and
                bool(evidence.get('resp_mode_compatibility_limit_acknowledged')), 'RESP_ELECTRICAL_BASIS_MISSING')
    return 'RESP_SOURCE_READY' if ready else 'RESP_SOURCE_OFFLINE_ONLY'


def raw_integrity(rows, export=None):
    failures = []
    if len(rows) < 2:
        return ['INSUFFICIENT_FRAMES']
    if any(b['source_seq'] != a['source_seq'] + 1 for a, b in zip(rows, rows[1:])):
        failures.append('SEQUENCE_GAP')
    if any(not 1 <= ((b['device_ms'] - a['device_ms']) & 0xffffffff) <= 8 for a, b in zip(rows, rows[1:])):
        failures.append('DEVICE_TIME_GAP')
    if any(r['flags_raw'] for r in rows):
        failures.append('SOURCE_FLAGS')
    if any(abs(r['ch1_raw']) >= 8220835 for r in rows):
        failures.append('CH1_NEAR_RAIL')
    if export and any(export.get(k, 0) for k in ('source_missing_within_span', 'multi_repeat_conflicts', 'paused_conflicts')):
        failures.append('SLOT_GAP_OR_CONFLICT')
    return failures


def estimate_period(rows, export=None):
    """按真实设备时间分箱，不补缺失点；三个估计器均不接收菜单参考作为先验。"""
    failures = raw_integrity(rows, export)
    result = {'origin': 'OFFLINE_RAW_CH1_ESTIMATE_NOT_BIO_NOT_REFERENCE', 'failures': failures,
              'impedance_calibration': 'NOT_CALIBRATED', 'Z0_ohm': None, 'delta_Zpp_ohm': None,
              'time_domain_rpm': None, 'spectral_rpm': None, 'autocorrelation_rpm': None,
              'periods_ms': [], 'peak_device_offsets_ms': []}
    if failures:
        return dict(result, status='NOT_EVALUATED_INPUT_INTEGRITY')
    times = np.array([((r['device_ms'] - rows[0]['device_ms']) & 0xffffffff) for r in rows], dtype=float)
    values = np.array([r['ch1_raw'] for r in rows], dtype=float)
    result.update(raw_peak_to_peak_codes=int(np.ptp(values)), duration_ms=float(times[-1]))
    if times[-1] < 6000:
        return dict(result, status='NOT_EVALUATED_TOO_SHORT')
    bins = (times // 100).astype(int)
    counts = np.bincount(bins)
    if np.any(counts == 0):
        return dict(result, status='NOT_EVALUATED_EMPTY_TIME_BIN')
    t = np.bincount(bins, weights=times) / counts
    y = np.bincount(bins, weights=values) / counts
    y -= np.polyval(np.polyfit(t / 1000, y, 1), t / 1000)
    # 仅在连续原码上降带宽，边缘不填充；时间标记取对应真实分箱中心。
    y = np.convolve(y, np.ones(3) / 3, mode='valid');t = t[1:-1]
    amplitude = float(np.percentile(y, 95) - np.percentile(y, 5))
    if amplitude < 1.0:
        return dict(result, status='NO_RESOLVABLE_CH1_VARIATION')
    peaks = []
    for i in range(1, len(y) - 1):
        if y[i] > y[i - 1] and y[i] >= y[i + 1] and y[i] > amplitude * .15:
            if peaks and t[i] - t[peaks[-1]] < 1500:
                if y[i] > y[peaks[-1]]:
                    peaks[-1] = i
            else:
                peaks.append(i)
    periods = np.diff(t[peaks])
    result['peak_device_offsets_ms'] = t[peaks].tolist()
    result['periods_ms'] = periods.tolist()
    if len(periods) >= 2 and np.all((periods >= 1500) & (periods <= 10000)):
        median = float(np.median(periods))
        result['time_domain_rpm'] = 60000 / median
        result['period_relative_max_deviation'] = float(np.max(np.abs(periods - median)) / median)
    rates = np.linspace(6, 40, 681)
    window = np.hanning(len(y));weighted = y * window
    power = np.abs(np.exp(-2j * np.pi * rates[:, None] / 60 * (t[None, :] / 1000)) @ weighted) ** 2
    result['spectral_rpm'] = float(rates[int(np.argmax(power))])
    result['finite_window_resolution_rpm'] = 60000 / (t[-1] - t[0])
    correlations = []
    dt = float(np.median(np.diff(t)))
    for lag in range(max(1, math.ceil(1500 / dt)), min(len(y) - 10, math.floor(10000 / dt)) + 1):
        left, right = y[:-lag], y[lag:]
        den = float(np.linalg.norm(left) * np.linalg.norm(right))
        correlations.append((lag, float(left @ right / den) if den else 0.0))
    for i in range(1, len(correlations) - 1):
        lag, value = correlations[i]
        if value > .5 and value > correlations[i - 1][1] and value >= correlations[i + 1][1]:
            result['autocorrelation_rpm'] = 60000 / float(np.median(t[lag:] - t[:-lag]))
            result['autocorrelation_coefficient'] = value
            break
    estimates = [result[k] for k in ('time_domain_rpm', 'spectral_rpm', 'autocorrelation_rpm')]
    coherent = all(x is not None for x in estimates)
    if coherent:
        center = float(np.median(estimates))
        coherent = max(estimates) - min(estimates) <= max(2.0, center * .1)
        coherent = coherent and result['period_relative_max_deviation'] <= .2
    result['status'] = 'PERIOD_COHERENT_EXPLORATORY_ONLY' if coherent else 'CH1_VARIATION_PERIOD_UNRESOLVED'
    result['short_window_limit'] = 'Few cycles and finite-window resolution; no calibrated frequency or L2 rate tracking proof'
    return result
