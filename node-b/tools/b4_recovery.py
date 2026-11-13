"""B4配套离线备份一致性、扇区安装/回退包与完整镜像核验；没有硬件入口。"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
PRIVATE = Path('E:/medical-monitor-node-b-precan-private/20261023')
FLASH_BASE, FLASH_SIZE, APP_LIMIT = 0x08000000, 1048576, 49152
SECTOR_ENDS = (16384, 32768, 49152)
SYNTHETIC_UID = '5a' * 12
MARKER = b'SYNTHETIC_B4_FIXTURE'
FILES = ('before-full-private.bin', 'options-private.bin', 'identity-private.json',
         'candidate-private.bin', 'install-sectors-private.bin', 'restore-sectors-private.bin',
         'expected-full-private.bin')


def require(ok, reason):
    if not ok:
        raise ValueError(reason)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def encoded(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + '\n').encode('utf-8')


def protected(path, synthetic):
    p = Path(path).resolve(strict=True)
    if synthetic:
        require(p.is_relative_to((ROOT / 'node-b/build').resolve()), 'SYNTHETIC_PATH_OUTSIDE_BUILD')
    else:
        # 实际整片/身份/配置只能在既有受限EFS根目录内，不让CLI另存到仓库。
        require(p.is_relative_to(PRIVATE.resolve()) and os.name == 'nt', 'PRIVATE_PATH_REQUIRED')
        import ctypes
        attrs = ctypes.windll.kernel32.GetFileAttributesW
        attrs.restype = ctypes.c_uint32
        value = attrs(str(p))
        require(value != 0xffffffff and value & 0x4000, 'EFS_REQUIRED')
    return p


def read(path, synthetic):
    return protected(path, synthetic).read_bytes()


def identity_check(value):
    require(value.get('device_id', 0) & 0xfff == 0x413, 'DEVICE_NOT_F407')
    require(value.get('cpuid', 0) >> 4 & 0xfff == 0xc24, 'CORE_NOT_M4')
    require(value.get('capacity_kib') == 1024, 'FLASH_NOT_1M')
    uid = value.get('uid_hex', '')
    require(isinstance(uid, str) and len(uid) == 24, 'UID_FORMAT')
    try:
        raw = bytes.fromhex(uid)
    except ValueError:
        raise ValueError('UID_FORMAT') from None
    require(len(raw) == 12 and uid not in ('00' * 12, 'ff' * 12), 'UID_INVALID')
    require(value.get('optcr', 0) >> 8 & 255 == 0xaa, 'RDP_NOT_ZERO_NO_UNLOCK')
    require(value.get('flash_sr', 0) & 0x100f2 == 0, 'FLASH_BUSY_OR_ERROR')


def vector_check(image):
    require(8 <= len(image) <= APP_LIMIT, 'IMAGE_EXCEEDS_REVIEWED_48K_APP_REGION')
    sp, pc = int.from_bytes(image[:4], 'little'), int.from_bytes(image[4:8], 'little')
    ram = 0x20000000 < sp <= 0x20020000 or 0x10000000 < sp <= 0x10010000
    require(ram and sp % 8 == 0, 'INVALID_STACK_VECTOR')
    require(pc & 1 and FLASH_BASE <= (pc & ~1) < FLASH_BASE + len(image), 'INVALID_FLASH_RESET_VECTOR')


def make_plan(board, flash_a, flash_b, options_a, options_b, identity_a, identity_b,
              candidate, candidate_sha, synthetic=False):
    """纯字节规划，可在离线测试注入负例；不把一致文件视为已完成真实双读采集。"""
    require(board in ('B', 'C'), 'BOARD_ROLE')
    require(len(flash_a) == FLASH_SIZE and flash_a == flash_b, 'FULL_BACKUPS_MISMATCH')
    require(len(options_a) == 16 and options_a == options_b, 'OPTIONS_BACKUPS_MISMATCH')
    identity_check(identity_a); identity_check(identity_b)
    require(identity_a == identity_b, 'IDENTITY_OR_PROTECTION_DRIFT')
    vector_check(flash_a[:APP_LIMIT]); vector_check(candidate)
    require(digest(candidate) == candidate_sha, 'CANDIDATE_SHA_MISMATCH')
    if synthetic:
        # 显式合成标记也检查数据本身，避免把真实整片借--synthetic导出到非加密目录。
        require(identity_a['uid_hex'] == SYNTHETIC_UID, 'SYNTHETIC_UID_REQUIRED')
        require(flash_a[256:256 + len(MARKER)] == candidate[256:256 + len(MARKER)] == MARKER,
                'SYNTHETIC_IMAGE_MARKER_REQUIRED')
    end = next(n for n in SECTOR_ENDS if len(candidate) <= n)
    sectors = list(range(SECTOR_ENDS.index(end) + 1))
    require(all(identity_a['optcr'] & (1 << (16 + i)) for i in sectors), 'TARGET_SECTOR_WRITE_PROTECTED')
    # 重刷整个受影响扇区，但新BIN尾部与其它所有字节均取现场原件，不能用FF补齐。
    expected = candidate + flash_a[len(candidate):]
    payloads = {'before-full-private.bin': flash_a, 'options-private.bin': options_a,
                'identity-private.json': encoded(identity_a), 'candidate-private.bin': candidate,
                'install-sectors-private.bin': expected[:end], 'restore-sectors-private.bin': flash_a[:end],
                'expected-full-private.bin': expected}
    manifest = {'schema': 1, 'board_role': board,
                'scope': 'SYNTHETIC_OFFLINE_PACKAGE' if synthetic else 'PRIVATE_OFFLINE_PACKAGE',
                'hardware_execution_enabled': False, 'independent_acquisition_proven': False,
                'backup_files_consistent': True, 'flash_base': FLASH_BASE, 'flash_size': FLASH_SIZE,
                'application_limit': APP_LIMIT, 'sectors': sectors, 'erase_end_exclusive': FLASH_BASE + end,
                'candidate_bytes': len(candidate), 'candidate_sha256': candidate_sha,
                'options_write_allowed': False, 'unlock_or_mass_erase_allowed': False,
                'config_region_from_0x0800C000_preserved': True,
                'layout_and_actual_board_review_required': True,
                'restore_note': 'Restore affected sectors from retained original; verify full 1MiB and unchanged options/identity. No target I/O exists in this tool.',
                'files': {name: {'bytes': len(data), 'sha256': digest(data)} for name, data in payloads.items()}}
    return manifest, payloads


def prepare(args):
    paths = [args.flash_a, args.flash_b, args.options_a, args.options_b, args.identity_a, args.identity_b]
    # 两次读取的文件必须独立路径；本工具仅核验一致性，不能证明它们实际来自独立SDK读取。
    for i in (0, 2, 4):
        require(not os.path.samefile(paths[i], paths[i + 1]), 'BACKUP_PATHS_NOT_DISTINCT')
    values = [read(p, args.synthetic) for p in paths]
    manifest, payloads = make_plan(args.board, *values[:4], json.loads(values[4]), json.loads(values[5]),
                                   read(args.candidate, args.synthetic), args.candidate_sha, args.synthetic)
    parent = protected(args.out.parent, args.synthetic)
    require(args.out.name not in ('', '.', '..'), 'OUTPUT_NAME')
    # 独占目录和文件，任何失败都留存已有内容，不删除现场失败或覆盖旧恢复包。
    out = parent / args.out.name; out.mkdir(exist_ok=False)
    for name, data in payloads.items():
        with (out / name).open('xb') as f:
            f.write(data)
        protected(out / name, args.synthetic)
    blob = encoded(manifest)
    with (out / 'manifest-private.json').open('xb') as f:
        f.write(blob)
    protected(out / 'manifest-private.json', args.synthetic)
    return {'status': 'OFFLINE_PACKAGE_PREPARED_NOT_AUTHORIZED', 'manifest_sha256': digest(blob),
            'board_role': args.board, 'sectors': manifest['sectors'], 'hardware_operations': 0}


def load_package(path, expected_sha, synthetic):
    raw = read(path / 'manifest-private.json', synthetic)
    require(digest(raw) == expected_sha, 'MANIFEST_SHA_MISMATCH')
    m = json.loads(raw)
    require(m.get('scope') == ('SYNTHETIC_OFFLINE_PACKAGE' if synthetic else 'PRIVATE_OFFLINE_PACKAGE'),
            'PACKAGE_SCOPE_MISMATCH')
    require(set(m['files']) == set(FILES), 'PACKAGE_FILE_SET')
    payload = {}
    for name in FILES:
        data = read(path / name, synthetic); meta = m['files'][name]
        require(len(data) == meta['bytes'] and digest(data) == meta['sha256'], 'PACKAGE_PAYLOAD_CHANGED')
        payload[name] = data
    # 从保留原件重算全部字节和边界，不仅信任可编辑的manifest描述。
    original, options, ident, image = (payload[n] for n in FILES[:4])
    plan, rebuilt = make_plan(m['board_role'], original, original, options, options, json.loads(ident),
                              json.loads(ident), image, m['candidate_sha256'], synthetic)
    require(plan == m and rebuilt == payload, 'PACKAGE_PLAN_DRIFT')
    return m, payload


def verify(args):
    _, payload = load_package(args.package, args.manifest_sha, args.synthetic)
    actual, options = read(args.flash, args.synthetic), read(args.options, args.synthetic)
    seen = json.loads(read(args.identity, args.synthetic)); identity_check(seen)
    require(seen == json.loads(payload['identity-private.json']), 'VERIFY_WRONG_IDENTITY_OR_PROTECTION')
    require(options == payload['options-private.bin'], 'VERIFY_OPTIONS_CHANGED')
    expected = payload['expected-full-private.bin' if args.phase == 'installed' else 'before-full-private.bin']
    require(actual == expected, 'VERIFY_FULL_FLASH_MISMATCH')
    return {'status': 'OFFLINE_' + args.phase.upper() + '_FULL_FLASH_MATCH', 'hardware_operations': 0,
            'full_flash_sha256': digest(actual), 'options_unchanged': True}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    actions = p.add_subparsers(dest='action', required=True)
    prep = actions.add_parser('prepare'); prep.add_argument('--board', choices=('B', 'C'), required=True)
    for key in ('flash-a', 'flash-b', 'options-a', 'options-b', 'identity-a', 'identity-b', 'candidate', 'out'):
        prep.add_argument('--' + key, type=Path, required=True)
    prep.add_argument('--candidate-sha', required=True)
    check = actions.add_parser('verify')
    for key in ('package', 'flash', 'options', 'identity'):
        check.add_argument('--' + key, type=Path, required=True)
    check.add_argument('--manifest-sha', required=True)
    check.add_argument('--phase', choices=('installed', 'restored'), required=True)
    for sub in (prep, check):
        sub.add_argument('--synthetic', action='store_true', help='仅接受build内显式合成夹具，不能用于真实固件')
    args = p.parse_args()
    try:
        result = prepare(args) if args.action == 'prepare' else verify(args)
        print(json.dumps(result)); return 0
    except (ValueError, OSError, KeyError, TypeError, StopIteration) as e:
        # 不打印异常对象或数据内容，避免私有路径/配置字节进入公共终端日志。
        reason = str(e) if isinstance(e, ValueError) and str(e).replace('_', '').isalnum() else type(e).__name__
        print(json.dumps({'status': 'STOP', 'reason': reason, 'hardware_operations': 0})); return 1


if __name__ == '__main__':
    sys.exit(main())
