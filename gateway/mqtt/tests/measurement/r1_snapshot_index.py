"""C2.5-R1 快照索引的脱机一致性检查；不读取探针内存或授予真机准入。"""

import argparse
import hashlib
import json
from pathlib import Path
import re


SOURCE = {
    'P4': '8dee339491cfd4edc468bb9451511d421f26db5e',
    'P5': 'e598fc63719acdf49a99c6da46c656dc8c607782',
}
DIAGNOSTIC_BIN = {
    'P4': 'fabd82b305e2fe1bc4bbc0d06bdde91d05daabd7f91c70ca017f48e4617ab551',
    'P5': '47a444ebd3642dffef80364309d0b100cc048b456d75dde0b2806a7f9a052efc',
}
HEX64 = re.compile(r'[0-9a-f]{64}\Z')
LABEL = re.compile(r'[A-Za-z][A-Za-z0-9_-]{0,39}\Z')
M02 = 'SYSTICK_ISR_SAMPLE_TO_COOPERATIVE_SERVICE_DONE'
M03 = 'GATEWAY_PUBLISH_INCLUSIVE_M03_PARTIAL_CPU_PURE_NOT_MEASURED'
M07 = 'OBSERVED_CACHE_EMPTY_AT_LAST_SNAPSHOT'
RUN_KEYS = {
    'run_id', 'observer_session_id', 'variant', 'ordinal', 'window_generation', 'recovery_generation',
    'source_commit', 'measurement_bin_sha256', 'environment_id', 'workload_id',
    'profile_id', 'core_clock_hz', 'observer_start_us', 'observer_halt_us',
    'observer_paused_in_window', 'capture_complete', 'saved_before_next_d',
    'snapshot_sha_first', 'snapshot_sha_second', 'snapshot_bytes', 'clock_seq',
    'depth', 'irq_flags', 'foreground_flags', 'dropped_observations',
    'tick_dropped_delta', 'unmatched_ticks', 'network_valid_mask',
    'cache_snapshot_mask', 'm02_semantics', 'm03_semantics', 'm07_semantics',
    'stack_method',
}


class InvalidIndex(ValueError):
    """固定错误类别；不把路径、身份或未知输入原文输出。"""


def _keys(value, required):
    if not isinstance(value, dict) or set(value) != required:
        raise InvalidIndex('SCHEMA_KEYS')


def _integer(value, low=0):
    # bool 是 int 的子类，不能把 true 当作窗口编号或计数。
    if type(value) is not int or value < low or value > (1 << 53) - 1:
        raise InvalidIndex('INTEGER_RANGE')
    return value


def _label(value):
    if not isinstance(value, str) or not LABEL.fullmatch(value):
        raise InvalidIndex('LABEL_FORMAT')
    return value


def _sha(value):
    if not isinstance(value, str) or not HEX64.fullmatch(value):
        raise InvalidIndex('SHA256_FORMAT')
    return value


EVENT_NAMES = ('D_SENT', 'HALT', 'READ1_DONE', 'READ2_DONE', 'SNAPSHOT_PERSISTED', 'RESUME')


def _event_digest(event):
    # 链可证明文件内部未被局部改写；完整重造日志仍需外部采集原件识别。
    payload = {key: event[key] for key in ('run_id', 'observer_session_id', 'event', 'at_us', 'prev_sha256')}
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def validate_event_log(log):
    _keys(log, {'schema_version', 'kind', 'events'})
    if type(log['schema_version']) is not int or log['schema_version'] != 1 or log['kind'] not in (
            'SYNTHETIC_R2_EVENT_LOG', 'REDACTED_CAPTURE_EVENT_LOG'):
        raise InvalidIndex('EVENT_LOG_VERSION')
    events = log['events']
    if not isinstance(events, list) or len(events) != 36:
        raise InvalidIndex('EVENT_LOG_COUNT')
    previous = '0' * 64
    last_time = -1
    grouped = {}
    for event in events:
        _keys(event, {'run_id', 'observer_session_id', 'event', 'at_us', 'prev_sha256', 'sha256'})
        run_id = _label(event['run_id'])
        _label(event['observer_session_id'])
        timestamp = _integer(event['at_us'])
        if timestamp <= last_time:
            raise InvalidIndex('EVENT_GLOBAL_TIME_ORDER')
        last_time = timestamp
        if event['event'] not in EVENT_NAMES or _sha(event['prev_sha256']) != previous:
            raise InvalidIndex('EVENT_CHAIN_ORDER')
        if _sha(event['sha256']) != _event_digest(event):
            raise InvalidIndex('EVENT_CHAIN_HASH')
        previous = event['sha256']
        grouped.setdefault(run_id, []).append(event)
    return grouped


def validate_index(data, event_log=None):
    """校验索引和独立事件链的顺序；SWD 字节、物理来源仍须另行核验。"""
    if event_log is None:
        raise InvalidIndex('ORDER_UNVERIFIED')
    event_groups = validate_event_log(event_log)
    _keys(data, {'schema_version', 'kind', 'comparison_scope', 'runs'})
    if data['schema_version'] != 1 or type(data['schema_version']) is not int:
        raise InvalidIndex('SCHEMA_VERSION')
    if data['kind'] not in ('SYNTHETIC_R1_FIXTURE', 'REDACTED_SNAPSHOT_INDEX'):
        raise InvalidIndex('INDEX_KIND')
    if data['comparison_scope'] != 'CAN1_SILENT_LOOPBACK':
        raise InvalidIndex('COMPARISON_SCOPE')
    runs = data['runs']
    if not isinstance(runs, list) or len(runs) != 6:
        raise InvalidIndex('THREE_WINDOWS_PER_VARIANT_REQUIRED')

    seen_sha = set()
    seen_ids = set()
    recovery_previous = {'P4': 0, 'P5': 0}
    durations = []
    last_resume = None
    common_session = None
    for position, run in enumerate(runs):
        _keys(run, RUN_KEYS)
        run_id = _label(run['run_id'])
        session = _label(run['observer_session_id'])
        if run_id in seen_ids or run_id not in event_groups:
            raise InvalidIndex('RUN_EVENT_ID_MISMATCH')
        seen_ids.add(run_id)
        if common_session is None:
            common_session = session
        elif session != common_session:
            # 跨QPC会话不能按绝对时间直接比较；现场换会话需重新设计独立桥接证据。
            raise InvalidIndex('OBSERVER_SESSION_DRIFT')
        events = event_groups[run_id]
        if len(events) != 6 or tuple(e['event'] for e in events) != EVENT_NAMES or any(
                e['observer_session_id'] != session for e in events):
            raise InvalidIndex('EVENT_SEQUENCE')
        times = [e['at_us'] for e in events]
        if times != sorted(times) or len(set(times)) != len(times):
            raise InvalidIndex('EVENT_TIME_ORDER')
        if last_resume is not None and times[0] <= last_resume:
            raise InvalidIndex('NEXT_D_BEFORE_PREVIOUS_SAVE_AND_RESUME')
        last_resume = times[-1]
        variant = 'P4' if position < 3 else 'P5'
        ordinal = position % 3 + 1
        if run['variant'] != variant or _integer(run['ordinal'], 1) != ordinal:
            raise InvalidIndex('WINDOW_ORDER_OR_MISSING')
        if _integer(run['window_generation'], 1) != ordinal:
            # fresh-flash测试中每版首次D应生成窗口1；缺号意味着旧数据可能已覆盖。
            raise InvalidIndex('WINDOW_OVERWRITTEN_OR_GENERATION_GAP')
        recovery = _integer(run['recovery_generation'], 1)
        # 初次入网也调用gateway_network_open；重连失败还可能多次调用，故只要求逐轮严格递增。
        if recovery <= recovery_previous[variant]:
            raise InvalidIndex('RECOVERY_GENERATION_NOT_ADVANCING')
        recovery_previous[variant] = recovery
        if run['source_commit'] != SOURCE[variant] or _sha(run['measurement_bin_sha256']) != DIAGNOSTIC_BIN[variant]:
            raise InvalidIndex('FIRMWARE_IDENTITY_DRIFT')
        if (_label(run['environment_id']) != 'H16_FIXED_ENV' or
                _label(run['workload_id']) != 'TWO_CAN_SYNTHETIC' or
                run['profile_id'] != 'C25_PROFILE_1' or
                _integer(run['core_clock_hz'], 1) != 16_000_000):
            raise InvalidIndex('ENVIRONMENT_OR_PROFILE_DRIFT')
        start, halt = _integer(run['observer_start_us']), _integer(run['observer_halt_us'])
        if start != times[0] or halt != times[1] or halt <= start:
            raise InvalidIndex('OBSERVER_EVENT_MISMATCH')
        duration = halt - start
        # 90秒观察之后才允许首次halt；2秒是待C3A批准的外部操作容差。
        if not 90_000_000 <= duration <= 92_000_000:
            raise InvalidIndex('OBSERVER_WINDOW_DURATION_DRIFT')
        durations.append(duration)
        for name in ('observer_paused_in_window', 'capture_complete', 'saved_before_next_d'):
            if type(run[name]) is not bool:
                raise InvalidIndex('BOOLEAN_REQUIRED')
        if run['observer_paused_in_window'] or not run['capture_complete'] or not run['saved_before_next_d']:
            raise InvalidIndex('WINDOW_CAPTURE_INCOMPLETE')
        first, second = _sha(run['snapshot_sha_first']), _sha(run['snapshot_sha_second'])
        if first != second:
            raise InvalidIndex('INCONSISTENT_FROZEN_SNAPSHOT')
        if first in seen_sha:
            raise InvalidIndex('REUSED_SNAPSHOT')
        seen_sha.add(first)
        if _integer(run['snapshot_bytes']) != 1264:
            raise InvalidIndex('PROBE_STATE_SIZE_DRIFT')
        if (_integer(run['clock_seq']) & 1 or _integer(run['depth']) or
                _integer(run['irq_flags']) or _integer(run['foreground_flags']) != 64 or
                _integer(run['dropped_observations']) or _integer(run['tick_dropped_delta']) or
                _integer(run['unmatched_ticks'])):
            raise InvalidIndex('PROBE_WINDOW_INVALID')
        if (_integer(run['network_valid_mask']) != 0x1ff or
                _integer(run['cache_snapshot_mask']) != 3):
            raise InvalidIndex('MISSING_NETWORK_OR_CACHE_POINTS')
        if (run['m02_semantics'] != M02 or run['m03_semantics'] != M03 or
                run['m07_semantics'] != M07 or run['stack_method'] != 'NOT_MEASURED'):
            raise InvalidIndex('METRIC_SEMANTICS_DRIFT')

    if set(event_groups) != seen_ids:
        raise InvalidIndex('EXTRA_OR_MISSING_EVENT_RUN')
    if max(durations) - min(durations) > 2_000_000:
        raise InvalidIndex('OBSERVER_WINDOW_NOT_COMPARABLE')
    return {'status': 'INDEX_CONSISTENCY_ONLY', 'runs': 6,
            'H16_acceptance': 'NOT_GRANTED', 'physical_identity_verified': False,
            'snapshot_bytes_verified_by_index_only': True,
            'order_evidence': 'HASH_CHAINED_OFFLINE_EVENT_LOG_NOT_PHYSICAL_AUTHENTICITY'}


def _unique_object(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise InvalidIndex('DUPLICATE_JSON_KEY')
        value[key] = item
    return value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input', type=Path)
    parser.add_argument('--event-log', type=Path, required=True)
    args = parser.parse_args()
    try:
        workspace = Path(__file__).resolve().parents[4]
        path = args.input
        # 仅取工作树内的本地小型JSON，防止误读设备、共享目录或私有配置。
        for candidate in (path, args.event_log):
            if (str(candidate).startswith(('\\\\', '//')) or candidate.suffix.lower() != '.json' or
                    not candidate.resolve().is_relative_to(workspace) or not candidate.is_file() or
                    candidate.stat().st_size > 1_048_576):
                raise InvalidIndex('LOCAL_INDEX_REQUIRED')
        data = json.loads(path.read_text(encoding='utf-8'), object_pairs_hook=_unique_object,
                          parse_constant=lambda _: (_ for _ in ()).throw(InvalidIndex('NONFINITE_JSON')))
        log = json.loads(args.event_log.read_text(encoding='utf-8'), object_pairs_hook=_unique_object,
                         parse_constant=lambda _: (_ for _ in ()).throw(InvalidIndex('NONFINITE_JSON')))
        print(json.dumps(validate_index(data, log), sort_keys=True))
        return 0
    except (OSError, UnicodeError, json.JSONDecodeError, InvalidIndex):
        print(json.dumps({'status': 'INVALID_OFFLINE_INDEX', 'H16_acceptance': 'NOT_GRANTED'}))
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
