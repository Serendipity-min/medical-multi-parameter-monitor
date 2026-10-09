"""只解码两份已保存的本地 ProbeState 字节；不具备设备读取或业务准出能力。"""

import argparse
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
LAYOUT_SHA = '151a70d3f2bc874939844289d34ce1df48a65301a61a20a5d7884eab8ba36e7b'
EXPECTED_BIN = {
    'P4': 'fabd82b305e2fe1bc4bbc0d06bdde91d05daabd7f91c70ca017f48e4617ab551',
    'P5': '47a444ebd3642dffef80364309d0b100cc048b456d75dde0b2806a7f9a052efc',
}
FROZEN_HEADERS = {
    'probe_events.h': 'a13ca7a6399ac1dbe22cb92ba8961b1a0484ce63c8449815558a4db6cd6f6487',
    'probe_config.h': 'f805e6baeb5b730e6deac0822f13dd81ca1578dd2530d0d1df60171175405b1a',
}


class InvalidSnapshot(ValueError):
    """统一错误类别，不在输出中回显本地路径、设备身份或原始字节。"""


def sha(data):
    return hashlib.sha256(data).hexdigest()


def load_layout(path):
    raw = path.read_bytes()
    if sha(raw) != LAYOUT_SHA:
        raise InvalidSnapshot('LAYOUT_SHA_MISMATCH')
    layout = json.loads(raw)
    if (layout['layout_version'] != 'C25_ARM_GCC14_2_PROBE_V2' or
            layout['endianness'] != 'little' or
            layout['variants']['P4']['types'] != layout['variants']['P5']['types']):
        raise InvalidSnapshot('LAYOUT_VERSION_OR_ABI')
    diag = ROOT / 'gateway/mqtt/tests/measurement/diagnostic'
    for name, expected in FROZEN_HEADERS.items():
        if (layout[name.replace('.', '_') + '_sha256'] != expected or
                sha((diag / name).read_bytes()) != expected):
            raise InvalidSnapshot('FROZEN_HEADER_DRIFT')
    return layout


def _u(data, offset, width):
    if offset < 0 or offset + width > len(data):
        raise InvalidSnapshot('LAYOUT_OUT_OF_BOUNDS')
    return int.from_bytes(data[offset:offset + width], 'little')


def _field(data, types, typ, field, base=0, width=4):
    return _u(data, base + types[typ]['fields'][field], width)


def _struct(data, types, typ, fields, base):
    return {name: _field(data, types, typ, name, base) for name in fields}


def decode(data, layout, variant):
    if variant not in EXPECTED_BIN:
        raise InvalidSnapshot('VARIANT')
    entry = layout['variants'][variant]
    types = entry['types']
    if len(data) != entry['probe_state_bytes'] or len(data) != types['ProbeState']['size'] or len(data) != 1264:
        raise InvalidSnapshot('SNAPSHOT_EXACT_SIZE')
    get = lambda name, width=4: _field(data, types, 'ProbeState', name, width=width)
    variant_num = int(variant[-1])
    if (get('magic') != 0xC25D1A60 or get('profile') != 0xC2500001 or
            get('variant') != variant_num or get('marker_address') != entry['marker_address'] or
            get('initialized') != 1 or get('core_hz') != 16_000_000):
        raise InvalidSnapshot('PROBE_IDENTITY_OR_CLOCK')
    if (get('clock_seq') & 1 or get('depth') != 0 or get('irq_flags') != 0 or
            get('foreground_flags') != 64 or get('dropped_observations') != 0 or
            get('unmatched_ticks') != 0 or get('tick_dropped') != get('tick_drop_base')):
        raise InvalidSnapshot('PROBE_LOSS_OR_UNSTABLE_HALT')
    if get('window_generation') < 1 or get('recovery_generation') < 1:
        raise InvalidSnapshot('GENERATION_MISSING')
    if (get('network_valid_mask') != 0x1ff or get('cache_snapshot_mask') != 3 or
            get('event_count') > 16 or (get('tick_head') - get('tick_tail')) & 0xffffffff):
        raise InvalidSnapshot('INCOMPLETE_WINDOW_OR_PENDING_TICKS')

    # 类型步长和子字段偏移都来自同一 ARM 编译器，不使用 Python 猜测的对齐规则。
    aggregate = []
    base = types['ProbeState']['fields']['aggregate']
    for scope in range(10):
        at = base + scope * types['ProbeAggregate']['size']
        values = _struct(data, types, 'ProbeAggregate',
                         ('success', 'failure', 'invalid', 'min_cycles', 'max_cycles'), at)
        values['inclusive_cycles'] = _field(data, types, 'ProbeAggregate', 'inclusive_cycles', at, 8)
        values['direct_child_cycles'] = _field(data, types, 'ProbeAggregate', 'direct_child_cycles', at, 8)
        if values['direct_child_cycles'] > values['inclusive_cycles']:
            raise InvalidSnapshot('AGGREGATE_CHILD_EXCEEDS_PARENT')
        if values['success'] + values['failure'] and values['min_cycles'] > values['max_cycles']:
            raise InvalidSnapshot('AGGREGATE_MIN_MAX')
        aggregate.append(values)
    if not aggregate[2]['success'] or not aggregate[8]['success']:
        raise InvalidSnapshot('M01_OR_M02_NO_SUCCESS_SAMPLE')

    events = []
    event_classes = set()
    base = types['ProbeState']['fields']['events']
    for index in range(get('event_count')):
        at = base + index * types['ProbeEvent']['size']
        event = _struct(data, types, 'ProbeEvent', ('scope', 'start', 'end', 'bound_ms'), at)
        scope = event['scope'] & 0xff
        outcome = event['scope'] & 0x300
        elapsed = (event['end'] - event['start']) & 0xffffffff
        if (scope >= 10 or outcome not in (0x100, 0x200) or
                event['bound_ms'] < 1 or event['bound_ms'] * 16_000 > 0xffffffff or
                elapsed > event['bound_ms'] * 16_000):
            raise InvalidSnapshot('EVENT_CATEGORY_OR_DWT_BOUND')
        if (event['scope'] in event_classes or elapsed > aggregate[scope]['max_cycles']):
            raise InvalidSnapshot('EVENT_DUPLICATE_OR_MAX_CONFLICT')
        event_classes.add(event['scope'])
        events.append(event)
    if not {0x102, 0x108}.issubset(event_classes):
        raise InvalidSnapshot('M01_OR_M02_MAX_EVENT_MISSING')

    network_base = types['ProbeState']['fields']['network_us']
    network = [_u(data, network_base + i * 8, 8) for i in range(9)]
    if any(b < a for a, b in zip(network, network[1:])) or network[-1] <= network[5]:
        raise InvalidSnapshot('NETWORK_EVENT_ORDER')
    frame = _struct(data, types, 'ProbeFrameId', ('node', 'stream', 'seq', 'epoch', 'boot'),
                    types['ProbeState']['fields']['first_business_id'])
    cache_fields = ('cache', 'lost', 'replay', 'drop')
    before = _struct(data, types, 'ProbeCache', cache_fields, types['ProbeState']['fields']['cache_before'])
    after = _struct(data, types, 'ProbeCache', cache_fields, types['ProbeState']['fields']['cache_after'])
    if (before['cache'] > 32 or after['cache'] > 32 or
            any(after[k] < before[k] for k in ('lost', 'replay', 'drop'))):
        raise InvalidSnapshot('CACHE_COUNTER_DRIFT')
    drained = get('cache_drained_observed')
    if drained not in (0, 1) or (drained and (after['cache'] or not get('replay_observed'))):
        raise InvalidSnapshot('CACHE_LAST_SNAPSHOT_CLAIM')
    heap = get('heap_peak_bytes')
    errors = get('heap_enomem_count')
    if heap > 24576 or errors < get('heap_error_base'):
        raise InvalidSnapshot('HEAP_COUNTER_DRIFT')
    live_seen, replay_seen = get('live_observed'), get('replay_observed')
    live_us, replay_us = get('first_live_us', 8), get('first_replay_us', 8)
    if (live_seen not in (0, 1) or replay_seen not in (0, 1) or
            (live_seen and not live_us) or (replay_seen and not replay_us)):
        raise InvalidSnapshot('LIVE_REPLAY_CLOCK_INCONSISTENT')
    return {'status': 'OFFLINE_BYTES_DECODED_NO_HARDWARE_ACCEPTANCE', 'variant': variant,
            'layout_version': layout['layout_version'], 'measurement_bin_sha256': EXPECTED_BIN[variant],
            'window_generation': get('window_generation'), 'recovery_generation': get('recovery_generation'),
            'clock_seq': get('clock_seq'), 'irq_flags': get('irq_flags'),
            'foreground_flags': get('foreground_flags'), 'tick_dropped_delta': 0,
            'tick_head': get('tick_head'), 'tick_tail': get('tick_tail'),
            'dropped_observations': get('dropped_observations'),
            'unmatched_ticks': get('unmatched_ticks'),
            'event_count': len(events), 'events_max_per_category_only': events,
            'aggregate': aggregate, 'network_us': network, 'first_business_id': frame,
            'cache_before': before, 'cache_after': after,
            'cache_last_snapshot_empty_observed': bool(drained),
            'cache_loss_delta': after['lost'] - before['lost'],
            'first_live_us': live_us if live_seen else None,
            'first_replay_us': replay_us if replay_seen else None,
            'boundary_skipped_ticks': get('boundary_skipped_ticks'),
            'heap_peak_bytes': heap, 'heap_enomem_total': errors,
            'heap_enomem_delta': errors - get('heap_error_base'),
            'M03': 'PARTIAL_CPU_PURE_NOT_MEASURED', 'M04': 'BLOCKED_UNSAFE_SENTINEL',
            'H16_acceptance': 'NOT_GRANTED'}


def verify_pair(first_path, second_path, layout, variant):
    if first_path.resolve() == second_path.resolve():
        raise InvalidSnapshot('INDEPENDENT_FILES_REQUIRED')
    for path in (first_path, second_path):
        if not path.is_file() or path.is_symlink():
            raise InvalidSnapshot('REGULAR_SNAPSHOT_FILE_REQUIRED')
    first, second = first_path.read_bytes(), second_path.read_bytes()
    if len(first) != 1264 or len(second) != 1264 or sha(first) != sha(second):
        raise InvalidSnapshot('RAW_SNAPSHOT_BYTES_DISAGREE')
    result = decode(first, layout, variant)
    # 解码期间文件若被其它进程改写，不能把首次读取的SHA当成已持久化证据。
    if sha(first_path.read_bytes()) != sha(first) or sha(second_path.read_bytes()) != sha(second):
        raise InvalidSnapshot('FILE_CHANGED_DURING_VERIFY')
    result['raw_snapshot_sha256'] = sha(first)
    result['raw_snapshot_bytes'] = len(first)
    result['independent_file_pair_verified'] = True
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('variant', choices=('P4', 'P5'))
    parser.add_argument('layout', type=Path)
    parser.add_argument('read1', type=Path)
    parser.add_argument('read2', type=Path)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    try:
        # CLI 只接受工作树内的本地文件；原始冻结字节放忽略 build，输出独占创建。
        for path in (args.layout, args.read1, args.read2, *([args.output] if args.output else [])):
            if str(path).startswith(('\\\\', '//')) or not path.resolve().is_relative_to(ROOT):
                raise InvalidSnapshot('LOCAL_WORKSPACE_PATH_REQUIRED')
        result = verify_pair(args.read1, args.read2, load_layout(args.layout), args.variant)
        content = json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + '\n'
        if args.output:
            with args.output.open('x', encoding='utf-8') as stream:
                stream.write(content)
        else:
            print(content, end='')
        return 0
    except (OSError, UnicodeError, json.JSONDecodeError, KeyError, InvalidSnapshot):
        print(json.dumps({'status': 'INVALID_OFFLINE_SNAPSHOT', 'H16_acceptance': 'NOT_GRANTED'}))
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
