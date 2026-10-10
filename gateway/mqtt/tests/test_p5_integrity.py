"""普通来源/构建契约测试，验证损坏文件和扩大白名单会被离线检查拒绝。"""
import importlib.util
from pathlib import Path
import shutil
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[3]
spec = importlib.util.spec_from_file_location('p5_integrity', ROOT / 'gateway/third_party/verify_coremqtt_integrity.py')
integrity = importlib.util.module_from_spec(spec)
spec.loader.exec_module(integrity)


class IntegrityTests(unittest.TestCase):
    def setUp(self):
        # 只在临时目录模拟来源损坏，保留真实 vendor 和构建脚本原字节。
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.vendor = Path(self.temp.name) / 'coreMQTT'
        shutil.copytree(integrity.VENDOR, self.vendor)
        self.build = Path(self.temp.name) / 'build.py'
        self.build.write_bytes((ROOT / 'gateway/mqtt/build.py').read_bytes())

    def test_current_pinned_sources(self):
        self.assertEqual(integrity.verify_vendor(self.vendor), 9)
        integrity.check_build_sources(self.build)

    def test_changed_source_rejected(self):
        path = self.vendor / 'source/core_mqtt.c'
        path.write_bytes(path.read_bytes() + b'\n')
        with self.assertRaises(ValueError): integrity.verify_vendor(self.vendor)

    def test_changed_manifest_rejected(self):
        path = self.vendor / 'upstream.json'
        path.write_bytes(path.read_bytes() + b'\n')
        with self.assertRaises(ValueError): integrity.verify_vendor(self.vendor)

    def test_extra_source_rejected(self):
        (self.vendor / 'source/extra.c').write_text('/* synthetic */', encoding='utf-8')
        with self.assertRaises(ValueError): integrity.verify_vendor(self.vendor)

    def test_source_glob_rejected(self):
        text = self.build.read_text(encoding='utf-8').replace(
            "vendor / 'source/core_mqtt.c'", "*vendor.glob('*.c')")
        self.build.write_text(text, encoding='utf-8')
        with self.assertRaises(ValueError): integrity.check_build_sources(self.build)

    def test_source_mutation_rejected(self):
        with self.build.open('a', encoding='utf-8') as out:
            out.write("\nmqtt_sources.append(vendor / 'source/extra.c')\n")
        with self.assertRaises(ValueError): integrity.check_build_sources(self.build)


if __name__ == '__main__':
    unittest.main()
