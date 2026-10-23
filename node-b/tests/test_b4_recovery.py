"""合成1MiB NOR模拟：验证B4跨32KiB安装、配置保留、失败拒绝与精确回退。"""
import argparse
import datetime
import hashlib
import importlib.util
import json
from pathlib import Path
import struct
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
TOOL = ROOT / 'node-b/tools/b4_recovery.py'
spec = importlib.util.spec_from_file_location('b4_recovery', TOOL)
recovery = importlib.util.module_from_spec(spec); spec.loader.exec_module(recovery)


class FakeNor:
    """仅内存模拟，不包含调试器/DLL；擦除和1→0编程遵循扇区边界。"""
    def __init__(self, data):
        self.data = bytearray(data)

    def apply(self, plan, payload, partial=False):
        end = plan['erase_end_exclusive'] - recovery.FLASH_BASE
        self.data[:end] = b'\xff' * end
        for i, value in enumerate(payload[:10000] if partial else payload):
            if self.data[i] & value != value:
                raise ValueError('NOR_0_TO_1')
            self.data[i] = value


class RecoveryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        stamp = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
        cls.out = ROOT / 'node-b/build' / ('b4-recovery-tests-' + stamp); cls.out.mkdir()
        raw = bytearray(b'\xa5' * recovery.FLASH_SIZE)
        struct.pack_into('<II', raw, 0, 0x20010000, 0x08000101)
        raw[256:256 + len(recovery.MARKER)] = recovery.MARKER
        raw[49152:49176] = b'SYNTHETIC_CONFIG_KEPT!!!!'[:24]
        cls.original = bytes(raw)
        cls.options = b'\xaa\x55' * 8
        cls.ident = {'device_id': 0x10000413, 'cpuid': 0x410fc241, 'capacity_kib': 1024,
                     'uid_hex': recovery.SYNTHETIC_UID, 'optcr': 0x0fffaaed, 'flash_sr': 0}
        image = bytearray(b'\x5a' * 39948)
        struct.pack_into('<II', image, 0, 0x20020000, 0x08000101)
        image[256:256 + len(recovery.MARKER)] = recovery.MARKER
        cls.image = bytes(image)

    def plan(self, **changes):
        args = dict(board='B', flash_a=self.original, flash_b=self.original, options_a=self.options,
                    options_b=self.options, identity_a=self.ident, identity_b=self.ident,
                    candidate=self.image, candidate_sha=recovery.digest(self.image), synthetic=True)
        args.update(changes)
        return recovery.make_plan(**args)

    def reject(self, reason, **changes):
        with self.assertRaisesRegex(ValueError, reason): self.plan(**changes)

    def test_b_install_and_exact_restore(self):
        plan, files = self.plan(); flash = FakeNor(self.original)
        self.assertEqual(plan['sectors'], [0, 1, 2])
        flash.apply(plan, files['install-sectors-private.bin'])
        self.assertEqual(bytes(flash.data), files['expected-full-private.bin'])
        self.assertEqual(flash.data[len(self.image):], self.original[len(self.image):])
        flash.apply(plan, files['restore-sectors-private.bin'])
        self.assertEqual(bytes(flash.data), self.original)

    def test_c_config_sector_preserved(self):
        plan, files = self.plan(board='C'); flash = FakeNor(self.original)
        flash.apply(plan, files['install-sectors-private.bin'])
        self.assertEqual(flash.data[49152:], self.original[49152:])

    def test_partial_program_is_not_success(self):
        plan, files = self.plan(); flash = FakeNor(self.original)
        flash.apply(plan, files['install-sectors-private.bin'], partial=True)
        self.assertNotEqual(bytes(flash.data), files['expected-full-private.bin'])
        flash.apply(plan, files['restore-sectors-private.bin'])
        self.assertEqual(bytes(flash.data), self.original)

    def test_sector_boundaries(self):
        for size, sectors in ((16384, [0]), (16385, [0, 1]), (32768, [0, 1]), (32769, [0, 1, 2]), (49152, [0, 1, 2])):
            image = (self.image + b'\x5a' * 10000)[:size]
            plan, _ = self.plan(candidate=image, candidate_sha=recovery.digest(image))
            self.assertEqual(plan['sectors'], sectors)

    def test_backup_mismatch(self): self.reject('FULL_BACKUPS_MISMATCH', flash_b=self.original[:-1] + b'\x00')
    def test_backup_size(self): self.reject('FULL_BACKUPS_MISMATCH', flash_a=self.original[:-1], flash_b=self.original[:-1])
    def test_options_mismatch(self): self.reject('OPTIONS_BACKUPS_MISMATCH', options_b=b'\x00' * 16)
    def test_wrong_uid(self): self.reject('IDENTITY_OR_PROTECTION_DRIFT', identity_b={**self.ident, 'uid_hex': '6a' * 12})
    def test_wrong_cpu(self): self.reject('DEVICE_NOT_F407', identity_a={**self.ident, 'device_id': 0x123})
    def test_capacity(self): self.reject('FLASH_NOT_1M', identity_a={**self.ident, 'capacity_kib': 512})
    def test_rdp_no_unlock(self): self.reject('RDP_NOT_ZERO', identity_a={**self.ident, 'optcr': 0})
    def test_flash_busy(self): self.reject('FLASH_BUSY_OR_ERROR', identity_a={**self.ident, 'flash_sr': 0x10000})
    def test_write_protect(self):
        value = {**self.ident, 'optcr': self.ident['optcr'] & ~(1 << 18)}
        self.reject('TARGET_SECTOR_WRITE_PROTECTED', identity_a=value, identity_b=value)
    def test_config_collision(self): self.reject('48K_APP_REGION', candidate=self.image + b'\x00' * 10000)
    def test_bad_image_hash(self): self.reject('CANDIDATE_SHA_MISMATCH', candidate_sha='0' * 64)
    def test_bad_vector(self): self.reject('INVALID_STACK_VECTOR', candidate=b'\x00' * len(self.image))
    def test_bad_reset_vector(self):
        image = bytearray(self.image); struct.pack_into('<I', image, 4, 0x1fff0001)
        self.reject('INVALID_FLASH_RESET_VECTOR', candidate=bytes(image))
    def test_synthetic_label_guard(self):
        image = bytearray(self.image); image[256] = 0
        self.reject('SYNTHETIC_IMAGE_MARKER_REQUIRED', candidate=bytes(image), candidate_sha=recovery.digest(image))

    def test_cli_roundtrip_and_negative_verifications(self):
        out = self.out / 'cli'; out.mkdir()
        for name, data in {'fa': self.original, 'fb': self.original, 'oa': self.options, 'ob': self.options,
                           'ia': recovery.encoded(self.ident), 'ib': recovery.encoded(self.ident), 'image': self.image}.items():
            (out / name).write_bytes(data)
        cases = []
        def cli(label, command, expected):
            p = subprocess.run([sys.executable, '-X', 'utf8', str(TOOL), *map(str, command)], capture_output=True)
            (out / (label + '.log')).write_bytes(p.stdout + p.stderr)
            cases.append({'name': label, 'exit_code': p.returncode, 'expected': expected})
            self.assertEqual(p.returncode, expected, p.stdout.decode(errors='replace'))
            return json.loads(p.stdout)
        prep = ['prepare', '--board', 'C', '--synthetic', '--candidate', out / 'image', '--candidate-sha', recovery.digest(self.image), '--out', out / 'package']
        for key, name in (('flash-a', 'fa'), ('flash-b', 'fb'), ('options-a', 'oa'), ('options-b', 'ob'), ('identity-a', 'ia'), ('identity-b', 'ib')):
            prep += ['--' + key, out / name]
        result = cli('prepare', prep, 0); manifest_sha = result['manifest_sha256']
        cli('existing-output-rejected', prep, 1)
        package = out / 'package'
        check = ['verify', '--package', package, '--manifest-sha', manifest_sha, '--synthetic', '--options', out / 'oa', '--identity', out / 'ia']
        cli('installed', [*check, '--phase', 'installed', '--flash', package / 'expected-full-private.bin'], 0)
        cli('restored', [*check, '--phase', 'restored', '--flash', out / 'fa'], 0)
        cli('uninstalled-rejected', [*check, '--phase', 'installed', '--flash', out / 'fa'], 1)
        # 镜像头正确仍不够：配置区任一位损坏必须被整片核验发现。
        corrupt = bytearray((package / 'expected-full-private.bin').read_bytes()); corrupt[0x0c000] ^= 1
        (out / 'collateral-flash').write_bytes(corrupt)
        cli('config-corruption-rejected', [*check, '--phase', 'installed', '--flash', out / 'collateral-flash'], 1)
        cli('wrong-manifest-hash-rejected', [*check, '--manifest-sha', '0' * 64, '--phase', 'restored', '--flash', out / 'fa'], 1)
        (out / 'oa').write_bytes(b'\x00' * 16)
        cli('changed-options-rejected', [*check, '--phase', 'restored', '--flash', out / 'fa'], 1)
        (out / 'oa').write_bytes(self.options)
        (out / 'ia').write_bytes(recovery.encoded({**self.ident, 'uid_hex': '6a' * 12}))
        cli('wrong-board-rejected', [*check, '--phase', 'restored', '--flash', out / 'fa'], 1)
        (out / 'ia').write_bytes(recovery.encoded(self.ident))
        (package / 'restore-sectors-private.bin').write_bytes(b'\x00')
        cli('damaged-package-rejected', [*check, '--phase', 'restored', '--flash', out / 'fa'], 1)
        cli('same-backup-file-rejected', [*prep, '--flash-b', out / 'fa', '--out', out / 'other'], 1)
        cli('real-mode-rejects-unencrypted-build', [x for x in prep if x != '--synthetic'], 1)
        (out / 'cli-exits.json').write_bytes(recovery.encoded(cases))


if __name__ == '__main__':
    unittest.main(verbosity=2)
