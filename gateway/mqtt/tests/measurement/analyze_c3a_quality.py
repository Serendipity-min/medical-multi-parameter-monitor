"""既有C3A快照的逐指标离线评级；保留原flags/严格拒绝，不授予全窗PASS。"""

import argparse
import json
from pathlib import Path

from r2_snapshot_bytes import ROOT, EXPECTED_BIN, InvalidSnapshot, _field, _struct, load_layout, sha


ORIGINAL = ROOT / 'doc/P/04_第四阶段_P5_coreMQTT裸机迁移/验收/evidence/hardware-c3a-pilot-20261009.json'
ORIGINAL_SHA = '1077ad20896c6ce1d5bd2206ca321ee5bb1e1c41e76c1a9c1393ac567e7136c4'
LAYOUT = ROOT / 'doc/P/04_第四阶段_P5_coreMQTT裸机迁移/验收/evidence/c25-r2/probe-layout-v2.json'
SCOPES = ('OPEN', 'PUBLISH_Q0', 'PUBLISH_Q1', 'YIELD', 'LIBRARY_PUBLISH', 'PROCESS',
          'AT_SEND', 'AT_RECV', 'CAN_SERVICE', 'CAN_CALLBACK')
STREAMS = ('PPG', 'SPO2', 'PR', 'NIBP', 'ECG', 'HR', 'RESP', 'RR', 'TEMP')


def extract(data, layout, variant):
    """仅做字节/身份解码，测量质量由各指标分别决定，不清零或改写任何原字段。"""
    if variant not in EXPECTED_BIN or len(data) != 1264:
        raise InvalidSnapshot('SNAPSHOT_VARIANT_OR_SIZE')
    entry = layout['variants'][variant]
    types = entry['types']
    get = lambda field: _field(data, types, 'ProbeState', field)
    if (get('magic') != 0xC25D1A60 or get('profile') != 0xC2500001 or
            get('variant') != int(variant[-1]) or get('initialized') != 1 or
            get('marker_address') != entry['marker_address'] or get('core_hz') != 16_000_000):
        raise InvalidSnapshot('PROBE_IDENTITY_OR_CLOCK_CONFIG')
    raw = {name: get(name) for name in (
        'magic', 'profile', 'variant', 'initialized', 'marker_address', 'core_hz', 'clock_seq',
        'irq_flags', 'foreground_flags', 'tick_head', 'tick_tail', 'tick_dropped', 'tick_drop_base',
        'tick_armed', 'dropped_observations', 'unmatched_ticks', 'depth', 'window_generation',
        'recovery_generation', 'boundary_skipped_ticks', 'event_count', 'network_valid_mask',
        'cache_snapshot_mask', 'cache_drained_observed', 'heap_peak_bytes', 'heap_enomem_count',
        'heap_error_base', 'live_observed', 'replay_observed')}
    raw['aggregate'] = []
    for i in range(10):
        at = types['ProbeState']['fields']['aggregate'] + i * types['ProbeAggregate']['size']
        row = _struct(data, types, 'ProbeAggregate',
                      ('success', 'failure', 'invalid', 'min_cycles', 'max_cycles'), at)
        for name in ('inclusive_cycles', 'direct_child_cycles'):
            row[name] = _field(data, types, 'ProbeAggregate', name, at, 8)
        raw['aggregate'].append(row)
    raw['active_spans'] = []
    for i in range(min(raw['depth'], 6)):
        at = types['ProbeState']['fields']['spans'] + i * types['ProbeSpan']['size']
        raw['active_spans'].append(_struct(data, types, 'ProbeSpan',
                                         ('scope', 'serial', 'generation', 'cycle', 'millisecond'), at))
    raw['events'] = []
    for i in range(min(raw['event_count'], 16)):
        at = types['ProbeState']['fields']['events'] + i * types['ProbeEvent']['size']
        raw['events'].append(_struct(data, types, 'ProbeEvent', ('scope', 'start', 'end', 'bound_ms'), at))
    base = types['ProbeState']['fields']['network_us']
    raw['network_us'] = [int.from_bytes(data[base + i * 8:base + (i + 1) * 8], 'little') for i in range(9)]
    for name, typ, fields in (
            ('first_business_id', 'ProbeFrameId', ('node', 'stream', 'seq', 'epoch', 'boot')),
            ('cache_before', 'ProbeCache', ('cache', 'lost', 'replay', 'drop')),
            ('cache_after', 'ProbeCache', ('cache', 'lost', 'replay', 'drop'))):
        raw[name] = _struct(data, types, typ, fields, types['ProbeState']['fields'][name])
    for name in ('first_live_us', 'first_replay_us'):
        raw[name] = _field(data, types, 'ProbeState', name, width=8)
    return raw


def halt_interval(meta):
    """旧记录的请求时刻只能从已记录事务时长推导；确认不是实际停止瞬间。"""
    e = meta.get('host_qpc_events_us', {})
    required = ('D_SENT', 'HALT', 'READ1_DONE', 'READ2_DONE', 'SNAPSHOT_PERSISTED', 'RESUME')
    elapsed = meta.get('pause_control_transaction_upper_bound_us')
    if any(type(e.get(k)) is not int or e[k] < 0 for k in required) or type(elapsed) is not int or elapsed < 0:
        return {'grade': 'INVALID', 'reason': 'HALT_TIMING_MISSING', 'exact_cpu_stop_us': None}
    request = e['RESUME'] - elapsed
    provided = meta.get('HALT_request_us_derived_from_recorded_elapsed', request)
    ordered = [e['D_SENT'], request, e['HALT'], e['READ1_DONE'], e['READ2_DONE'], e['SNAPSHOT_PERSISTED'], e['RESUME']]
    if provided != request or request < 0 or ordered != sorted(ordered) or e['D_SENT'] >= request:
        return {'grade': 'INVALID', 'reason': 'HALT_TIMING_CONFLICT', 'exact_cpu_stop_us': None}
    return {'grade': 'BOUNDED_INTERVAL', 'request_us': request, 'request_source': 'DERIVED_FROM_RECORDED_TRANSACTION_ELAPSED',
            'confirm_us': e['HALT'], 'possible_cpu_stop_us': [request, e['HALT']],
            'confirm_delay_us': e['HALT'] - request, 'exact_cpu_stop_us': None,
            'exact_cpu_pause_us': None, 'pause_control_transaction_upper_bound_us': elapsed,
            'confirm_is_actual_stop': False}


def tick_quality(raw):
    total, base = raw['tick_dropped'], raw['tick_drop_base']
    # 两计数是uint32；无独立回绕证明时不做模减，防止回退被误记成0丢失。
    delta = total - base if total >= base else None
    pending = (raw['tick_head'] - raw['tick_tail']) & 0xffffffff
    if delta is None:
        status = 'COUNTER_REGRESSION_OR_WRAP_UNRESOLVED'
    elif delta or raw['unmatched_ticks'] or raw['foreground_flags'] & 32:
        status = 'CURRENT_WINDOW_LOSS_OR_MATCH_FAILURE'
    elif raw['irq_flags'] & 32 and base == 0:
        status = 'LIFETIME_FLAG_COUNTER_CONFLICT'
    elif raw['irq_flags'] & 32:
        status = 'PRE_WINDOW_CUMULATIVE_LOSS_ONLY'
    else:
        status = 'NO_TICK_LOSS_RECORDED'
    return {'status': status, 'raw_irq_flags': raw['irq_flags'], 'raw_foreground_flags': raw['foreground_flags'],
            'raw_tick_dropped': total, 'raw_tick_drop_base': base, 'window_new_tick_drops': delta,
            'window_unmatched_ticks': raw['unmatched_ticks'], 'pending_at_freeze': pending,
            'current_window_loss_free': delta == 0 and raw['unmatched_ticks'] == 0 and not raw['foreground_flags'] & 32
                                        and status not in ('LIFETIME_FLAG_COUNTER_CONFLICT',)}


def _aggregate_valid(row):
    count = row['success'] + row['failure']
    if not count:
        return row['max_cycles'] == row['inclusive_cycles'] == row['direct_child_cycles'] == 0
    return (row['min_cycles'] <= row['max_cycles'] <= row['inclusive_cycles'] and
            row['direct_child_cycles'] <= row['inclusive_cycles'])


def rate(raw, meta):
    ticks, timing = tick_quality(raw), halt_interval(meta)
    clock_ok = not ((raw['irq_flags'] | raw['foreground_flags']) & 3) and not raw['clock_seq'] & 1
    flags_known = not (raw['irq_flags'] & ~35 or raw['foreground_flags'] & ~127)
    context = meta.get('registers_at_halt', {})
    context_ok = (type(context.get('IPSR')) is int and type(context.get('XPSR')) is int and
                  context['IPSR'] == context['XPSR'] & 0x1ff and context['IPSR'] == 0)
    span_ok = (raw['depth'] <= 6 and not raw['foreground_flags'] & 12 and
               all(s['scope'] < 10 and s['generation'] == raw['window_generation'] for s in raw['active_spans']))
    event_ok = raw['event_count'] <= 16
    classes = set()
    for e in raw['events']:
        scope, outcome = e['scope'] & 255, e['scope'] & 0x300
        delta = (e['end'] - e['start']) & 0xffffffff
        if (scope >= 10 or e['scope'] & ~0x3ff or outcome not in (0x100, 0x200) or
                e['scope'] in classes or not e['bound_ms'] or e['bound_ms'] * 16000 >= 1 << 32 or
                delta > e['bound_ms'] * 16000):
            event_ok = False
        elif delta > raw['aggregate'][scope]['max_cycles']:
            event_ok = False
        classes.add(e['scope'])
    metrics = {}

    def metric(grade, usable, reasons, values=None, comparison='NOT_COMPARABLE_FOR_ACCEPTANCE'):
        return {'grade': grade, 'limited_observation_usable': usable, 'reasons': reasons,
                'values': values, 'comparison': comparison, 'acceptance_pass': False}

    # 活动span不是已经完成的aggregate：仅限制全窗最大值，不能抹去真实完成统计。
    m1_ok = clock_ok and flags_known and context_ok and span_ok and all(_aggregate_valid(a) for a in raw['aggregate'][:4])
    m1_present = any(a['success'] + a['failure'] for a in raw['aggregate'][:4])
    m1_values = {SCOPES[i]: {**raw['aggregate'][i], 'max_seen_nominal_ms': raw['aggregate'][i]['max_cycles'] / 16000}
                 for i in range(4)}
    metrics['M01'] = metric('LIMITED_OBSERVATION' if m1_ok and m1_present else 'INVALID' if not m1_ok else 'NOT_MEASURED',
                            m1_ok and m1_present, ['COMPLETED_CALLS_ONLY', 'ACTIVE_CALLS_NOT_IN_COMPLETED_AGGREGATE',
                                                   'UNRESOLVED_STOP_INTERVAL', 'UNCALIBRATED_PROBE_OVERHEAD'], m1_values)
    metrics['M01']['active_scopes'] = [SCOPES[s['scope']] if s['scope'] < 10 else 'INVALID_SCOPE' for s in raw['active_spans']]
    metrics['M01']['full_window_maximum_complete'] = False
    metrics['M01']['event_provenance_valid'] = event_ok
    needed = {(0x100 if outcome == 'success' else 0x200) | i
              for i in range(4) for outcome in ('success', 'failure') if raw['aggregate'][i][outcome]}
    metrics['M01']['max_seen_record_provenance_valid'] = (event_ok and needed.issubset(classes) and
                                                        not raw['dropped_observations'] and not raw['foreground_flags'] & 16)
    metrics['M01']['completed_statistics_usable'] = bool(m1_ok and m1_present)

    service = raw['aggregate'][8]
    m2_ok = clock_ok and flags_known and context_ok and ticks['current_window_loss_free'] and ticks['pending_at_freeze'] <= 16
    m2_ok = m2_ok and _aggregate_valid(service) and not service['invalid'] and event_ok and 0x108 in classes
    metrics['M02'] = metric('LIMITED_OBSERVATION' if m2_ok and service['success'] else 'INVALID', bool(m2_ok and service['success']),
                            ['SYSTICK_ISR_SAMPLE_TO_COOPERATIVE_SERVICE_DONE', 'COMPLETED_MATCHED_SERVICES_ONLY',
                             'PENDING_TASKS_EXCLUDED', 'HARDWARE_DUE_TO_ISR_NOT_MEASURED'],
                            {**service, 'max_seen_nominal_ms': service['max_cycles'] / 16000, 'tick_quality': ticks})
    metrics['M02']['full_window_maximum_complete'] = False
    metrics['M03'] = metric('PARTIAL', m1_ok and m1_present,
                            ['FULL_GATEWAY_PUBLISH_INCLUSIVE_ONLY', 'CPU_PURE_NOT_MEASURED',
                             'LIBRARY_API_BOUNDARIES_NOT_EQUIVALENT', 'UNCALIBRATED_PROBE_OVERHEAD'],
                            {'Q0': raw['aggregate'][1], 'Q1': raw['aggregate'][2]})
    metrics['M04'] = metric('BLOCKED', False, ['BLOCKED_UNSAFE_SENTINEL', 'STACK_HIGH_WATER_NOT_MEASURED'])

    heap_ok = raw['heap_peak_bytes'] <= 24576 and raw['heap_enomem_count'] >= raw['heap_error_base']
    metrics['M05'] = metric('LIMITED_OBSERVATION' if heap_ok else 'INVALID', heap_ok,
                            ['SBRK_HIGH_WATER_INCLUDES_INITIALIZATION', 'DOES_NOT_ESTABLISH_STACK_SAFETY'],
                            {'peak_bytes': raw['heap_peak_bytes'], 'remaining_bytes': 24576 - raw['heap_peak_bytes'] if heap_ok else None,
                             'raw_ENOMEM_total': raw['heap_enomem_count'], 'raw_ENOMEM_base': raw['heap_error_base'],
                             'window_ENOMEM_delta': raw['heap_enomem_count'] - raw['heap_error_base'] if heap_ok else None},
                            'LIMITED_SAME_METHOD_SINGLE_RUN_PEAK_COMPARISON' if heap_ok else 'NOT_COMPARABLE')
    net, frame = raw['network_us'], raw['first_business_id']
    broker = meta.get('broker_correlated_after_OFFLINE', {}).get('first_VALID_business', {})
    identity_ok = (frame == meta.get('first_business_numeric_identity') and frame['node'] in (1, 2) and frame['stream'] < 9 and
                   broker.get('node') == ('NODE-A' if frame['node'] == 1 else 'NODE-B') and
                   broker.get('stream') == STREAMS[frame['stream']] and broker.get('seq') == frame['seq'] and
                   broker.get('session_id') == f"can-{frame['epoch']}-{frame['boot']}" and broker.get('synthetic') is True and
                   broker.get('validity') == 'VALID' and broker.get('source') == 'MOCK')
    m6_ok = clock_ok and flags_known and raw['network_valid_mask'] == 0x1ff and net == sorted(net) and net[8] > net[5] and identity_ok
    metrics['M06'] = metric('LIMITED_OBSERVATION' if m6_ok else 'INVALID', m6_ok,
                            ['COMPLETED_DEVICE_ENDPOINTS_BEFORE_HALT', 'NOMINAL_16MHZ_CLOCK',
                             'DEVICE_PUBLISH_SUCCESS_NOT_BROKER_ACK', 'ONE_RUN_PER_VARIANT_NO_MEDIAN_GATE'],
                            {'network_open_to_TLS_us': net[6] - net[5], 'TLS_to_CONNACK_us': net[7] - net[6],
                             'CONNACK_to_first_business_us': net[8] - net[7], 'network_open_to_first_business_us': net[8] - net[5]},
                            'EXPLORATORY_SINGLE_RUN_NOMINAL_TIME_ONLY' if m6_ok else 'NOT_COMPARABLE')
    before, after = raw['cache_before'], raw['cache_after']
    cache_ok = (raw['cache_snapshot_mask'] == 3 and before['cache'] <= 32 and after['cache'] <= 32 and
                all(after[k] >= before[k] for k in ('lost', 'replay', 'drop')))
    drain_ok = (raw['cache_drained_observed'] in (0, 1) and
                (not raw['cache_drained_observed'] or after['cache'] == 0 and raw['replay_observed'] == 1))
    time_ok = (clock_ok and raw['live_observed'] == raw['replay_observed'] == 1 and
               raw['first_live_us'] > 0 and raw['first_replay_us'] > 0)
    metrics['M07'] = metric('LIMITED_OBSERVATION' if cache_ok and drain_ok else 'INVALID', cache_ok and drain_ok,
                            ['OBSERVED_CACHE_EMPTY_AT_LAST_SNAPSHOT_ONLY', 'NO_TERMINAL_SNAPSHOT_TIMESTAMP',
                             'NO_LOSSLESS_OR_FULL_DRAIN_CLAIM', 'CACHE_BASELINES_DIFFER_ACROSS_PILOT_RUNS'],
                            {'before': before, 'after': after,
                             'deltas': {k: after[k] - before[k] for k in ('lost', 'replay', 'drop')},
                             'raw_last_snapshot_empty': raw['cache_drained_observed'], 'drain_claim_consistent': drain_ok,
                             'live_replay_time_usable': time_ok,
                             'LIVE_before_REPLAY': raw['first_live_us'] < raw['first_replay_us'] if time_ok else None},
                            'NO_LOSS_RATE_COMPARISON_WITH_DIFFERENT_BASELINES')
    return {'raw_observation': raw, 'tick_quality': ticks, 'halt_timing': timing,
            'checks': {'cycle_clock_usable_for_limited_observation': clock_ok, 'flags_recognized': flags_known,
                       'thread_context_verified': context_ok, 'active_span_structure_valid': span_ok,
                       'max_event_structure_valid': event_ok},
            'metrics': metrics, 'original_strict_decode_status': meta.get('strict_decode_status'),
            'whole_window_acceptance': 'NOT_QUALIFIED', 'H16_acceptance': 'NOT_GRANTED',
            'hardware_tests_executed_this_analysis': False}


def analyze_pair(first, second, layout, meta):
    if first.resolve() == second.resolve() or first.samefile(second):
        raise InvalidSnapshot('INDEPENDENT_FILES_REQUIRED')
    for path in (first, second):
        if not path.is_file() or path.is_symlink() or path.stat().st_size != 1264:
            raise InvalidSnapshot('REGULAR_EXACT_SNAPSHOT_REQUIRED')
    a, b = first.read_bytes(), second.read_bytes()
    if a != b or sha(a) != meta['snapshot_read1_sha256'] or sha(b) != meta['snapshot_read2_sha256']:
        raise InvalidSnapshot('ORIGINAL_SNAPSHOT_HASH_MISMATCH')
    variant = meta['variant']
    if variant not in EXPECTED_BIN or meta['bin_sha256'] != EXPECTED_BIN[variant]:
        raise InvalidSnapshot('MEASUREMENT_FIRMWARE_IDENTITY')
    result = rate(extract(a, layout, variant), meta)
    if first.read_bytes() != a or second.read_bytes() != b:
        raise InvalidSnapshot('SNAPSHOT_CHANGED_DURING_ANALYSIS')
    result.update(variant=variant, snapshot_sha256=sha(a), snapshot_bytes=len(a))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--private-window', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    try:
        if str(args.private_window).startswith(('\\\\', '//')) or not args.private_window.is_dir():
            raise InvalidSnapshot('LOCAL_PRIVATE_SNAPSHOT_DIRECTORY_REQUIRED')
        if not args.output.resolve().is_relative_to(ROOT) or args.output.suffix != '.json':
            raise InvalidSnapshot('LOCAL_NEW_JSON_OUTPUT_REQUIRED')
        original_bytes = ORIGINAL.read_bytes()
        if sha(original_bytes) != ORIGINAL_SHA:
            raise InvalidSnapshot('ORIGINAL_REPORT_CHANGED')
        original = json.loads(original_bytes)
        if args.private_window.name != original['window_id']:
            raise InvalidSnapshot('ORIGINAL_WINDOW_IDENTITY')
        layout = load_layout(LAYOUT)
        runs = [analyze_pair(args.private_window / (r['variant'] + '-snapshot-read1.bin'),
                             args.private_window / (r['variant'] + '-snapshot-read2.bin'), layout, r)
                for r in original['runs']]
        result = {'kind': 'OFFLINE_EXISTING_C3A_METRIC_QUALITY_REANALYSIS', 'schema_version': 1,
                  'original_report_sha256': sha(original_bytes), 'original_source_commit': 'd21a796547be6812f12fc15ce9f7852fcde58151',
                  'runs': runs, 'hardware_activity_this_round': False, 'H16_acceptance': 'NOT_GRANTED'}
        # 只新建派生结果，拒绝覆盖原报告、输入快照和任何旧输出。
        with args.output.open('x', encoding='utf-8') as stream:
            json.dump(result, stream, ensure_ascii=False, indent=2)
            stream.write('\n')
        print(json.dumps({'status': 'OFFLINE_REANALYSIS_COMPLETE', 'runs': len(runs), 'H16_acceptance': 'NOT_GRANTED'}))
        return 0
    except (OSError, UnicodeError, KeyError, ValueError, InvalidSnapshot):
        print(json.dumps({'status': 'INVALID_OFFLINE_REANALYSIS_INPUT', 'hardware_activity': False}))
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
