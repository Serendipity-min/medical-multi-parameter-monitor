"""A恢复适配的调试看门狗范围与异常路径；无SDK或设备调用。"""
import ctypes as C
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import abc_board_install as abc


class InstallAdapter(unittest.TestCase):
    def test_short_C_image_uses_only_required_sectors_and_preserves_tail(self):
        build=Path(__file__).resolve().parents[1]/'build'
        with tempfile.TemporaryDirectory(dir=build) as temp:
            out=Path(temp);self.assertTrue(out.resolve().is_relative_to(build.resolve()))
            probe=out/'probe';probe.mkdir()
            original=bytearray(b'\xa5'*1048576)
            original[:8]=(0x20020000).to_bytes(4,'little')+(0x08000101).to_bytes(4,'little')
            ident={'device_id':0x10000413,'cpuid':0x410fc241,'capacity_kib':1024,
                   'uid_hex':'5a'*12,'optcr':0x0fffaaed,'flash_sr':0}
            (out/'receipt-private.json').write_text(json.dumps({'board':'C','exit_code':0,'independent_reads_match':True,'Close_completed':True}))
            for n in (1,2):
                (probe/f'flash-{n}-private.bin').write_bytes(original)
                (probe/f'options-{n}-private.bin').write_bytes(b'\xaa'*16)
            for name in ('identity-private.json','identity-after-private.json'):
                (probe/name).write_text(json.dumps(ident))
            for size,end,sectors in ((7164,16384,[0]),(20000,32768,[0,1]),(44520,49152,[0,1,2])):
                image=bytes(original[:8])+b'\x5a'*(size-8);candidate=out/'candidate.bin';candidate.write_bytes(image)
                with patch.object(abc.recovery,'protected',side_effect=lambda p,s:Path(p)):
                    plan,payload=abc.prepare('C',out,candidate,abc.recovery.digest(image))
                self.assertEqual(plan['sectors'],sectors)
                self.assertEqual(len(payload['install-sectors-private.bin']),end)
                self.assertEqual(payload['expected-full-private.bin'][size:],bytes(original[size:]))
                with patch.object(abc.install.InstallLink,'__init__',return_value=None) as init:
                    abc.Link(probe,'C',end)
                init.assert_called_once_with(probe,end)

    def link(self,board='A'):
        link=object.__new__(abc.Link);link.board=board;link.original_freeze=None;link.debug_freeze_writes=0
        return link

    def test_freeze_helpers_only_touch_exact_debug_register(self):
        link=self.link();memory=8;calls=[]
        def native(obj,name,*args,**kw):
            nonlocal memory
            calls.append((name,args[0],args[1]))
            self.assertEqual(args[:2],(0xe0042008,4))
            if name=='JLINKARM_WriteMem':memory=int.from_bytes(C.string_at(args[2],4),'little')
            else:C.memmove(args[2],memory.to_bytes(4,'little'),4)
            return 4
        with patch.object(abc.install.raw.Link,'call',side_effect=native):
            link.freeze_write(0x1008);self.assertEqual(link.freeze_read(),0x1008)
        self.assertEqual(link.debug_freeze_writes,1);self.assertTrue(calls)

    def test_A_watchdog_frozen_before_halt_and_restored_after_Go(self):
        link=self.link();events=[]
        with patch.object(link,'freeze_read',return_value=8),patch.object(link,'freeze_write',side_effect=lambda x:events.append(('freeze',x))),patch.object(abc.install.InstallLink,'call',side_effect=lambda n,*a,**kw:events.append((n,)) or 0):
            link.call('JLINKARM_Halt');link.call('JLINKARM_Go')
        self.assertEqual(events,[('freeze',0x1008),('JLINKARM_Halt',),('JLINKARM_Go',),('freeze',8)])

    def test_failed_halt_does_not_issue_Go_or_automatic_restore(self):
        link=self.link()
        with patch.object(link,'freeze_read',return_value=8),patch.object(link,'freeze_write') as write,patch.object(abc.install.InstallLink,'call',side_effect=ValueError('NATIVE_ERROR')) as call:
            with self.assertRaisesRegex(ValueError,'NATIVE_ERROR'):link.call('JLINKARM_Halt')
        write.assert_called_once_with(0x1008);self.assertEqual(call.call_count,1)

    def test_C_and_B_keep_original_install_watchdog_behavior(self):
        for board in ('C','B'):
            link=self.link(board)
            with patch.object(link,'freeze_read') as read,patch.object(link,'freeze_write') as write,patch.object(abc.install.InstallLink,'call',return_value=0):
                link.call('JLINKARM_Halt');link.call('JLINKARM_Go')
            read.assert_not_called();write.assert_not_called()


if __name__=='__main__':unittest.main()
