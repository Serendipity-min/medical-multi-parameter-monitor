"""仅覆盖清单漂移与构建白名单的固定回归，不执行编译脚本或联网。"""

import importlib.util
import json
from pathlib import Path
import shutil
import tempfile
import unittest


THIRD_PARTY = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    'paho_integrity', THIRD_PARTY / 'verify_paho_integrity.py'
)
integrity = importlib.util.module_from_spec(spec)
spec.loader.exec_module(integrity)


class PahoIntegrityTests(unittest.TestCase):
    def setUp(self):
        # 只修改隔离临时副本，真实 vendor 与构建脚本始终保持只读。
        self.sandbox = tempfile.TemporaryDirectory(prefix='paho-integrity-')
        self.addCleanup(self.sandbox.cleanup)
        self.root = Path(self.sandbox.name)
        self.vendor = self.root / 'paho'
        shutil.copytree(integrity.VENDOR, self.vendor)
        self.build = self.root / 'build.py'
        shutil.copyfile(integrity.GATEWAY_BUILD, self.build)

    def test_current_pinned_files_and_sources_pass(self):
        self.assertEqual(integrity.verify_vendor(self.vendor, self.build), (12, 9))

    def test_pristine_change_is_rejected(self):
        path = self.vendor / 'MQTTPacket/src/MQTTConnect.h'
        path.write_bytes(path.read_bytes() + b'\n')
        with self.assertRaisesRegex(integrity.IntegrityError, 'pristine file mismatch'):
            integrity.verify_vendor(self.vendor, self.build)

    def test_patched_change_is_rejected(self):
        path = self.vendor / 'MQTTClient-C/src/MQTTClient.c'
        path.write_bytes(path.read_bytes() + b'\n')
        with self.assertRaisesRegex(integrity.IntegrityError, 'patched file mismatch'):
            integrity.verify_vendor(self.vendor, self.build)

    def test_original_upstream_hash_cannot_be_replaced(self):
        path = self.vendor / 'upstream.json'
        manifest = json.loads(path.read_text(encoding='utf-8'))
        manifest['sha256']['MQTTPacket/src/MQTTConnect.h'] = '0' * 64
        path.write_text(json.dumps(manifest), encoding='utf-8')
        with self.assertRaisesRegex(integrity.IntegrityError, 'pinned original manifest'):
            integrity.verify_vendor(self.vendor, self.build)

    def test_missing_license_or_patch_notes_is_rejected(self):
        for name in ('edl-v10', 'epl-v20', 'PATCHES.md'):
            with self.subTest(name=name):
                path = self.vendor / name
                original = path.read_bytes()
                path.unlink()
                with self.assertRaisesRegex(integrity.IntegrityError, 'required vendor document'):
                    integrity.verify_vendor(self.vendor, self.build)
                path.write_bytes(original)

    def test_formatter_source_is_rejected(self):
        text = self.build.read_text(encoding='utf-8')
        self.build.write_text(
            text.replace(
                "vendor / 'MQTTPacket/src/MQTTPacket.c',",
                "vendor / 'MQTTPacket/src/MQTTFormat.c',",
            ),
            encoding='utf-8',
        )
        with self.assertRaisesRegex(integrity.IntegrityError, 'MQTTFormat.c'):
            integrity.check_build_sources(self.build)

    def test_paho_glob_is_rejected(self):
        text = self.build.read_text(encoding='utf-8')
        self.build.write_text(
            text.replace(
                "vendor / 'MQTTPacket/src/MQTTPacket.c',",
                "*vendor.glob('MQTTPacket/src/*.c'),",
            ),
            encoding='utf-8',
        )
        with self.assertRaisesRegex(integrity.IntegrityError, 'explicit vendor-relative literals'):
            integrity.check_build_sources(self.build)

    def test_source_append_is_rejected(self):
        text = self.build.read_text(encoding='utf-8')
        self.build.write_text(
            text + "\nsources.append(vendor / 'MQTTPacket/src/MQTTFormat.c')\n",
            encoding='utf-8',
        )
        with self.assertRaisesRegex(integrity.IntegrityError, 'mutation methods'):
            integrity.check_build_sources(self.build)

    def test_checker_does_not_execute_build_script(self):
        text = self.build.read_text(encoding='utf-8')
        self.build.write_text("raise RuntimeError('must never execute')\n" + text, encoding='utf-8')
        self.assertEqual(integrity.check_build_sources(self.build), integrity.PAHO_SOURCES)


if __name__ == '__main__':
    unittest.main()
