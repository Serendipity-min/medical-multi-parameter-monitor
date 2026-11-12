"""只从受限原件离线编制B5配置包；无串口、DLL、网络或实板入口。"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import time

import b4_recovery as recovery
import b5_sector3_plan as planner

ROOT = Path(__file__).resolve().parents[2]
ELF_SHA = '3c726f61f76eadac4909826203ca84dee65521aec448ad477ddca0c3c58795d8'
SYMBOL_SHA = 'fbf88b80076b6b508cc49b225067e9daf775d9c1c9ffeaeb559f9100ac365716'


def sha(b): return hashlib.sha256(b).hexdigest()


def prepare(out):
    recovery.protected(out.parent, False)
    recovery.require(not out.exists(), 'OUTPUT_EXISTS')
    source = json.loads((ROOT/'node-b/build/b5-fresh-install-restore-pointer.json').read_bytes())
    g1ref = json.loads((ROOT/'node-b/build/b5-g1-private-pointer.json').read_bytes())
    g1 = Path(g1ref['base'])
    old_m, old = recovery.load_package(Path(source['package']), source['manifest_sha256'], False)
    acquisition = json.loads(recovery.read(Path(source['package'])/'fresh-read-binding-private.json', False))
    recovery.require(sha(recovery.read(Path(source['package'])/'fresh-read-binding-private.json', False)) ==
                     source['fresh_binding_sha256'], 'SOURCE_ACQUISITION_BINDING')
    recovery.require(acquisition['independent_flash_API_reads'] == acquisition['independent_options_API_reads'] == 2,
                     'SOURCE_NOT_DOUBLE_READ')
    data = recovery.read(g1/g1ref['package'], False)
    g1package = json.loads(data)
    accepted = json.loads((ROOT/'node-b/evidence/B5-G1/execution-summary.json').read_bytes())
    recovery.require(sha(data) == accepted['package_sha256'] and accepted['status'] ==
                     'PASS_CLOUD_ADMISSION_ONLY_NOT_DEVICE_E2E', 'G1_SOURCE_NOT_APPROVED')
    creds_blob = recovery.read(g1/'test-credentials-private.json', False)
    creds = json.loads(creds_blob)
    mqtt = {'gateway_id': 'GW-B5-001', 'username': 'b5-gateway', 'client_id': 'b5-c-isolated',
            'host': g1package['snapshot']['backend']['host'], 'port': 8883,
            'password': creds['passwords']['b5-gateway'], 'validate_certificate': True, 'tls_insecure': False}
    original, app = old['before-full-private.bin'], old['expected-full-private.bin']
    _, old_floor, _ = planner.parse_record(original[49152:49488])
    # 这是配置接受的纪元下界，不是授时，也不改变设备时钟。
    floor = max(old_floor, int(time.time())-86400)
    plan, files = planner.build_plan(original, app, mqtt, floor)
    files.update({'original-full-private.bin': original, 'app-before-private.bin': app,
                  'options-private.bin': old['options-private.bin'],
                  'identity-private.json': old['identity-private.json']})
    files['manifest-private.json'] = recovery.encoded(plan)
    binding = {'schema': 'B5_SECTOR3_BOUND_PACKAGE_V1',
        'plan_manifest_sha256': sha(files['manifest-private.json']),
        'files': {n: {'bytes': len(b), 'sha256': sha(b)} for n, b in files.items()},
        'source_fresh_read_binding_sha256': source['fresh_binding_sha256'],
        'source_acquisition_date': '2026-10-26_CHECKPOINT_NOT_TODAY_READBACK',
        'source_original_full_sha256': sha(original), 'source_app_full_sha256': sha(app),
        'source_G1_tx': accepted['tx'], 'source_G1_package_sha256': sha(data),
        'source_G1_credentials_file_sha256': sha(creds_blob),
        'minimum_epoch': floor, 'minimum_epoch_source': 'LOCAL_UTC_MINUS_86400_FLOOR_NOT_TIME_SYNC',
        'generation_from': plan['generation_from'], 'generation_to': plan['generation_to'],
        'gateway_id': 'GW-B5-001', 'username': 'b5-gateway', 'client_id': 'b5-c-isolated', 'port': 8883,
        'runtime_state': {'address': 0x20001918, 'bytes': 4, 'disarmed_expected_hex': '00000000',
                          'ELF_sha256': ELF_SHA, 'symbols_sha256': SYMBOL_SHA},
        'hardware_execution_enabled': False, 'latest_power_state_recheck_required': True,
        'real_record_generated': True, 'target_writes': 0,
        'created_utc': datetime.now(timezone.utc).isoformat(),
        'planner_sha256': sha((ROOT/'node-b/tools/b5_sector3_plan.py').read_bytes()),
        'builder_sha256': sha(Path(__file__).read_bytes()),
        'restore_order_for_execution': 'R_CFG_FIRST_THEN_SEPARATELY_AUTHORIZED_R_APP',
        'plan_physical_writer_label': 'FROZEN_PLANNER_HAS_NO_HARDWARE_ENTRY_CAPABILITY_SEPARATE'}
    out.mkdir(exist_ok=False)
    for name, blob in files.items():
        with (out/name).open('xb') as stream: stream.write(blob)
        recovery.protected(out/name, False)
        recovery.require((out/name).read_bytes() == blob, 'OUTPUT_DISK_VERIFY')
    raw = recovery.encoded(binding)
    with (out/'binding-private.json').open('xb') as stream: stream.write(raw)
    recovery.protected(out/'binding-private.json', False)
    return {'scope': 'G2B_REAL_CONFIG_OFFLINE_ONLY_NO_TARGET_IO', 'status': 'REAL_CONFIG_PACKAGE_PREPARED',
        'package_binding_sha256': sha(raw), 'plan_manifest_sha256': binding['plan_manifest_sha256'],
        'candidate_BIN_bytes': 42552, 'candidate_BIN_sha256': planner.APP_SHA,
        'record336_sha256': sha(files['record336-committed-private.bin']),
        'sector3_original_sha256': sha(files['sector3-original-private.bin']),
        'sector3_uncommitted_sha256': sha(files['sector3-uncommitted-private.bin']),
        'sector3_committed_sha256': sha(files['sector3-committed-private.bin']),
        'before_config_full_sha256': sha(app),
        'uncommitted_full_sha256': sha(files['expected-full-uncommitted-private.bin']),
        'after_config_full_sha256': sha(files['expected-full-B5-new-config-private.bin']),
        'R_CFG_only_full_sha256': sha(files['expected-full-R-CFG-only-private.bin']),
        'R_APP_only_full_sha256': sha(files['expected-full-R-APP-only-private.bin']),
        'fully_restored_full_sha256': sha(original),
        'generation_from': binding['generation_from'], 'generation_to': binding['generation_to'],
        'record_bytes': 336, 'sector_bytes': 16384, 'tail_preserved_bytes': 16048,
        'hardware_execution_enabled': False, 'target_writes': 0, 'DLL_loaded': False,
        'latest_power_state_recheck_required': True, 'source_checkpoint_date': '2026-10-26',
        'builder_sha256': binding['builder_sha256'], 'exit_code': 0}


def formal_plan(current, mqtt):
    planner.require(len(current) == 1048576, 'FULL_SIZE')
    start, end = planner.START, planner.END
    original = current[start:end]
    record, uncommitted, old, new = planner.make_record(
        original[:planner.RECORD_BYTES], mqtt, formal_cloud=True)
    tail = original[planner.RECORD_BYTES:]
    before, after = current[:start], current[end:]
    files = {'sector3-original-private.bin': original,
             'sector3-uncommitted-private.bin': uncommitted + tail,
             'sector3-committed-private.bin': record + tail,
             'expected-full-uncommitted-private.bin': before + uncommitted + tail + after,
             'expected-full-committed-private.bin': before + record + tail + after}
    gateway_id, username, client_id = planner.FORMAL_IDENTITY
    manifest = {'schema': 'WP_AY0_FORMAL_SECTOR3_OFFLINE_V1',
                'source_full_sha256': sha(current), 'source_board_readback_verified': False,
                'gateway_id': gateway_id, 'username': username, 'client_id': client_id,
                'tls_port': 8883, 'sector_range': [0x0800c000, 0x08010000],
                'generation_from': old, 'generation_to': new, 'commit_offset': 20,
                'preserved_tail_bytes': len(tail), 'hardware_execution_enabled': False,
                'target_writes': 0, 'files': {name: {'bytes': len(blob), 'sha256': sha(blob)}
                                              for name, blob in files.items()}}
    return manifest, files


def prepare_formal(out, current_full, mqtt_private_json):
    recovery.protected(out.parent, False)
    current = recovery.read(current_full, False)
    mqtt = json.loads(recovery.read(mqtt_private_json, False))
    manifest, files = formal_plan(current, mqtt)
    files['manifest-private.json'] = recovery.encoded(manifest)
    out.mkdir(exist_ok=False)
    for name, data in files.items():
        path = out / name
        with path.open('xb') as stream:
            stream.write(data)
        recovery.require(recovery.read(path, False) == data, 'OUTPUT_DISK_VERIFY')
    return {'status': 'FORMAL_OFFLINE_PLAN_ONLY', 'manifest_sha256': sha(files['manifest-private.json']),
            'target_writes': 0, 'DLL_loaded': False, 'exit_code': 0}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', required=True, type=Path)
    parser.add_argument('--formal-cloud', action='store_true')
    parser.add_argument('--current-full', type=Path)
    parser.add_argument('--mqtt-private-json', type=Path)
    args = parser.parse_args()
    if args.formal_cloud:
        if not (args.current_full and args.mqtt_private_json):
            parser.error('--formal-cloud requires --current-full and --mqtt-private-json')
    elif args.current_full or args.mqtt_private_json:
        parser.error('--current-full and --mqtt-private-json require --formal-cloud')
    try:
        result = (prepare_formal(args.out, args.current_full, args.mqtt_private_json)
                  if args.formal_cloud else prepare(args.out))
    except Exception as error:
        result = {'status': 'STOP_OFFLINE_PREPARATION', 'error_type': type(error).__name__,
                  'target_writes': 0, 'DLL_loaded': False, 'exit_code': 1}
    print(json.dumps(result)); return result['exit_code']


if __name__ == '__main__': raise SystemExit(main())
