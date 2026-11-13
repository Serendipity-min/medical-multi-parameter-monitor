"""新采集入口与既有槽重建器的集成负例；全部脱机，不启动DLL。"""
import copy
import hashlib
import json
from pathlib import Path
import struct
import sys
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import capture_b as module


def slot(seq,value=1):
    return b'\xc0\x00\x00'+value.to_bytes(3,'big')*2+b'\0'*3+struct.pack('<III',seq,seq*672000,seq*4)


def fixture(folder,conflict=False):
    block=b''.join(slot(i) for i in range(1,129))
    chunks=[block,block]
    if conflict:
        altered=slot(1,2)+block[24:]
        chunks=[block,block,block,altered,altered]
    (folder/'running-slots-private.bin').write_bytes(b''.join(chunks))
    ram=bytearray(131072);struct.pack_into('<I',ram,0x140,128);ram[0x1f30:0x1f30+3072]=block
    (folder/'final-paused-ram-private.bin').write_bytes(ram)


class Cases(unittest.TestCase):
    def test_real_artifact_profile_and_drift(self):
        with tempfile.TemporaryDirectory() as name:
            profile=module.prepare(Path(name)/'profile.json')
            module.validate(profile)
            for field,value,reason in [('schema','legacy','OLD_CAPTURE_PROFILE'),
                                       ('tools_sha256',{},'CAPTURE_TOOL_DRIFT'),
                                       ('layout',{},'CAPTURE_LAYOUT_DRIFT'),
                                       ('flash_sha256','00','CAPTURE_FLASH_BINDING')]:
                with self.subTest(field=field):
                    bad=copy.deepcopy(profile);bad[field]=value
                    with self.assertRaisesRegex(RuntimeError,reason):module.validate(bad)

    def test_export_raw_and_same_ram_tail(self):
        with tempfile.TemporaryDirectory() as name:
            folder=Path(name);fixture(folder)
            result=module.export(folder)
            self.assertEqual(result['stable_frames'],128)
            self.assertEqual(result['source_missing_within_span'],0)
            self.assertEqual(result['multi_repeat_conflicts'],0)
            self.assertEqual(result['input_accuracy'],'NOT_EVALUATED')

    def test_repeated_conflict_is_not_majority_vote(self):
        with tempfile.TemporaryDirectory() as name:
            folder=Path(name);fixture(folder,True)
            result=module.export(folder)
            self.assertEqual(result['multi_repeat_conflicts'],1)
            self.assertEqual(result['stable_frames'],127)
            self.assertEqual(result['pending'],1)

    def test_partial_block_rejected(self):
        with tempfile.TemporaryDirectory() as name:
            folder=Path(name);fixture(folder)
            with (folder/'running-slots-private.bin').open('ab') as stream:stream.write(b'X')
            with self.assertRaises(ValueError):module.export(folder)


if __name__=='__main__':unittest.main(verbosity=2)
