"""D 首写的离线范围检查；不加载调试器或连接设备。"""
from pathlib import Path
import json
import sys
import unittest
import tempfile
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'node-b/tools'))
import phy01_d_install as d


class Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        base=ROOT/'node-b/docs/FIVE-NODE-MIGRATION/M1-20261104'
        item=json.loads((base/'RELEASE-MANIFEST.json').read_text())['applications']['D']['artifacts']['FIVE_NODE_D.bin']
        cls.candidate=(base/item['path']).read_bytes();cls.sha=item['sha256']
        cls.before=b'\xa5'*1048576;cls.options=b'\xaa\x55'*8
        cls.identity={'device_id':0x10000413,'cpuid':0x410fc241,'capacity_kib':1024,
                      'uid_hex':'5a'*12,'optcr':0x0fffaaed,'flash_sr':0}

    def plan(self,**kw):
        args=dict(before=self.before,options=self.options,identity=self.identity,candidate=self.candidate,expected_sha=self.sha)
        args.update(kw);return d.plan(**args)

    def test_exact_candidate_and_preserved_all_other_bytes(self):
        expected=self.plan()
        self.assertEqual(len(expected),1048576)
        self.assertEqual(expected[:len(self.candidate)],self.candidate)
        self.assertEqual(expected[len(self.candidate):],self.before[len(self.candidate):])
        programmed=bytearray(self.before);programmed[:32768]=b'\xff'*32768
        for i,v in enumerate(expected[:32768]):programmed[i]&=v
        self.assertEqual(bytes(programmed),expected)

    def test_protected_or_wrong_chip_rejected(self):
        for change in ({'optcr':self.identity['optcr']&~(1<<17)},{'capacity_kib':512},{'device_id':0}):
            with self.assertRaises(ValueError):self.plan(identity=dict(self.identity,**change))

    def test_size_sha_and_vector_rejected(self):
        for change in ({'candidate':self.candidate+b'\0'*32768},{'expected_sha':'0'*64},{'before':self.before[:-1]},{'options':b''}):
            with self.assertRaises(ValueError):self.plan(**change)
        bad=b'\0'*8+self.candidate[8:]
        with self.assertRaisesRegex(ValueError,'STACK'):self.plan(candidate=bad,expected_sha=d.engine.package.digest(bad))

    def test_default_never_opens_debugger(self):
        with patch.object(sys,'argv',['phy01_d_install.py']),patch.object(d.engine,'InstallLink') as sdk:
            self.assertEqual(d.main(),0);sdk.assert_not_called()

    def test_updated_image_plan_requires_exact_sha_without_target_access(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'candidate.bin';candidate=self.candidate+b'\0'*8;path.write_bytes(candidate)
            argv=['phy01_d_install.py','--image',str(path),'--image-sha256',d.engine.package.digest(candidate)]
            with patch.object(sys,'argv',argv),patch.object(d.engine,'InstallLink') as sdk:
                self.assertEqual(d.main(),0);sdk.assert_not_called()
            with patch.object(sys,'argv',argv[:-1]+['0'*64]),patch.object(d.engine,'InstallLink') as sdk:
                with self.assertRaisesRegex(ValueError,'D_MANIFEST_SHA'):d.main()
                sdk.assert_not_called()


if __name__=='__main__':unittest.main(verbosity=2)
