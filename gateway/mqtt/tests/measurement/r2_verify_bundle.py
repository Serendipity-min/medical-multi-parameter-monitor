"""将脱机事件链、两份原始快照与逐轮索引绑定；不会连接设备或授予 C3A。"""

import argparse
import json
from pathlib import Path

from r1_snapshot_index import InvalidIndex, validate_index
from r2_snapshot_bytes import ROOT, InvalidSnapshot, load_layout, verify_pair


BUILD = ROOT / 'gateway/mqtt/build/h16-diagnostic'


def _snapshot_path(relative):
    if not isinstance(relative, str) or not relative or relative.startswith(('\\\\', '//')):
        raise InvalidSnapshot('LOCAL_SNAPSHOT_PATH_REQUIRED')
    path = (ROOT / relative).resolve()
    if not path.is_relative_to(BUILD.resolve()):
        raise InvalidSnapshot('SNAPSHOT_OUTSIDE_IGNORED_BUILD')
    return path


def verify_bundle(index, event_log, bundle, layout):
    chronology = validate_index(index, event_log)
    if (not isinstance(bundle, dict) or set(bundle) != {'schema_version', 'kind', 'snapshots'} or
            type(bundle['schema_version']) is not int or bundle['schema_version'] != 1 or
            bundle['kind'] not in ('SYNTHETIC_R2_BUNDLE', 'REDACTED_LOCAL_SNAPSHOT_BUNDLE') or
            not isinstance(bundle['snapshots'], list) or len(bundle['snapshots']) != 6):
        raise InvalidSnapshot('BUNDLE_SCHEMA')
    decoded = []
    previous = {'P4': None, 'P5': None}
    for manifest, entry in zip(index['runs'], bundle['snapshots']):
        if not isinstance(entry, dict) or set(entry) != {'run_id', 'read1', 'read2'}:
            raise InvalidSnapshot('BUNDLE_ENTRY_SCHEMA')
        if entry['run_id'] != manifest['run_id']:
            raise InvalidSnapshot('BUNDLE_RUN_ORDER')
        first, second = _snapshot_path(entry['read1']), _snapshot_path(entry['read2'])
        result = verify_pair(first, second, layout, manifest['variant'])
        if (result['raw_snapshot_sha256'] != manifest['snapshot_sha_first'] or
                result['raw_snapshot_sha256'] != manifest['snapshot_sha_second'] or
                result['raw_snapshot_bytes'] != manifest['snapshot_bytes'] or
                result['window_generation'] != manifest['window_generation'] or
                result['recovery_generation'] != manifest['recovery_generation'] or
                result['clock_seq'] != manifest['clock_seq'] or
                result['irq_flags'] != manifest['irq_flags'] or
                result['foreground_flags'] != manifest['foreground_flags'] or
                result['tick_dropped_delta'] != manifest['tick_dropped_delta'] or
                result['dropped_observations'] != manifest['dropped_observations'] or
                result['unmatched_ticks'] != manifest['unmatched_ticks']):
            raise InvalidSnapshot('INDEX_RAW_BYTES_MISMATCH')
        prior = previous[manifest['variant']]
        if prior is not None:
            if (result['heap_peak_bytes'] < prior['heap_peak_bytes'] or
                    result['heap_enomem_total'] < prior['heap_enomem_total'] or
                    any(result['cache_before'][name] < prior['cache_after'][name]
                        for name in ('lost', 'replay', 'drop'))):
                raise InvalidSnapshot('CROSS_WINDOW_COUNTER_REGRESSION')
        previous[manifest['variant']] = result
        # 输出仅含脱敏计数与文件SHA；不包含原始RAM、地址、路径或配置。
        decoded.append({'run_id': entry['run_id'], 'variant': result['variant'],
                        'raw_snapshot_sha256': result['raw_snapshot_sha256'],
                        'window_generation': result['window_generation'],
                        'recovery_generation': result['recovery_generation'],
                        'heap_peak_bytes': result['heap_peak_bytes'],
                        'cache_loss_delta': result['cache_loss_delta'],
                        'network_us': result['network_us'],
                        'M01_qos1_success_count': result['aggregate'][2]['success'],
                        'M02_service_success_count': result['aggregate'][8]['success'],
                        'M03': result['M03'], 'M04': result['M04']})
    return {'status': 'OFFLINE_BYTE_AND_ORDER_CHAIN_VERIFIED', 'runs': decoded,
            'event_order_evidence': chronology['order_evidence'],
            'physical_source_verified': False, 'observer_environment_verified': False,
            'IPSR_verified': False, 'DWT_continuity_verified': False,
            'H16_acceptance': 'NOT_GRANTED', 'C3A_entry': 'HOLD'}


def _unique_object(pairs):
    result = {}
    for name, value in pairs:
        if name in result:
            raise InvalidSnapshot('DUPLICATE_JSON_KEY')
        result[name] = value
    return result


def _read_json(path):
    if (str(path).startswith(('\\\\', '//')) or path.suffix.lower() != '.json' or
            not path.resolve().is_relative_to(ROOT) or not path.is_file() or
            path.stat().st_size > 1_048_576):
        raise InvalidSnapshot('LOCAL_JSON_REQUIRED')
    return json.loads(path.read_text(encoding='utf-8'), object_pairs_hook=_unique_object,
                      parse_constant=lambda _: (_ for _ in ()).throw(InvalidSnapshot('NONFINITE_JSON')))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('index', type=Path)
    parser.add_argument('event_log', type=Path)
    parser.add_argument('bundle', type=Path)
    parser.add_argument('layout', type=Path)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    try:
        for path in (args.layout, *([args.output] if args.output else [])):
            if str(path).startswith(('\\\\', '//')) or not path.resolve().is_relative_to(ROOT):
                raise InvalidSnapshot('LOCAL_WORKSPACE_PATH_REQUIRED')
        result = verify_bundle(_read_json(args.index), _read_json(args.event_log),
                               _read_json(args.bundle), load_layout(args.layout))
        content = json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + '\n'
        if args.output:
            # 独占创建，使任何旧轮次摘要不能被本次结果覆盖。
            with args.output.open('x', encoding='utf-8') as stream:
                stream.write(content)
        else:
            print(content, end='')
        return 0
    except (OSError, UnicodeError, json.JSONDecodeError, KeyError, InvalidIndex, InvalidSnapshot):
        print(json.dumps({'status': 'INVALID_OFFLINE_BUNDLE', 'H16_acceptance': 'NOT_GRANTED'}))
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
