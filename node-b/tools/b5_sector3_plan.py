"""B5 sector3纯离线编制：只产EFS字节计划，没有任何实板写入入口。"""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import zlib

import b4_recovery as recovery

CURRENT_FULL_SHA = 'b460d917e1d454fdb0882d1f837d91c606363179b817a3896a1df6897b2dcb98'
APP_BYTES = 42552
APP_SHA = 'd5b9624b3da1129b4e045d3b2f669c00d2d93cb7379b15293ff143fe9f130683'
START, END, RECORD_BYTES = 49152, 65536, 336
FIELDS = (('ssid', 8, 33), ('wifi_password', 41, 65), ('host', 106, 65),
          ('username', 171, 33), ('password', 204, 65), ('client_id', 269, 41))


def require(ok, reason):
    if not ok: raise ValueError(reason)


def sha(blob): return hashlib.sha256(blob).hexdigest()


def field_bytes(value, size, required=True):
    require(isinstance(value, (str, bytes)), 'FIELD_TYPE')
    data = value.encode('utf8') if isinstance(value, str) else value
    require((bool(data) or not required) and len(data) < size, 'FIELD_LENGTH')
    require(all(b >= 32 and b not in (34, 92) for b in data), 'FIELD_AT_CHARACTER')
    return data


def record_crc(record): return zlib.crc32(record[:16]+record[24:RECORD_BYTES])


def parse_record(record):
    require(len(record) == RECORD_BYTES, 'RECORD_SIZE')
    record = bytes(record)
    magic, version, header, size, generation, crc, committed = struct.unpack_from('<IHHIIII', record)
    require((magic, version, header, size) == (0x32433348, 1, 24, 312), 'RECORD_HEADER')
    require(generation != 0 and committed == 0x54494D43, 'RECORD_UNCOMMITTED_OR_ZERO_GENERATION')
    require(record_crc(record) == crc, 'RECORD_CRC')
    payload = record[24:]
    pmagic, minimum_epoch = struct.unpack_from('<II', payload)
    require(pmagic == 0x31435747 and minimum_epoch >= 1700000000, 'PAYLOAD_HEADER')
    values = {}
    for key, offset, width in FIELDS:
        data = payload[offset:offset+width]
        require(b'\0' in data, 'FIELD_NOT_TERMINATED')
        values[key] = field_bytes(data.split(b'\0', 1)[0], width, key != 'wifi_password')
    return generation, minimum_epoch, values


def make_record(original_record, mqtt, minimum_epoch=None):
    old_generation, old_epoch, old = parse_record(original_record)
    require(old_generation < 0xffffffff, 'GENERATION_OVERFLOW')
    require(isinstance(mqtt, dict), 'MQTT_OBJECT')
    require(mqtt.get('gateway_id') == 'GW-B5-001' and mqtt.get('username') == 'b5-gateway'
            and mqtt.get('client_id') == 'b5-c-isolated', 'B5_IDENTITY')
    require(type(mqtt.get('port')) is int and mqtt['port'] == 8883, 'B5_TLS_PORT')
    require(mqtt.get('tls_insecure', False) is False and mqtt.get('validate_certificate', True) is True,
            'B5_TLS_VALIDATION_REQUIRED')
    epoch = old_epoch if minimum_epoch is None else minimum_epoch
    require(type(epoch) is int and old_epoch <= epoch <= 0xffffffff, 'MINIMUM_EPOCH')
    # 重新构造完整payload，只在内存复用原SSID/WiFi密码；不就地修改旧record。
    values = {'ssid': old['ssid'], 'wifi_password': old['wifi_password']}
    for key in ('host', 'username', 'password', 'client_id'): values[key] = mqtt.get(key)
    payload = bytearray(312)
    struct.pack_into('<II', payload, 0, 0x31435747, epoch)
    for key, offset, width in FIELDS:
        data = field_bytes(values[key], width, key != 'wifi_password')
        payload[offset:offset+len(data)] = data
    record = bytearray(24) + payload
    struct.pack_into('<IHHIIII', record, 0, 0x32433348, 1, 24, 312, old_generation+1, 0, 0x54494D43)
    struct.pack_into('<I', record, 16, record_crc(record))
    parse_record(record)
    uncommitted = record[:]; uncommitted[20:24] = b'\xff'*4
    return bytes(record), bytes(uncommitted), old_generation, old_generation+1


def build_plan(original_full, app_installed_full, mqtt, minimum_epoch=None):
    require(len(original_full) == len(app_installed_full) == 1048576, 'FULL_SIZE')
    require(sha(original_full) == CURRENT_FULL_SHA, 'ORIGINAL_C24104_SHA')
    require(sha(app_installed_full[:APP_BYTES]) == APP_SHA, 'B5_42552_APPLICATION_SHA')
    require(app_installed_full[APP_BYTES:] == original_full[APP_BYTES:], 'APPLICATION_TAIL_OR_PROTECTED_REGION_DRIFT')
    original_sector = original_full[START:END]
    record, uncommitted, old_gen, new_gen = make_record(original_sector[:RECORD_BYTES], mqtt, minimum_epoch)
    final_sector = record + original_sector[RECORD_BYTES:]
    precommit_sector = uncommitted + original_sector[RECORD_BYTES:]
    final_full = app_installed_full[:START] + final_sector + app_installed_full[END:]
    precommit_full = app_installed_full[:START] + precommit_sector + app_installed_full[END:]
    # R-APP和R-CFG是分别批准的事务，两个中间组合不能冒充完整恢复。
    app_restore_first = original_full[:START] + final_full[START:]
    config_restore_first = final_full[:START] + original_sector + final_full[END:]
    app_then_config = app_restore_first[:START] + original_sector + app_restore_first[END:]
    config_then_app = original_full[:START] + config_restore_first[START:]
    require(app_then_config == config_then_app == original_full, 'RESTORE_COMBINATION_MISMATCH')
    files = {'sector3-original-private.bin': original_sector,
             'sector3-uncommitted-private.bin': precommit_sector,
             'sector3-committed-private.bin': final_sector,
             'record336-committed-private.bin': record,
             'record336-uncommitted-private.bin': uncommitted,
             'expected-full-uncommitted-private.bin': precommit_full,
             'expected-full-B5-new-config-private.bin': final_full,
             'expected-full-R-APP-only-private.bin': app_restore_first,
             'expected-full-R-CFG-only-private.bin': config_restore_first,
             'expected-full-fully-restored-private.bin': original_full}
    manifest = {'schema': 'B5_SECTOR3_OFFLINE_PLAN_V1', 'hardware_execution_enabled': False,
        'physical_writer': 'NOT_IMPLEMENTED_NOT_AUTHORIZED', 'target_writes': 0,
        'source_acquisition_claim': 'BYTE_PLANNING_ONLY_BIND_FRESH_READBACK_SEPARATELY',
        'gateway_id': 'GW-B5-001', 'username': 'b5-gateway', 'client_id': 'b5-c-isolated', 'MQTT_TLS_port': 8883,
        'sector_range': [0x0800c000, 0x08010000], 'record_bytes': RECORD_BYTES,
        'sector_bytes': END-START, 'preserved_tail_bytes': END-START-RECORD_BYTES,
        'committed_write_offset': 20, 'committed_write_bytes': 4,
        'generation_from': old_gen, 'generation_to': new_gen, 'CRC_skips_offsets_16_through_23': True,
        'original_full_sha256': sha(original_full), 'app_installed_full_sha256': sha(app_installed_full),
        'both_restore_orders_equal_original': True, 'sector7_11_and_options_write_allowed': False,
        'TLS_CA_SNI_module_readiness': 'SEPARATE_HARDWARE_GATE_NOT_PROVEN_BY_RECORD',
        'files': {name: {'bytes': len(blob), 'sha256': sha(blob)} for name, blob in files.items()}}
    return manifest, files


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('original-full', 'app-installed-full', 'mqtt-private-json', 'out'):
        parser.add_argument('--'+name, required=True, type=Path)
    parser.add_argument('--minimum-epoch', type=int)
    args = parser.parse_args()
    try:
        original = recovery.read(args.original_full, False)
        installed = recovery.read(args.app_installed_full, False)
        mqtt = json.loads(recovery.read(args.mqtt_private_json, False))
        manifest, files = build_plan(original, installed, mqtt, args.minimum_epoch)
        recovery.protected(args.out.parent, False); args.out.mkdir(exist_ok=False)
        for name, blob in files.items():
            with (args.out/name).open('xb') as f: f.write(blob)
            recovery.protected(args.out/name, False)
            require((args.out/name).read_bytes() == blob, 'DISK_VERIFY')
        encoded = recovery.encoded(manifest)
        with (args.out/'manifest-private.json').open('xb') as f: f.write(encoded)
        recovery.protected(args.out/'manifest-private.json', False)
        print(json.dumps({'status': 'OFFLINE_PLAN_ONLY_NOT_AUTHORIZED_FOR_WRITE',
                          'manifest_sha256': sha(encoded), 'hardware_execution_enabled': False,
                          'target_writes': 0, 'physical_writer': 'NOT_IMPLEMENTED_NOT_AUTHORIZED'})); return 0
    except BaseException as error:
        # 不打印异常值、路径或输入JSON；配置原文始终留EFS。
        print(json.dumps({'status': 'STOP', 'error_type': type(error).__name__, 'target_writes': 0})); return 1


if __name__ == '__main__': raise SystemExit(main())
