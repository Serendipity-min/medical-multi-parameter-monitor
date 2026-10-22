"""烧录状态机合成验证：写入范围、原件漂移与校验失败停止；不连接硬件。"""
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import install_b as module
from test_readback_b import FakeLink
from readback_b import identity, sha, HALT


class Function:
    pass


class ProgrammingLink(FakeLink):
    def __init__(self,out,original,corrupt=False):
        super().__init__()
        self.out,self.flash,self.corrupt=out,original,corrupt
        self.dll=type('DLL',(),{n:Function() for n in
                              ('JLINKARM_BeginDownload','JLINKARM_WriteMem','JLINKARM_EndDownload')})()

    def call(self,name,*args,timeout=5):
        self.commands.append(name)
        if name.endswith('Halt') or name.endswith('Reset'):self.state=HALT
        if name.endswith('Go'):self.state=0
        if name.endswith('WriteMem'):
            address,size,buffer=args
            assert address==0x08000000 and size==32768
            self.flash=bytes(buffer)+self.flash[size:]
            if self.corrupt:self.flash=self.flash[:-1]+bytes([self.flash[-1]^1])
            return size
        return 0

    def read(self,address,size):
        return self.flash if address==0x08000000 else super().read(address,size)


class Cases(unittest.TestCase):
    def test_scope_and_failure_gates(self):
        # 合成固件与原件用测试常量替换固定SHA；生产命令仍只接受合同候选。
        with tempfile.TemporaryDirectory() as name:
            root=Path(name);backup=root/'backup';backup.mkdir()
            original=bytes(range(256))*4096
            binary=root/'candidate.bin';binary.write_bytes(b'C'*25284)
            for i in (1,2):(backup/f'flash-read-{i}.bin').write_bytes(original)
            (backup/'options-read-1.bin').write_bytes(b'X'*16)
            reference=identity(ProgrammingLink(root,original))
            (backup/'identity-before-private.json').write_text(json.dumps(reference))
            with patch.object(module,'CANDIDATE',sha(binary)),patch.object(module,'ORIGINAL',hashlib.sha256(original).hexdigest()):
                folder=root/'plan';plan=module.prepare(binary,backup,folder)
                self.assertEqual(plan['preserved_sector_tail_bytes'],7484)
                for mode in ('success','drift','corrupt','wrong_uid'):
                    with self.subTest(mode=mode):
                        out=root/mode;out.mkdir()
                        link=ProgrammingLink(out,original,corrupt=mode=='corrupt')
                        if mode=='drift':link.flash=b'D'+original[1:]
                        if mode=='wrong_uid':
                            reference['uid_hex']='01'*12
                            (backup/'identity-before-private.json').write_text(json.dumps(reference))
                            plan['identity_file_sha256']=sha(backup/'identity-before-private.json')
                        receipt={'halt_requests':0,'go_requests':0,'reset_requests':0}
                        if mode=='success':
                            module.install(link,folder,plan,receipt)
                            self.assertEqual(receipt['status'],'BIO_V2_INSTALLED_FULL_FLASH_VERIFIED')
                            self.assertEqual((receipt['halt_requests'],receipt['reset_requests'],receipt['go_requests']),(1,1,1))
                            self.assertEqual(link.flash[25284:],original[25284:])
                        else:
                            with self.assertRaisesRegex(RuntimeError,{'drift':'CURRENT_FLASH_DRIFT','corrupt':'FULL_FLASH_VERIFY_MISMATCH','wrong_uid':'WRONG_BOARD_OR_OPTIONS'}[mode]):
                                module.install(link,folder,plan,receipt)
                            self.assertNotIn('JLINKARM_Reset',link.commands)
                            self.assertNotIn('JLINKARM_Go',link.commands)
                            if mode!='corrupt':self.assertNotIn('JLINKARM_BeginDownload',link.commands)


if __name__=='__main__':unittest.main(verbosity=2)
