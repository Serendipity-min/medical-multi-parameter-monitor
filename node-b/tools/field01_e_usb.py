"""FIELD01 E 板串口ROM下载；只写固定M1应用的sector0/1，不解保护或整片擦除。"""
import argparse
import hashlib
import json
from pathlib import Path
import sys

import b4_recovery as package

ROOT = Path(__file__).resolve().parents[2]
BASE = 0x08000000
APP_END = 32768
FLASH_SIZE = 1048576
E_SHA = 'b141262059fad511bff9a05b7c682580fdacda19d954a74b80809f0b464a6867'
need = package.require


def image(path=None, expected_sha=None):
    need((path is None) == (expected_sha is None), 'E_IMAGE_AND_SHA_REQUIRED_TOGETHER')
    frozen = path is None
    path = path or ROOT / 'node-b/docs/FIVE-NODE-MIGRATION/M1-20261104/artifacts/E/FIVE_NODE_E.bin'
    data = path.read_bytes()
    need((len(data) == 29416 if frozen else 16384 < len(data) <= APP_END)
         and package.digest(data) == (E_SHA if frozen else expected_sha), 'E_FIXED_IMAGE_DRIFT')
    package.vector_check(data)
    return data


def identity(boot):
    version = boot.get()
    chip = boot.get_id()
    need(chip == 0x413, 'E_NOT_F407')
    size, uid = boot.get_flash_size_and_uid()
    need(size == 1024 and len(uid) == 12 and bytes(uid) not in (b'\0'*12, b'\xff'*12), 'E_CAPACITY_OR_UID')
    return dict(device_id=chip, capacity_kib=size, uid_hex=bytes(uid).hex(), rom_version=version)


def read_exact(boot, address, length):
    data = bytes(boot.read_memory_data(address, length))
    need(len(data) == length, 'E_ROM_SHORT_READ')
    return data


def outside_digest(boot):
    digest = hashlib.sha256()
    for offset in range(APP_END, FLASH_SIZE, 32768):
        digest.update(read_exact(boot, BASE + offset, min(32768, FLASH_SIZE-offset)))
    return digest.hexdigest()


def install(boot, candidate, expected, journal):
    candidate_sha = package.digest(candidate)
    seen = identity(boot)
    need(seen == expected, 'E_IDENTITY_DRIFT_BEFORE_ERASE')
    need(boot.extended_erase, 'E_EXTENDED_SECTOR_ERASE_REQUIRED')
    options = read_exact(boot, 0x1fffc000, 16)
    need(options[1] == 0xaa, 'E_RDP_NOT_ZERO_NO_UNLOCK')
    app = read_exact(boot, BASE, APP_END)
    outside = outside_digest(boot)
    journal('before-fingerprints-private.json', dict(outside_sha256=outside,
        options_sha256=package.digest(options), application_backup_saved=False))
    payload = candidate + app[len(candidate):]
    journal('program-intent-private.json', dict(board='E', address=BASE, sectors=[0, 1],
        candidate_bytes=len(candidate), candidate_sha256=candidate_sha, payload_sha256=package.digest(payload)))
    boot.extended_erase_memory([0, 1])
    boot.write_memory_data(BASE, payload)
    need(read_exact(boot, BASE, APP_END) == payload, 'E_APPLICATION_READBACK_MISMATCH')
    need(outside_digest(boot) == outside, 'E_OUTSIDE_SECTORS_CHANGED')
    need(read_exact(boot, 0x1fffc000, 16) == options, 'E_OPTIONS_CHANGED')
    need(identity(boot) == seen, 'E_IDENTITY_DRIFT_AFTER_WRITE')
    return dict(status='E_M1_SECTOR01_ROM_FULL_VERIFY_PASS', board='E', candidate_bytes=len(candidate),
        candidate_sha256=candidate_sha, sectors=[0, 1], outside_affected_sectors_unchanged=True,
        options_unchanged=True, local_sensor_screen_status='NOT_RUN')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    action = p.add_mutually_exclusive_group()
    action.add_argument('--identify', action='store_true', help='会复位进入ROM；不擦除，不启动原程序')
    action.add_argument('--install', action='store_true')
    p.add_argument('--port')
    p.add_argument('--out', type=Path)
    p.add_argument('--reference-identity', type=Path)
    p.add_argument('--image', type=Path)
    p.add_argument('--image-sha256')
    p.add_argument('--known-identity', action='append', type=Path, default=[])
    a = p.parse_args()
    candidate = image(a.image, a.image_sha256)
    if not (a.identify or a.install):
        print(json.dumps(dict(status='PLAN_ONLY_NO_PORT_OPENED', board='E', bytes=len(candidate),
            sha256=package.digest(candidate), sectors=[0, 1], mass_erase=False, options_write=False)))
        return 0
    need(a.port and a.out and len(a.known_identity) == 4, 'E_PORT_PRIVATE_OUTPUT_AND_FOUR_KNOWN_BOARDS_REQUIRED')
    package.protected(a.out.parent, False)
    need(not a.out.exists(), 'E_NEW_OUTPUT_REQUIRED')
    excluded = {json.loads(package.read(f, False))['uid_hex'] for f in a.known_identity}
    need(len(excluded) == 4, 'E_KNOWN_IDENTITIES_NOT_DISTINCT')
    expected = json.loads(package.read(a.reference_identity, False)) if a.install else None
    need(not a.install or expected['uid_hex'] not in excluded, 'E_REFERENCE_IS_OTHER_BOARD')
    a.out.mkdir()
    def journal(name, value):
        (a.out / name).write_text(json.dumps(value, indent=2), encoding='utf-8')
    from stm32loader.main import SerialConnection
    from stm32loader.bootloader import Stm32Bootloader
    connection = SerialConnection(a.port, 115200, 'E')
    connection.reset_active_high = True
    connection.boot0_active_low = True
    boot = Stm32Bootloader(connection, device_family='F4', verbosity=0)
    result = dict(board='E', status='STOP_TARGET', exit_code=1, automatic_retry_or_restore=False)
    try:
        connection.connect()
        connection.timeout = 3
        boot.reset_from_system_memory()
        seen = identity(boot)
        journal('identity-private.json', seen)
        need(seen['uid_hex'] not in excluded, 'E_ROUTE_IS_KNOWN_A_B_C_D')
        if a.install:
            result.update(install(boot, candidate, expected, journal))
            boot.reset_from_flash()
            result.update(exit_code=0, reset_to_flash_performed=True, application_running_status='NOT_YET_OBSERVED')
        else:
            result.update(status='E_ROM_IDENTIFIED_NO_ERASE', exit_code=0, reset_to_flash_performed=False)
    except (Exception, KeyboardInterrupt) as error:
        journal('failure-private.json', dict(type=type(error).__name__, reason=str(error)))
        result.update(status='STOP_TARGET', exit_code=1, error_type=type(error).__name__)
    finally:
        connection.disconnect()
        journal('receipt-private.json', result)
    print(json.dumps(result))
    return result['exit_code']


if __name__ == '__main__':
    sys.exit(main())
