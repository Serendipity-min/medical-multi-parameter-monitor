"""A恢复适配的调试看门狗范围与异常路径；无SDK或设备调用。"""
import ctypes as C
import unittest
from unittest.mock import patch

import abc_board_install as abc


class InstallAdapter(unittest.TestCase):
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
