"""H16纯脱机解析：读取脱敏JSON，分析计数/时序；不包含设备、串口、网络或进程调用。"""
import argparse
from collections import defaultdict
import json
from pathlib import Path
import re
import statistics

PINS = {
    'P4': ('8dee339491cfd4edc468bb9451511d421f26db5e',
           '5fd386b8bfe0bcf54d4f53ffb1ec6483d086a1c3287b4fe6c37a3ddeacd90547'),
    'P5': ('e598fc63719acdf49a99c6da46c656dc8c607782',
           'fd81076b9b34ad0a8f4ee35c08cd7ea14704f6d7b04620741cdf083c9c6c1069'),
}
MASK32 = (1 << 32) - 1
LABEL = re.compile(r'[A-Za-z][A-Za-z0-9_-]{0,39}\Z')
HEX64 = re.compile(r'[0-9a-f]{64}\Z')


class InvalidObservation(ValueError):
    """仅返回固定错误分类，避免把未知输入值或配置内容回显。"""


def fields(value, required, optional=()):
    if not isinstance(value, dict) or set(value) != set(required) | (set(value) & set(optional)):
        raise InvalidObservation('SCHEMA_KEYS')


def integer(value, low=0, high=(1 << 53) - 1):
    # JSON布尔是Python整数子类，必须显式拒绝，不能把true当成周期或字节数。
    if type(value) is not int or not low <= value <= high:
        raise InvalidObservation('INTEGER_RANGE')
    return value


def boolean(value):
    if type(value) is not bool:
        raise InvalidObservation('BOOLEAN_REQUIRED')
    return value


def label(value):
    if not isinstance(value, str) or not LABEL.fullmatch(value):
        raise InvalidObservation('LABEL_FORMAT')
    return value


def stats(values):
    # 少量有效样本只给逐次/min/median/max；不制造p95或推断总体分布。
    if not values:
        return {'count': 0, 'status': 'NOT_MEASURED'}
    return {'count': len(values), 'values': values, 'min': min(values),
            'median': statistics.median(values), 'max': max(values)}


def cycle_delta(sample, frequency):
    fields(sample, ['metric', 'scope', 'outcome', 'start', 'end', 'elapsed_upper_bound_us'])
    if sample['metric'] not in ('M01', 'M02', 'M03') or sample['outcome'] not in ('SUCCESS', 'FAILURE'):
        raise InvalidObservation('CYCLE_CATEGORY')
    label(sample['scope'])
    start, end = [integer(sample[key], 0, MASK32) for key in ('start', 'end')]
    bound = integer(sample['elapsed_upper_bound_us'], 1)
    bound_cycles = bound * frequency // 1_000_000
    # 模减只在可信间隔小于一个完整回绕周期时唯一；超界不能猜测回绕次数。
    if bound_cycles >= 1 << 32:
        raise InvalidObservation('AMBIGUOUS_COUNTER_WRAP')
    cycles = (end - start) & MASK32
    if cycles > bound_cycles:
        raise InvalidObservation('COUNTER_EXCEEDS_INTERVAL_BOUND')
    return cycles


def network_phases(value):
    fields(value, ['clock_domain', 'resolution_us', 'endpoint', 'start_boundary', 'fault_command_us',
                   'pause_end_us', 'recovery_start_us', 'tls_ready_us', 'connack_us',
                   'first_valid_telemetry_us', 'first_stream', 'validity', 'source', 'synthetic'])
    if value['clock_domain'] not in ('MCU_MONOTONIC_US', 'HOST_QPC_US'):
        raise InvalidObservation('NETWORK_CLOCK_DOMAIN')
    if value['endpoint'] not in ('DEVICE_PUBLISH_SUCCESS', 'BROKER_RECEIVE'):
        raise InvalidObservation('NETWORK_ENDPOINT')
    if value['start_boundary'] != 'GATEWAY_NETWORK_OPEN_ENTRY':
        raise InvalidObservation('RECOVERY_START_BOUNDARY')
    if value['validity'] != 'VALID' or value['source'] != 'MOCK' or boolean(value['synthetic']) is not True:
        raise InvalidObservation('EXPECTED_SYNTHETIC_MOCK')
    if value['first_stream'] not in ('PPG', 'SPO2', 'PR', 'NIBP', 'ECG', 'HR', 'RESP', 'TEMP'):
        raise InvalidObservation('FIRST_FRAME_NOT_VALID_BUSINESS_STREAM')
    integer(value['resolution_us'], 1, 1_000_000)
    keys = ['fault_command_us', 'pause_end_us', 'recovery_start_us', 'tls_ready_us',
            'connack_us', 'first_valid_telemetry_us']
    times = [integer(value[key]) for key in keys]
    if times != sorted(times):
        raise InvalidObservation('NETWORK_EVENT_ORDER')
    if times[-1] == times[2]:
        raise InvalidObservation('ZERO_RECOVERY_INTERVAL')
    fault, pause, recovery, tls, connack, frame = times
    return {'fixed_pause_us': pause - fault, 'post_pause_before_network_us': recovery - pause,
            'network_to_tls_us': tls - recovery, 'tls_to_connack_us': connack - tls,
            'connack_to_business_frame_us': frame - connack, 'network_reconnect_us': frame - recovery,
            'D_to_business_frame_us': frame - fault}


def memory_summary(value):
    fields(value, ['stack_reserved_bytes', 'stack_min_free_bytes', 'stack_method', 'stack_region_verified',
                   'heap_limit_bytes', 'heap_peak_bytes', 'heap_failure_count', 'heap_method'])
    if value['stack_method'] not in ('EARLY_RESET_SENTINEL', 'NOT_MEASURED'):
        raise InvalidObservation('STACK_METHOD')
    if value['heap_method'] not in ('SBRK_HIGH_WATER', 'NOT_MEASURED'):
        raise InvalidObservation('HEAP_METHOD')
    stack_limit = integer(value['stack_reserved_bytes'], 1)
    heap_limit = integer(value['heap_limit_bytes'], 1)
    if stack_limit != 8192 or heap_limit != 24576:
        raise InvalidObservation('MEMORY_RESERVATION_DRIFT')
    if value['heap_failure_count'] is not None:
        integer(value['heap_failure_count'])
    verified = boolean(value['stack_region_verified'])
    stack_free, heap_peak = value['stack_min_free_bytes'], value['heap_peak_bytes']
    if value['stack_method'] == 'NOT_MEASURED':
        if stack_free is not None:
            raise InvalidObservation('UNMEASURED_STACK_HAS_VALUE')
    elif stack_free is None or not verified:
        raise InvalidObservation('STACK_REGION_UNVERIFIED')
    else:
        integer(stack_free, 0, stack_limit)
    if value['heap_method'] == 'NOT_MEASURED':
        if heap_peak is not None:
            raise InvalidObservation('UNMEASURED_HEAP_HAS_VALUE')
    else:
        integer(heap_peak, 0, heap_limit)
    return {'stack_used_bytes': None if stack_free is None else stack_limit - stack_free,
            'stack_min_free_bytes': stack_free, 'heap_peak_bytes': heap_peak,
            'heap_remaining_bytes': None if heap_peak is None else heap_limit - heap_peak,
            'heap_failure_count': value['heap_failure_count']}


def cache_summary(value):
    fields(value, ['capacity', 'before', 'after', 'drained_observed', 'first_live_us', 'first_replay_us'])
    capacity = integer(value['capacity'], 1)
    if capacity != 32:
        raise InvalidObservation('CACHE_CAPACITY_DRIFT')
    for stage in ('before', 'after'):
        fields(value[stage], ['cache', 'lost', 'replay', 'drop'])
        integer(value[stage]['cache'], 0, capacity)
        for counter in ('lost', 'replay', 'drop'):
            integer(value[stage][counter])
    drained = boolean(value['drained_observed'])
    if drained and value['after']['cache']:
        raise InvalidObservation('CACHE_DRAIN_CLAIM_CONFLICT')
    deltas = {key: value['after'][key] - value['before'][key] for key in ('lost', 'replay', 'drop')}
    if any(delta < 0 for delta in deltas.values()):
        raise InvalidObservation('CACHE_COUNTER_RESET_OR_WRAP_UNRESOLVED')
    live, replay = value['first_live_us'], value['first_replay_us']
    if live is not None:
        integer(live)
    if replay is not None:
        integer(replay)
    return {'capacity': capacity, 'cache_after': value['after']['cache'], **deltas,
            'cache_drained_observed': drained,
            'live_before_replay': None if live is None or replay is None else live < replay,
            'lossless_observed': False if deltas['lost'] else 'NOT_ESTABLISHED'}


def analyze(data):
    fields(data, ['schema_version', 'kind', 'synthetic', 'comparison_scope', 'baselines', 'runs'])
    if type(data['schema_version']) is not int or data['schema_version'] != 1:
        raise InvalidObservation('SCHEMA_VERSION')
    if data['kind'] not in ('SYNTHETIC_DEMO', 'REDACTED_HARDWARE_OBSERVATION'):
        raise InvalidObservation('PROVENANCE_KIND')
    if boolean(data['synthetic']) is not True or data['comparison_scope'] != 'CAN1_SILENT_LOOPBACK':
        raise InvalidObservation('SYNTHETIC_SCOPE')
    fields(data['baselines'], ['P4', 'P5'])
    for variant, expected in PINS.items():
        fields(data['baselines'][variant], ['source_commit', 'production_bin_sha256'])
        # 不依赖JSON键插入次序，按字段核对冻结生产身份。
        if (data['baselines'][variant]['source_commit'], data['baselines'][variant]['production_bin_sha256']) != expected:
            raise InvalidObservation('BASELINE_IDENTITY')
    if not isinstance(data['runs'], list) or not 1 <= len(data['runs']) <= 100:
        raise InvalidObservation('RUN_COUNT')
    groups, profiles, ids, summaries = defaultdict(list), defaultdict(set), set(), []
    for run in data['runs']:
        fields(run, ['firmware', 'run_id', 'environment_id', 'workload_id', 'profile_id',
                     'measurement_bin_sha256', 'core_clock_hz', 'valid', 'observations_complete',
                     'observer_paused_run', 'dropped_observations', 'cycle_samples', 'network', 'memory', 'cache'])
        variant = run['firmware']
        if variant not in PINS:
            raise InvalidObservation('FIRMWARE_VARIANT')
        run_id = label(run['run_id'])
        if run_id in ids:
            raise InvalidObservation('DUPLICATE_RUN_ID')
        ids.add(run_id)
        environment, workload, profile = [label(run[key]) for key in ('environment_id', 'workload_id', 'profile_id')]
        if not isinstance(run['measurement_bin_sha256'], str) or not HEX64.fullmatch(run['measurement_bin_sha256']):
            raise InvalidObservation('MEASUREMENT_BIN_IDENTITY')
        frequency = integer(run['core_clock_hz'], 1, 200_000_000)
        valid, complete, paused = [boolean(run[key]) for key in ('valid', 'observations_complete', 'observer_paused_run')]
        dropped = integer(run['dropped_observations'])
        if not isinstance(run['cycle_samples'], list) or len(run['cycle_samples']) > 100_000:
            raise InvalidObservation('CYCLE_SAMPLE_COUNT')
        cycles = defaultdict(list)
        for sample in run['cycle_samples']:
            count = cycle_delta(sample, frequency)
            cycles[(sample['metric'], sample['scope'], sample['outcome'])].append(count)
        phases = None if run['network'] is None else network_phases(run['network'])
        memory = None if run['memory'] is None else memory_summary(run['memory'])
        cache = None if run['cache'] is None else cache_summary(run['cache'])
        eligible = valid and complete and not paused and not dropped and phases is not None
        if phases:
            net = run['network']
            declared_profile = (environment, workload, profile, frequency, net['clock_domain'],
                                net['resolution_us'], net['endpoint'], net['start_boundary'], run['measurement_bin_sha256'])
            profiles[variant].add(declared_profile)
        if eligible:
            groups[variant].append(phases['network_reconnect_us'])
        summaries.append({'firmware': variant, 'run_id': run_id, 'eligible_for_network_comparison': eligible,
                          'network': phases, 'memory': memory, 'cache': cache,
                          'cycles_by_scope_and_outcome': [dict(metric=k[0], scope=k[1], outcome=k[2], **stats(values))
                                                        for k, values in sorted(cycles.items())]})
    enough = all(len(groups[variant]) >= 3 for variant in PINS)
    # 两套诊断BIN理应不同；其它声明条件必须一致，且同一variant内BIN不得中途漂移。
    comparable = all(len(profiles[variant]) == 1 for variant in PINS)
    if comparable:
        p4_profile, p5_profile = [next(iter(profiles[variant])) for variant in ('P4', 'P5')]
        # 固定P4/P5是不同单客户端产物；同一个测量BIN被声明为两个版本不能用于性能对照。
        comparable = p4_profile[:-1] == p5_profile[:-1] and p4_profile[-1] != p5_profile[-1]
    comparison = {'status': 'READY_FOR_REVIEW' if enough and comparable else
                            'INSUFFICIENT_SAMPLES' if not enough else 'NOT_COMPARABLE',
                  'P4_network_reconnect_us': stats(groups['P4']), 'P5_network_reconnect_us': stats(groups['P5'])}
    if enough and comparable:
        p4 = statistics.median(groups['P4']); p5 = statistics.median(groups['P5'])
        percent = (p5 - p4) / p4 * 100
        comparison.update({'median_regression_percent': round(percent, 6),
                           'review_required_over_20_percent': p5 * 5 > p4 * 6,
                           'physical_setup_verified_by_parser': False})
    missing = []
    for metric in ('M01', 'M02', 'M03'):
        if any(not any(row['metric'] == metric for row in run['cycles_by_scope_and_outcome']) for run in summaries):
            missing.append(metric)
    for key, metric in [('memory', 'M04_M05'), ('network', 'M06'), ('cache', 'M07')]:
        if any(run[key] is None for run in summaries):
            missing.append(metric)
    if any(run['memory'] is not None and run['memory']['stack_used_bytes'] is None for run in summaries):
        missing.append('M04')
    if any(run['memory'] is not None and run['memory']['heap_peak_bytes'] is None for run in summaries):
        missing.append('M05')
    if any(run['memory'] is not None and run['memory']['heap_failure_count'] is None for run in summaries):
        missing.append('M05_FAILURE_COUNT')
    return {'schema_version': 1, 'kind': data['kind'], 'synthetic': True,
            'verdict': 'SIMULATION_ONLY' if data['kind'] == 'SYNTHETIC_DEMO' else 'ANALYSIS_ONLY_NO_ACCEPTANCE',
            'hardware_tests_executed': False, 'H16_acceptance': 'NOT_GRANTED',
            'network_comparison': comparison, 'not_measured': sorted(set(missing)), 'runs': summaries}


def unique_object(pairs):
    # 重复键会静默覆盖有效性/身份；直接拒绝，不打印键名或对应值。
    result = {}
    for key, value in pairs:
        if key in result:
            raise InvalidObservation('DUPLICATE_JSON_KEY')
        result[key] = value
    return result


def reject_constant(_):
    raise InvalidObservation('NONFINITE_JSON')


def load_input(path):
    if not path.is_file():
        raise InvalidObservation('REGULAR_JSON_FILE_REQUIRED')
    if path.stat().st_size > 8 * 1024 * 1024:
        raise InvalidObservation('INPUT_SIZE')
    # 非有限JSON数不是有效观测；未知键亦由白名单拒绝，输出不复制任意输入文本。
    return json.loads(path.read_text(encoding='utf-8'), parse_constant=reject_constant,
                      object_pairs_hook=unique_object)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input', type=Path, help='本地脱敏JSON，纯离线解析')
    parser.add_argument('--output', type=Path, help='另存解析摘要，不覆盖输入')
    args = parser.parse_args()
    try:
        # 采集导出的脱敏JSON放在本仓库本地build；拒绝UNC/设备路径和仓库外输入输出。
        # 路径限制在读文件之前检查，避免“离线解析”意外变成远程共享或设备访问。
        workspace = Path(__file__).resolve().parents[4]
        for path in [args.input, *([args.output] if args.output else [])]:
            if str(path).startswith(('\\\\', '//')) or path.suffix.lower() != '.json':
                raise InvalidObservation('LOCAL_JSON_PATH_REQUIRED')
            if not path.resolve().is_relative_to(workspace):
                raise InvalidObservation('PATH_OUTSIDE_WORKSPACE')
        result = analyze(load_input(args.input))
        text = json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + '\n'
        if args.output:
            # 独占创建阻止覆盖既有历史和输入，并解决检查后到写入前的竞态。
            with args.output.open('x', encoding='utf-8') as output:
                output.write(text)
        else:
            print(text, end='')
        return 0
    except (OSError, json.JSONDecodeError, InvalidObservation):
        # 不回显路径、未知值或异常原文；输入不合格的退出码不能被误读为硬件测量失败。
        print(json.dumps({'status': 'INVALID_OFFLINE_INPUT', 'hardware_tests_executed': False}))
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
